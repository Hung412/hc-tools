from odoo import models, fields

from odoo.addons.record_history.models import source_selection


class TestHistoryRecordHistory(models.Model):
    _name = 'test.history.record.history'
    _inherit = 'history.line.mixin'
    _description = 'Test Record History - History'

    record_id = fields.Many2one('test.history.record', ondelete='set null', index=True)
    name = fields.Char()
    state = fields.Selection(selection=source_selection('test.history.record', 'state'))
    partner_id = fields.Many2one('res.partner')
    tag_ids = fields.Many2many('res.partner.category')
    amount = fields.Float()
    amount_doubled = fields.Float()
