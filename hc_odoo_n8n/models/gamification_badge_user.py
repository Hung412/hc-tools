from odoo import models, api, fields
import requests
import logging

_logger = logging.getLogger(__name__)

class BadgeUser(models.Model):
    _inherit = 'gamification.badge.user'

    def _send_badge(self):
        """Wizard action for sending a badge to a chosen user"""
        res = super(BadgeUser, self)._send_badge()
        self._trigger_n8n_webhook()

        return res

    def _trigger_n8n_webhook(self):
        """Gửi dữ liệu employee đến n8n"""
        try:
            webhook_url = self.env['ir.config_parameter'].sudo().get_param('hc_odoo_n8n.webhook_url')
            if not webhook_url:
                _logger.warning("N8N webhook URL not configured")
                return
            
            data = {
                're_user_id': self.user_id.id,
                're_user_name': self.user_id.name,
                'badge': self.badge_id.name,
                'creator': self.sender_id.name
            }
            
            response = requests.post(
                webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                _logger.info(f"Successfully sent data to n8n")
            else:
                _logger.error(f"Failed to send data to n8n: {response.status_code}")
                
        except Exception as e:
            _logger.error(f"Error sending data to n8n: {str(e)}")
