import logging

from odoo import http, _
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

PORTAL_LANG_PARAM = 'hc_cashback.portal_lang'
DEFAULT_PORTAL_LANG = 'vi_VN'


class HcCashbackPortalH5(http.Controller):

    @http.route('/hc_cashback/go/<string:tracking_key>', type='http', auth='public', methods=['GET'])
    def go_shopping(self, tracking_key, **kwargs):
        """Stable entry point owned by us, so a provider switch never invalidates
        the link members saved to their home screen."""
        member = request.env['hc.cashback.member'].sudo().resolve_tracking_key(tracking_key)
        if not member or not member.tracking_url:
            return request.render('hc_cashback.h5_expired', {})
        member.register_click()
        return request.redirect(member.tracking_url, local=False)

    @http.route('/hc_cashback/me/<string:portal_key>', type='http', auth='public', methods=['GET'])
    def h5_portal(self, portal_key, message=None, **kwargs):
        """The member's permanent page; the URL itself is the credential."""
        member = request.env['hc.cashback.member'].sudo().resolve_portal_key(portal_key)
        if not member:
            return request.render('hc_cashback.h5_expired', {})
        self._use_member_language(member)
        return request.render('hc_cashback.h5_home', self._render_values(member, message))

    @http.route('/hc_cashback/h5/home', type='http', auth='public', methods=['GET'])
    def h5_home(self, t=None, message=None, **kwargs):
        try:
            member = request.env['hc.cashback.member'].sudo().resolve_h5_token(t)
        except AccessDenied:
            return request.render('hc_cashback.h5_expired', {})
        self._use_member_language(member)
        return request.render('hc_cashback.h5_home', self._render_values(member, message))

    @http.route('/hc_cashback/h5/submit', type='http', auth='public', methods=['POST'], csrf=False)
    def h5_submit(self, t=None, portal_key=None, **post):
        """Actions always authenticate with a short lived token, even when the page
        behind them is permanent."""
        try:
            member = request.env['hc.cashback.member'].sudo().resolve_h5_token(t)
        except AccessDenied:
            return request.render('hc_cashback.h5_expired', {})
        self._use_member_language(member)
        message = None
        try:
            member.write({
                'bank_name': post.get('bank_name'),
                'bank_account_number': post.get('bank_account_number'),
                'bank_account_name': post.get('bank_account_name'),
            })
            if post.get('withdraw'):
                request.env['hc.cashback.withdrawal'].sudo().request_for_member(
                    member, member.balance_available)
                message = _('Your withdrawal request has been submitted.')
            else:
                message = _('Your bank details have been saved.')
        except UserError as error:
            message = str(error)
        if portal_key and portal_key == member.portal_key:
            return request.redirect('/hc_cashback/me/%s?message=%s' % (portal_key, message))
        return request.redirect('/hc_cashback/h5/home?t=%s&message=%s' % (t, message))

    def _use_member_language(self, member):
        """Public pages have no session language, so pick the member's own."""
        lang = member.partner_id.lang or request.env['ir.config_parameter'].sudo().get_param(
            PORTAL_LANG_PARAM, DEFAULT_PORTAL_LANG)
        request.update_context(lang=lang)

    def _render_values(self, member, message):
        orders = request.env['hc.cashback.order'].sudo().search(
            [('member_id', '=', member.id)], limit=30)
        withdrawals = request.env['hc.cashback.withdrawal'].sudo().search(
            [('member_id', '=', member.id)], limit=10)
        return {
            'member': member,
            'token': member.build_h5_token(),
            'portal_key': member.portal_key,
            'message': message,
            'orders': orders,
            'withdrawals': withdrawals,
        }
