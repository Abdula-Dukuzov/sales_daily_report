from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {"order_id", "order_date", "sku", "quantity", "price", "status"}
STATUS_ALIASES = {"canceled": "cancelled"}
VALID_STATUSES = {"delivered", "cancelled"}


@dataclass(frozen=True)
class Order:
    order_id: str
    order_date: date
    sku: str
    quantity: int | None
    price: Decimal
    status: str


def normalize_status(value: str) -> str:
    """Normalize known spelling/case/whitespace variations of order status."""
    normalized = value.strip().lower()
    normalized = STATUS_ALIASES.get(normalized, normalized)
    if normalized not in VALID_STATUSES:
        raise ValueError(f"Неизвестный статус заказа: {value!r}")
    return normalized


def parse_order(row: dict[str, str], line_number: int) -> Order:
    """Validate and convert one CSV row."""
    try:
        order_id = row["order_id"].strip()
        sku = row["sku"].strip()
        if not order_id:
            raise ValueError("пустой order_id")
        if not sku:
            raise ValueError("пустой sku")

        order_date = date.fromisoformat(row["order_date"].strip())
        status = normalize_status(row["status"])

        raw_quantity = row["quantity"].strip()
        quantity = int(raw_quantity) if raw_quantity else None
        if quantity is not None and quantity < 0:
            raise ValueError("quantity не может быть отрицательным")
        if status == "delivered" and quantity is None:
            raise ValueError("у delivered-заказа отсутствует quantity")

        price = Decimal(row["price"].strip())
        if not price.is_finite() or price < 0:
            raise ValueError("price должен быть конечным неотрицательным числом")

        return Order(order_id, order_date, sku, quantity, price, status)
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"Строка {line_number}: {exc}") from exc


def load_orders(input_path: Path) -> list[Order]:
    """Read CSV and remove repeated order IDs without hiding conflicting rows."""
    orders_by_id: dict[str, Order] = {}
    with input_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("CSV-файл пуст или не содержит заголовка")

        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(
                "В CSV отсутствуют обязательные колонки: "
                + ", ".join(sorted(missing_columns))
            )

        for line_number, row in enumerate(reader, start=2):
            order = parse_order(row, line_number)
            previous = orders_by_id.get(order.order_id)
            if previous is not None:
                if previous != order:
                    raise ValueError(
                        f"Конфликтующие строки для order_id={order.order_id!r}"
                    )
                continue
            orders_by_id[order.order_id] = order

    return list(orders_by_id.values())


def calculate_daily_metrics(orders: Iterable[Order]) -> list[dict[str, str | int]]:
    """Aggregate unique orders by SKU and date."""
    metrics: dict[tuple[str, date], dict[str, int | Decimal]] = defaultdict(
        lambda: {"orders": 0, "revenue": Decimal("0")}
    )

    for order in orders:
        key = (order.sku, order.order_date)
        metrics[key]["orders"] += 1
        if order.status == "delivered":
            # parse_order validates this, but keep the invariant explicit here too.
            if order.quantity is None:
                raise ValueError(
                    f"У delivered-заказа {order.order_id!r} отсутствует quantity"
                )
            metrics[key]["revenue"] += order.price * order.quantity

    result: list[dict[str, str | int]] = []
    for (sku, order_date), values in sorted(metrics.items()):
        result.append(
            {
                "sku": sku,
                "order_date": order_date.isoformat(),
                "orders": int(values["orders"]),
                "revenue": format(values["revenue"], "f"),
            }
        )
    return result


def write_report(rows: Iterable[dict[str, str | int]], output_path: Path) -> None:
    """Write the report in the required column order."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["sku", "order_date", "orders", "revenue"],
        )
        writer.writeheader()
        writer.writerows(rows)


def run(input_path: Path, output_path: Path) -> None:
    orders = load_orders(input_path)
    report = calculate_daily_metrics(orders)
    write_report(report, output_path)
    total_orders = sum(int(row["orders"]) for row in report)
    total_revenue = sum((Decimal(str(row["revenue"])) for row in report), Decimal("0"))
    print(f"Готово: {output_path}")
    print(f"Уникальных заказов учтено: {total_orders}")
    print(f"Строк в отчёте: {len(report)}")
    print(f"Выручка по delivered: {total_revenue} руб.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Расчёт ежедневных показателей продаж по артикулам."
    )
    parser.add_argument("--input", type=Path, default=Path("sales.csv"))
    parser.add_argument("--output", type=Path, default=Path("daily_by_sku.csv"))
    args = parser.parse_args()
    try:
        run(args.input, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
