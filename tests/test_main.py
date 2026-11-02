import csv
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from main import (
    Order,
    calculate_daily_metrics,
    load_orders,
    normalize_status,
    write_report,
)


class SalesReportTests(unittest.TestCase):
    def test_cancelled_orders_count_but_do_not_add_revenue(self):
        orders = [
            Order("1", date(2026, 9, 1), "SKU-1", 2, Decimal("10"), "delivered"),
            Order("2", date(2026, 9, 1), "SKU-1", 1, Decimal("10"), "cancelled"),
        ]
        result = calculate_daily_metrics(orders)
        self.assertEqual(result, [{
            "sku": "SKU-1",
            "order_date": "2026-09-01",
            "orders": 2,
            "revenue": "20",
        }])

    def test_status_variants_are_normalized(self):
        self.assertEqual(normalize_status(" DELIVERED "), "delivered")
        self.assertEqual(normalize_status("CANCELED"), "cancelled")

    def test_duplicate_order_id_is_counted_once(self):
        row = (
            "order_id,order_date,sku,quantity,price,status\n"
            "1,2026-09-01,SKU-1,2,10,delivered\n"
            "1,2026-09-01,SKU-1,2,10,delivered\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sales.csv"
            path.write_text(row, encoding="utf-8")
            orders = load_orders(path)
        self.assertEqual(len(orders), 1)
        self.assertEqual(calculate_daily_metrics(orders)[0]["orders"], 1)

    def test_conflicting_duplicate_order_id_fails(self):
        row = (
            "order_id,order_date,sku,quantity,price,status\n"
            "1,2026-09-01,SKU-1,2,10,delivered\n"
            "1,2026-09-01,SKU-1,3,10,delivered\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sales.csv"
            path.write_text(row, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Конфликтующие строки"):
                load_orders(path)

    def test_report_has_required_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.csv"
            write_report([], path)
            with path.open(encoding="utf-8", newline="") as file:
                reader = csv.reader(file)
                self.assertEqual(
                    next(reader), ["sku", "order_date", "orders", "revenue"]
                )


if __name__ == "__main__":
    unittest.main()
