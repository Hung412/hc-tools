# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

try:
    import openrouter
except ImportError:
    _logger.warning("OpenRouter library not installed. Please install it: pip install openrouter")
    openrouter = None


class OpenRouterConfig(models.Model):
    _name = 'openrouter.config'
    _description = 'OpenRouter Configuration'
    _order = 'sequence, id'

    name = fields.Char(string='Configuration Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    api_key = fields.Char(string='API Key', required=True)
    model = fields.Selection([
        ('gpt-oss-20b', 'GPT-OSS-20B'),
        ('gemini-2.0-flash-exp', 'Gemini-2.0-Flash-Exp'),
        ('deepseek-r1t2-chimera', 'DeepSeek-R1T2-Chimera'),
        ('gemma-3-27b-it', 'Gemma-3-27B-IT'),
    ], string='Model', default='gpt-oss-20b', required=True)
    max_tokens = fields.Integer(string='Max Tokens', default=1000, help='Maximum number of tokens in response')
    temperature = fields.Float(string='Temperature', default=0.7, help='Controls randomness. Lower = more focused, Higher = more random')
    system_prompt = fields.Text(
        string='System Prompt',
        default='You are a helpful AI assistant integrated into Odoo ERP system. You can help users with questions about their business data, processes, and general queries.',
        help='System prompt that defines the AI personality and context'
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', 
                                  default=lambda self: self.env.company)
    
    # Statistics
    total_requests = fields.Integer(string='Total Requests', readonly=True, default=0)
    total_tokens_used = fields.Integer(string='Total Tokens Used', readonly=True, default=0)
    last_used = fields.Datetime(string='Last Used', readonly=True)

    @api.model
    def get_active_config(self):
        """Get active OpenRouter configuration"""
        config = self.search([('active', '=', True), ('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise UserError(_('No active OpenRouter configuration found. Please configure one in Settings > OpenRouter > Configuration.'))
        return config

    def call_openrouter_api(self, messages):
        """Call OpenRouter API with conversation history"""
        self.ensure_one()
        
        if not openrouter:
            raise UserError(_('OpenRouter library is not installed. Please install it: pip install openrouter'))
        
        if not self.api_key:
            raise UserError(_('OpenRouter API key is not configured.'))
        
        try:
            # Initialize OpenRouter client
            open_router = openrouter.OpenRouter(api_key=self.api_key)
            
            _logger.info(f'Calling OpenRouter API with model {self.model}')
            
            response = open_router.chat.send(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            
            # Update statistics
            self.sudo().write({
                'total_requests': self.total_requests + 1,
                'total_tokens_used': self.total_tokens_used + response.usage.total_tokens,
                'last_used': fields.Datetime.now(),
            })
            
            return response.choices[0].message.content
            
        except Exception as e:
            _logger.error(f'Error calling OpenRouter API: {str(e)}')
            raise UserError(_('Error calling OpenRouter API: %s') % str(e))

    def action_test_connection(self):
        """Test OpenRouter API connection"""
        self.ensure_one()
        
        try:
            test_messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': 'Say Successfully in one word.'}
            ]
            response = self.call_openrouter_api(test_messages)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful'),
                    'message': _('OpenRouter API connection test successful! Response: %s') % response,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

