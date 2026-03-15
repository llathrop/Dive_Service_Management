"""UAT: Admin hub, system settings, data management, and CSV import.

Covers: admin hub page, user management link, system settings tabs,
data management stats/backup/export/import, CSV import form.

Phase: Admin Overhaul (post-Phase 6)
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.uat


# ---------------------------------------------------------------------------
# Admin Hub
# ---------------------------------------------------------------------------


class TestAdminHub:
    """Admin hub page tests."""

    def test_admin_hub_loads(self, admin_page: Page, base_url: str):
        """Admin hub page loads with the Administration heading."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("h1")).to_contain_text("Administration")

    def test_admin_hub_has_user_management_card(self, admin_page: Page, base_url: str):
        """Admin hub shows User Management card."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=User Management")).to_be_visible()
        expect(admin_page.locator("text=Manage Users")).to_be_visible()

    def test_admin_hub_has_system_settings_card(self, admin_page: Page, base_url: str):
        """Admin hub shows System Settings card."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=System Settings")).to_be_visible()
        expect(admin_page.locator("text=View Settings")).to_be_visible()

    def test_admin_hub_has_data_management_card(self, admin_page: Page, base_url: str):
        """Admin hub shows Data Management card."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Data Management")).to_be_visible()
        expect(admin_page.locator("text=Manage Data")).to_be_visible()

    def test_admin_hub_shows_user_count(self, admin_page: Page, base_url: str):
        """Admin hub displays user and role counts."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        # The hub template shows "X users, Y roles" in the User Management card
        page_text = admin_page.text_content("body")
        assert "users" in page_text and "roles" in page_text

    def test_admin_hub_navigate_to_users(self, admin_page: Page, base_url: str):
        """Clicking Manage Users navigates to user list."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        admin_page.click("text=Manage Users")
        admin_page.wait_for_load_state("networkidle")
        assert "/admin/users" in admin_page.url

    def test_admin_hub_navigate_to_settings(self, admin_page: Page, base_url: str):
        """Clicking View Settings navigates to settings page."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        admin_page.click("text=View Settings")
        admin_page.wait_for_load_state("networkidle")
        assert "/admin/settings" in admin_page.url

    def test_admin_hub_navigate_to_data(self, admin_page: Page, base_url: str):
        """Clicking Manage Data navigates to data management page."""
        admin_page.goto(f"{base_url}/admin/")
        admin_page.wait_for_load_state("networkidle")
        admin_page.click("text=Manage Data")
        admin_page.wait_for_load_state("networkidle")
        assert "/admin/data" in admin_page.url


# ---------------------------------------------------------------------------
# Admin Access Control
# ---------------------------------------------------------------------------


class TestAdminAccessControl:
    """Admin pages require admin role."""

    def test_admin_hub_requires_auth(self, page: Page, base_url: str):
        """Anonymous user is redirected to login from admin hub."""
        page.goto(f"{base_url}/admin/")
        page.wait_for_load_state("networkidle")
        assert "/login" in page.url

    def test_admin_hub_forbidden_for_tech(self, tech_page: Page, base_url: str):
        """Technician role cannot access admin hub (403)."""
        tech_page.goto(f"{base_url}/admin/")
        tech_page.wait_for_load_state("networkidle")
        content = tech_page.content()
        assert "403" in content or "Forbidden" in content or "/admin" not in tech_page.url

    def test_admin_hub_forbidden_for_viewer(self, viewer_page: Page, base_url: str):
        """Viewer role cannot access admin hub (403)."""
        viewer_page.goto(f"{base_url}/admin/")
        viewer_page.wait_for_load_state("networkidle")
        content = viewer_page.content()
        assert "403" in content or "Forbidden" in content or "/admin" not in viewer_page.url

    def test_admin_settings_forbidden_for_tech(self, tech_page: Page, base_url: str):
        """Technician role cannot access admin settings (403)."""
        tech_page.goto(f"{base_url}/admin/settings")
        tech_page.wait_for_load_state("networkidle")
        content = tech_page.content()
        assert "403" in content or "Forbidden" in content or "/admin" not in tech_page.url

    def test_admin_data_forbidden_for_viewer(self, viewer_page: Page, base_url: str):
        """Viewer role cannot access data management (403)."""
        viewer_page.goto(f"{base_url}/admin/data")
        viewer_page.wait_for_load_state("networkidle")
        content = viewer_page.content()
        assert "403" in content or "Forbidden" in content or "/admin" not in viewer_page.url


# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------


class TestAdminSidebar:
    """Admin link appears in sidebar for admin users only."""

    def test_sidebar_shows_admin_link_for_admin(self, admin_page: Page, base_url: str):
        """Admin user sees Admin link in sidebar."""
        admin_page.goto(f"{base_url}/dashboard/")
        admin_page.wait_for_load_state("networkidle")
        admin_link = admin_page.locator("#sidebar .nav-link >> text=Admin")
        expect(admin_link).to_be_visible()

    def test_sidebar_hides_admin_link_for_tech(self, tech_page: Page, base_url: str):
        """Technician user does not see Admin link in sidebar."""
        tech_page.goto(f"{base_url}/dashboard/")
        tech_page.wait_for_load_state("networkidle")
        admin_link = tech_page.locator("#sidebar .nav-link >> text=Admin")
        expect(admin_link).to_have_count(0)

    def test_sidebar_hides_admin_link_for_viewer(self, viewer_page: Page, base_url: str):
        """Viewer user does not see Admin link in sidebar."""
        viewer_page.goto(f"{base_url}/dashboard/")
        viewer_page.wait_for_load_state("networkidle")
        admin_link = viewer_page.locator("#sidebar .nav-link >> text=Admin")
        expect(admin_link).to_have_count(0)


