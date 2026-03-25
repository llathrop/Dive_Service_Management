"""Customer portal blueprint.

This namespace keeps customer-facing auth isolated from the internal
Flask-Security user system. Portal users are tracked in separate tables
and stored in a separate session key.
"""

from datetime import datetime
from io import BytesIO
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for,
)
from werkzeug.local import LocalProxy

from app.extensions import db
from app.forms.portal import PortalActivationForm, PortalLoginForm
from app.models.portal_user import (
    PORTAL_TOKEN_PURPOSE_ACTIVATION,
    PortalAccessToken,
    PortalUser,
)
from app.services import portal_service
from app.services import portal_invoice_service

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


class PortalAnonymousUser:
    """Fallback object for unauthenticated portal sessions."""

    is_authenticated = False
    is_anonymous = True
    is_active = False
    email = None
    customer = None
    display_name = "Guest"

    def get_id(self):
        return None


def _utcnow():
    return datetime.utcnow()


def _get_portal_user():
    user_id = session.get("portal_user_id")
    if user_id is None:
        return PortalAnonymousUser()

    user = db.session.get(PortalUser, user_id)
    if user is None or not user.active:
        session.pop("portal_user_id", None)
        session.pop("portal_remember", None)
        return PortalAnonymousUser()

    return user


portal_current_user = LocalProxy(_get_portal_user)


def _safe_next_url(target):
    if not target:
        return None
    base = request.host_url
    test_url = urlparse(urljoin(base, target))
    if test_url.scheme not in {"http", "https"}:
        return None
    if test_url.netloc != urlparse(base).netloc:
        return None
    return target


def portal_login_required(view):
    """Decorator for portal-only routes."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not portal_current_user.is_authenticated:
            flash("Please sign in to continue.", "warning")
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for("portal.login", next=next_url))
        return view(*args, **kwargs)

    return wrapped


def _login_portal_user(user, remember=False):
    session["portal_user_id"] = user.id
    session["portal_remember"] = bool(remember)
    session.permanent = bool(remember)

    user.last_login_at = user.current_login_at
    user.current_login_at = _utcnow()
    user.login_count = (user.login_count or 0) + 1


@portal_bp.app_context_processor
def inject_portal_user():
    return {"portal_current_user": portal_current_user}


@portal_bp.route("/")
def index():
    if portal_current_user.is_authenticated:
        return redirect(url_for("portal.dashboard"))
    return redirect(url_for("portal.login"))


@portal_bp.route("/login", methods=["GET", "POST"])
def login():
    if portal_current_user.is_authenticated:
        return redirect(url_for("portal.dashboard"))

    form = PortalLoginForm()
    next_url = _safe_next_url(request.args.get("next") or request.form.get("next"))

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = PortalUser.query.filter_by(email=email).first()
        if user and user.active and user.check_password(form.password.data):
            _login_portal_user(user, remember=form.remember.data)
            db.session.commit()
            flash("Signed in to the customer portal.", "success")
            return redirect(next_url or url_for("portal.dashboard"))
        flash("Invalid email or password.", "danger")

    return render_template("portal/login.html", form=form, next_url=next_url)


@portal_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("portal_user_id", None)
    session.pop("portal_remember", None)
    session.permanent = False
    flash("You have been signed out of the customer portal.", "info")
    return redirect(url_for("portal.login"))


@portal_bp.route("/dashboard")
@portal_login_required
def dashboard():
    dashboard_data = portal_service.get_customer_dashboard(
        portal_current_user.customer.id
    )
    return render_template(
        "portal/dashboard.html",
        dashboard=dashboard_data,
    )


@portal_bp.route("/orders/<int:order_id>")
@portal_login_required
def order_detail(order_id):
    order_data = portal_service.get_customer_order_detail(
        portal_current_user.customer.id,
        order_id,
    )
    return render_template("portal/order_detail.html", **order_data)


@portal_bp.route("/invoices")
@portal_login_required
def invoices():
    customer_id = getattr(portal_current_user.customer, "id", None)
    if customer_id is None:
        abort(404)

    page = request.args.get("page", 1, type=int)
    pagination = portal_invoice_service.get_customer_invoices(
        customer_id,
        page=page,
        per_page=10,
    )
    return render_template(
        "portal/invoices/list.html",
        invoices=pagination,
    )


@portal_bp.route("/invoices/<int:invoice_id>")
@portal_login_required
def invoice_detail(invoice_id):
    customer_id = getattr(portal_current_user.customer, "id", None)
    if customer_id is None:
        abort(404)

    view = portal_invoice_service.get_customer_invoice_view(customer_id, invoice_id)
    if view is None:
        abort(404)

    return render_template("portal/invoices/detail.html", **view)


@portal_bp.route("/invoices/<int:invoice_id>/pdf")
@portal_login_required
def invoice_pdf(invoice_id):
    customer_id = getattr(portal_current_user.customer, "id", None)
    if customer_id is None:
        abort(404)

    invoice = portal_invoice_service.get_customer_invoice(customer_id, invoice_id)
    if invoice is None:
        abort(404)

    from app.utils.pdf import generate_portal_invoice_pdf

    pdf_bytes = generate_portal_invoice_pdf(invoice)
    filename = f"{invoice.invoice_number}.pdf"
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@portal_bp.route("/activate/<token>", methods=["GET", "POST"])
def activate(token):
    token_record = PortalAccessToken.lookup_valid_token(token)
    if token_record is None or token_record.purpose != PORTAL_TOKEN_PURPOSE_ACTIVATION:
        abort(404)

    form = PortalActivationForm()

    if form.validate_on_submit():
        user = token_record.portal_user
        if user is None:
            user = PortalUser.query.filter_by(
                customer_id=token_record.customer_id,
                email=token_record.email,
            ).one_or_none()
        if user is None:
            user = PortalUser(
                customer_id=token_record.customer_id,
                email=token_record.email,
                active=False,
            )
            db.session.add(user)

        user.email = token_record.email
        user.customer_id = token_record.customer_id
        user.set_password(form.password.data)
        user.active = True
        user.confirmed_at = _utcnow()

        token_record.consume(user)
        db.session.commit()

        _login_portal_user(user, remember=False)
        db.session.commit()

        flash("Your portal account is ready.", "success")
        return redirect(url_for("portal.dashboard"))

    return render_template(
        "portal/activate.html",
        form=form,
        token_record=token_record,
        token=token,
    )
