from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HcCashbackCommissionRule(models.Model):
    _name = 'hc.cashback.commission.rule'
    _description = 'Cashback Commission Rule'
    _order = 'date_from desc, id desc'

    name = fields.Char(required=True)
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date()
    tax_rate = fields.Float(
        digits=(5, 4), default=0.1,
        help="Withholding tax deducted from the gross commission before splitting.")
    member_share = fields.Float(
        digits=(5, 4), default=0.9, required=True,
        help="Share of the net commission returned to the member.")
    platform_share = fields.Float(compute='_compute_platform_share', digits=(5, 4))
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('check_member_share',
         'CHECK(member_share >= 0 AND member_share <= 1)',
         'Member share must be between 0 and 1.'),
        ('check_tax_rate',
         'CHECK(tax_rate >= 0 AND tax_rate < 1)',
         'Tax rate must be between 0 and 1.'),
    ]

    @api.depends('member_share')
    def _compute_platform_share(self):
        for r in self:
            r.platform_share = 1.0 - r.member_share

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for r in self:
            if r.date_to and r.date_to < r.date_from:
                raise UserError(_('End date must be after start date.'))

    @api.model
    def _get_for_date(self, date=None):
        date = date or fields.Date.context_today(self)
        rule = self.search([
            ('date_from', '<=', date),
            '|', ('date_to', '=', False), ('date_to', '>=', date),
        ], limit=1)
        if not rule:
            raise UserError(_('No cashback commission rule is active on %s.', date))
        return rule

    def split(self, commission_gross):
        """Return (net, member_amount, platform_amount) for a gross commission."""
        self.ensure_one()
        net = commission_gross * (1.0 - self.tax_rate)
        member_amount = net * self.member_share
        return net, member_amount, net - member_amount
