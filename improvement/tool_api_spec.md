# AI Support Tool API Specification

AI tools allow the model to query internal systems.

------------------------------------------------------------------------

## Tool: Database Query

Endpoint: /api/ai/db_query

Parameters: - table - filters

Example:

{ "table": "transactions", "filters": { "ref_no": "OR123456" } }

------------------------------------------------------------------------

## Tool: Voucher Check

Endpoint: /api/ai/check_voucher

Parameters: - voucher_code

Response: - status - expiry_date - usage_count

------------------------------------------------------------------------

## Tool: POS Device Diagnostics

Endpoint: /api/ai/device_check

Parameters: - device_id - device_type

Example types: - printer - scanner - terminal

------------------------------------------------------------------------

## Tool: Log Analyzer

Endpoint: /api/ai/log_search

Parameters: - device_id - log_type - time_range
