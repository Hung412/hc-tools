import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HcCashbackImportWizard(models.TransientModel):
    _name = 'hc.cashback.import.wizard'
    _description = 'Import Affiliate Conversion Report'

    provider_id = fields.Many2one(
        'hc.cashback.provider', required=True,
        default=lambda self: self.env['hc.cashback.provider'].get_default())
    report_file = fields.Binary(required=True)
    report_filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        conversions = self.provider_id.get_implementation().parse_report(
            base64.b64decode(self.report_file))
        if not conversions:
            raise UserError(_('This report contains no order line.'))

        Order = self.env['hc.cashback.order']
        keys = [Order._build_external_key(
            self.provider_id.key, c.order_reference, c.item_reference, c.model_reference)
            for c in conversions]
        Order.sync_from_conversions(self.provider_id, conversions)

        orders = Order.search([('external_order_key', 'in', keys)])
        unmatched = len(orders.filtered(lambda order: not order.member_id))
        if unmatched:
            _logger.warning("%s imported order lines carry an unknown sub id", unmatched)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imported Orders'),
            'res_model': 'hc.cashback.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', orders.ids)],
        }
