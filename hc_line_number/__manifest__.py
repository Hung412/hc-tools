{
    "name": "Line Number Widget",
    "summary": "Add an automatic line number column (1, 2, 3…) to one2many / many2many lists",
    "description": """
Line Number Widget
==================

Provides a ``x2many_line_number`` widget for **one2many / many2many fields**
that automatically adds a line number column to the embedded list, showing the
**ordinal position** of each row (1, 2, 3…).

Key features
------------
* One attribute on the x2many field — no extra column in the embedded list,
  no need for a ``sequence`` field on the line model.
* Renumbers instantly when rows are reordered with the ``handle`` widget,
  added or removed.
* Pagination aware: page 2 continues from the previous page (offset + index).
* The column is placed right after the drag handle (or first, if there is
  no handle) and its header label is configurable.
* Zero Python dependencies — pure OWL / JavaScript widget.

Usage
-----
Set the widget on the x2many field itself:

.. code-block:: xml

    <field name="group_ids" widget="x2many_line_number"
           options="{'line_number_string': 'Priority'}">
        <list>
            <field name="sequence" widget="handle"/>
            <field name="name"/>
        </list>
    </field>

``line_number_string`` is optional — the column header defaults to ``#``.
    """,
    "author": "Hc",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "hc_line_number/static/src/js/line_number_field.js",
            "hc_line_number/static/src/xml/line_number_field.xml",
        ],
    },
    "images": [
        "static/description/banner.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "OPL-1",
}
