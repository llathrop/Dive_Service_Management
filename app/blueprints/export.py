"""Export blueprint — CSV and XLSX export endpoints for entity data."""
from flask import Blueprint, Response, request
from flask_security import login_required

from app.services import export_service

export_bp = Blueprint("export", __name__, url_prefix="/export")


@export_bp.route("/customers/<format>")
@login_required
def export_customers(format):
    """Export customers to CSV or XLSX."""
    if format == "csv":
        data = export_service.export_customers_csv()
        return Response(
            data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=customers.csv"},
        )
    elif format == "xlsx":
        data = export_service.export_customers_xlsx()
        return Response(
            data.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=customers.xlsx"},
        )
    return Response("Unsupported format", status=400)


@export_bp.route("/inventory/<format>")
@login_required
def export_inventory(format):
    """Export inventory to CSV or XLSX."""
    if format == "csv":
        data = export_service.export_inventory_csv()
        return Response(
            data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=inventory.csv"},
        )
    elif format == "xlsx":
        data = export_service.export_inventory_xlsx()
        return Response(
            data.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=inventory.xlsx"},
        )
    return Response("Unsupported format", status=400)


@export_bp.route("/orders/<format>")
@login_required
def export_orders(format):
    """Export orders to CSV or XLSX."""
    if format == "csv":
        data = export_service.export_orders_csv()
        return Response(
            data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=orders.csv"},
        )
    elif format == "xlsx":
        data = export_service.export_orders_xlsx()
        return Response(
            data.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=orders.xlsx"},
        )
    return Response("Unsupported format", status=400)


@export_bp.route("/invoices/<format>")
@login_required
def export_invoices(format):
    """Export invoices to CSV or XLSX."""
    if format == "csv":
        data = export_service.export_invoices_csv()
        return Response(
            data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=invoices.csv"},
        )
    elif format == "xlsx":
        data = export_service.export_invoices_xlsx()
        return Response(
            data.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=invoices.xlsx"},
        )
    return Response("Unsupported format", status=400)
