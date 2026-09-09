import base64
import hashlib
import hmac
import logging
import secrets
from urllib.parse import urlencode

from odoo import http, _
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

class HcCashbackZaloWebhook(http.Controller):

    def _help_text(self):
        return _(
            "Paste a Shopee product link and I will send back your cashback link.\n"
            "SODU - check your balance\n"
            "LICHSU - order history\n"
            "RUT - withdraw"
        )

    @http.route('/hc_cashback/zalo/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def zalo_webhook(self, **kwargs):
        if not self._verify_signature():
            _logger.warning("Rejected a Zalo webhook call with an invalid signature")
            return {'error': 'invalid signature'}
        payload = request.get_json_data()
        if payload.get('event_name') != 'user_send_text':
            return {}
        zalo_user_id = (payload.get('sender') or {}).get('id')
        text = ((payload.get('message') or {}).get('text') or '').strip()
        if not zalo_user_id:
            return {}
        try:
            self._handle_message(zalo_user_id, text)
        except Exception:
            _logger.exception("Unhandled error while processing a Zalo message")
        return {}

    def _verify_signature(self):
        config = request.env['ir.config_parameter'].sudo()
        app_id = config.get_param('hc_cashback.zalo_app_id')
        oa_secret = config.get_param('hc_cashback.zalo_oa_secret')
        if not app_id or not oa_secret:
            _logger.warning("Zalo webhook credentials are not configured")
            return False
        received = (request.httprequest.headers.get('X-ZEvent-Signature') or '').removeprefix('mac=')
        body = request.httprequest.get_data(as_text=True)
        timestamp = request.get_json_data().get('timestamp', '')
        expected = hashlib.sha256(f"{app_id}{body}{timestamp}{oa_secret}".encode()).hexdigest()
        return hmac.compare_digest(received, expected)

    def _handle_message(self, zalo_user_id, text):
        member = request.env['hc.cashback.member'].sudo().get_or_create_from_zalo(zalo_user_id)
        command = text.replace(' ', '').lower()
        if 'http' in text:
            reply = self._reply_link(member, text)
        elif command.startswith('sodu'):
            reply = _("Pending: %(pending)s\nAvailable: %(available)s", pending=member.balance_pending, available=member.balance_available)
        elif command.startswith(('lichsu', 'rut')):
            reply = self._reply_page(member)
        else:
            reply = self._help_text()
        member.send_zalo_message(reply)

    def _reply_link(self, member, text):
        url = next((word for word in text.split() if word.startswith('http')), None)
        if not url:
            return self._help_text()
        try:
            link = request.env['hc.cashback.link'].sudo().create_for_url(member, url)
        except UserError as error:
            return str(error)
        return _("Here is your cashback link:\n%s\n\nOpen it and complete the purchase in the same session.", link.tracking_url)

    def _reply_page(self, member):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return _("Open your cashback page (valid 15 minutes):\n%s/hc_cashback/h5/home?t=%s", base_url, member.build_h5_token())


PARAM_CODE_VERIFIER = 'hc_cashback.zalo_code_verifier'
PARAM_OAUTH_STATE = 'hc_cashback.zalo_oauth_state'
PERMISSION_URL = 'https://oauth.zaloapp.com/v4/oa/permission'


class HcCashbackZaloOAuth(http.Controller):
    """One-off PKCE authorisation so the database owns a renewable token pair."""

    @http.route('/hc_cashback/zalo/oauth/start', type='http', auth='user', methods=['GET'])
    def oauth_start(self, **kwargs):
        if not request.env.user.has_group('hc_cashback.group_cashback_manager'):
            raise AccessDenied()
        config = request.env['ir.config_parameter'].sudo()
        app_id = config.get_param('hc_cashback.zalo_app_id')
        if not app_id:
            raise UserError(_('Set hc_cashback.zalo_app_id before authorising the Zalo account.'))
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(16)
        config.set_param(PARAM_CODE_VERIFIER, verifier)
        config.set_param(PARAM_OAUTH_STATE, state)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        query = urlencode({
            'app_id': app_id,
            'redirect_uri': self._redirect_uri(),
            'code_challenge': challenge,
            'state': state,
        })
        return request.redirect('%s?%s' % (PERMISSION_URL, query), local=False)

    @http.route('/hc_cashback/zalo/oauth/callback', type='http', auth='public', methods=['GET'])
    def oauth_callback(self, code=None, state=None, **kwargs):
        config = request.env['ir.config_parameter'].sudo()
        expected_state = config.get_param(PARAM_OAUTH_STATE)
        if not code or not expected_state or not hmac.compare_digest(state or '', expected_state):
            return request.make_response(_('Authorisation rejected: unexpected callback state.'))
        config.set_param(PARAM_OAUTH_STATE, '')
        try:
            request.env['hc.cashback.zalo'].sudo().exchange_authorization_code(
                code, config.get_param(PARAM_CODE_VERIFIER))
        except UserError as error:
            return request.make_response(str(error))
        config.set_param(PARAM_CODE_VERIFIER, '')
        return request.make_response(_('Zalo account authorised. The bot can now send messages.'))

    def _redirect_uri(self):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return '%s/hc_cashback/zalo/oauth/callback' % base_url.rstrip('/')
