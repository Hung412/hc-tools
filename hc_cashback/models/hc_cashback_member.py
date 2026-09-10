import hashlib
import hmac
import logging
import time
import uuid

import requests

from odoo import models, fields, api, _
from odoo.exceptions import AccessDenied, UserError

_logger = logging.getLogger(__name__)

TOKEN_TTL = 900
ZALO_MESSAGE_URL = 'https://openapi.zalo.me/v3.0/oa/message/cs'


class HcCashbackMember(models.Model):
    _name = 'hc.cashback.member'
    _inherit = ['mail.thread']
    _description = 'Cashback Member'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='restrict', tracking=True)
    name = fields.Char(related='partner_id.name', store=True)
    zalo_user_id = fields.Char(required=True, index=True, copy=False, tracking=True)
    phone = fields.Char(related='partner_id.phone', readonly=False)
    tracking_key = fields.Char(required=True, index=True, copy=False,
                               default=lambda self: uuid.uuid4().hex[:16],
                               help="Alphanumeric sub id carried by this member's shopping link.")
    tracking_url = fields.Char(compute='_compute_urls',
                               help="The marketplace link this member's traffic is attributed to.")
    shopping_url = fields.Char(compute='_compute_urls',
                               help="Stable link handed to the member; it redirects to the tracking link.")
    click_count = fields.Integer(readonly=True)
    last_click_datetime = fields.Datetime(readonly=True)
    bank_name = fields.Char(tracking=True)
    bank_account_number = fields.Char(tracking=True)
    bank_account_name = fields.Char(tracking=True)
    is_blocked = fields.Boolean(tracking=True, help="Blocked members can no longer shop or withdraw.")
    active = fields.Boolean(default=True)
    ledger_ids = fields.One2many('hc.cashback.ledger', 'member_id')
    balance_pending = fields.Monetary(compute='_compute_balances')
    balance_available = fields.Monetary(compute='_compute_balances')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ('unique_zalo_user_id', 'UNIQUE(zalo_user_id)', 'This Zalo account is already registered.'),
        ('unique_tracking_key', 'UNIQUE(tracking_key)', 'Tracking key must be unique.'),
    ]

    @api.depends('ledger_ids.state', 'ledger_ids.amount')
    def _compute_balances(self):
        self.balance_pending = 0.0
        self.balance_available = 0.0
        groups = self.env['hc.cashback.ledger']._read_group(
            [('member_id', 'in', self.ids), ('state', '!=', 'cancelled')],
            ['member_id', 'state'],
            ['amount:sum'],
        )
        for member, state, amount in groups:
            if state == 'payable':
                member.balance_available += amount
            else:
                member.balance_pending += amount

    @api.depends('tracking_key')
    def _compute_urls(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
        provider = self.env['hc.cashback.provider'].search([('is_default', '=', True)], limit=1)
        implementation = provider.get_implementation() if provider else None
        for r in self:
            r.shopping_url = '%s/hc_cashback/go/%s' % (base_url, r.tracking_key) if base_url else False
            try:
                r.tracking_url = implementation.build_link(None, [str(r.id), r.tracking_key])
            except (AttributeError, UserError):
                r.tracking_url = False

    @api.model
    def get_or_create_from_zalo(self, zalo_user_id, display_name=None):
        member = self.search([('zalo_user_id', '=', zalo_user_id)], limit=1)
        if member:
            return member
        partner = self.env['res.partner'].create({
            'name': display_name or _('Zalo %s', zalo_user_id),
            'company_id': False,
        })
        return self.create({'partner_id': partner.id, 'zalo_user_id': zalo_user_id})

    @api.model
    def resolve_tracking_key(self, tracking_key):
        return self.search([('tracking_key', '=', tracking_key), ('is_blocked', '=', False)], limit=1)

    def register_click(self):
        self.ensure_one()
        self.sudo().write({
            'click_count': self.click_count + 1,
            'last_click_datetime': fields.Datetime.now(),
        })

    def can_withdraw(self):
        self.ensure_one()
        return bool(not self.is_blocked and self.bank_account_number and self.bank_account_name)

    # -- token authenticated mobile page -----------------------------------

    def _token_secret(self):
        return self.env['ir.config_parameter'].sudo().get_param('database.secret') or ''

    def _sign(self, payload):
        return hmac.new(self._token_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]

    def build_h5_token(self):
        self.ensure_one()
        payload = '%s.%s' % (self.id, int(time.time()) + TOKEN_TTL)
        return '%s.%s' % (payload, self._sign(payload))

    @api.model
    def resolve_h5_token(self, token):
        try:
            member_id, expiry, signature = (token or '').split('.')
            payload = '%s.%s' % (member_id, expiry)
        except ValueError:
            raise AccessDenied()
        if not hmac.compare_digest(signature, self._sign(payload)) or int(expiry) < time.time():
            raise AccessDenied()
        member = self.browse(int(member_id)).exists()
        if not member:
            raise AccessDenied()
        return member

    def send_zalo_message(self, text):
        """Push a message to the member through the Zalo Official Account API."""
        self.ensure_one()
        try:
            access_token = self.env['hc.cashback.zalo'].get_access_token()
        except UserError:
            _logger.exception("No usable Zalo token, message to %s dropped", self.zalo_user_id)
            return False
        try:
            response = requests.post(
                ZALO_MESSAGE_URL,
                json={'recipient': {'user_id': self.zalo_user_id}, 'message': {'text': text}},
                headers={'access_token': access_token},
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException:
            _logger.exception("Cannot deliver Zalo message to %s", self.zalo_user_id)
            return False
        return True
