from odoo import http
from odoo.http import request

from odoo.addons.web.controllers import dataset


class DataSet(dataset.DataSet):

    @http.route()
    def call_kw(self, model, method, args, kwargs, path=None):
        result = super().call_kw(model, method, args, kwargs, path=path)
        # Plain read/search_read stay unmasked for server code; only mask what reaches the browser
        if method in ('read', 'search_read') and isinstance(result, list):
            request.env[model]._hc_mask_password_values(result)
        return result
