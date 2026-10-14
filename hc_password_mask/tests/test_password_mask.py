from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from ..models.base import PASSWORD_MASK


class TestPasswordMask(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.ui.view'].create({
            'name': 'res.partner.view.form.password.mask.test',
            'model': 'res.partner',
            'type': 'form',
            'priority': 1000,
            'arch': """
                <form>
                    <field name="name"/>
                    <field name="ref" password="True"/>
                    <field name="comment" password="False"/>
                    <field name="child_ids">
                        <list><field name="name"/><field name="ref" password="True"/></list>
                    </field>
                </form>
            """,
        })
        cls.Partner = cls.env['res.partner']
        cls.partner = cls.Partner.create({
            'name': 'Parent',
            'ref': 'secret-key',
            'child_ids': [Command.create({'name': 'Child', 'ref': 'child-secret'})],
        })

    def test_detect_password_fields(self):
        self.assertIn('ref', self.Partner._hc_password_fields())
        self.assertNotIn('comment', self.Partner._hc_password_fields())
        self.assertTrue(self.Partner._hc_is_password_path('child_ids/ref'))
        self.assertFalse(self.Partner._hc_is_password_path('comment'))

    def test_web_read_masks_value(self):
        spec = {'ref': {}, 'child_ids': {'fields': {'ref': {}}}}
        values = self.partner.web_read(spec)[0]
        self.assertEqual(values['ref'], PASSWORD_MASK)
        self.assertEqual(values['child_ids'][0]['ref'], PASSWORD_MASK)

        empty = self.Partner.create({'name': 'No secret'})
        self.assertFalse(empty.web_read({'ref': {}})[0]['ref'])

    def test_web_save_keeps_value_when_mask_sent_back(self):
        child = self.partner.child_ids
        result = self.partner.web_save({
            'name': 'Renamed',
            'ref': PASSWORD_MASK,
            'child_ids': [Command.update(child.id, {'ref': PASSWORD_MASK})],
        }, {'ref': {}})
        self.assertEqual(result[0]['ref'], PASSWORD_MASK)
        self.assertRecordValues(self.partner, [{'name': 'Renamed', 'ref': 'secret-key'}])
        self.assertEqual(child.ref, 'child-secret')

        self.partner.web_save({'ref': 'new-key'}, {})
        self.assertEqual(self.partner.ref, 'new-key')

    def test_onchange_masks_default_value(self):
        result = self.Partner.with_context(default_ref='default-secret').onchange(
            {}, [], {'name': {}, 'ref': {}},
        )
        self.assertEqual(result['value']['ref'], PASSWORD_MASK)

    def test_load_refuses_mask(self):
        with self.assertRaises(UserError):
            self.Partner.load(['name', 'ref'], [['Imported', PASSWORD_MASK]])
