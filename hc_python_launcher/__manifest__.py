{
    'name': 'HC Python Launcher',
    'version': '18.0.1.0',
    'category': 'Tools',
    'summary': 'Launch Python scripts from Odoo',
    'description': """
HC Python Launcher
==================
Module để chạy file Python từ Odoo interface.
Tính năng:
- Chạy BTMC Launcher từ Odoo
- Subprocess management
- Notification system
    """,
    'author': 'TuanHung',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/python_launcher_views.xml',
    ],
    'installable': True,
    'license': 'OPL-1',
}
