# -*- coding: utf-8 -*-
{
    'name': 'OpenAI ChatGPT Integration',
    'version': '18.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Integrate ChatGPT with Odoo Discuss',
    'description': """
        OpenAI ChatGPT Integration for Odoo 18
        =====================================
        Features:
        - Chat with ChatGPT directly in Discuss channels
        - Conversation history management
        - Configurable AI models (GPT-4, GPT-3.5)
        - Customizable system prompts
        - Context-aware conversations
        - Multi-user session support
    """,
    'author': 'HC',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'mail', 'web'],
    'external_dependencies': {
        'python': ['openai'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/openai_config_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

