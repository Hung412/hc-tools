import logging
import time

import requests

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

OAUTH_TOKEN_URL = 'https://oauth.zaloapp.com/v4/oa/access_token'
PARAM_APP_ID = 'hc_cashback.zalo_app_id'
PARAM_APP_SECRET = 'hc_cashback.zalo_app_secret'
PARAM_ACCESS_TOKEN = 'hc_cashback.zalo_access_token'
PARAM_REFRESH_TOKEN = 'hc_cashback.zalo_refresh_token'
PARAM_EXPIRY = 'hc_cashback.zalo_token_expiry'
REFRESH_MARGIN = 600


class HcCashbackZalo(models.AbstractModel):
    _name = 'hc.cashback.zalo'
    _description = 'Zalo Official Account API'

    def get_access_token(self):
        config = self.env['ir.config_parameter'].sudo()
        token = config.get_param(PARAM_ACCESS_TOKEN)
        expiry = config.get_param(PARAM_EXPIRY)
        if token and expiry and float(expiry) - time.time() > REFRESH_MARGIN:
            return token
        return self.refresh_access_token()

    def refresh_access_token(self):
        config = self.env['ir.config_parameter'].sudo()
        refresh_token = config.get_param(PARAM_REFRESH_TOKEN)
        if not refresh_token:
            raise UserError(_('No Zalo refresh token stored. Run the Zalo authorisation once.'))
        return self._exchange({
            'refresh_token': refresh_token,
            'app_id': config.get_param(PARAM_APP_ID),
            'grant_type': 'refresh_token',
        })

    def exchange_authorization_code(self, code, code_verifier):
        config = self.env['ir.config_parameter'].sudo()
        return self._exchange({
            'code': code,
            'app_id': config.get_param(PARAM_APP_ID),
            'grant_type': 'authorization_code',
            'code_verifier': code_verifier,
        })

    def _exchange(self, payload):
        config = self.env['ir.config_parameter'].sudo()
        app_secret = config.get_param(PARAM_APP_SECRET)
        if not payload.get('app_id') or not app_secret:
            raise UserError(_('Zalo application credentials are not configured.'))
        try:
            response = requests.post(
                OAUTH_TOKEN_URL, data=payload, headers={'secret_key': app_secret}, timeout=20)
            response.raise_for_status()
            body = response.json()
        except requests.Timeout:
            raise UserError(_('The Zalo authorisation service timed out.'))
        except requests.RequestException:
            _logger.exception("Zalo token exchange failed")
            raise UserError(_('Cannot reach the Zalo authorisation service.'))
        except ValueError:
            _logger.exception("Zalo token exchange returned a non JSON body")
            raise UserError(_('The Zalo authorisation service returned an unreadable response.'))

        access_token = body.get('access_token')
        refresh_token = body.get('refresh_token')
        if not access_token or not refresh_token:
            _logger.warning("Zalo token exchange rejected: %s", body)
            raise UserError(_('Zalo refused the authorisation: %s', body.get('error_description') or body.get('error')))
        self._store_tokens(access_token, refresh_token, int(body.get('expires_in') or 3600))
        return access_token

    def _store_tokens(self, access_token, refresh_token, expires_in):
        """Persist on a dedicated cursor.

        Zalo invalidates the previous refresh token on every exchange. If the
        calling transaction later rolls back we would lose the only credential
        able to renew the session, and the OA would have to be re-authorised by
        hand, so this write must survive independently of the caller.
        """
        with self.pool.cursor() as cr:
            config = self.env(cr=cr)['ir.config_parameter'].sudo()
            config.set_param(PARAM_ACCESS_TOKEN, access_token)
            config.set_param(PARAM_REFRESH_TOKEN, refresh_token)
            config.set_param(PARAM_EXPIRY, str(time.time() + expires_in))

    @api.model
    def cron_refresh_access_token(self):
        try:
            self.refresh_access_token()
        except UserError:
            _logger.exception("Scheduled Zalo token refresh failed")
