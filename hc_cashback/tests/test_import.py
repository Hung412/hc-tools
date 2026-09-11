from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

REPORT_HEADER = ['ID đơn hàng',
 'Trạng thái đặt hàng',
 'Checkout id',
 'Thời Gian Đặt Hàng',
 'Thời gian hoàn thành',
 'Thời gian Click',
 'Tên Shop',
 'Shop id',
 'Loại Shop',
 'Item id',
 'Tên Item',
 'ID Model',
 'Loại sản phẩm',
 'Promotion id',
 'L1 Danh mục toàn cầu',
 'L2 Danh mục toàn cầu',
 'L3 Danh mục toàn cầu',
 'Giá(₫)',
 'Số lượng',
 'Loại Hoa hồng',
 'Đối tác chiến dịchr',
 'Giá trị đơn hàng (₫)',
 'Số tiền hoàn trả (₫)',
 'Tỷ lệ sản phẩm hoa hồng Shope',
 'Hoa hồng Shopee trên sản phẩm(₫)',
 'Tỷ lệ sản phẩm hoa hồng người bán',
 'Hoa hồng Xtra trên sản phẩm(₫)',
 'Tổng hoa hồng sản phẩm(₫)',
 'Hoa hồng đơn hàng từ Shopee(₫)',
 'Hoa hồng đơn hàng từ Người bán(₫)',
 'Tổng hoa hồng đơn hàng(₫)',
 'Tên MNC đã liên kết',
 'Mã hợp đồng MCN',
 'Mức phí quản lý MCN',
 'Phí quản lý MCN(₫)',
 'Mức hoa hồng tiếp thị liên kết theo thỏa thuận',
 'Hoa hồng ròng tiếp thị liên kết(₫)',
 'Trạng thái sản phẩm liên kết',
 'Ghi chú sản phẩm',
 'Loại thuộc tính',
 'Trạng thái người mua',
 'Sub_id1',
 'Sub_id2',
 'Sub_id3',
 'Sub_id4',
 'Sub_id5',
 'Kênh',
 'Content Type']

SAMPLE_ROW = {'Checkout id': '242638454271451',
 'Content Type': '',
 'Ghi chú sản phẩm': 'note',
 'Giá trị đơn hàng (₫)': '47999',
 'Giá(₫)': '68999',
 'Hoa hồng Shopee trên sản phẩm(₫)': '1199.975',
 'Hoa hồng Xtra trên sản phẩm(₫)': '4799.9',
 'Hoa hồng ròng tiếp thị liên kết(₫)': '5999.875',
 'Hoa hồng đơn hàng từ Người bán(₫)': '4799.9',
 'Hoa hồng đơn hàng từ Shopee(₫)': '1199.975',
 'ID Model': '290159074460',
 'ID đơn hàng': '260909JJKDEB2M',
 'Item id': '23119593211',
 'Kênh': 'Messenger',
 'L1 Danh mục toàn cầu': 'Sức Khỏe',
 'L2 Danh mục toàn cầu': 'Vật tư y tế',
 'L3 Danh mục toàn cầu': 'Bao tay và khẩu trang y tế',
 'Loại Hoa hồng': 'XTRA Comm',
 'Loại Shop': 'Preferred(Non-CB)',
 'Loại sản phẩm': 'Normal Product',
 'Loại thuộc tính': 'Đơn hàng từ cùng một Shop',
 'Mã hợp đồng MCN': '0',
 'Mức hoa hồng tiếp thị liên kết theo thỏa thuận': '100.00%',
 'Mức phí quản lý MCN': '0.00%',
 'Phí quản lý MCN(₫)': '0',
 'Promotion id': '',
 'Shop id': '13213141',
 'Sub_id1': '1',
 'Sub_id2': 'shp001',
 'Sub_id3': '',
 'Sub_id4': '',
 'Sub_id5': '',
 'Số lượng': '1',
 'Số tiền hoàn trả (₫)': '',
 'Thời Gian Đặt Hàng': '2026-09-09 14:34:14',
 'Thời gian Click': '2026-09-09 14:24:53',
 'Thời gian hoàn thành': '',
 'Trạng thái người mua': 'Đã tồn tại',
 'Trạng thái sản phẩm liên kết': 'Đang chờ xử lý',
 'Trạng thái đặt hàng': 'Đang chờ xử lý',
 'Tên Item': '[CHÍNH HÃNG ĐỦ 10 MÀU] Khẩu Trang 5D THỊNH PHÁT 3 Lớp Vải Không Dệt Kháng Khuẩn Lọc '
             'Bụi Mịn Tia UV',
 'Tên MNC đã liên kết': '',
 'Tên Shop': 'Hana - Khẩu Trang Thịnh Phát',
 'Tổng hoa hồng sản phẩm(₫)': '5999.875',
 'Tổng hoa hồng đơn hàng(₫)': '5999.875',
 'Tỷ lệ sản phẩm hoa hồng Shope': '2.50%',
 'Tỷ lệ sản phẩm hoa hồng người bán': '10.00%',
 'Đối tác chiến dịchr': ''}


