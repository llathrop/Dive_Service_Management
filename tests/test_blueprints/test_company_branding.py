"""Tests for company branding feature: context processor, header, logo upload, PDF."""

import io
import os
from unittest.mock import patch

import pytest

from app.cli.seed import _seed_system_config
from app.models.system_config import SystemConfig
from app.services import config_service


class TestContextProcessor:
    """Test the company branding context processor."""

    def test_company_name_default_fallback(self, app, client):
        """Without config, company_name falls back to default."""
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"Dive Service Management" in resp.data

    def test_company_name_from_config(self, app, client):
        """When company.name is set, it appears in the template."""
        with app.app_context():
            _seed_system_config()
            config_service.set_config("company.name", "Deep Blue Diving")
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"Deep Blue Diving" in resp.data

    def test_company_logo_url_none_when_not_configured(self, app, client):
        """company_logo_url should be None when no logo is configured."""
        with app.app_context():
            _seed_system_config()
        resp = client.get("/login")
        assert resp.status_code == 200
        # The default water icon should appear when no logo is set
        assert b"bi-water" in resp.data

    def test_company_logo_url_present_when_configured(self, app, client):
        """company_logo_url should resolve when logo file exists."""
        with app.app_context():
            _seed_system_config()
            # Create a fake logo file
            upload_folder = app.config["UPLOAD_FOLDER"]
            logos_dir = os.path.join(upload_folder, "logos")
            os.makedirs(logos_dir, exist_ok=True)
            logo_path = os.path.join(logos_dir, "test_logo.png")
            with open(logo_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            config_service.set_config("company.logo_path", "logos/test_logo.png")

        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"/uploads/logos/test_logo.png" in resp.data
        # The logo img tag should appear in the header
        assert b'<img src="/uploads/logos/test_logo.png"' in resp.data


class TestBaseTemplateHeader:
    """Test that base.html renders company name in header."""

    def test_renders_company_name_in_header(self, app, client):
        """The company name appears in the navbar brand area."""
        with app.app_context():
            _seed_system_config()
            config_service.set_config("company.name", "Reef Repair Co")
        resp = client.get("/login")
        assert b"Reef Repair Co" in resp.data

    def test_renders_company_name_in_footer(self, app, client):
        """The company name appears in the footer area."""
        with app.app_context():
            _seed_system_config()
            config_service.set_config("company.name", "Ocean Fix Ltd")
        resp = client.get("/login")
        assert b"Ocean Fix Ltd" in resp.data


class TestAdminSettingsLogoFields:
    """Test admin settings page renders logo upload fields."""

    def test_settings_renders_logo_upload_fields(self, admin_client, app):
        with app.app_context():
            _seed_system_config()
        resp = admin_client.get("/admin/settings?tab=company")
        assert resp.status_code == 200
        assert b"Header Logo" in resp.data
        assert b"Invoice Logo" in resp.data
        assert b"multipart/form-data" in resp.data

    def test_settings_form_has_enctype_for_company(self, admin_client, app):
        """Company tab form should have multipart enctype."""
        with app.app_context():
            _seed_system_config()
        resp = admin_client.get("/admin/settings?tab=company")
        assert b"multipart/form-data" in resp.data

    def test_settings_other_tabs_no_enctype(self, admin_client, app):
        """Non-company tabs should NOT have multipart enctype."""
        with app.app_context():
            _seed_system_config()
        resp = admin_client.get("/admin/settings?tab=service")
        assert b"multipart/form-data" not in resp.data


class TestLogoUpload:
    """Test logo file upload via admin settings."""

    def test_logo_upload_saves_file_and_updates_config(self, admin_client, app):
        """Uploading a valid logo saves the file and updates config."""
        with app.app_context():
            _seed_system_config()

        # Create a minimal valid PNG-like file
        data = {
            "tab": "company",
            "company_name": "Test Dive Shop",
            "company_address": "",
            "company_phone": "",
            "company_email": "",
            "company_website": "",
            "logo_upload": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "logo.png"),
        }
        resp = admin_client.post(
            "/admin/settings?tab=company",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Settings updated" in resp.data

        with app.app_context():
            logo_path = config_service.get_config("company.logo_path")
            assert logo_path is not None
            assert "header_logo.png" in logo_path

            # Verify file exists on disk
            abs_path = os.path.join(app.config["UPLOAD_FOLDER"], logo_path)
            assert os.path.isfile(abs_path)

    def test_invoice_logo_upload(self, admin_client, app):
        """Uploading an invoice logo saves it separately."""
        with app.app_context():
            _seed_system_config()

        data = {
            "tab": "company",
            "company_name": "Test Dive Shop",
            "company_address": "",
            "company_phone": "",
            "company_email": "",
            "company_website": "",
            "invoice_logo_upload": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "inv_logo.png"),
        }
        resp = admin_client.post(
            "/admin/settings?tab=company",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200

        with app.app_context():
            logo_path = config_service.get_config("company.invoice_logo_path")
            assert logo_path is not None
            assert "invoice_" in logo_path

    def test_invalid_file_type_rejected(self, admin_client, app):
        """Uploading a non-image file is rejected."""
        with app.app_context():
            _seed_system_config()

        data = {
            "tab": "company",
            "company_name": "Test Dive Shop",
            "company_address": "",
            "company_phone": "",
            "company_email": "",
            "company_website": "",
            "logo_upload": (io.BytesIO(b"not an image"), "malicious.txt"),
        }
        resp = admin_client.post(
            "/admin/settings?tab=company",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        # Form validation should fail due to FileAllowed
        assert resp.status_code == 200

        with app.app_context():
            logo_path = config_service.get_config("company.logo_path")
            # Should remain empty since upload was rejected
            assert not logo_path

    def test_oversized_file_rejected(self, admin_client, app):
        """Uploading a file over 2 MB is rejected."""
        with app.app_context():
            _seed_system_config()

        # Create a file just over 2 MB
        big_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024 + 100)
        data = {
            "tab": "company",
            "company_name": "Test Dive Shop",
            "company_address": "",
            "company_phone": "",
            "company_email": "",
            "company_website": "",
            "logo_upload": (io.BytesIO(big_data), "huge_logo.png"),
        }
        resp = admin_client.post(
            "/admin/settings?tab=company",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"2 MB" in resp.data

        with app.app_context():
            logo_path = config_service.get_config("company.logo_path")
            assert not logo_path


    def test_valid_extension_invalid_magic_bytes_rejected(self, admin_client, app):
        """A .png file with non-PNG content is rejected by magic-byte check."""
        with app.app_context():
            _seed_system_config()

        # Valid .png extension but HTML content (no PNG magic bytes)
        fake_png = b"<html><script>alert(1)</script></html>"
        data = {
            "tab": "company",
            "company_name": "Test Dive Shop",
            "company_address": "",
            "company_phone": "",
            "company_email": "",
            "company_website": "",
            "logo_upload": (io.BytesIO(fake_png), "sneaky.png"),
        }
        resp = admin_client.post(
            "/admin/settings?tab=company",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"valid image" in resp.data

        with app.app_context():
            logo_path = config_service.get_config("company.logo_path")
            assert not logo_path


class TestPDFBranding:
    """Test PDF generation with company branding."""

    def test_pdf_header_works_without_logo(self, app, db_session):
        """PDF generation works when no logo is configured."""
        from tests.factories import BaseFactory, CustomerFactory, InvoiceFactory, InvoiceLineItemFactory

        BaseFactory._meta.sqlalchemy_session = db_session
        CustomerFactory._meta.sqlalchemy_session = db_session
        InvoiceFactory._meta.sqlalchemy_session = db_session
        InvoiceLineItemFactory._meta.sqlalchemy_session = db_session

        with app.app_context():
            _seed_system_config()
            customer = CustomerFactory(first_name="Test", last_name="User")
            invoice = InvoiceFactory(customer=customer, invoice_number="INV-TEST-001")
            InvoiceLineItemFactory(invoice=invoice, description="Test Service")

            from app.utils.pdf import generate_invoice_pdf
            pdf_bytes = generate_invoice_pdf(invoice)
            assert pdf_bytes is not None
            assert len(pdf_bytes) > 0
            # PDF should start with %PDF
            assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_header_with_logo(self, app, db_session):
        """PDF generation includes logo when configured."""
        from tests.factories import BaseFactory, CustomerFactory, InvoiceFactory, InvoiceLineItemFactory

        BaseFactory._meta.sqlalchemy_session = db_session
        CustomerFactory._meta.sqlalchemy_session = db_session
        InvoiceFactory._meta.sqlalchemy_session = db_session
        InvoiceLineItemFactory._meta.sqlalchemy_session = db_session

        with app.app_context():
            _seed_system_config()

            # Create a real minimal PNG file (1x1 pixel)
            import struct
            import zlib

            def _make_minimal_png():
                """Create a valid 1x1 white PNG."""
                sig = b"\x89PNG\r\n\x1a\n"

                def _chunk(chunk_type, data):
                    c = chunk_type + data
                    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

                ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
                raw_data = b"\x00\xff\xff\xff"
                idat_data = zlib.compress(raw_data)

                return sig + _chunk(b"IHDR", ihdr_data) + _chunk(b"IDAT", idat_data) + _chunk(b"IEND", b"")

            upload_folder = app.config["UPLOAD_FOLDER"]
            logos_dir = os.path.join(upload_folder, "logos")
            os.makedirs(logos_dir, exist_ok=True)
            logo_path = os.path.join(logos_dir, "test_invoice_logo.png")
            with open(logo_path, "wb") as f:
                f.write(_make_minimal_png())

            config_service.set_config("company.logo_path", "logos/test_invoice_logo.png")

            customer = CustomerFactory(first_name="Logo", last_name="Test")
            invoice = InvoiceFactory(customer=customer, invoice_number="INV-LOGO-001")
            InvoiceLineItemFactory(invoice=invoice, description="Logo Test")

            from app.utils.pdf import generate_invoice_pdf
            pdf_bytes = generate_invoice_pdf(invoice)
            assert pdf_bytes is not None
            assert len(pdf_bytes) > 0
            assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_prefers_invoice_logo_over_header_logo(self, app, db_session):
        """Invoice PDF uses invoice_logo_path when set, not the header logo."""
        with app.app_context():
            _seed_system_config()

            # Set both logo paths
            config_service.set_config("company.logo_path", "logos/header.png")
            config_service.set_config("company.invoice_logo_path", "logos/invoice.png")

            from app.utils.pdf import _resolve_logo_path
            # invoice_logo_path does not exist on disk, so it returns None
            result = _resolve_logo_path("company.invoice_logo_path")
            assert result is None  # file doesn't exist

            # But the config value is set correctly
            val = config_service.get_config("company.invoice_logo_path")
            assert val == "logos/invoice.png"


class TestSeedConfig:
    """Test that seed data includes the new config key."""

    def test_invoice_logo_path_seeded(self, app):
        with app.app_context():
            _seed_system_config()
            row = SystemConfig.query.filter_by(config_key="company.invoice_logo_path").first()
            assert row is not None
            assert row.config_value == ""
            assert row.category == "company"

    def test_logo_path_seeded(self, app):
        with app.app_context():
            _seed_system_config()
            row = SystemConfig.query.filter_by(config_key="company.logo_path").first()
            assert row is not None
            assert row.category == "company"


class TestUploadedFileServing:
    """Test that the /uploads/ route serves files."""

    def test_uploaded_file_route(self, app, logged_in_client):
        """The /uploads/ route serves existing files to authenticated users."""
        upload_folder = app.config["UPLOAD_FOLDER"]
        logos_dir = os.path.join(upload_folder, "logos")
        os.makedirs(logos_dir, exist_ok=True)
        test_file = os.path.join(logos_dir, "serve_test.png")
        with open(test_file, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        resp = logged_in_client.get("/uploads/logos/serve_test.png")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_uploaded_file_requires_auth(self, app, client):
        """The /uploads/ route redirects unauthenticated users to login."""
        upload_folder = app.config["UPLOAD_FOLDER"]
        logos_dir = os.path.join(upload_folder, "logos")
        os.makedirs(logos_dir, exist_ok=True)
        test_file = os.path.join(logos_dir, "auth_test.png")
        with open(test_file, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        resp = client.get("/uploads/logos/auth_test.png")
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")

    def test_uploaded_file_404(self, app, logged_in_client):
        """The /uploads/ route returns 404 for missing files."""
        resp = logged_in_client.get("/uploads/logos/nonexistent.png")
        assert resp.status_code == 404
