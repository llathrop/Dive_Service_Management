#!/usr/bin/env python3
"""Capture the documentation screenshots referenced by the user guide.

The script seeds a small, deterministic snapshot dataset in the UAT database,
logs in as the demo admin user, and captures the two screenshots referenced by
``docs/user_guide.md``.

Run it from the UAT container so the Playwright browser and the application
share the same network and upload volume:

    docker compose -f docker-compose.uat.yml up -d web db
    docker compose -f docker-compose.uat.yml run --rm uat \
      python scripts/capture_docs_screenshots.py
"""

from __future__ import annotations

import argparse
import base64
import io
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from werkzeug.datastructures import FileStorage

from app import create_app
from app.extensions import db
from app.models.attachment import Attachment  # noqa: F401
from app.models.customer import Customer
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.models.shipment import Shipment  # noqa: F401
from app.models.user import Role, User
from app.services import attachment_service, customer_service, item_service, order_service


DEFAULT_OUTPUT_DIR = ROOT / "docs" / "screenshots"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"
TECH_EMAIL = "tech@example.com"
TECH_PASSWORD = "tech123"
CUSTOMER_EMAIL = "wave5a.screenshot@example.com"
CUSTOMER_NAME = "Wave 5A Screenshot Diver"
ITEM_SERIAL = "W5A-DS-001"
ITEM_NAME = "Wave 5A Drysuit"
OPEN_ORDER_DESC = "Wave 5A screenshot open order"
COMPLETE_ORDER_DESC = "Wave 5A screenshot completed order"

# 1x1 PNG used for attachment thumbnails.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
    "x8AAwMCAO+/b9cAAAAASUVORK5CYII="
)


@dataclass(frozen=True)
class SnapshotState:
    customer_id: int
    item_id: int
    open_order_id: int
    completed_order_id: int
    completed_order_item_id: int


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DSM_UAT_BASE_URL", "http://web:8080"),
        help="Base URL of the live web container.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Where to write the PNG screenshots.",
    )
    return parser.parse_args()


def _file_storage(filename: str) -> FileStorage:
    return FileStorage(
        stream=io.BytesIO(PNG_BYTES),
        filename=filename,
        content_type="image/png",
    )


def _ensure_role(name: str, description: str) -> Role:
    role = Role.query.filter_by(name=name).first()
    if role is None:
        role = Role(name=name, description=description)
        db.session.add(role)
        db.session.flush()
    return role


