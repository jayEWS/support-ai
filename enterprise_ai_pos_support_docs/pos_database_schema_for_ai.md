# POS Database Schema for AI Support Systems

This schema is designed to allow an AI support agent to query
operational data safely for diagnostics and troubleshooting.

------------------------------------------------------------------------

## Key Design Principles

1.  Read‑only access for AI
2.  Simplified views for AI queries
3.  Clear relationships between transactions, devices, and customers
4.  Log traceability

------------------------------------------------------------------------

## Core Tables

### outlets

outlet_id outlet_name location timezone pos_version

### pos_devices

device_id outlet_id device_type device_name status last_seen ip_address

device_type examples: - pos_terminal - printer - barcode_scanner -
payment_terminal

------------------------------------------------------------------------

### transactions

transaction_id outlet_id pos_device_id transaction_time total_amount
tax_amount payment_method status

status examples: - completed - pending - failed - void

------------------------------------------------------------------------

### vouchers

voucher_code campaign_id status expiry_date usage_limit usage_count

status examples: - active - expired - redeemed

------------------------------------------------------------------------

### memberships

membership_id customer_name points_balance tier created_at

------------------------------------------------------------------------

### inventory_items

item_id item_name category price status

status: - active - inactive

------------------------------------------------------------------------

### inventory_movements

movement_id item_id movement_type quantity reference created_at

movement_type: - sale - purchase - adjustment - return

------------------------------------------------------------------------

### system_logs

log_id device_id log_type log_message severity created_at

log_type examples: - pos - payment - sync - printer

severity examples: - info - warning - error

------------------------------------------------------------------------

## AI Query Views

Recommended read-only views:

ai_transactions_view ai_voucher_status_view ai_membership_view
ai_device_status_view ai_inventory_status_view

These simplify AI tool queries.
