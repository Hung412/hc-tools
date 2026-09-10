import hashlib
import json
import logging
import re
import time
from datetime import datetime

import requests

from odoo import _
from odoo.exceptions import UserError

from .base import (
    STATUS_CANCELLED,
    STATUS_PAYABLE,
    STATUS_PENDING,
    STATUS_VALIDATED,
    AffiliateProvider,
    Conversion,
    register,
)

_logger = logging.getLogger(__name__)

LANDING_URL = 'https://shopee.vn/'
SUB_ID_SLOTS = 5
SUB_ID_SEPARATOR = '-'
SUB_ID_RE = re.compile(r'^[A-Za-z0-9]*$')

ITEM_URL_RE = re.compile(r'-i\.(\d+)\.(\d+)')
PRODUCT_URL_RE = re.compile(r'/product/(\d+)/(\d+)')

SHOPEE_STATUS_MAP = {
    'PENDING': STATUS_PENDING,
    'UNPAID': STATUS_PENDING,
    'COMPLETED': STATUS_VALIDATED,
    'FULFILLED': STATUS_VALIDATED,
    'PAID': STATUS_PAYABLE,
    'SETTLED': STATUS_PAYABLE,
    'CANCELLED': STATUS_CANCELLED,
    'INVALID': STATUS_CANCELLED,
}

SHORT_LINK_MUTATION = """
mutation ($input: GenerateShortLinkInput!) {
  generateShortLink(input: $input) {
    shortLink
  }
}
"""

CONVERSION_QUERY = """
query ($start: Int64!, $end: Int64!, $limit: Int, $scrollId: String) {
  conversionReport(purchaseTimeStart: $start, purchaseTimeEnd: $end, limit: $limit, scrollId: $scrollId) {
    nodes {
      purchaseTime
      utmContent
      orders {
        orderId
        items {
          itemId
          itemTotalCommission
          actualAmount
          itemStatus
        }
      }
    }
    pageInfo {
      hasNextPage
      scrollId
    }
  }
}
"""


def format_sub_ids(sub_ids):
    """Shopee packs five alphanumeric slots into utm_content, joined by a dash."""
    slots = (list(sub_ids) + [''] * SUB_ID_SLOTS)[:SUB_ID_SLOTS]
    invalid = [slot for slot in slots if not SUB_ID_RE.match(slot)]
    if invalid:
        raise UserError(_('Shopee only accepts letters and digits in a sub id: %s', ', '.join(invalid)))
    return SUB_ID_SEPARATOR.join(slots)


def parse_sub_ids(utm_content):
    """Keep empty slots so positions stay meaningful."""
    return (utm_content or '').split(SUB_ID_SEPARATOR)


@register('shopee_direct', 'Shopee Affiliate (direct account)')
class ShopeeDirectProvider(AffiliateProvider):
    """Shopee Affiliate Open API driven from a single publisher account."""

    _url_patterns = (r'shopee\.vn/', r'shp\.ee/')

    # -- transport ---------------------------------------------------------

    def _credentials(self):
        provider = self.provider.sudo()
        if not provider.app_id or not provider.app_secret:
            raise UserError(_("Provider %s has no API credentials configured.", provider.display_name))
        return provider.app_id, provider.app_secret

    def _call(self, query, variables):
        app_id, app_secret = self._credentials()
        payload = json.dumps({'query': query, 'variables': variables}, separators=(',', ':'))
        timestamp = int(time.time())
        signature = hashlib.sha256(f"{app_id}{timestamp}{payload}{app_secret}".encode()).hexdigest()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={signature}",
        }
        try:
            response = requests.post(
                self.provider.endpoint_url,
                data=payload,
                headers=headers,
                timeout=self.provider.request_timeout,
            )
            response.raise_for_status()
            body = response.json()
        except requests.Timeout:
            raise UserError(_("Shopee affiliate API timed out. Please retry in a moment."))
        except requests.ConnectionError:
            raise UserError(_("Cannot reach the Shopee affiliate API."))
        except requests.HTTPError as error:
            _logger.exception("Shopee affiliate API returned an HTTP error")
            raise UserError(_("Shopee affiliate API rejected the request (HTTP %s).", error.response.status_code))
        except ValueError:
            _logger.exception("Shopee affiliate API returned a non JSON body")
            raise UserError(_("Shopee affiliate API returned an unreadable response."))

        if body.get('errors'):
            message = body['errors'][0].get('message', '')
            _logger.warning("Shopee affiliate API error: %s", body['errors'])
            raise UserError(_("Shopee affiliate API error: %s", message))
        return body.get('data') or {}

    # -- url handling ------------------------------------------------------

    def normalize_url(self, url):
        resolved = self._resolve_redirects(url)
        match = ITEM_URL_RE.search(resolved) or PRODUCT_URL_RE.search(resolved)
        if not match:
            raise UserError(_("This does not look like a Shopee product link."))
        shop_reference, item_reference = match.group(1), match.group(2)
        clean_url = f"https://shopee.vn/product/{shop_reference}/{item_reference}"
        return clean_url, shop_reference, item_reference

    def _resolve_redirects(self, url):
        if not re.search(r'shp\.ee/|s\.shopee\.vn/|shopee\.vn/[A-Za-z0-9]{5,12}/?$', url):
            return url
        try:
            response = requests.get(url, timeout=self.provider.request_timeout, allow_redirects=True)
            return response.url
        except requests.RequestException:
            _logger.exception("Cannot resolve Shopee short link %s", url)
            raise UserError(_("Cannot open this shortened link. Please paste the full product link."))

    # -- provider api ------------------------------------------------------

    def build_link(self, clean_url, sub_ids):
        variables = {'input': {'originUrl': clean_url or LANDING_URL, 'subIds': list(sub_ids[:5])}}
        data = self._call(SHORT_LINK_MUTATION, variables)
        short_link = (data.get('generateShortLink') or {}).get('shortLink')
        if not short_link:
            raise UserError(_("Shopee did not return a tracking link."))
        return short_link

    def fetch_conversions(self, date_from, date_to):
        variables = {
            'start': int(datetime.combine(date_from, datetime.min.time()).timestamp()),
            'end': int(datetime.combine(date_to, datetime.max.time()).timestamp()),
            'limit': 100,
            'scrollId': None,
        }
        conversions = []
        while True:
            report = (self._call(CONVERSION_QUERY, variables).get('conversionReport') or {})
            conversions.extend(self._parse_nodes(report.get('nodes') or []))
            page_info = report.get('pageInfo') or {}
            if not page_info.get('hasNextPage'):
                break
            variables['scrollId'] = page_info.get('scrollId')
        return conversions

    def _parse_nodes(self, nodes):
        conversions = []
        for node in nodes:
            sub_ids = parse_sub_ids(node.get('utmContent'))
            purchase_datetime = None
            if node.get('purchaseTime'):
                purchase_datetime = datetime.utcfromtimestamp(int(node['purchaseTime']))
            for order in node.get('orders') or []:
                for item in order.get('items') or []:
                    conversions.append(Conversion(
                        order_reference=str(order.get('orderId') or ''),
                        item_reference=str(item.get('itemId') or ''),
                        commission_gross=float(item.get('itemTotalCommission') or 0.0),
                        status=SHOPEE_STATUS_MAP.get((item.get('itemStatus') or '').upper(), STATUS_PENDING),
                        sub_ids=sub_ids,
                        order_amount=float(item.get('actualAmount') or 0.0),
                        purchase_datetime=purchase_datetime,
                        raw={'node': node, 'order': order, 'item': item},
                    ))
        return conversions
