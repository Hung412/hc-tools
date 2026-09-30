# hc-tools

A personal collection of Odoo addons and small tools I build for my own use
and experiments. Most modules target **Odoo 18.0**.

Each module lives in its own top-level folder (prefixed `hc_`) and is independent,
so you can drop the repo into your `addons_path` and install only what you need.

```bash
git clone https://github.com/Hung412/hc-tools.git
pip install -r hc-tools/requirements.txt
```

```ini
[options]
addons_path = /path/to/odoo/addons,/path/to/hc-tools
```

Things here are shared as-is: some modules are polished and reusable,
others are personal utilities or work in progress. Check each module's
`__manifest__.py` for its summary, dependencies and license (OPL-1).

Issues and suggestions are welcome.
