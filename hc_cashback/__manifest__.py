# -*- coding: utf-8 -*-
{
    'name': "HC Cashback",
    'version': '18.0.4.2.0',
    'author': "TuanHung",
    'summary': "Share affiliate commission back to buyers through a Zalo bot",
    'description': """
        HC Cashback
        ===========
        Turns a buyer's marketplace product link into an affiliate tracking link,
        reconciles the resulting commission and returns most of it to the buyer.

        - Pluggable affiliate providers, with or without Open API access
        - Immutable ledger with pending / validated / payable states
        - Zalo Official Account bot as the member facing channel
        - Token authenticated mobile page for history and withdrawals
    """,
    'depends': ['base', 'mail'],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/hc_cashback_groups.xml',
        'security/ir.model.access.csv',
        'data/hc_cashback_data.xml',
        'data/cron.xml',
        'views/hc_cashback_commission_rule_views.xml',
        'views/hc_cashback_provider_views.xml',
        'views/hc_cashback_member_views.xml',
        'views/hc_cashback_order_views.xml',
        'views/hc_cashback_ledger_views.xml',
        'views/hc_cashback_withdrawal_views.xml',
        'views/hc_cashback_h5_templates.xml',
        'wizard/hc_cashback_import_wizard_views.xml',
        'views/menu.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
}