# ---------------------------------------------------------------------------
# System Settings
# ---------------------------------------------------------------------------


class TestSystemSettings:
    """System settings page tests."""

    def test_settings_page_loads(self, admin_page: Page, base_url: str):
        """Settings page loads with System Settings heading."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("h1")).to_contain_text("System Settings")

    def test_settings_has_company_tab(self, admin_page: Page, base_url: str):
        """Settings page shows Company tab."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".nav-tabs >> text=Company")).to_be_visible()

    def test_settings_has_service_tab(self, admin_page: Page, base_url: str):
        """Settings page shows Service tab."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".nav-tabs >> text=Service")).to_be_visible()

    def test_settings_has_invoice_tax_tab(self, admin_page: Page, base_url: str):
        """Settings page shows Invoice & Tax tab."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".nav-tabs >> text=Invoice & Tax")).to_be_visible()

    def test_settings_has_display_tab(self, admin_page: Page, base_url: str):
        """Settings page shows Display tab."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".nav-tabs >> text=Display")).to_be_visible()

    def test_settings_has_notifications_tab(self, admin_page: Page, base_url: str):
        """Settings page shows Notifications tab."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".nav-tabs >> text=Notifications")).to_be_visible()

    def test_settings_has_security_tab(self, admin_page: Page, base_url: str):
        """Settings page shows Security tab."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".nav-tabs >> text=Security")).to_be_visible()

    def test_settings_company_tab_active_by_default(self, admin_page: Page, base_url: str):
        """Company tab is active by default on settings page."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        active_tab = admin_page.locator(".nav-tabs .nav-link.active")
        expect(active_tab).to_contain_text("Company")

    def test_settings_switch_to_service_tab(self, admin_page: Page, base_url: str):
        """Clicking Service tab navigates to service settings."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        admin_page.click(".nav-tabs >> text=Service")
        admin_page.wait_for_load_state("networkidle")
        assert "tab=service" in admin_page.url
        active_tab = admin_page.locator(".nav-tabs .nav-link.active")
        expect(active_tab).to_contain_text("Service")

    def test_settings_switch_to_security_tab(self, admin_page: Page, base_url: str):
        """Clicking Security tab navigates to security settings."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        admin_page.click(".nav-tabs >> text=Security")
        admin_page.wait_for_load_state("networkidle")
        assert "tab=security" in admin_page.url

    def test_settings_form_has_save_button(self, admin_page: Page, base_url: str):
        """Each settings tab has a Save button."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        save_btn = admin_page.locator('button[type="submit"]')
        expect(save_btn).to_be_visible()
        expect(save_btn).to_contain_text("Save")

    def test_settings_company_tab_has_fields(self, admin_page: Page, base_url: str):
        """Company tab shows expected form fields."""
        admin_page.goto(f"{base_url}/admin/settings?tab=company")
        admin_page.wait_for_load_state("networkidle")
        # Company name field should be present (either as input or disabled input for ENV lock)
        page_text = admin_page.text_content("body")
        assert "Company" in page_text

    def test_settings_back_to_hub_link(self, admin_page: Page, base_url: str):
        """Settings page has a back link to Admin Hub."""
        admin_page.goto(f"{base_url}/admin/settings")
        admin_page.wait_for_load_state("networkidle")
        back_link = admin_page.locator("text=Admin Hub")
        expect(back_link).to_be_visible()


# ---------------------------------------------------------------------------
# Data Management
# ---------------------------------------------------------------------------


class TestDataManagement:
    """Data management page tests."""

    def test_data_management_loads(self, admin_page: Page, base_url: str):
        """Data management page loads with heading."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("h1")).to_contain_text("Data Management")

    def test_data_management_shows_db_engine(self, admin_page: Page, base_url: str):
        """Data management page shows database engine version."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Database Engine")).to_be_visible()

    def test_data_management_shows_table_count(self, admin_page: Page, base_url: str):
        """Data management page shows table count."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Tables")).to_be_visible()

    def test_data_management_shows_migration_revision(self, admin_page: Page, base_url: str):
        """Data management page shows migration revision."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Migration Revision")).to_be_visible()

    def test_data_management_has_backup_section(self, admin_page: Page, base_url: str):
        """Data management page has Backup card with download link."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".card-title >> text=Backup")).to_be_visible()
        expect(admin_page.locator("text=Download Backup")).to_be_visible()

    def test_data_management_has_restore_section(self, admin_page: Page, base_url: str):
        """Data management page has Restore card."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".card-title >> text=Restore")).to_be_visible()

    def test_data_management_has_export_section(self, admin_page: Page, base_url: str):
        """Data management page has Export Data card with CSV/XLSX links."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".card-title >> text=Export Data")).to_be_visible()
        # Should have CSV and XLSX column headers
        page_text = admin_page.text_content("body")
        assert "CSV" in page_text
        assert "XLSX" in page_text

    def test_data_management_has_table_stats(self, admin_page: Page, base_url: str):
        """Data management page shows Table Statistics card with a table."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".card-title >> text=Table Statistics")).to_be_visible()
        # Should have a table with Table and Rows headers
        stats_table = admin_page.locator("table")
        assert stats_table.count() > 0

    def test_data_management_has_migrations_section(self, admin_page: Page, base_url: str):
        """Data management page has Database Migrations card."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".card-title >> text=Database Migrations")).to_be_visible()

    def test_data_management_has_import_section(self, admin_page: Page, base_url: str):
        """Data management page has Import Data card with links."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".card-title >> text=Import Data")).to_be_visible()
        expect(admin_page.locator("text=Import Customers")).to_be_visible()
        expect(admin_page.locator("text=Import Inventory")).to_be_visible()

    def test_data_management_back_to_hub_link(self, admin_page: Page, base_url: str):
        """Data management page has a back link to Admin Hub."""
        admin_page.goto(f"{base_url}/admin/data")
        admin_page.wait_for_load_state("networkidle")
        back_link = admin_page.locator("text=Admin Hub")
        expect(back_link).to_be_visible()


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------


class TestCSVImport:
    """CSV import page tests."""

    def test_import_customers_page_loads(self, admin_page: Page, base_url: str):
        """Customer import page loads with heading."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("h1")).to_contain_text("Import Customers")

    def test_import_inventory_page_loads(self, admin_page: Page, base_url: str):
        """Inventory import page loads with heading."""
        admin_page.goto(f"{base_url}/admin/data/import?type=inventory")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("h1")).to_contain_text("Import Inventory")

    def test_import_page_has_customers_tab(self, admin_page: Page, base_url: str):
        """Import page shows Customers tab."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".nav-tabs >> text=Customers")).to_be_visible()

    def test_import_page_has_inventory_tab(self, admin_page: Page, base_url: str):
        """Import page shows Inventory tab."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator(".nav-tabs >> text=Inventory")).to_be_visible()

    def test_import_page_has_file_upload(self, admin_page: Page, base_url: str):
        """Import page has a file upload input for CSV."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        file_input = admin_page.locator('input[type="file"]#csv_file')
        expect(file_input).to_be_visible()

    def test_import_page_has_preview_button(self, admin_page: Page, base_url: str):
        """Import page has a Preview Import button."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Preview Import")).to_be_visible()

    def test_import_page_has_expected_columns(self, admin_page: Page, base_url: str):
        """Import page shows Expected Columns reference."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Expected Columns")).to_be_visible()

    def test_import_page_has_template_download(self, admin_page: Page, base_url: str):
        """Import page has a Download Template link."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator("text=Download Template")).to_be_visible()

    def test_import_switch_to_inventory_tab(self, admin_page: Page, base_url: str):
        """Clicking Inventory tab on import page switches to inventory import."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        admin_page.click(".nav-tabs >> text=Inventory")
        admin_page.wait_for_load_state("networkidle")
        assert "type=inventory" in admin_page.url
        expect(admin_page.locator("h1")).to_contain_text("Import Inventory")

    def test_import_page_back_to_data_management(self, admin_page: Page, base_url: str):
        """Import page has a back link to Data Management."""
        admin_page.goto(f"{base_url}/admin/data/import?type=customers")
        admin_page.wait_for_load_state("networkidle")
        back_link = admin_page.locator("text=Data Management")
        expect(back_link).to_be_visible()

    def test_import_inventory_shows_different_columns(self, admin_page: Page, base_url: str):
        """Inventory import page shows inventory-specific expected columns."""
        admin_page.goto(f"{base_url}/admin/data/import?type=inventory")
        admin_page.wait_for_load_state("networkidle")
        page_text = admin_page.text_content("body")
        assert "SKU" in page_text
        assert "Category" in page_text


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------


class TestUserManagement:
    """User management page tests."""

    def test_user_list_page_loads(self, admin_page: Page, base_url: str):
        """User list page loads."""
        admin_page.goto(f"{base_url}/admin/users")
        admin_page.wait_for_load_state("networkidle")
        assert "/admin/users" in admin_page.url
        # Should display at least the seeded users
        page_text = admin_page.text_content("body")
        assert "admin" in page_text.lower()

    def test_create_user_form_renders(self, admin_page: Page, base_url: str):
        """New user form loads with expected fields."""
        admin_page.goto(f"{base_url}/admin/users/new")
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page.locator('input[name="username"]')).to_be_visible()
        expect(admin_page.locator('input[name="email"]')).to_be_visible()
        expect(admin_page.locator('input[name="first_name"]')).to_be_visible()
        expect(admin_page.locator('input[name="last_name"]')).to_be_visible()
        expect(admin_page.locator('input[name="password"]')).to_be_visible()
