"""Export blueprint -- CSV and XLSX export endpoints for entity data.

CSV exports use streaming responses via ``stream_with_context`` to avoid
loading entire datasets into memory.  XLSX exports remain buffered
(openpyxl does not support streaming).
"""

from flask import Blueprint, Response, stream_with_context
from flask_security import login_required, roles_accepted

from app.services import export_service

export_bp = Blueprint("export", __name__, url_prefix="/export")


def _streaming_csv_response(entity_type, filename):
    """Build a streaming CSV response for the given entity type."""
    generator = export_service.stream_csv_export(entity_type)
    return Response(
        stream_with_context(generator),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@export_bp.route("/customers/<format>")
@login_required
@roles_accepted("admin", "technician")
def export_customers(format):
    """Export customers to CSV or XLSX."""
    if format == "csv":
        return _streaming_csv_response("customers", "customers.csv")
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
@roles_accepted("admin", "technician")
def export_inventory(format):
    """Export inventory to CSV or XLSX."""
    if format == "csv":
        return _streaming_csv_response("inventory", "inventory.csv")
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
@roles_accepted("admin", "technician")
def export_orders(format):
    """Export orders to CSV or XLSX."""
    if format == "csv":
        return _streaming_csv_response("orders", "orders.csv")
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
@roles_accepted("admin", "technician")
def export_invoices(format):
    """Export invoices to CSV or XLSX."""
    if format == "csv":
        return _streaming_csv_response("invoices", "invoices.csv")
    elif format == "xlsx":
        data = export_service.export_invoices_xlsx()
        return Response(
            data.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=invoices.xlsx"},
        )
    return Response("Unsupported format", status=400)
