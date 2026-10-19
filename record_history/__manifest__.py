{
    "name": "Record History",
    "summary": "Snapshot-based history table for any model, with typed columns per tracked field",
    "description": """
Record History
==============

Keeps a **history model** next to any business model: every create / write /
unlink stores a snapshot of the tracked fields in a real table (typed columns),
so history can be filtered, grouped, pivoted and exported like any other model.

How it works
------------
* ``history.mixin`` goes on the source model and points to its history
  model through ``_history_model``.
* ``history.line.mixin`` goes on the history model. **Every field declared on
  the history model whose name and type match a source field is tracked** —
  declaring a field is how you choose what goes into the history.
* The history model must declare ``record_id``, a Many2one to the source model
  (``ondelete='cascade'`` drops history with the record, ``'set null'`` keeps
  an ``unlink`` snapshot).
* A "History" smart button is injected into the source form views, and the
  history list / search views are generated automatically.
* History lines inherit the record rules of their source record.

Usage
-----
.. code-block:: python

    from odoo.addons.record_history.models import source_selection

    class SaleOrder(models.Model):
        _name = 'sale.order'
        _inherit = ['sale.order', 'history.mixin']
        _history_model = 'sale.order.history'

    class SaleOrderHistory(models.Model):
        _name = 'sale.order.history'
        _inherit = 'history.line.mixin'
        _description = 'Sale Order History'

        record_id = fields.Many2one('sale.order', ondelete='set null', index=True)
        state = fields.Selection(selection=source_selection('sale.order', 'state'))
        partner_id = fields.Many2one('res.partner')
        amount_total = fields.Monetary()
        currency_id = fields.Many2one('res.currency')

Remember the ``ir.model.access.csv`` rows for the history model (read-only for
users: history lines are written with ``sudo()``).

Pass ``history_disable=True`` in the context to skip tracking (imports, bulk updates).

Limitations
-----------
* Stored computed fields are compared only when ``write`` touches one of their
  direct dependencies; changes triggered from other records (e.g. editing an
  order line) are not snapshotted on the parent.
* One2many fields are not tracked.
    """,
    "author": "Hc",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "depends": ["base"],
    "images": [
        "static/description/banner.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "OPL-1",
}
