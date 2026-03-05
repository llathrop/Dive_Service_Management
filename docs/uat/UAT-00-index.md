# Dive Service Management - User Acceptance Testing (UAT) Master Index

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Application**    | Dive Service Management                    |
| **Version**        | 1.0                                        |
| **Date Created**   | 2026-03-04                                 |
| **Total Scripts**  | 10                                         |
| **Total Estimated Time** | ~3 hours                             |
| **Application URL** | http://localhost:8080                     |

---

## Overview

This document serves as the master index for all User Acceptance Testing (UAT) scripts for the Dive Service Management application. Each script contains step-by-step instructions for a human tester to validate a specific feature area. Scripts should be executed in order, as later scripts depend on data created by earlier ones.

---

## Demo Test Accounts

| Role    | Email                    | Password   | Access Level                              |
|---------|--------------------------|------------|-------------------------------------------|
| Admin   | admin@example.com        | admin123   | Full access to all features               |
| Tech    | tech@example.com         | tech123    | Standard access, no Admin section         |
| Viewer  | viewer@example.com       | viewer123  | Read-only access, no create/edit actions  |

---

## UAT Scripts

| #  | Script | Feature | Est. Time | Prerequisites | Link |
|----|--------|---------|-----------|---------------|------|
| 01 | UAT-01 | Authentication & Authorization | 15 min | Application running | [UAT-01-authentication.md](UAT-01-authentication.md) |
| 02 | UAT-02 | Customer Management | 20 min | UAT-01 | [UAT-02-customers.md](UAT-02-customers.md) |
| 03 | UAT-03 | Service Items | 20 min | UAT-01, UAT-02 | [UAT-03-service-items.md](UAT-03-service-items.md) |
| 04 | UAT-04 | Inventory Management | 20 min | UAT-01 | [UAT-04-inventory.md](UAT-04-inventory.md) |
| 05 | UAT-05 | Price List | 15 min | UAT-01 | [UAT-05-price-list.md](UAT-05-price-list.md) |
| 06 | UAT-06 | Service Orders | 25 min | UAT-01, UAT-02, UAT-03 | [UAT-06-service-orders.md](UAT-06-service-orders.md) |
| 07 | UAT-07 | Invoices & Billing | 25 min | UAT-01, UAT-02, UAT-06 | [UAT-07-invoices.md](UAT-07-invoices.md) |
| 08 | UAT-08 | Reports | 20 min | UAT-01 (recommended: UAT-02 through UAT-07 for data) | [UAT-08-reports.md](UAT-08-reports.md) |
| 09 | UAT-09 | Tools & Calculators | 20 min | UAT-01 | [UAT-09-tools.md](UAT-09-tools.md) |
| 10 | UAT-10 | Notifications | 15 min | UAT-01 (recommended: UAT-07 for payment notifications) | [UAT-10-notifications.md](UAT-10-notifications.md) |

---

## Execution Order & Dependencies

The following diagram shows the recommended execution order. Scripts connected by arrows indicate that the later script depends on data created by the earlier one.

```
UAT-01 (Authentication)
  |
  +---> UAT-02 (Customers)
  |       |
  |       +---> UAT-03 (Service Items)
  |       |       |
  |       |       +---> UAT-06 (Service Orders)
  |       |               |
  |       +---------------+---> UAT-07 (Invoices & Billing)
  |                               |
  +---> UAT-04 (Inventory)        |
  |                               |
  +---> UAT-05 (Price List)       |
  |                               |
  +---> UAT-08 (Reports) <-------+ (recommended: run after UAT-02 through UAT-07)
  |
  +---> UAT-09 (Tools & Calculators)
  |
  +---> UAT-10 (Notifications) <--- (recommended: run after UAT-07)
```

**Recommended full execution order:**
1. UAT-01 -- Authentication
2. UAT-02 -- Customers
3. UAT-03 -- Service Items
4. UAT-04 -- Inventory
5. UAT-05 -- Price List
6. UAT-06 -- Service Orders
7. UAT-07 -- Invoices & Billing
8. UAT-08 -- Reports
9. UAT-09 -- Tools & Calculators
10. UAT-10 -- Notifications

---

## Before You Begin

### Environment Setup

1. Ensure the Dive Service Management application is running at **http://localhost:8080**.
2. Ensure the database has been seeded with demo data (demo accounts, price list categories, etc.).
3. Use a modern browser (Chrome, Firefox, or Edge recommended).
4. Clear browser cache and cookies before starting for a clean test.

