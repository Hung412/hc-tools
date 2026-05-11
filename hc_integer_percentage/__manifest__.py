{
    "name": "Integer Percentage Widget",
    "summary": "Display integer fields with a % suffix — a lightweight percentage widget for Integer field types",
    "description": """
Integer Percentage Widget
=========================

Odoo's built-in **percentage** widget is designed for Float fields and internally
multiplies the stored value by 100 before display (e.g. 0.5 → 50 %).
This module provides a dedicated ``integer_percentage`` widget that treats the
stored integer value as the percentage directly (e.g. 50 → 50 %).

Key features
------------
* Readonly mode: renders ``<value>%`` using Odoo's integer formatter
  (thousand-separator aware).
* Edit mode: plain numeric input box with a static ``%`` symbol — no hidden
  multiplication/division.
* Smart parsing: users can type ``50`` or ``50%``; both save ``50``.
* Works on **any** Integer field in any model — not limited to hr.employee.
* Zero Python dependencies — pure OWL / JavaScript widget.

Usage
-----
Add ``widget="integer_percentage"`` to any ``<field>`` tag whose underlying
field is an ``Integer``:

.. code-block:: xml

    <field name="completion_rate" widget="integer_percentage"/>
    <field name="discount_pct"    widget="integer_percentage"/>
    <field name="tax_rate"        widget="integer_percentage" placeholder="0"/>
    """,
    "author": "Hc",
    "website": "https://github.com/hc-tools",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "assets": {
        "web.assets_backend": [
            "hc_integer_percentage/static/src/js/integer_percentage_field.js",
            "hc_integer_percentage/static/src/xml/integer_percentage_field.xml",
        ],
    },
    "images": [
        "static/description/icon.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
    "license": "OPL-1",
}
