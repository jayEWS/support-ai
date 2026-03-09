# Knowledge Base Schema for AI POS Support

A structured knowledge base is critical for reliable AI troubleshooting.

Each issue must be represented as a structured record.

------------------------------------------------------------------------

## Schema

problem_id problem_name category priority affected_system

symptoms root_causes diagnostic_steps fix_steps automation_tools
verification_steps

------------------------------------------------------------------------

## Example Entry

problem_id: POS_SYNC_001

problem_name: POS cannot sync transactions

category: synchronization

priority: high

affected_system: - POS terminal - backend API

symptoms: - sales missing in backend - sync pending status

root_causes: - internet connection failure - outdated POS version -
backend API unavailable

diagnostic_steps: 1 check internet connectivity 2 check API status 3
check last sync log 4 verify POS version

fix_steps: 1 reconnect network 2 restart POS 3 update POS application 4
retry sync

automation_tools: - network_check - api_status_check - log_analysis

verification_steps: 1 confirm sync completed 2 verify sales visible in
backend
