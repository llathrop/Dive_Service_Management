# Technical Issue: System-Wide Dropdown Extensibility (Quick-Create)

**Status:** Proposed / Open
**Priority:** High
**Scope:** Application-Wide (Dive Service Management)

## 1. Problem Statement
Many dropdowns (SelectFields) in the application currently rely on hardcoded choices in the Python form definitions (e.g., `Material Type`, `Wrist Seal Type`, `Boot Type`). Users frequently encounter new equipment types or materials that are not in the predefined list, forcing them to either choose an incorrect option or request a code update.

## 2. Objective
Implement a universal "Quick-Create" pattern for all managed dropdowns. Any SelectField representing a list of types, brands, or categories should allow the user to add a new option directly from the page where the dropdown is used, without a page reload.

## 3. Technical Requirements

### 3.1 Model Layer Refactoring
Currently, fields like `drysuit_details.material_type` are simple `db.String` columns. To support extensibility:
*   **Lookup Table:** Implement a generic `LookupValue` model or dedicated tables (e.g., `MaterialType`, `SealType`) to store user-defined options.
*   **Foreign Keys:** Transition `db.String` columns in models (like `DrysuitDetails`, `ServiceItem`, etc.) to `db.ForeignKey` references to these lookup tables.
*   **Seeding:** Move existing hardcoded choices from `forms/item.py` into a database migration/seed script.

### 3.2 Backend Implementation
*   **Generic Quick-Create API:** Create a centralized endpoint (e.g., `/api/lookup/create`) that accepts:
    - `type`: The category/table of the lookup (e.g., 'material_type').
    - `name`: The value to add.
*   **Service Layer Integration:** Update `item_service.py` and other relevant services to handle the validation and persistence of these new lookup values.

### 3.3 Frontend & UI Macros
*   **Macro Update:** Refactor `app/templates/macros/forms.html`'s `render_select` macro.
    - Add an optional `allow_quick_create` boolean parameter.
    - If true, render a small "plus" button (+) next to the dropdown.
    - Integrate with a generic Modal or Popover for inputting the new value.
*   **Javascript Handler:** Implement a global Alpine.js or Vanilla JS handler that:
    1.  Opens the "Add New" modal.
    2.  Submits the new value to the API.
    3.  Appends the new `<option>` to the select element.
    4.  Automatically selects the newly created item.

## 4. Specific Target Areas
While this is a universal requirement, the following areas are high priority:
*   **Drysuit Details:** Material Type, Neck/Wrist Seal Type, Suit Entry Type, Zipper Type, Dump Valve Type, Boot Type.
*   **Service Items:** Brand, Model, Item Category (if not restricted).
*   **Inventory:** Locations, Categories.
*   **Price List:** Categories, Service Types.

## 5. Reference Implementation
Refer to the existing `orders.quick_create_customer` and the `test_items_quick_create.py` test suite for the established pattern of returning JSON `id` and `display_text` to update the DOM dynamically.

## 6. Definition of Done
- [ ] All hardcoded choices for managed fields are migrated to database tables.
- [ ] The `render_select` macro supports a universal "Add New" UI.
- [ ] Users can add a new "Material Type" from the Item Form and have it immediately available.
- [ ] Comprehensive tests are added for the generic lookup creation API.
- [ ] No regressions in existing forms.
