from lxml.builder import E

from odoo import models, fields, api, _


class HistoryMixin(models.AbstractModel):
    _name = 'history.mixin'
    _description = 'Record History Mixin'

    # Name of the history model (inheriting history.line.mixin)
    _history_model = None

    history_count = fields.Integer(compute='_compute_history_count')

    def _compute_history_count(self):
        if not self._history_model or not self.env[self._history_model].has_access('read'):
            self.history_count = 0
            return
        counts = dict(self.env[self._history_model]._read_group(
            [('record_id', 'in', self._origin.ids)], ['record_id'], ['__count'],
        ))
        for record in self:
            record.history_count = counts.get(record._origin, 0)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if records._history_enabled():
            self.env[self._history_model]._create_history(records, 'create')
        return records

    def write(self, vals):
        if not self._history_enabled():
            return super().write(vals)
        history = self.env[self._history_model]
        fnames = history._history_fnames_to_compare(self, vals)
        if not fnames:
            return super().write(vals)

        old_values = history._history_read(self, fnames)
        res = super().write(vals)
        new_values = history._history_read(self, fnames)

        changed_fnames = {}
        for record_id, values in new_values.items():
            changed = [fname for fname in fnames if values[fname] != old_values[record_id][fname]]
            if changed:
                changed_fnames[record_id] = changed
        if changed_fnames:
            history._create_history(self.browse(changed_fnames), 'write', changed_fnames)
        return res

    def unlink(self):
        # With ondelete='cascade' the snapshot would be deleted right away
        if self._history_enabled() and self.env[self._history_model]._fields['record_id'].ondelete != 'cascade':
            self.env[self._history_model]._create_history(self, 'unlink')
        return super().unlink()

    def _history_enabled(self):
        return bool(self._history_model) and not self.env.context.get('history_disable')

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form' and self._history_model:
            self._history_add_button(arch)
        return arch, view

    @api.model
    def _history_add_button(self, arch):
        if arch.xpath("//button[@name='action_open_history']"):
            return
        button_box = next(iter(arch.xpath("//div[@name='button_box']")), None)
        if button_box is None:
            sheet = next(iter(arch.xpath("//sheet")), None)
            if sheet is None:
                return
            button_box = E.div(name='button_box', **{'class': 'oe_button_box'})
            sheet.insert(0, button_box)
        button_box.append(E.button(
            E.field(name='history_count', widget='statinfo', string=_("History")),
            name='action_open_history',
            type='object',
            icon='fa-history',
            invisible='history_count == 0',
            **{'class': 'oe_stat_button'},
        ))

    def action_open_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("History of %s", self.display_name),
            'res_model': self._history_model,
            'view_mode': 'list,form',
            'domain': [('record_id', '=', self.id)],
            'context': {'create': False},
        }
