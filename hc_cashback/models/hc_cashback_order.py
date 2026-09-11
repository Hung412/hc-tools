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
    provider_key = fields.Char(required=True, index=True, readonly=True,
                               help="Frozen at creation so history survives a provider switch.")
    external_order_key = fields.Char(required=True, index=True, copy=False, readonly=True)
    order_reference = fields.Char(required=True, index=True)
    item_reference = fields.Char()
    model_reference = fields.Char(help="Product variant; one order line exists per variant.")
    click_datetime = fields.Datetime(help="When the member clicked, used when attribution is disputed.")
    member_id = fields.Many2one('hc.cashback.member', index=True, ondelete='restrict')
    commission_rule_id = fields.Many2one(
        'hc.cashback.commission.rule', required=True, ondelete='restrict',
        default=lambda self: self.env['hc.cashback.commission.rule']._find_for_date())
    order_amount = fields.Monetary()
    commission_gross = fields.Monetary()
    commission_net = fields.Monetary(compute='_compute_amounts', store=True)
    member_amount = fields.Monetary(compute='_compute_amounts', store=True)
    platform_amount = fields.Monetary(compute='_compute_amounts', store=True)
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

    @api.depends('commission_gross', 'commission_rule_id')
    def _compute_amounts(self):
        for r in self:
            r.commission_net, r.member_amount, r.platform_amount = (
                r.commission_rule_id.split(r.commission_gross) if r.commission_rule_id else (0.0, 0.0, 0.0))

    @api.onchange('provider_id', 'order_reference', 'item_reference', 'model_reference')
    def _onchange_technical_keys(self):
        """Fill the derived keys in the form; the client checks required before saving."""
        for r in self:
            if r._origin.id:
                continue
            r.provider_key = r.provider_id.key
            r.external_order_key = self._build_external_key(
                r.provider_id.key, r.order_reference, r.item_reference, r.model_reference)

    @api.model
    def _build_external_key(self, provider_key, order_reference, item_reference, model_reference=None):
        return '%s|%s|%s|%s' % (
            provider_key or '', order_reference or '', item_reference or '', model_reference or '')

    @api.model_create_multi
    def create(self, vals_list):
        rule_model = self.env['hc.cashback.commission.rule']
        for vals in vals_list:
            if not vals.get('provider_key') and vals.get('provider_id'):
                vals['provider_key'] = self.env['hc.cashback.provider'].browse(vals['provider_id']).key
            if not vals.get('external_order_key'):
                vals['external_order_key'] = self._build_external_key(
                    vals.get('provider_key'), vals.get('order_reference'),
                    vals.get('item_reference'), vals.get('model_reference'))
            if not vals.get('commission_rule_id'):
                purchased = vals.get('purchase_datetime')
                date = fields.Datetime.to_datetime(purchased).date() if purchased else None
                vals['commission_rule_id'] = rule_model._get_for_date(date).id
        orders = super().create(vals_list)
        orders._create_earn_entries()
        return orders

    @api.model
    def sync_from_conversions(self, provider, conversions):
        """Idempotently import conversions and keep their ledger entries in sync."""
        if not conversions:
            return self.browse()

        keys = [self._build_external_key(provider.key, c.order_reference, c.item_reference, c.model_reference)
                for c in conversions]
        by_key = {order.external_order_key: order for order in self.search([('external_order_key', 'in', keys)])}
        member_by_key = self._members_by_tracking_key(conversions)
        rule_model = self.env['hc.cashback.commission.rule']
        rule_by_date = {}

        vals_list = []
        for conversion, key in zip(conversions, keys):
            order = by_key.get(key)
            if order:
                order._apply_status(conversion.status)
                continue
            member = member_by_key.get(self._tracking_key_of(conversion))
            date = (conversion.purchase_datetime or fields.Datetime.now()).date()
            if date not in rule_by_date:
                rule_by_date[date] = rule_model._get_for_date(date)
            rule = rule_by_date[date]
            vals_list.append({
                'provider_id': provider.id,
                'provider_key': provider.key,
                'external_order_key': key,
                'order_reference': conversion.order_reference,
                'item_reference': conversion.item_reference,
                'model_reference': conversion.model_reference,
                'click_datetime': conversion.click_datetime,
                'member_id': member.id if member else False,
                'commission_rule_id': rule.id,
                'order_amount': conversion.order_amount,
                'commission_gross': conversion.commission_gross,
                'purchase_datetime': conversion.purchase_datetime,
                'status': conversion.status,
                'raw_payload': json.dumps(conversion.raw, default=str),
            })

        return self.create(vals_list)

    @api.model
    def _tracking_key_of(self, conversion):
        """Slot two carries the member tracking key; slot one is a readable fallback."""
        return conversion.sub_ids[1] if len(conversion.sub_ids) > 1 else None

    @api.model
    def _members_by_tracking_key(self, conversions):
        keys = [key for key in (self._tracking_key_of(c) for c in conversions) if key]
        members = self.env['hc.cashback.member'].search([('tracking_key', 'in', keys)])
        return {member.tracking_key: member for member in members}

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

    def write(self, vals):
        result = super().write(vals)
        if {'commission_gross', 'commission_rule_id', 'member_id'} & vals.keys():
            self._post_amount_correction()
        return result

    def _post_amount_correction(self):
        """Book the difference as a new entry.

        A ledger row can never be rewritten, so correcting an order that was
        saved with the wrong commission means posting the delta instead.
        """
        vals_list = []
        for order in self.filtered('member_id'):
            entries = order.ledger_ids.filtered(lambda entry: entry.state != 'cancelled')
            delta = order.member_amount - sum(entries.mapped('amount'))
            if order.currency_id.is_zero(delta):
                continue
            vals_list.append({
                'member_id': order.member_id.id,
                'order_id': order.id,
                'commission_rule_id': order.commission_rule_id.id,
                'provider_key': order.provider_key,
                'external_order_key': order.external_order_key,
                'entry_type': 'adjustment' if entries else 'earn',
                'state': entries[:1].state or LEDGER_STATE_BY_STATUS.get(order.status, 'cancelled'),
                'amount': delta,
                'currency_id': order.currency_id.id,
                'note': _('Commission corrected on %s.', order.order_reference),
            })
        return self.env['hc.cashback.ledger'].create(vals_list)

    def action_mark_settled(self):
        """Release validated commission once the marketplace has actually paid.

        The conversion report never says the money arrived; that only shows on the
        payment statement, so settling stays a deliberate act by an operator.
        """
        settled = self.filtered(lambda order: order.status == 'validated')
        for order in settled:
            order._apply_status('payable')
        return len(settled)

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
