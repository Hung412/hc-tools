# -*- coding: utf-8 -*-
{
    'name': 'OpenRouter Chatbot Integration',
    'version': '18.0.1.0',
    'category': 'Productivity/Discuss',
    'summary': 'Integrate ChatGPT with Odoo Discuss',
    'description': """
        OpenRouter Chatbot Integration for Odoo 18
        =====================================
        Features:
        - Chat with Chatbot AI directly in Discuss channels
        - Conversation history management
        - Configurable AI models (GPT-OSS-20B, Gemini-2.0-Flash-Exp, DeepSeek-R1T2-Chimera, Gemma-3-27B-IT)
        - Customizable system prompts
        - Context-aware conversations
        - Multi-user session support
    """,
    'author': 'TuanHung',
    'depends': ['base', 'mail', 'web'],
    'external_dependencies': {
        'python': ['openrouter'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/chatbot_user_data.xml',
        # 'data/chatbot_channel_data.xml',
        'views/openrouter_config_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}

