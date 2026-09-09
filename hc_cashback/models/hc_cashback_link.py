import logging
import uuid

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HcCashbackLink(models.Model):
    _name = 'hc.cashback.link'
    _description = 'Cashback Tracking Link'
    _rec_name = 'request_key'
    _order = 'create_date desc'

    member_id = fields.Many2one('hc.cashback.member', required=True, index=True, ondelete='restrict')
    provider_id = fields.Many2one('hc.cashback.provider', required=True, ondelete='restrict')
    request_key = fields.Char(required=True, index=True, copy=False,
                              default=lambda self: uuid.uuid4().hex[:16])
    origin_url = fields.Char(required=True)
    clean_url = fields.Char(index=True)
    shop_reference = fields.Char()
    item_reference = fields.Char()
    tracking_url = fields.Char()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ], required=True, default='draft')
    error_message = fields.Text()

    _sql_constraints = [
        ('unique_request_key', 'UNIQUE(request_key)', 'Tracking key must be unique.'),
    ]

    @api.model
    def create_for_url(self, member, origin_url):
        """Return a ready link for `origin_url`, reusing an identical one if any."""
        if member.is_blocked:
            raise UserError(_('Your account is on hold. Please contact support.'))
        provider = self.env['hc.cashback.provider'].find_for_url(origin_url)
        if not provider:
            provider = self.env['hc.cashback.provider'].get_default()
        implementation = provider.get_implementation()
        clean_url, shop_reference, item_reference = implementation.normalize_url(origin_url)

        existing = self.search([
            ('member_id', '=', member.id),
            ('provider_id', '=', provider.id),
            ('clean_url', '=', clean_url),
            ('state', '=', 'ready'),
        ], limit=1)
        if existing:
            return existing

        link = self.create({
            'member_id': member.id,
            'provider_id': provider.id,
            'origin_url': origin_url,
            'clean_url': clean_url,
            'shop_reference': shop_reference,
            'item_reference': item_reference,
        })
        link._generate(implementation)
        return link

    def _generate(self, implementation):
        self.ensure_one()
        try:
            tracking_url = implementation.build_link(self.clean_url, [str(self.member_id.id), self.request_key])
        except UserError as error:
            self.write({'state': 'failed', 'error_message': str(error)})
            raise
        self.write({'tracking_url': tracking_url, 'state': 'ready', 'error_message': False})
