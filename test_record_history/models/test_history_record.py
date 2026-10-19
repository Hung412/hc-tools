from odoo import models, fields, api


class TestHistoryRecord(models.Model):
    _name = 'test.history.record'
    _inherit = 'history.mixin'
    _description = 'Test Record History - Record'
    _history_model = 'test.history.record.history'

    name = fields.Char(required=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
    partner_id = fields.Many2one('res.partner')
    tag_ids = fields.Many2many('res.partner.category')
    amount = fields.Float()
    amount_doubled = fields.Float(compute='_compute_amount_doubled', store=True)
    note = fields.Char()

    @api.depends('amount')
    def _compute_amount_doubled(self):
        for record in self:
            record.amount_doubled = record.amount * 2
