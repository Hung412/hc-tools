import logging

from odoo import _
from odoo.exceptions import UserError

from .base import register
from .shopee_direct import ShopeeDirectProvider, format_sub_ids

_logger = logging.getLogger(__name__)

SUB_IDS_PLACEHOLDER = '{sub_ids}'


@register('shopee_manual', 'Shopee Affiliate (no Open API)')
class ShopeeManualProvider(ShopeeDirectProvider):
    """Derives every member link from one marketplace generated template.

    Shopee closed its Open API to ordinary affiliates, but the sub id slots ride
    along in utm_content as a plain label, so a single link obtained from the
    Custom Link tool can be re-labelled per member without calling anything.
    """

    def build_link(self, clean_url, sub_ids):
        template = self.provider.sudo().link_template
        if not template:
            raise UserError(_('Set the link template on provider %s first.', self.provider.display_name))
        if SUB_IDS_PLACEHOLDER not in template:
            raise UserError(_('The link template must contain the %s placeholder.', SUB_IDS_PLACEHOLDER))
        return template.replace(SUB_IDS_PLACEHOLDER, format_sub_ids(sub_ids))

    def fetch_conversions(self, date_from, date_to):
        # Override, ignoring super() because this account cannot call the API:
        # conversions are imported from the dashboard report export instead.
        raise UserError(_(
            'This provider has no API access. Import the conversion report exported '
            'from the Shopee affiliate dashboard instead of syncing.'))
