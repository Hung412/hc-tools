from datetime import datetime

from odoo.exceptions import AccessDenied, UserError
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from ..providers.base import Conversion

TEMPLATE = ('https://shopee.vn/?mmp_pid=an_17321270627&utm_source=an_17321270627'
            '&utm_medium=affiliates&utm_content={sub_ids}')


class TestCashback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref('hc_cashback.provider_shopee_direct')
        cls.Order = cls.env['hc.cashback.order']
        cls.Ledger = cls.env['hc.cashback.ledger']
        cls.member = cls.env['hc.cashback.member'].create({
            'partner_id': cls.env['res.partner'].create({'name': 'Test Buyer'}).id,
            'zalo_user_id': 'zalo-test',
            'tracking_key': 'abcdef0123456789',
        })

    def _sync(self, order_reference, status, gross=50000.0, tracking_key=None):
        return self.Order.sync_from_conversions(self.provider, [Conversion(
            order_reference=order_reference,
            item_reference='I1',
            commission_gross=gross,
            status=status,
            sub_ids=[str(self.member.id), tracking_key or self.member.tracking_key, '', '', ''],
            order_amount=gross * 10,
            purchase_datetime=datetime(2026, 9, 1, 10, 0, 0),
        )])

    def _balances(self):
        self.member.invalidate_recordset()
        return self.member.balance_pending, self.member.balance_available

    def test_commission_split_and_member_matching(self):
        order = self._sync('O-A', 'pending')
        self.assertRecordValues(order, [{
            'commission_gross': 50000.0,
            'commission_net': 45000.0,
            'member_amount': 40500.0,
            'platform_amount': 4500.0,
            'member_id': self.member.id,
        }])

    def test_manual_order_derives_everything_from_gross(self):
        order = self.Order.create({
            'member_id': self.member.id,
            'provider_id': self.provider.id,
            'order_reference': 'MANUAL-1',
            'commission_gross': 50000.0,
        })
        self.assertEqual(order.provider_key, 'shopee_direct')
        self.assertEqual(order.external_order_key, 'shopee_direct|MANUAL-1||')
        self.assertTrue(order.commission_rule_id)
        self.assertRecordValues(order, [{
            'commission_net': 45000.0, 'member_amount': 40500.0, 'platform_amount': 4500.0}])
        self.assertEqual(len(order.ledger_ids), 1)
        self.assertEqual(order.ledger_ids.amount, 40500.0)
        self.assertEqual(self._balances(), (40500.0, 0.0))

    def test_manual_order_saves_from_the_form(self):
        """Reproduces a save through the web client, which validates required
        fields before the server ever sees the record."""
        form = Form(self.Order)
        form.member_id = self.member
        form.provider_id = self.provider
        form.order_reference = 'FORM-1'
        form.commission_gross = 50000.0
        self.assertEqual(form.provider_key, 'shopee_direct')
        self.assertEqual(form.external_order_key, 'shopee_direct|FORM-1||')
        self.assertTrue(form.commission_rule_id)
        order = form.save()
        self.assertEqual(order.member_amount, 40500.0)
        self.assertEqual(len(order.ledger_ids), 1)

    def test_editing_gross_keeps_the_ledger_in_step(self):
        """Saving an order before typing the commission, then correcting it, must
        not leave the ledger behind."""
        order = self.Order.create({
            'member_id': self.member.id,
            'provider_id': self.provider.id,
            'order_reference': 'TYPO-1',
        })
        self.assertEqual(self._balances(), (0.0, 0.0))
        order.commission_gross = 50000.0
        self.assertEqual(order.member_amount, 40500.0)
        self.assertEqual(sum(order.ledger_ids.mapped('amount')), 40500.0)
        self.assertEqual(self._balances(), (40500.0, 0.0))

    def test_correction_survives_a_second_edit(self):
        order = self.Order.create({
            'member_id': self.member.id,
            'provider_id': self.provider.id,
            'order_reference': 'TYPO-2',
            'commission_gross': 50000.0,
        })
        order.commission_gross = 20000.0
        self.assertEqual(sum(order.ledger_ids.mapped('amount')), order.member_amount)
        self.assertEqual(self._balances(), (16200.0, 0.0))

    def test_manual_orders_cannot_collide(self):
        vals = {'member_id': self.member.id, 'provider_id': self.provider.id,
                'order_reference': 'MANUAL-1', 'commission_gross': 1000.0}
        self.Order.create(vals)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Order.create(vals)

    def test_unknown_tracking_key_leaves_order_unmatched(self):
        order = self._sync('O-X', 'pending', tracking_key='deadbeefdeadbeef')
        self.assertFalse(order.member_id)
        self.assertFalse(order.ledger_ids)

    def test_sync_is_idempotent(self):
        self._sync('O-A', 'pending')
        self.assertFalse(self._sync('O-A', 'pending'))
        self.assertEqual(self.Order.search_count([('order_reference', '=', 'O-A')]), 1)

    def test_status_moves_balance_to_available(self):
        self._sync('O-A', 'pending')
        self.assertEqual(self._balances(), (40500.0, 0.0))
        self._sync('O-A', 'validated')
        self.assertEqual(self._balances(), (40500.0, 0.0))
        self._sync('O-A', 'payable')
        self.assertEqual(self._balances(), (0.0, 40500.0))

    def test_cancellation_after_settlement_posts_reversal(self):
        self._sync('O-A', 'payable')
        self._sync('O-A', 'cancelled')
        self.assertEqual(self._balances(), (0.0, 0.0))
        self.assertEqual(self.Ledger.search_count([('entry_type', '=', 'reversal')]), 1)

    def test_cancellation_before_settlement_voids_entry(self):
        self._sync('O-A', 'pending')
        self._sync('O-A', 'cancelled')
        self.assertEqual(self._balances(), (0.0, 0.0))
        self.assertFalse(self.Ledger.search_count([('entry_type', '=', 'reversal')]))

    def test_balance_always_equals_ledger_sum(self):
        self._sync('O-A', 'payable')
        self._sync('O-B', 'payable', gross=100000.0)
        self._sync('O-B', 'cancelled', gross=100000.0)
        entries = self.Ledger.search([('member_id', '=', self.member.id), ('state', '=', 'payable')])
        self.assertEqual(sum(entries.mapped('amount')), self._balances()[1])

    def test_withdrawal_guards(self):
        self._sync('O-A', 'payable')
        Withdrawal = self.env['hc.cashback.withdrawal']
        with self.assertRaises(UserError):
            Withdrawal.request_for_member(self.member, 60000.0)
        self.member.write({
            'bank_name': 'VCB', 'bank_account_number': '007', 'bank_account_name': 'TEST'})
        with self.assertRaises(UserError):
            Withdrawal.request_for_member(self.member, 10000.0)
        with self.assertRaises(UserError):
            Withdrawal.request_for_member(self.member, 999999.0)

    def test_approved_withdrawal_debits_balance(self):
        self._sync('O-A', 'payable')
        self._sync('O-B', 'payable', gross=100000.0)
        self.member.write({
            'bank_name': 'VCB', 'bank_account_number': '007', 'bank_account_name': 'TEST'})
        withdrawal = self.env['hc.cashback.withdrawal'].request_for_member(self.member, 60000.0)
        withdrawal.action_approve()
        self.assertEqual(self._balances(), (0.0, 61500.0))
        withdrawal.action_reject()
        self.assertEqual(self._balances(), (0.0, 121500.0))

    def test_ledger_is_immutable(self):
        self._sync('O-A', 'pending')
        entry = self.Ledger.search([('member_id', '=', self.member.id)], limit=1)
        with self.assertRaises(UserError):
            entry.write({'amount': 1.0})
        with self.assertRaises(UserError):
            entry.unlink()

    def test_h5_token_round_trip(self):
        Member = self.env['hc.cashback.member']
        token = self.member.build_h5_token()
        self.assertEqual(Member.resolve_h5_token(token), self.member)
        with self.assertRaises(AccessDenied):
            Member.resolve_h5_token(token[:-1] + ('x' if token[-1] != 'x' else 'y'))
        with self.assertRaises(AccessDenied):
            Member.resolve_h5_token('garbage')