class TestReportImport(TransactionCase):
    """Pinned to a real export from the Shopee affiliate dashboard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref('hc_cashback.provider_shopee_direct')
        cls.Order = cls.env['hc.cashback.order']
        cls.member = cls.env['hc.cashback.member'].create({
            'partner_id': cls.env['res.partner'].create({'name': 'Importer'}).id,
            'zalo_user_id': 'zalo-import',
            'tracking_key': 'shp001',
        })

    def _csv(self, *rows, header=None):
        import csv, io
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=header or REPORT_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buffer.getvalue().encode('utf-8')

    def _import(self, content):
        return self.provider.get_implementation().parse_report(content)

    def _row(self, **overrides):
        row = dict(SAMPLE_ROW)
        row.update(overrides)
        return row

    def test_report_row_becomes_a_matched_order(self):
        conversions = self._import(self._csv(self._row()))
        self.assertEqual(len(conversions), 1)
        orders = self.Order.sync_from_conversions(self.provider, conversions)
        self.assertEqual(orders.member_id, self.member)
        self.assertEqual(orders.order_reference, '260909JJKDEB2M')
        self.assertEqual(orders.item_reference, '23119593211')
        self.assertEqual(orders.model_reference, '290159074460')
        self.assertEqual(orders.status, 'pending')
        self.assertTrue(orders.click_datetime)
        self.assertAlmostEqual(orders.commission_gross, 5999.875, delta=1)
        self.assertAlmostEqual(orders.member_amount, 4859.9, delta=1)

    def test_importing_the_same_file_twice_changes_nothing(self):
        content = self._csv(self._row())
        self.Order.sync_from_conversions(self.provider, self._import(content))
        self.Order.sync_from_conversions(self.provider, self._import(content))
        self.assertEqual(self.Order.search_count([('order_reference', '=', '260909JJKDEB2M')]), 1)

    def test_variants_of_one_item_stay_separate(self):
        conversions = self._import(self._csv(
            self._row(),
            self._row(**{'ID Model': '290159074461'}),
        ))
        orders = self.Order.sync_from_conversions(self.provider, conversions)
        self.assertEqual(len(orders), 2)
        self.assertEqual(len(set(orders.mapped('external_order_key'))), 2)

    def test_completed_rows_become_validated(self):
        conversions = self._import(self._csv(
            self._row(**{'Trạng thái sản phẩm liên kết': 'Đã hoàn thành'})))
        self.assertEqual(conversions[0].status, 'validated')

    def test_cancelled_rows_become_cancelled(self):
        conversions = self._import(self._csv(
            self._row(**{'Trạng thái sản phẩm liên kết': 'Đã hủy'})))
        self.assertEqual(conversions[0].status, 'cancelled')

    def test_unknown_status_is_held_as_pending(self):
        conversions = self._import(self._csv(
            self._row(**{'Trạng thái sản phẩm liên kết': 'Trạng thái lạ'})))
        self.assertEqual(conversions[0].status, 'pending')

    def test_a_file_without_sub_ids_is_refused(self):
        header = [name for name in REPORT_HEADER if not name.startswith('Sub_id')]
        row = {k: v for k, v in SAMPLE_ROW.items() if not k.startswith('Sub_id')}
        with self.assertRaises(UserError):
            self._import(self._csv(row, header=header))

    def test_settling_releases_the_balance(self):
        conversions = self._import(self._csv(
            self._row(**{'Trạng thái sản phẩm liên kết': 'Đã hoàn thành'})))
        orders = self.Order.sync_from_conversions(self.provider, conversions)
        self.member.invalidate_recordset()
        self.assertTrue(self.member.balance_pending)
        self.assertFalse(self.member.balance_available)
        orders.action_mark_settled()
        self.member.invalidate_recordset()
        self.assertFalse(self.member.balance_pending)
        self.assertAlmostEqual(self.member.balance_available, 4859.9, delta=1)
