import logging
from collections import defaultdict

from odoo import SUPERUSER_ID, api, models, tools
from odoo.tools import frozendict

_logger = logging.getLogger(__name__)

PASSWORD_FALSY_VALUES = ('', '0', 'false')


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    @tools.ormcache(cache='templates')
    def _hc_password_field_map(self):
        """ Return {model_name: frozenset(field_names)} of the fields displayed
        with password="True" in any active form/list/kanban view.
        The 'templates' cache is cleared whenever a view is created/written/deleted.
        """
        views = self.with_user(SUPERUSER_ID).sudo().search([
            ('type', 'in', ('form', 'list', 'kanban')),
            ('arch_db', 'ilike', 'password'),
        ])
        field_map = defaultdict(set)
        for view in views:
            try:
                arch = view._get_combined_arch()
            except Exception:
                _logger.warning("Cannot combine view %s to detect password fields", view.id, exc_info=True)
                continue
            self._hc_collect_password_fields(arch, view.model, field_map)
        return frozendict({model_name: frozenset(names) for model_name, names in field_map.items()})

    @api.model
    def _hc_collect_password_fields(self, node, model_name, field_map):
        if model_name not in self.env:
            return
        model_fields = self.env[model_name]._fields
        for child in node:
            sub_model_name = model_name
            if child.tag in ('field', 'groupby'):
                field = model_fields.get(child.get('name'))
                if field is None:
                    continue
                if (
                    child.tag == 'field'
                    and field.type in ('char', 'text')
                    and child.get('password', '').lower() not in PASSWORD_FALSY_VALUES
                ):
                    field_map[model_name].add(field.name)
                if field.relational:
                    # sub-views (x2many list/form, groupby) describe the comodel
                    sub_model_name = field.comodel_name
            self._hc_collect_password_fields(child, sub_model_name, field_map)