class TestShoppingLink(TransactionCase):
    """Plan A: one permanent link per member, derived from a marketplace template."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('hc_cashback.provider_shopee_direct').is_default = False
        cls.provider = cls.env['hc.cashback.provider'].create({
            'name': 'Shopee Manual',
            'key': 'shopee_manual',
            'link_template': TEMPLATE,
            'is_default': True,
        })
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://cashback.example')
        cls.member = cls.env['hc.cashback.member'].create({
            'partner_id': cls.env['res.partner'].create({'name': 'Shopper'}).id,
            'zalo_user_id': 'zalo-shopper',
            'tracking_key': 'feedface12345678',
        })

    def test_member_gets_a_tracking_url_from_the_template(self):
        self.assertEqual(
            self.member.tracking_url,
            TEMPLATE.replace('{sub_ids}', '%s-feedface12345678---' % self.member.id))

    def test_shopping_url_is_stable_and_points_at_us(self):
        self.assertEqual(
            self.member.shopping_url,
            'https://cashback.example/hc_cashback/go/feedface12345678')

    def test_tracking_key_resolves_only_for_active_members(self):
        Member = self.env['hc.cashback.member']
        self.assertEqual(Member.resolve_tracking_key('feedface12345678'), self.member)
        self.member.is_blocked = True
        self.assertFalse(Member.resolve_tracking_key('feedface12345678'))
        self.assertFalse(Member.resolve_tracking_key('nope'))

    def test_clicks_are_counted(self):
        self.member.register_click()
        self.member.register_click()
        self.assertEqual(self.member.click_count, 2)
        self.assertTrue(self.member.last_click_datetime)

    def test_template_must_carry_the_placeholder(self):
        self.provider.link_template = 'https://shopee.vn/?utm_content=static'
        with self.assertRaises(UserError):
            self.provider.get_implementation().build_link(None, ['1', 'abc'])

    def test_switching_provider_changes_target_but_not_member_link(self):
        stable = self.member.shopping_url
        self.provider.link_template = 'https://other.example/?sub={sub_ids}'
        self.member.invalidate_recordset()
        self.assertEqual(self.member.shopping_url, stable)
        self.assertTrue(self.member.tracking_url.startswith('https://other.example/'))


class TestShopeeLinkFormat(TransactionCase):
    """Pinned to a link actually produced by the Shopee Custom Link tool."""

    def test_sub_ids_use_five_dash_joined_slots(self):
        from ..providers.shopee_direct import format_sub_ids, parse_sub_ids
        self.assertEqual(format_sub_ids(['1', 'abc123']), '1-abc123---')
        self.assertEqual(parse_sub_ids('1-abc123---'), ['1', 'abc123', '', '', ''])

    def test_empty_leading_slot_keeps_positions(self):
        from ..providers.shopee_direct import parse_sub_ids
        self.assertEqual(parse_sub_ids('-abc123---')[1], 'abc123')

    def test_sub_ids_reject_non_alphanumeric(self):
        from ..providers.shopee_direct import format_sub_ids
        with self.assertRaises(UserError):
            format_sub_ids(['1', 'rk-a'])

    def test_product_url_is_normalised_from_slug(self):
        provider = self.env.ref('hc_cashback.provider_shopee_direct')
        clean, shop, item = provider.get_implementation().normalize_url(
            'https://shopee.vn/-CHINH-HANG-Khau-Trang-5D-i.13213141.23119593211?xptdk=abc')
        self.assertEqual((shop, item), ('13213141', '23119593211'))
        self.assertEqual(clean, 'https://shopee.vn/product/13213141/23119593211')


class TestPermanentPortal(TransactionCase):
    """The member page is reachable for good, without a chat bot issuing tokens."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://cashback.example')
        cls.member = cls.env['hc.cashback.member'].create({
            'partner_id': cls.env['res.partner'].create({'name': 'Portal User'}).id,
            'zalo_user_id': 'zalo-portal',
        })

    def test_every_member_gets_its_own_keys(self):
        other = self.env['hc.cashback.member'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Second'}).id,
            'zalo_user_id': 'zalo-portal-2',
        })
        self.assertTrue(self.member.portal_key)
        self.assertNotEqual(self.member.portal_key, other.portal_key)
        self.assertNotEqual(self.member.portal_key, self.member.tracking_key)

    def test_portal_url_is_permanent_and_resolvable(self):
        Member = self.env['hc.cashback.member']
        self.assertEqual(
            self.member.portal_url,
            'https://cashback.example/hc_cashback/me/%s' % self.member.portal_key)
        self.assertEqual(Member.resolve_portal_key(self.member.portal_key), self.member)
        self.assertFalse(Member.resolve_portal_key('nope'))
        self.assertFalse(Member.resolve_portal_key(False))

    def test_page_renders_with_a_working_shopping_button(self):
        provider = self.env.ref('hc_cashback.provider_shopee_direct')
        provider.write({'key': 'shopee_manual', 'link_template': TEMPLATE, 'is_default': True})
        self.member.invalidate_recordset()
        html = str(self.env['ir.qweb']._render('hc_cashback.h5_home', {
            'member': self.member,
            'token': self.member.build_h5_token(),
            'portal_key': self.member.portal_key,
            'message': None,
            'orders': self.env['hc.cashback.order'],
            'withdrawals': self.env['hc.cashback.withdrawal'],
        }))
        self.assertIn('/hc_cashback/go/%s' % self.member.tracking_key, html)
        self.assertIn(self.member.portal_key, html)
        self.assertNotIn('/web/assets', html)
