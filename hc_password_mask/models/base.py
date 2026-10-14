from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.http import request

PASSWORD_MASK = '********'


class Base(models.AbstractModel):
    _inherit = 'base'

    def _hc_password_fields(self):
        return self.env['ir.ui.view']._hc_password_field_map().get(self._name, frozenset())

    @api.model
    def _hc_is_password_path(self, path):
        """ Tell whether an export/import path like 'line_ids/api_key' ends on a password field. """
        *parent_names, field_name = path.split('/')
        model = self
        for name in parent_names:
            field = model._fields.get(name)
            if field is None or not field.relational:
                return False
            model = self.env[field.comodel_name]
        return field_name in model._hc_password_fields()

    def _hc_mask_password_values(self, values_list):
        password_fields = self._hc_password_fields()
        for values in values_list:
            for field_name in password_fields.intersection(values):
                if values[field_name]:
                    values[field_name] = PASSWORD_MASK
        return values_list

    def _hc_mask_onchange_values(self, values):
        """ Mask the onchange result, including the values of x2many commands. """
        self._hc_mask_password_values([values])
        for field_name, value in values.items():
            field = self._fields.get(field_name)
            if field is None or field.type not in ('one2many', 'many2many') or not isinstance(value, list):
                continue
            comodel = self.env[field.comodel_name]
            for command in value:
                if isinstance(command, (list, tuple)) and len(command) == 3 and isinstance(command[2], dict):
                    comodel._hc_mask_onchange_values(command[2])
        return values

    def _hc_strip_password_mask(self, vals):
        """ Drop the placeholder sent back by the client so the stored value is kept. """
        password_fields = self._hc_password_fields()
        vals = {
            field_name: value
            for field_name, value in vals.items()
            if not (field_name in password_fields and value == PASSWORD_MASK)
        }
        for field_name, value in vals.items():
            field = self._fields.get(field_name)
            if field is None or field.type not in ('one2many', 'many2many') or not isinstance(value, list):
                continue
            comodel = self.env[field.comodel_name]
            vals[field_name] = [
                (command[0], command[1], comodel._hc_strip_password_mask(command[2]))
                if isinstance(command, (list, tuple)) and len(command) == 3 and isinstance(command[2], dict)
                else command
                for command in value
            ]
        return vals

    @api.readonly
    def web_read(self, specification):
        # x2many/many2one sub-records go through web_read of their comodel, so they are masked too
        return self._hc_mask_password_values(super().web_read(specification))

    def web_save(self, vals, specification, next_id=None):
        return super().web_save(self._hc_strip_password_mask(vals), specification, next_id=next_id)

    def onchange(self, values, field_names, fields_spec):
        masked_fields = [
            field_name for field_name in self._hc_password_fields()
            if values.get(field_name) == PASSWORD_MASK
        ]
        if masked_fields:
            # Onchange methods/computes must work on the real value, not on the placeholder
            if self:
                real_values = {field_name: self[field_name] for field_name in masked_fields}
            else:
                real_values = self.default_get(masked_fields)
            values = {
                **{key: value for key, value in values.items() if key not in masked_fields},
                **real_values,
            }
        result = super().onchange(values, field_names, fields_spec)
        if isinstance(result.get('value'), dict):
            self._hc_mask_onchange_values(result['value'])
        return result

    def export_data(self, fields_to_export):
        result = super().export_data(fields_to_export)
        if not request:
            return result
        masked_indexes = [
            index for index, path in enumerate(fields_to_export)
            if self._hc_is_password_path(path)
        ]
        for row in result['datas'] if masked_indexes else []:
            for index in masked_indexes:
                if row[index]:
                    row[index] = PASSWORD_MASK
        return result

    @api.model
    def load(self, fields, data):
        masked_indexes = [index for index, path in enumerate(fields) if self._hc_is_password_path(path)]
        if any(row[index] == PASSWORD_MASK for row in data for index in masked_indexes):
            raise UserError(_(
                "The file contains the masked value \"%(mask)s\" for a password field. "
                "Replace it with the real value or remove the column before importing.",
                mask=PASSWORD_MASK,
            ))
        return super().load(fields, data)