def _ensure_user_schema_ready() -> None:
    """Patch the UAT schema if it is missing the dashboard_config column."""
    inspector = inspect(db.engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "dashboard_config" not in user_columns:
        db.session.execute(text("ALTER TABLE users ADD COLUMN dashboard_config TEXT NULL"))
        db.session.commit()

    item_columns = {column["name"] for column in inspector.get_columns("service_items")}
    if "service_interval_days" not in item_columns:
        db.session.execute(
            text("ALTER TABLE service_items ADD COLUMN service_interval_days INT NULL")
        )
        db.session.commit()


def _ensure_user(
    user_datastore,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    role_name: str,
) -> User:
    user = User.query.filter_by(email=email).first()
    if user is None:
        role = _ensure_role(role_name, f"{role_name.title()} access")
        user = user_datastore.create_user(
            username=email.split("@", 1)[0],
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        user_datastore.add_role_to_user(user, role)
        db.session.commit()
    return user


def _ensure_customer(tech: User) -> Customer:
    customer = Customer.query.filter_by(email=CUSTOMER_EMAIL).first()
    payload = {
        "customer_type": "individual",
        "first_name": "Wave 5A",
        "last_name": "Diver",
        "email": CUSTOMER_EMAIL,
        "phone_primary": "555-0145",
        "address_line1": "145 Dive Lane",
        "city": "Corpus Christi",
        "state_province": "TX",
        "postal_code": "78401",
        "preferred_contact": "email",
        "notes": "Documentation snapshot customer.",
    }
    if customer is None:
        customer = customer_service.create_customer(payload, created_by=tech.id)
    else:
        customer_service.update_customer(customer.id, payload)
    return customer


def _ensure_item(customer: Customer, tech: User):
    item = item_service.lookup_by_serial(ITEM_SERIAL)
    payload = {
        "serial_number": ITEM_SERIAL,
        "name": ITEM_NAME,
        "item_category": "Drysuit",
        "serviceability": "serviceable",
        "serviceability_notes": "Snapshot equipment for documentation capture.",
        "brand": "DUI",
        "model": "CF200X",
        "year_manufactured": 2024,
        "notes": "Used to show the item detail service history lane.",
        "service_interval_days": 365,
        "customer_id": customer.id,
    }
    drysuit_data = {
        "size": "Large",
        "material_type": "Compressed neoprene",
        "color": "Black",
        "suit_entry_type": "Front zip",
        "neck_seal_type": "Latex",
        "wrist_seal_type": "Latex",
        "zipper_type": "Dry zipper",
        "zipper_length": "28 inch",
        "zipper_orientation": "Diagonal",
        "inflate_valve_brand": "Si Tech",
        "inflate_valve_model": "K",
        "dump_valve_brand": "Si Tech",
        "dump_valve_model": "Apeks",
        "dump_valve_type": "Automatic",
        "boot_type": "Attached",
        "boot_size": "11",
    }
    if item is None:
        item = item_service.create_item(payload, drysuit_data=drysuit_data, created_by=tech.id)
    else:
        item_service.update_item(item.id, payload, drysuit_data=drysuit_data)
    return item


def _ensure_order(customer: Customer, item, tech: User, description: str, status: str):
    order = ServiceOrder.query.filter_by(customer_id=customer.id, description=description).first()
    if order is None:
        order = order_service.create_order(
            {
                "customer_id": customer.id,
                "assigned_tech_id": tech.id,
                "date_received": date.today(),
                "date_promised": date.today() + timedelta(days=7),
                "priority": "normal",
                "description": description,
                "status": "intake",
            },
            created_by=tech.id,
        )

    order_item = (
        ServiceOrderItem.query.filter_by(order_id=order.id, service_item_id=item.id).first()
    )
    if order_item is None:
        order_item = order_service.add_order_item(
            order.id,
            item.id,
            work_description="Replace zipper and perform leak test.",
            condition_at_receipt="Minor scuffs, otherwise serviceable.",
        )

    if status == "intake" and order.status != "intake":
        order.status = "intake"
        db.session.commit()
    elif status == "completed" and order.status != "completed":
        transitions = {
            "intake": "assessment",
            "assessment": "in_progress",
            "awaiting_approval": "in_progress",
            "awaiting_parts": "in_progress",
            "in_progress": "completed",
        }
        while order.status != "completed":
            next_status = transitions.get(order.status)
            if next_status is None:
                break
            order, _ = order_service.change_status(order.id, next_status, tech.id)

    return order, order_item


def _ensure_attachment(attachable_type: str, attachable_id: int, filename: str, description: str):
    existing = [
        att for att in attachment_service.get_attachments(attachable_type, attachable_id)
        if att.filename == filename
    ]
    if existing:
        return existing[0]
    return attachment_service.save_attachment(
        _file_storage(filename),
        attachable_type,
        attachable_id,
        description=description,
        uploaded_by=None,
    )


def _seed_snapshot_state() -> SnapshotState:
    app = create_app()
    with app.app_context():
        Attachment.__table__.create(db.engine, checkfirst=True)
        Shipment.__table__.create(db.engine, checkfirst=True)
        db.create_all()
        _ensure_user_schema_ready()
        user_datastore = app.extensions["security"].datastore
        _admin = _ensure_user(user_datastore, ADMIN_EMAIL, ADMIN_PASSWORD, "Admin", "User", "admin")
        tech = _ensure_user(user_datastore, TECH_EMAIL, TECH_PASSWORD, "Jane", "Technician", "technician")
        customer = _ensure_customer(tech)
        item = _ensure_item(customer, tech)

        open_order, _ = _ensure_order(customer, item, tech, OPEN_ORDER_DESC, "intake")
        completed_order, completed_order_item = _ensure_order(
            customer, item, tech, COMPLETE_ORDER_DESC, "completed"
        )

        _ensure_attachment(
            "service_item",
            item.id,
            "wave5a-item-reference.png",
            "Item reference photo for the screenshot lane.",
        )
        _ensure_attachment(
            "service_order_item",
            completed_order_item.id,
            "wave5a-service-visit.png",
            "Service visit photo for the screenshot lane.",
        )

        db.session.refresh(customer)
        db.session.refresh(item)
        db.session.refresh(open_order)
        db.session.refresh(completed_order)
        db.session.refresh(completed_order_item)

        return SnapshotState(
            customer_id=customer.id,
            item_id=item.id,
            open_order_id=open_order.id,
            completed_order_id=completed_order.id,
            completed_order_item_id=completed_order_item.id,
        )


def _capture_screenshots(base_url: str, output_dir: Path, state: SnapshotState) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1440, "height": 1400},
            ignore_https_errors=True,
        )
        page = context.new_page()

        page.goto(f"{base_url}/login")
        page.fill('input[name="email"]', ADMIN_EMAIL)
        page.fill('input[name="password"]', ADMIN_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")

        page.goto(f"{base_url}/customers/{state.customer_id}")
        page.wait_for_load_state("networkidle")
        page.screenshot(
            path=str(output_dir / "customer_detail.png"),
            full_page=True,
        )

        page.goto(f"{base_url}/items/{state.item_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Service History", timeout=10_000)
        page.wait_for_selector(
            f"#unified-gallery-{state.item_id} img",
            timeout=10_000,
        )
        page.screenshot(
            path=str(output_dir / "item_detail_service_history.png"),
            full_page=True,
        )

        context.close()
        browser.close()


def main() -> int:
    args = _parse_args()
    state = _seed_snapshot_state()
    _capture_screenshots(args.base_url, Path(args.output_dir), state)
    print(f"Captured screenshots in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
