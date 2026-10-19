from odoo import Command
from odoo.tests import TransactionCase, new_test_user


class TestRecordHistory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Record = cls.env['test.history.record']
        cls.History = cls.env['test.history.record.history']
        cls.partner = cls.env['res.partner'].create({'name': 'History Partner'})
        cls.tag_a, cls.tag_b = cls.env['res.partner.category'].create([{'name': 'A'}, {'name': 'B'}])
        cls.record = cls.Record.create({'name': 'Rec 1', 'partner_id': cls.partner.id, 'amount': 10})

    def _history(self, record):
        return self.History.search([('record_id', '=', record.id)])

    def _changed(self, line):
        return set(line.changed_field_ids.mapped('name'))

    def test_tracked_fields(self):
        self.assertEqual(
            set(self.History._history_tracked_fields()),
            {'name', 'state', 'partner_id', 'tag_ids', 'amount', 'amount_doubled'},
        )

    def test_create_snapshot(self):
        history = self._history(self.record)
        self.assertRecordValues(history, [{
            'operation': 'create',
            'record_name': 'Rec 1',
            'name': 'Rec 1',
            'state': 'draft',
            'partner_id': self.partner.id,
            'amount': 10,
            'amount_doubled': 20,
        }])
        self.assertEqual(self._changed(history), set(self.History._history_tracked_fields()))

    def test_write_tracked_field(self):
        self.record.write({'state': 'done', 'tag_ids': [Command.set((self.tag_a | self.tag_b).ids)]})
        last = self._history(self.record)[0]
        self.assertRecordValues(last, [{'operation': 'write', 'state': 'done', 'amount': 10}])
        self.assertEqual(last.tag_ids, self.tag_a | self.tag_b)
        self.assertEqual(self._changed(last), {'state', 'tag_ids'})

    def test_write_untracked_or_same_value(self):
        self.record.write({'note': 'not tracked'})
        self.record.write({'name': 'Rec 1', 'partner_id': self.partner.id})
        self.assertEqual(len(self._history(self.record)), 1)

    def test_write_stored_compute_dependency(self):
        self.record.amount = 15
        last = self._history(self.record)[0]
        self.assertRecordValues(last, [{'amount': 15, 'amount_doubled': 30}])
        self.assertEqual(self._changed(last), {'amount', 'amount_doubled'})

    def test_batch_write_only_changed_records(self):
        record_2 = self.Record.create({'name': 'Rec 2', 'state': 'done'})
        (self.record | record_2).write({'state': 'done'})
        self.assertEqual(len(self._history(self.record)), 2)
        self.assertEqual(len(self._history(record_2)), 1)

    def test_history_disable(self):
        self.record.with_context(history_disable=True).write({'name': 'Silent'})
        self.Record.with_context(history_disable=True).create({'name': 'Silent create'})
        self.assertEqual(len(self._history(self.record)), 1)
        self.assertFalse(self.History.search([('record_name', '=', 'Silent create')]))

    def test_unlink_keeps_snapshot(self):
        record_id = self.record.id
        self.record.unlink()
        unlink_line = self.History.search([('operation', '=', 'unlink'), ('record_name', '=', 'Rec 1')])
        self.assertEqual(len(unlink_line), 1)
        self.assertFalse(unlink_line.record_id)
        self.assertFalse(self.History.search([('record_id', '=', record_id)]))

    def test_history_count_and_action(self):
        self.record.name = 'Rec 1 bis'
        self.assertEqual(self.record.history_count, 2)
        action = self.record.action_open_history()
        self.assertEqual(action['res_model'], 'test.history.record.history')
        self.assertEqual(self.History.search(action['domain']), self._history(self.record))

    def test_form_view_button(self):
        arch = self.Record.get_view(view_type='form')['arch']
        self.assertIn('name="action_open_history"', arch)
        self.assertIn('name="history_count"', arch)

    def test_default_list_view(self):
        arch = self.History.get_view(view_type='list')['arch']
        for fname in ('operation', 'amount_doubled', 'changed_field_ids'):
            self.assertIn(f'name="{fname}"', arch)

    def test_history_follows_source_rules(self):
        user_a = new_test_user(self.env, login='hist_user_a', groups='base.group_user')
        user_b = new_test_user(self.env, login='hist_user_b', groups='base.group_user')
        record_a = self.Record.with_user(user_a).create({'name': 'Owned by A'})
        record_a.write({'amount': 5})

        self.assertEqual(len(self.History.with_user(user_a).search([('record_id', '=', record_a.id)])), 2)
        self.assertFalse(self.History.with_user(user_b).search([('record_id', '=', record_a.id)]))
        self.assertEqual(record_a.with_user(user_a).history_count, 2)