### Test Data

The UAT scripts create test data in a specific order. If you need to re-run a script, be aware that:
- **UAT-02** creates customer "John Diver" used by UAT-03, UAT-06, and UAT-07.
- **UAT-03** creates service items associated with "John Diver" used by UAT-06.
- **UAT-06** creates service orders used by UAT-07.
- If re-running later scripts, ensure the prerequisite data still exists.

---

## How to Use These Scripts

Each UAT script follows a consistent format:

1. **Header table** -- Script metadata, estimated time, prerequisites, and test account.
2. **Objective** -- What the script validates.
3. **Test Steps** -- Numbered, detailed steps organized into test cases (TC-XX.X).
   - Each step describes exactly what to do and what to expect.
   - Screenshots are embedded where available to show expected state.
   - **Pass/Fail checkboxes** (`- [ ]`) should be checked off as you complete each step.
4. **Test Summary table** -- Quick overview of all test cases with Pass/Fail columns.
5. **Notes section** -- Space for tester comments, issues, and observations.
6. **Sign-off** -- Tester name, date, and overall result.

### Recording Results

- Check the `- [ ]` checkbox next to each step that passes (change to `- [x]`).
- For any failed step, leave the checkbox unchecked and add a comment in the Notes section describing the failure.
- Fill in the Test Summary table at the bottom of each script.
- Sign and date each script when complete.

---

## Overall UAT Sign-Off

| Script   | Feature                      | Tester | Date | Result |
|----------|------------------------------|--------|------|--------|
| UAT-01   | Authentication               |        |      |        |
| UAT-02   | Customer Management          |        |      |        |
| UAT-03   | Service Items                |        |      |        |
| UAT-04   | Inventory Management         |        |      |        |
| UAT-05   | Price List                   |        |      |        |
| UAT-06   | Service Orders               |        |      |        |
| UAT-07   | Invoices & Billing           |        |      |        |
| UAT-08   | Reports                      |        |      |        |
| UAT-09   | Tools & Calculators          |        |      |        |
| UAT-10   | Notifications                |        |      |        |

**Overall UAT Result:** PASS / FAIL

**Approved By:** ____________________
**Date:** ____________________

---

## Screenshots Reference

All screenshots are located in the `screenshots/` subdirectory relative to these UAT scripts. The following screenshots are available:

| File | Description |
|------|-------------|
| `screenshots/01-login-page.png` | Login page with email/password form |
| `screenshots/02-dashboard.png` | Dashboard after successful login |
| `screenshots/03-customers-list.png` | Customer list page |
| `screenshots/04-customer-form.png` | Empty customer creation form |
| `screenshots/05-orders-list.png` | Service orders list page |
| `screenshots/06-order-form.png` | Empty order creation form |
| `screenshots/07-inventory-list.png` | Inventory list page |
| `screenshots/08-inventory-form.png` | Empty inventory item form |
| `screenshots/09-price-list.png` | Price list page |
| `screenshots/10-price-list-form.png` | Price list item form |
| `screenshots/11-invoices-list.png` | Invoices list page |
| `screenshots/12-reports-hub.png` | Reports hub with 5 report cards |
| `screenshots/13-revenue-report.png` | Revenue report with date filters |
| `screenshots/14-tools-hub.png` | Tools hub with 6 tool cards |
| `screenshots/15-seal-calculator.png` | Seal calculator tool |
| `screenshots/16-notifications.png` | Notifications list page |
| `screenshots/17-customer-form-filled.png` | Customer form with test data |
| `screenshots/18-customer-created.png` | Customer detail after creation |
| `screenshots/19-item-form-filled.png` | Service item form with test data |
| `screenshots/20-item-created.png` | Service item detail after creation |
| `screenshots/21-inventory-form-filled.png` | Inventory form with test data |
| `screenshots/22-inventory-created.png` | Inventory item detail after creation |
| `screenshots/23-order-form-filled.png` | Order form with test data |
| `screenshots/24-order-created.png` | Order detail after creation |
| `screenshots/25-order-add-item.png` | Adding service item to an order |
| `screenshots/26-price-list-categories.png` | Price list categories page |
| `screenshots/27-pricing-calculator.png` | Pricing calculator tool |
| `screenshots/28-unit-converter.png` | Unit converter tool |
