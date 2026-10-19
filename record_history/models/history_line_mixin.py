import logging

from lxml.builder import E

from odoo import models, fields, api, tools, _
from odoo.fields import Command

_logger = logging.getLogger(__name__)

UNTRACKABLE_TYPES = {'one2many', 'properties', 'properties_definition'}


def source_selection(model_name, field_name):
    """Return a selection callable mirroring the (possibly extended) selection of a source field."""
    def _selection(self):
        return self.env[model_name]._fields[field_name]._description_selection(self.env)
    return _selection


class HistoryLineMixin(models.AbstractModel):
    _name = 'history.line.mixin'
    _description = 'Record History Line Mixin'
    _order = 'id desc'
    _rec_name = 'record_name'

    record_name = fields.Char(readonly=True)
    operation = fields.Selection([
        ('create', 'Created'),
        ('write', 'Updated'),
        ('unlink', 'Deleted'),
    ], required=True, readonly=True)
    changed_field_ids = fields.Many2many('ir.model.fields', string='Changed Fields', readonly=True)

    @api.model
    @tools.ormcache()
    def _history_tracked_fields(self):
        """Names of the fields snapshotted from the source model.

        A field is tracked when it is a plain stored field of the history model
        and the source model has a field with the same name, type and comodel.
        """
        source = self.env[self._fields['record_id'].comodel_name]
        reserved = set(self.env['history.line.mixin']._fields) | {'record_id'}
        tracked = []
        for fname, field in self._fields.items():
            if fname in reserved or field.automatic or not field.store or field.compute:
                continue
            source_field = source._fields.get(fname)
            if not source_field:
                continue
            if (
                source_field.type != field.type
                or source_field.type in UNTRACKABLE_TYPES
                or source_field.comodel_name != field.comodel_name
            ):
                _logger.warning(
                    "%s.%s does not match %s.%s (type/comodel), it is not tracked",
                    self._name, fname, source._name, fname,
                )
                continue
            tracked.append(fname)
        return tuple(tracked)

    @api.model
    def _history_fnames_to_compare(self, source, vals):
        """Tracked fields that a ``write(vals)`` on ``source`` may change.

        Stored computed fields are included when ``vals`` touches one of their
        direct dependencies.
        """
        fnames = []
        for fname in self._history_tracked_fields():
            field = source._fields[fname]
            if fname in vals or (
                field.compute and field.store
                and any(dep.split('.')[0] in vals for dep in field.get_depends(source)[0])
            ):
                fnames.append(fname)
        return fnames

    @api.model
    def _history_value(self, record, fname):
        """Value of ``record[fname]`` in a format usable by both ``create`` and ``==``."""
        field = record._fields[fname]
        value = record[fname]
        if field.type == 'many2many':
            return [Command.set(sorted(value.ids))]
        if field.type == 'many2one':
            return value.id
        return field.convert_to_write(value, record)

    @api.model
    def _history_read(self, records, fnames):
        return {
            record.id: {fname: self._history_value(record, fname) for fname in fnames}
            for record in records
        }

    @api.model
    def _create_history(self, records, operation, changed_fnames=None):
        """Snapshot ``records``.

        :param changed_fnames: ``{record_id: [field names]}``; defaults to every
            tracked field (create / unlink).
        """
        tracked = self._history_tracked_fields()
        field_ids = self.env['ir.model.fields']._get_ids(records._name)
        values_by_id = self._history_read(records, tracked)
        vals_list = []
        for record in records:
            changed = tracked if changed_fnames is None else changed_fnames[record.id]
            vals_list.append({
                **values_by_id[record.id],
                'record_id': record.id,
                'record_name': record.display_name,
                'operation': operation,
                'changed_field_ids': [Command.set([field_ids[fname] for fname in changed])],
            })
        return self.sudo().create(vals_list)

    @api.model
    def _get_default_list_view(self):
        tracked_columns = [
            E.field(name=fname, widget='many2many_tags') if self._fields[fname].type == 'many2many'
            else E.field(name=fname)
            for fname in self._history_tracked_fields()
        ]
        return E.list(
            E.field(name='create_date', string=_("Date")),
            E.field(name='create_uid', string=_("User"), widget='many2one_avatar_user'),
            E.field(name='operation'),
            E.field(name='record_name', optional='hide'),
            *tracked_columns,
            E.field(name='changed_field_ids', widget='many2many_tags', optional='show'),
            string=self._description,
            create='0',
            edit='0',
        )

    @api.model
    def _get_default_search_view(self):
        return E.search(
            E.field(name='record_name'),
            E.field(name='changed_field_ids'),
            E.field(name='create_uid'),
            E.filter(name='created', string=_("Created"), domain="[('operation', '=', 'create')]"),
            E.filter(name='updated', string=_("Updated"), domain="[('operation', '=', 'write')]"),
            E.filter(name='deleted', string=_("Deleted"), domain="[('operation', '=', 'unlink')]"),
            E.group(
                E.filter(name='group_by_user', string=_("User"), context="{'group_by': 'create_uid'}"),
                E.filter(name='group_by_date', string=_("Date"), context="{'group_by': 'create_date'}"),
            ),
            string=self._description,
        )
