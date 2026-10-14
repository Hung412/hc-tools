# -*- coding: utf-8 -*-
{
    'name': "HC Password Mask",
    'version': '18.0.1.0.0',
    'author': "TuanHung",
    'category': 'Tools',
    'summary': "Never send the real value of password fields to the browser",
    'description': """
        HC Password Mask
        ================
        Fields rendered with password="True" in form/list/kanban views
        (passwords, API keys, tokens, ...) are replaced by a placeholder before
        being sent to the web client, so switching the input type to "text"
        in the browser devtools or inspecting the network tab reveals nothing.

        - Masks web_read, web_search_read, onchange and direct read/search_read RPC
        - Keeps the stored value when the placeholder is saved back unchanged
        - Masks password columns in exports and refuses to import the placeholder
        - Fields are detected automatically from the views, no configuration needed
    """,
    'depends': ['web'],
    'license': 'OPL-1',
    'installable': True,
}
