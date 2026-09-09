from odoo import models, fields, api, _
from odoo.exceptions import UserError

MUTABLE_FIELDS = {'state', 'note', 'withdrawal_id'}


class HcCashbackLedger(models.Model):
    _name = 'hc.cashback.ledger'
    _description = 'Cashback Ledger Entry'
    _order = 'id desc'

    member_id = fields.Many2one('hc.cashback.member', required=True, index=True, ondelete='restrict')
    order_id = fields.Many2one('hc.cashback.order', index=True, ondelete='restrict')
    withdrawal_id = fields.Many2one('hc.cashback.withdrawal', index=True, ondelete='restrict')
    commission_rule_id = fields.Many2one('hc.cashback.commission.rule', ondelete='restrict')
    provider_key = fields.Char(required=True, index=True)
    external_order_key = fields.Char(index=True)
    entry_type = fields.Selection([
        ('earn', 'Commission Earned'),
        ('reversal', 'Commission Reversed'),
        ('withdrawal', 'Withdrawal'),
        ('adjustment', 'Manual Adjustment'),
    ], required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('validated', 'Validated'),
        ('payable', 'Payable'),
        ('cancelled', 'Cancelled'),
    ], required=True, default='pending')
    amount = fields.Monetary(required=True, help="Signed amount: positive credits the member, negative debits.")
    currency_id = fields.Many2one('res.currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    date = fields.Date(required=True, default=fields.Date.context_today)
    note = fields.Char()

    def write(self, vals):
        # A ledger row is an audit trail: only its settlement state and its link
        # to a withdrawal may still move after creation.
        if set(vals) - MUTABLE_FIELDS:
            raise UserError(_('Ledger entries are immutable. Post an adjustment entry instead.'))
        return super().write(vals)

    def unlink(self):
        # Override, ignoring super() because deleting a ledger row would silently
        # rewrite a member's balance history.
        raise UserError(_('Ledger entries cannot be deleted. Post an adjustment entry instead.'))

    @api.model
    def post_adjustment(self, member, amount, note, state='payable'):
        return self.create({
            'member_id': member.id,
            'provider_key': 'manual',
            'entry_type': 'adjustment',
            'state': state,
            'amount': amount,
            'currency_id': member.currency_id.id,
            'note': note,
        })
