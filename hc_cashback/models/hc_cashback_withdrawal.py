from odoo import models, fields, api, _
from odoo.exceptions import UserError

MIN_AMOUNT_PARAM = 'hc_cashback.min_withdrawal_amount'


class HcCashbackWithdrawal(models.Model):
    _name = 'hc.cashback.withdrawal'
    _inherit = ['mail.thread']
    _description = 'Cashback Withdrawal Request'
    _order = 'create_date desc'

    name = fields.Char(required=True, copy=False, default=lambda self: _('New'))
    member_id = fields.Many2one('hc.cashback.member', required=True, index=True,
                                ondelete='restrict', tracking=True)
    amount = fields.Monetary(required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    bank_name = fields.Char(required=True)
    bank_account_number = fields.Char(required=True)
    bank_account_name = fields.Char(required=True)
    state = fields.Selection([
        ('draft', 'Requested'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ], required=True, default='draft', tracking=True)
    ledger_ids = fields.One2many('hc.cashback.ledger', 'withdrawal_id')
    payment_reference = fields.Char(tracking=True)
    rejection_reason = fields.Char(tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hc.cashback.withdrawal') or _('New')
        return super().create(vals_list)

    @api.model
    def request_for_member(self, member, amount):
        if not member.can_withdraw():
            raise UserError(_('Please register your bank account before withdrawing.'))
        minimum = float(self.env['ir.config_parameter'].sudo().get_param(MIN_AMOUNT_PARAM, 50000))
        if amount < minimum:
            raise UserError(_('The minimum withdrawal amount is %s.', minimum))
        if amount > member.balance_available:
            raise UserError(_('You can withdraw at most %s right now.', member.balance_available))
        if self.search_count([('member_id', '=', member.id), ('state', 'in', ('draft', 'approved'))]):
            raise UserError(_('You already have a withdrawal being processed.'))
        return self.create({
            'member_id': member.id,
            'amount': amount,
            'currency_id': member.currency_id.id,
            'bank_name': member.bank_name,
            'bank_account_number': member.bank_account_number,
            'bank_account_name': member.bank_account_name,
        })

    def action_approve(self):
        for r in self:
            if r.state != 'draft':
                raise UserError(_('Only a requested withdrawal can be approved.'))
            if r.amount > r.member_id.balance_available:
                raise UserError(_('%s no longer has enough available balance.', r.member_id.display_name))
            self.env['hc.cashback.ledger'].create({
                'member_id': r.member_id.id,
                'withdrawal_id': r.id,
                'provider_key': 'withdrawal',
                'entry_type': 'withdrawal',
                'state': 'payable',
                'amount': -r.amount,
                'currency_id': r.currency_id.id,
                'note': r.name,
            })
            r.state = 'approved'

    def action_mark_paid(self):
        for r in self:
            if r.state != 'approved':
                raise UserError(_('Only an approved withdrawal can be marked as paid.'))
            r.state = 'paid'

    def action_reject(self):
        for r in self:
            if r.state in ('paid', 'rejected'):
                raise UserError(_('This withdrawal can no longer be rejected.'))
            if r.state == 'approved':
                self.env['hc.cashback.ledger'].post_adjustment(
                    r.member_id, r.amount, _('Withdrawal %s rejected.', r.name))
            r.state = 'rejected'
