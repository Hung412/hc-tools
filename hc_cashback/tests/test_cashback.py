from datetime import datetime

from odoo.exceptions import AccessDenied, UserError
from odoo.tests.common import TransactionCase

from ..providers.base import Conversion


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
        })
        for key in ('rk-a', 'rk-b'):
            cls.env['hc.cashback.link'].create({
                'member_id': cls.member.id,
                'provider_id': cls.provider.id,
                'request_key': key,
                'origin_url': 'https://shopee.vn/x-i.1.2',
                'clean_url': 'https://shopee.vn/product/1/%s' % key,
                'state': 'ready',
            })

    def _sync(self, order_reference, request_key, status, gross=50000.0):
        return self.Order.sync_from_conversions(self.provider, [Conversion(
            order_reference=order_reference,
            item_reference='I1',
            commission_gross=gross,
            status=status,
            sub_ids=[str(self.member.id), request_key],
            order_amount=gross * 10,
            purchase_datetime=datetime(2026, 9, 1, 10, 0, 0),
        )])

    def _balances(self):
        self.member.invalidate_recordset()
        return self.member.balance_pending, self.member.balance_available

    def test_commission_split_and_member_matching(self):
        order = self._sync('O-A', 'rk-a', 'pending')
        self.assertRecordValues(order, [{
            'commission_gross': 50000.0,
            'commission_net': 45000.0,
            'member_amount': 40500.0,
            'platform_amount': 4500.0,
            'member_id': self.member.id,
        }])
        self.assertEqual(order.link_id.request_key, 'rk-a')

    def test_sync_is_idempotent(self):
        self._sync('O-A', 'rk-a', 'pending')
        self.assertFalse(self._sync('O-A', 'rk-a', 'pending'))
        self.assertEqual(self.Order.search_count([('order_reference', '=', 'O-A')]), 1)

    def test_status_moves_balance_to_available(self):
        self._sync('O-A', 'rk-a', 'pending')
        self.assertEqual(self._balances(), (40500.0, 0.0))
        self._sync('O-A', 'rk-a', 'validated')
        self.assertEqual(self._balances(), (40500.0, 0.0))
        self._sync('O-A', 'rk-a', 'payable')
        self.assertEqual(self._balances(), (0.0, 40500.0))

    def test_cancellation_after_settlement_posts_reversal(self):
        self._sync('O-A', 'rk-a', 'payable')
        self._sync('O-A', 'rk-a', 'cancelled')
        self.assertEqual(self._balances(), (0.0, 0.0))
        self.assertEqual(self.Ledger.search_count([
            ('order_id.order_reference', '=', 'O-A'), ('entry_type', '=', 'reversal')]), 1)

    def test_cancellation_before_settlement_voids_entry(self):
        self._sync('O-A', 'rk-a', 'pending')
        self._sync('O-A', 'rk-a', 'cancelled')
        self.assertEqual(self._balances(), (0.0, 0.0))
        self.assertFalse(self.Ledger.search_count([('entry_type', '=', 'reversal')]))

    def test_balance_always_equals_ledger_sum(self):
        self._sync('O-A', 'rk-a', 'payable')
        self._sync('O-B', 'rk-b', 'payable', gross=100000.0)
        self._sync('O-B', 'rk-b', 'cancelled', gross=100000.0)
        entries = self.Ledger.search([('member_id', '=', self.member.id), ('state', '=', 'payable')])
        self.assertEqual(sum(entries.mapped('amount')), self._balances()[1])

    def test_withdrawal_guards(self):
        self._sync('O-A', 'rk-a', 'payable')
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
        self._sync('O-A', 'rk-a', 'payable')
        self._sync('O-B', 'rk-b', 'payable', gross=100000.0)
        self.member.write({
            'bank_name': 'VCB', 'bank_account_number': '007', 'bank_account_name': 'TEST'})
        withdrawal = self.env['hc.cashback.withdrawal'].request_for_member(self.member, 60000.0)
        withdrawal.action_approve()
        self.assertEqual(withdrawal.state, 'approved')
        self.assertEqual(self._balances(), (0.0, 61500.0))
        withdrawal.action_reject()
        self.assertEqual(self._balances(), (0.0, 121500.0))

    def test_ledger_is_immutable(self):
        self._sync('O-A', 'rk-a', 'pending')
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
