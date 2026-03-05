"""Reports blueprint — data visualization and report generation."""
from datetime import date, timedelta

from flask import Blueprint, render_template, request
from flask_security import login_required

from app.services import report_service

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
@login_required
def hub():
    """Reports hub — card-based layout with all available reports."""
    return render_template("reports/hub.html")


@reports_bp.route("/revenue")
@login_required
def revenue():
    """Revenue report with breakdown by type and monthly trend."""
    date_from = request.args.get("date_from", type=str)
    date_to = request.args.get("date_to", type=str)
    # Parse dates
    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    data = report_service.revenue_report(date_from=df, date_to=dt)
    return render_template("reports/revenue.html", data=data, date_from=date_from or "", date_to=date_to or "")


@reports_bp.route("/orders")
@login_required
def orders():
    """Service order statistics."""
    date_from = request.args.get("date_from", type=str)
    date_to = request.args.get("date_to", type=str)
    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    data = report_service.orders_report(date_from=df, date_to=dt)
    return render_template("reports/orders.html", data=data, date_from=date_from or "", date_to=date_to or "")


@reports_bp.route("/inventory")
@login_required
def inventory():
    """Inventory analysis report."""
    data = report_service.inventory_report()
    return render_template("reports/inventory.html", data=data)


@reports_bp.route("/customers")
@login_required
def customers():
    """Customer statistics."""
    date_from = request.args.get("date_from", type=str)
    date_to = request.args.get("date_to", type=str)
    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    data = report_service.customer_report(date_from=df, date_to=dt)
    return render_template("reports/customers.html", data=data, date_from=date_from or "", date_to=date_to or "")


@reports_bp.route("/aging")
@login_required
def aging():
    """Accounts receivable aging report."""
    data = report_service.aging_report()
    return render_template("reports/aging.html", data=data)


def _parse_date(date_str):
    """Parse a YYYY-MM-DD date string, returning None if invalid."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None
