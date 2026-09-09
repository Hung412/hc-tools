import json
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

LEDGER_STATE_BY_STATUS = {
    'pending': 'pending',
    'validated': 'validated',
    'payable': 'payable',
}


class HcCashbackOrder(models.Model):
    _name = 'hc.cashback.order'
    _description = 'Cashback Affiliate Order'
    _rec_name = 'order_reference'
    _order = 'purchase_datetime desc, id desc'

    provider_id = fields.Many2one('hc.cashback.provider', required=True, ondelete='restrict')
    provider_key = fields.Char(required=True, index=True,
                               help="Frozen at creation so history survives a provider switch.")
    external_order_key = fields.Char(required=True, index=True, copy=False)
    order_reference = fields.Char(index=True)
    item_reference = fields.Char()
    member_id = fields.Many2one('hc.cashback.member', index=True, ondelete='restrict')
    link_id = fields.Many2one('hc.cashback.link', ondelete='set null')
    commission_rule_id = fields.Many2one('hc.cashback.commission.rule', required=True, ondelete='restrict')
    order_amount = fields.Monetary()
    commission_gross = fields.Monetary()
    commission_net = fields.Monetary()
    member_amount = fields.Monetary()
    platform_amount = fields.Monetary()
    currency_id = fields.Many2one('res.currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    purchase_datetime = fields.Datetime(index=True)
    status = fields.Selection([
        ('pending', 'Pending'),
        ('validated', 'Validated'),
        ('payable', 'Payable'),
        ('cancelled', 'Cancelled'),
    ], required=True, default='pending', index=True)
    ledger_ids = fields.One2many('hc.cashback.ledger', 'order_id')
    raw_payload = fields.Text(groups='hc_cashback.group_cashback_manager')

    _sql_constraints = [
        ('unique_external_order_key', 'UNIQUE(external_order_key)',
         'This affiliate order line has already been imported.'),
    ]

    @api.model
    def sync_from_conversions(self, provider, conversions):
        """Idempotently import conversions and keep their ledger entries in sync."""
        if not conversions:
            return self.browse()

        keys = ['%s|%s|%s' % (provider.key, c.order_reference, c.item_reference) for c in conversions]
        by_key = {order.external_order_key: order for order in self.search([('external_order_key', 'in', keys)])}
        links = self.env['hc.cashback.link'].search([('request_key', 'in', self._request_keys(conversions))])
        link_by_key = {link.request_key: link for link in links}
        rule_model = self.env['hc.cashback.commission.rule']
        rule_by_date = {}

        vals_list = []
        for conversion, key in zip(conversions, keys):
            order = by_key.get(key)
            if order:
                order._apply_status(conversion.status)
                continue
            link = link_by_key.get(self._request_key_of(conversion))
            date = (conversion.purchase_datetime or fields.Datetime.now()).date()
            if date not in rule_by_date:
                rule_by_date[date] = rule_model._get_for_date(date)
            rule = rule_by_date[date]
            net, member_amount, platform_amount = rule.split(conversion.commission_gross)
            vals_list.append({
                'provider_id': provider.id,
                'provider_key': provider.key,
                'external_order_key': key,
                'order_reference': conversion.order_reference,
                'item_reference': conversion.item_reference,
                'member_id': link.member_id.id if link else False,
                'link_id': link.id if link else False,
                'commission_rule_id': rule.id,
                'order_amount': conversion.order_amount,
                'commission_gross': conversion.commission_gross,
                'commission_net': net,
                'member_amount': member_amount,
                'platform_amount': platform_amount,
                'purchase_datetime': conversion.purchase_datetime,
                'status': conversion.status,
                'raw_payload': json.dumps(conversion.raw, default=str),
            })

        orders = self.create(vals_list)
        orders._create_earn_entries()
        return orders

    @api.model
    def _request_keys(self, conversions):
        return [key for key in (self._request_key_of(c) for c in conversions) if key]

    @api.model
    def _request_key_of(self, conversion):
        return conversion.sub_ids[1] if len(conversion.sub_ids) > 1 else None

    def _create_earn_entries(self):
        vals_list = [{
            'member_id': order.member_id.id,
            'order_id': order.id,
            'commission_rule_id': order.commission_rule_id.id,
            'provider_key': order.provider_key,
            'external_order_key': order.external_order_key,
            'entry_type': 'earn',
            'state': LEDGER_STATE_BY_STATUS.get(order.status, 'cancelled'),
            'amount': order.member_amount,
            'currency_id': order.currency_id.id,
            'date': (order.purchase_datetime or fields.Datetime.now()).date(),
        } for order in self.filtered('member_id')]
        return self.env['hc.cashback.ledger'].create(vals_list)

    def _apply_status(self, status):
        self.ensure_one()
        if status == self.status:
            return
        self.status = status
        earn = self.ledger_ids.filtered(lambda entry: entry.entry_type == 'earn')
        if not earn:
            return
        if status == 'cancelled':
            self._reverse(earn)
        else:
            earn.filtered(lambda entry: entry.state != 'cancelled').state = LEDGER_STATE_BY_STATUS[status]

    def _reverse(self, earn):
        already_payable = earn.filtered(lambda entry: entry.state == 'payable')
        (earn - already_payable).state = 'cancelled'
        if already_payable:
            self.env['hc.cashback.ledger'].create([{
                'member_id': entry.member_id.id,
                'order_id': self.id,
                'commission_rule_id': entry.commission_rule_id.id,
                'provider_key': entry.provider_key,
                'external_order_key': entry.external_order_key,
                'entry_type': 'reversal',
                'state': 'payable',
                'amount': -entry.amount,
                'currency_id': entry.currency_id.id,
                'note': _('Order cancelled or returned after settlement.'),
            } for entry in already_payable])
