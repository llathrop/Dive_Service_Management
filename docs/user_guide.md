# User Guide

This guide walks through common tasks in Dive Service Management (DSM), organized by what you need to accomplish. It assumes the application is already installed and running.

## Table of Contents

- [Getting Started](#getting-started)
- [Customer Management](#customer-management)
- [Equipment (Service Items)](#equipment-service-items)
- [Service Orders](#service-orders)
- [Inventory Management](#inventory-management)
- [Invoicing and Billing](#invoicing-and-billing)
- [Reports](#reports)
- [Tools](#tools)
- [Notifications](#notifications)
- [Admin Tasks](#admin-tasks)

---

## Getting Started

### Logging In

1. Open your browser and navigate to the application URL (default: `http://localhost:8080`).
2. You will be redirected to the login page if not already authenticated.
3. Enter your email address and password, then click **Login**.
4. After successful login, you will land on the **Dashboard**.

If this is a fresh installation running in development mode, three demo accounts are available:

| Email | Password | Role |
|-------|----------|------|
| `admin@example.com` | `admin123` | Admin (full access) |
| `tech@example.com` | `tech123` | Technician (create/edit) |
| `viewer@example.com` | `viewer123` | Viewer (read-only) |

In production mode, demo users are not created. Your administrator will create your account and provide credentials.

### The Dashboard

The dashboard is your home screen after login. It displays four summary cards with live counts:

- **Open Orders** -- Number of service orders that are not yet picked up or cancelled
- **Awaiting Pickup** -- Orders with status "Ready for Pickup"
- **Low Stock Alerts** -- Inventory items at or below their reorder level
- **Overdue Invoices** -- Invoices past their due date that have not been paid, voided, or refunded

Click any card to navigate to the relevant list view.

### Navigation

The sidebar provides quick access to all sections:

- **Dashboard** -- Summary overview
- **Customers** -- Customer records
- **Items** -- Service items (equipment)
- **Orders** -- Service work orders
- **Inventory** -- Parts and consumables
- **Invoices** -- Billing and payments
- **Price List** -- Service pricing catalog
- **Reports** -- Data analysis and visualizations
- **Tools** -- Utility calculators
- **Notifications** -- In-app alerts
- **Search** -- Global search across all entities
- **Admin** (admin role only) -- Settings, users, data management

---

## Customer Management

### Adding a New Individual Customer

1. Navigate to **Customers** in the sidebar.
2. Click the **New Customer** button.
3. Select the **Individual** customer type (this is the default).
4. Fill in the required fields:
   - **First Name** and **Last Name** (both required for individuals)
   - **Email** (recommended for communication)
5. Optionally fill in phone numbers, address, preferred contact method, and notes.
6. Click **Save Customer**.
7. You will be redirected to the customer detail page.

### Adding a New Business Customer

1. Navigate to **Customers** > **New Customer**.
2. Select the **Business** customer type.
3. Fill in the **Business Name** (required for business customers).
4. Optionally add a **Contact Person**, email, phone, and address.
5. Click **Save Customer**.

### Quick-Creating a Customer from the Order Form

When creating a new service order, if the customer does not already exist:

1. On the **New Order** form, look for the quick-create customer option (modal or link near the customer dropdown).
2. Fill in the minimum required fields (name and optionally email/phone).
3. Save the new customer -- they will be automatically selected in the order form's customer dropdown.

This also works on mobile and touch devices. The quick-create dropdowns for customers, inventory items, price list categories, and tags are fully touch-compatible.

### Searching for Customers

- **From the customer list**: Use the search box at the top of the customer list page. Type a name, email, or phone number and the results will filter.
- **From global search**: Use the **Search** link in the sidebar to search across customers, equipment, and inventory simultaneously.

### Viewing Customer History

1. Navigate to a customer's detail page (click their name in the customer list).
2. The detail page shows:
   - Contact information and address
   - Service items (equipment) owned by this customer
   - **Open Orders** -- active service orders (intake through ready_for_pickup)
   - **Completed Orders** -- orders with picked_up or cancelled status
   - Invoice history
   - Tags applied to this customer
3. Use the **New Order** button on the customer detail page to create a service order pre-populated with this customer.

<!-- Screenshot: docs/screenshots/customer_detail.png -->

### Editing a Customer

1. Open the customer detail page.
2. Click the **Edit** button.
3. Modify any fields and click **Save Customer**.

### Deleting a Customer

Customers are soft-deleted, meaning the record is hidden but preserved:

1. Open the customer detail page.
2. Click **Delete** and confirm.
3. The customer will no longer appear in lists but can be restored if needed.

---

## Equipment (Service Items)

### Adding a New Service Item

1. Navigate to **Items** in the sidebar.
2. Click **New Item**.
3. Fill in:
   - **Name** (required) -- a descriptive name for the equipment
   - **Customer** (required) -- select the owner from the dropdown. Every item must belong to a customer. You can reassign an item to a different customer later by editing the item and changing the customer dropdown.
   - **Item Category** -- the type of equipment (e.g., Drysuit, BCD, Regulator)
   - **Serial Number** (optional but recommended)
   - **Brand** and **Model** (optional)
4. If the category is **Drysuit**, additional fields appear for drysuit-specific details:
   - Seal types and systems (neck, wrist)
   - Zipper type, length, and orientation
   - Valve details (inflate and dump)
   - Boot type and size
5. Click **Save Item**.

### Viewing Equipment History

The item detail page shows:

- Equipment specifications
- Owner information (with link to customer detail)
- Drysuit details (if applicable)
- **Service history** -- a list of all service orders that included this item, showing order number, status, date received, and assigned technician. This is derived from the `ServiceOrderItem` -> `ServiceOrder` relationship.
- File attachments associated with this item

<!-- Screenshot: docs/screenshots/item_detail_service_history.png -->

---

## Service Orders

### Creating a New Service Order

1. Navigate to **Orders** in the sidebar.
2. Click **New Order**.
3. Fill in the required fields:
   - **Customer** -- select from the dropdown (or quick-create a new customer)
   - **Date Received** -- defaults to today
   - **Priority** -- Low, Normal, High, or Rush
4. Optionally fill in:
   - **Assigned Technician** -- the tech responsible for the work
   - **Date Promised** -- expected completion date
   - **Description** -- overall description of the work needed
   - **Internal Notes** -- notes visible only to staff
   - **Estimated Total**, **Rush Fee**, **Discount**
5. Click **Save Order**.
6. The system generates an order number in the format `SO-YYYY-NNNNN` (e.g., SO-2026-00001).

### Adding Items to an Order

After creating the order:

1. On the order detail page, find the **Service Items** section.
2. Click **Add Item** to add a piece of customer equipment to this order.
3. Select the service item from the dropdown (these are items previously registered under the customer).
4. Optionally describe the work to be performed and the condition at receipt.
5. Click **Add**.

### Applying Services from the Price List

For each item on the order:

1. In the item's section, click **Add Service**.
2. Select a service from the **Price List** dropdown. The name, description, and price will auto-populate from the price list.
3. Adjust the quantity if needed.
4. If the price list item has linked parts with auto-deduction enabled, those parts will be automatically deducted from inventory when the service is applied.
5. Click **Save**.

### Adding Custom Charges

To add a charge not in the price list:

1. Click **Add Service** on the relevant order item.
2. Leave the price list item blank.
3. Enter a **Service Name**, **Description**, and **Unit Price** manually.
4. Click **Save**.

### Adding Parts Used

To record parts consumed during service (with automatic inventory deduction):

1. In the order item's section, click **Add Part**.
2. Select the inventory item from the dropdown.
3. Enter the **Quantity** used.
4. The unit price defaults to the item's resale price but can be overridden.
5. Click **Save**.
6. The quantity is deducted from inventory stock. If there is insufficient stock, the system will display an error.

### Recording Labor

1. In the order item's section, click **Add Labor**.
2. Select the **Technician** who performed the work.
3. Enter the **Hours** worked and the **Hourly Rate** (defaults from system settings).
4. Optionally add a description and work date.
5. Click **Save**.

### Writing Service Notes

1. In the order item's section, click **Add Note**.
2. Select the **Note Type**: General, Diagnostic, Repair, Testing, or Customer Communication.
3. Enter the note text.
4. Click **Save**.

Notes are timestamped and attributed to the logged-in user.

### Changing Order Status

Orders follow a defined workflow. The available status transitions are:

```
intake --> assessment --> awaiting_approval --> in_progress --> completed --> ready_for_pickup --> picked_up
                  \                                  |
                   \--> in_progress                  +--> awaiting_parts --> in_progress

cancelled can be reached from most statuses
cancelled --> intake (to reopen)
```

To change status:

1. On the order detail page, find the **Change Status** section.
2. Select the new status from the dropdown (only valid transitions are shown).
3. Click **Change Status**.

When an order moves to **Completed**, the completion date is automatically set. When it moves to **Picked Up**, the pickup date is set.

### Financial Summary

The order detail page shows a real-time financial summary:

- Applied services total
- Parts total (excludes auto-deducted parts that are included in service prices)
- Labor total
- Rush fee
- Discounts (percentage and fixed amount)
- Estimated total

---

## Inventory Management

### Adding a New Inventory Item

1. Navigate to **Inventory** in the sidebar.
2. Click **New Item**.
3. Fill in:
   - **Name** (required)
   - **Category** (required) -- e.g., Seals, Zippers, Adhesives, Valves
   - **SKU** (optional, must be unique)
   - **Quantity in Stock** -- current count
   - **Reorder Level** -- stock level that triggers low-stock alerts
   - **Purchase Cost** and **Resale Price**
   - **Manufacturer**, **Part Number**, **Supplier** details
   - **Unit of Measure** -- defaults to "each"
4. Click **Save**.

### Adjusting Stock Levels

To manually adjust stock (e.g., after a physical count or receiving a shipment):

1. Open the inventory item detail page.
2. Click **Edit**.
3. Update the **Quantity in Stock** field.
4. Click **Save**.

Stock is also automatically adjusted when parts are used on service orders (deducted) or when parts used records are removed (restored).

### Viewing Low-Stock Alerts

Items are flagged as low stock when their quantity is at or below the reorder level (and the reorder level is greater than zero).

- The **Dashboard** shows a count of low-stock items.
- The **Inventory** list can be filtered to show only low-stock items.
- The system generates **Notifications** for low-stock items on a periodic schedule.

---

## Invoicing and Billing

### Creating an Invoice from a Service Order

1. Navigate to the service order detail page.
2. Look for the **Generate Invoice** or **Create Invoice** action.
3. The system creates a draft invoice linked to the order, with line items automatically populated from the order's applied services, parts, and labor.
4. The invoice number is generated in the format `INV-YYYY-NNNNN`.

### Creating an Invoice Manually

1. Navigate to **Invoices** in the sidebar.
2. Click **New Invoice**.
3. Select the **Customer** and set the **Issue Date**.
4. Optionally link one or more service orders.
5. Click **Save**.
6. Add line items manually on the invoice detail page.

### Editing Invoice Line Items

1. On the invoice detail page, find the **Line Items** section.
2. Click **Add Line Item** to add a new charge.
3. Fill in:
   - **Line Type**: Service, Labor, Part, Fee, Discount, or Other
   - **Description**
   - **Quantity** and **Unit Price**
4. Click **Save**.
5. The invoice totals (subtotal, tax, total, balance due) are automatically recalculated.

### Recording Payments

1. On the invoice detail page, find the **Payments** section.
2. Click **Record Payment**.
3. Enter the **Amount**, **Payment Method** (cash, check, credit card, etc.), and optionally a **Reference Number**.
4. Click **Save**.
5. The balance due updates automatically. If the full amount is paid, the invoice status transitions to **Paid**.

### Invoice Status Workflow

```
draft --> sent --> viewed --> partially_paid --> paid --> refunded
                     |              |
                     v              v
                  overdue -------> paid
                     |
                     v
                   void
```

- **Draft**: Initial state. Can be edited freely.
- **Sent**: Invoice has been sent to the customer.
- **Viewed**: Customer has acknowledged or viewed the invoice.
- **Partially Paid**: Some payment received, balance remaining.
- **Paid**: Full payment received (terminal).
- **Overdue**: Past due date without full payment.
- **Void**: Cancelled invoice (terminal).
- **Refunded**: Payment returned (terminal).

### Searching Invoices

The invoice list page supports filtering by:

- Search text (matches invoice number)
- Status
- Date range (issue date)
- Sort by invoice number, status, issue date, due date, total, or balance due

---

## Reports

Navigate to **Reports** in the sidebar to access the reports hub. Available reports:

### Revenue Report

Shows revenue breakdown and trends over a selected date range:

- Total revenue by type (services, parts, labor, fees)
- Monthly revenue trend
- Filter by date range

### Service Orders Report

Provides statistics on service orders:

- Orders by status
- Orders by priority
- Turnaround time analysis
- Filter by date range

### Inventory Report

Analyzes current inventory state:

- Total items and total stock value
- Low-stock items list
- Items by category

### Customer Report

Customer activity analysis:

- Customer count and new customers in period
- Top customers by order count or revenue
- Filter by date range

### Accounts Receivable Aging Report

Shows outstanding invoice balances grouped by age:

- Current (not yet due)
- 1-30 days overdue
- 31-60 days overdue
- 61-90 days overdue
- 90+ days overdue

All reports with date filters accept a **Date From** and **Date To** range. Leave both blank to see all-time data.

---

## Tools

Navigate to **Tools** in the sidebar to access utility calculators. These are reference tools that run entirely in the browser -- they do not save data.

### Seal Size Calculator

Calculate the correct seal size for drysuit neck and wrist seals based on measurements.

### Material Estimator

Estimate material quantities needed for common drysuit repairs (adhesive amounts, patch sizes, etc.).

### Pricing Calculator

Quickly estimate service costs by selecting services and entering quantities. Useful for providing phone or counter estimates before creating a formal order.

### Leak Test Log

A structured form for documenting leak test procedures and results. Print or save the completed log.

### Valve Service Reference

A compatibility guide for common dive valve brands and models, including torque specifications and O-ring sizes.

### Unit Converter

Convert between common dive service measurements (metric/imperial, pressure units, etc.).

---

## Notifications

The notification system alerts you to important events. Access notifications from the **Notifications** link in the sidebar or the notification indicator in the header.

### Notification Types

- **Low Stock** / **Critical Stock** -- An inventory item is at or below its reorder level.
- **Overdue Invoice** -- An invoice has passed its due date.
- **Order Status Change** -- A service order's status has been updated.
- **Order Approaching Due** -- A service order is nearing its promised date.
- **Order Overdue** -- A service order has passed its promised date.
- **Order Assigned** -- A service order has been assigned to you.
- **Payment Received** -- A payment has been recorded on an invoice.
- **System** -- General system notifications.

### Severity Levels

- **Info** -- Informational, no action required.
- **Warning** -- Attention recommended.
- **Critical** -- Immediate action needed.

### Reading Notifications

- Click a notification to view its details. If it is linked to an entity (order, invoice, inventory item), you can navigate directly to that record.
- Mark notifications as read individually or use bulk actions.
- Broadcast notifications (sent to all users) track read status per user.

---

## Admin Tasks

The Admin section is accessible only to users with the **admin** role.

### User Management

1. Navigate to **Admin** > **Users**.
2. To create a new user, click **New User** and fill in:
   - **Username** and **Email** (both required, both unique)
   - **First Name** and **Last Name**
   - **Password** (minimum 8 characters)
   - **Roles** (select one or more: admin, technician, viewer)
3. Click **Create User**.
4. To edit an existing user, click their name in the list and modify their details.

### System Settings

1. Navigate to **Admin** > **Settings**.
2. Settings are organized into seven tabs:
   - **Company** -- Business name, address, phone, email, website, logo
   - **Service** -- Order number prefix, default labor rate, rush fee
   - **Invoice & Tax** -- Invoice number prefix, default terms, due days, footer text, tax rate, tax label
   - **Display** -- Date format, currency symbol/code, pagination size
   - **Notifications** -- Low stock check frequency, overdue check time, retention days, due date warning
   - **Email** -- Enable/disable email, SMTP server, port, TLS, credentials, sender address and name
   - **Security** -- Minimum password length, lockout attempts/duration, session lifetime
3. Some settings may show a lock icon and be read-only if they are controlled by environment variables.
4. Modify settings and click **Save** on each tab.

### Data Management

Navigate to **Admin** > **Data Management** to:

- View database table statistics (row counts per table)
- Check database version and size
- View migration status
- Download a SQL backup of the database

### CSV Import

1. Navigate to **Admin** > **Import**.
2. Select the entity type to import (Customers or Inventory).
3. Upload a CSV file.
4. The system parses and validates the data, showing a preview with any errors highlighted.
5. Review the preview and click **Confirm Import** to commit the records.

### XLSX Export

Use the **Export** feature (available from list views) to download data as Excel spreadsheets. Exports use the openpyxl library and include column headers and formatting.

### Audit Log

Navigate to **Admin** > **Audit Log** to review a chronological record of significant actions taken in the system, including who performed each action and when.
