from odoo import models, api, tools
from odoo.osv import expression
from odoo.tools import config


class IrRule(models.Model):
    _inherit = 'ir.rule'

    @api.model
    @tools.conditional(
        'xml' not in config['dev_mode'],
        tools.ormcache('self.env.uid', 'self.env.su', 'model_name', 'mode',
                       'tuple(self._compute_domain_context_values())'),
    )
    def _compute_domain(self, model_name, mode="read"):
        """History lines inherit the record rules of their source record,
        the same way ``_inherits`` children inherit the rules of their parent."""
        domain = super()._compute_domain(model_name, mode)
        model = self.env[model_name]
        if isinstance(model, self.pool['history.line.mixin']) and 'record_id' in model._fields:
            source_domain = self._compute_domain(model._fields['record_id'].comodel_name, mode)
            if source_domain:
                domain = expression.AND([domain or [], [('record_id', 'any', source_domain)]])
        return domain
