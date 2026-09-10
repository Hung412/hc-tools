import logging

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..providers.base import PROVIDER_REGISTRY, selection_keys

_logger = logging.getLogger(__name__)


class HcCashbackProvider(models.Model):
    _name = 'hc.cashback.provider'
    _description = 'Cashback Affiliate Provider'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    key = fields.Selection(selection=lambda self: selection_keys(), required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(help="Provider used when generating new tracking links.")
    endpoint_url = fields.Char(default='https://open-api.affiliate.shopee.vn/graphql')
    request_timeout = fields.Integer(default=20)
    link_template = fields.Char(
        help="A link produced by the marketplace with its sub id placeholder written "
             "as {sub_ids}, e.g. https://shopee.vn/?mmp_pid=an_1&utm_content={sub_ids}")
    app_id = fields.Char(groups='hc_cashback.group_cashback_manager')
    app_secret = fields.Char(groups='hc_cashback.group_cashback_manager')
    sync_from_date = fields.Date(
        required=True, default=fields.Date.context_today,
        help="Conversions are never fetched before this date.")
    last_sync_date = fields.Date(readonly=True)
    sync_overlap_days = fields.Integer(
        default=14,
        help="How far back each run re-reads, so late status changes are picked up.")

    _sql_constraints = [
        ('unique_key', 'UNIQUE(key)', 'One configuration per affiliate provider.'),
    ]

    def get_implementation(self):
        self.ensure_one()
        implementation = PROVIDER_REGISTRY.get(self.key)
        if not implementation:
            raise UserError(_('No implementation is registered for provider %s.', self.key))
        return implementation(self)

    @api.model
    def get_default(self):
        provider = self.search([('is_default', '=', True)], limit=1) or self.search([], limit=1)
        if not provider:
            raise UserError(_('No affiliate provider is configured.'))
        return provider

    @api.model
    def find_for_url(self, url):
        for provider in self.search([]):
            if provider.get_implementation().owns_url(url):
                return provider
        return self.browse()

    def write(self, vals):
        if vals.get('is_default'):
            self.search([('is_default', '=', True), ('id', 'not in', self.ids)]).is_default = False
        return super().write(vals)

    @api.model
    def cron_sync_conversions(self):
        for provider in self.search([]):
            try:
                provider.sync_conversions()
                self.env.cr.commit()
            except Exception:
                self.env.cr.rollback()
                _logger.exception("Cashback conversion sync failed for provider %s", provider.key)

    def sync_conversions(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        anchor = self.last_sync_date or self.sync_from_date
        date_from = max(self.sync_from_date, anchor - relativedelta(days=self.sync_overlap_days))
        conversions = self.get_implementation().fetch_conversions(date_from, today)
        orders = self.env['hc.cashback.order'].sync_from_conversions(self, conversions)
        self.last_sync_date = today
        _logger.info("Cashback sync %s: %s conversions read, %s new orders", self.key, len(conversions), len(orders))
        return orders
