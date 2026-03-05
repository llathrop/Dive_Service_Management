"""Tools blueprint — utility calculators and reference tools for dive service."""
from flask import Blueprint, render_template
from flask_security import login_required

tools_bp = Blueprint("tools", __name__, url_prefix="/tools")


@tools_bp.route("/")
@login_required
def hub():
    """Tools hub — grid of available tools."""
    return render_template("tools/hub.html")


@tools_bp.route("/seal-calculator")
@login_required
def seal_calculator():
    """Seal size calculator for drysuit neck and wrist seals."""
    return render_template("tools/seal_calculator.html")


@tools_bp.route("/material-estimator")
@login_required
def material_estimator():
    """Material quantity estimator for common drysuit repairs."""
    return render_template("tools/material_estimator.html")


@tools_bp.route("/pricing-calculator")
@login_required
def pricing_calculator():
    """Quick pricing calculator for service estimates."""
    return render_template("tools/pricing_calculator.html")


@tools_bp.route("/leak-test-log")
@login_required
def leak_test_log():
    """Leak test logger for structured test documentation."""
    return render_template("tools/leak_test_log.html")


@tools_bp.route("/valve-reference")
@login_required
def valve_reference():
    """Valve service reference and compatibility guide."""
    return render_template("tools/valve_reference.html")


@tools_bp.route("/converter")
@login_required
def converter():
    """Unit converter for dive service measurements."""
    return render_template("tools/converter.html")
