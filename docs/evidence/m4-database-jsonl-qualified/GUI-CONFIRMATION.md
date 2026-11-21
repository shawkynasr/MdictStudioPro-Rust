# SQLite → JSONL confirmation

The user exported prefix-test.jsonl through the GUI and ran verify_database_jsonl.py against prefix-test.db. The reported status was passed: 8 records, 390 bytes, no dictionary metadata in JSONL, row digest 28b954eb69af2807d5f1901b98f71700cc1ce1c3a324b42fbca97f7fa368db2c, database source SHA-256 7d9a76e514ae9cd0e102d925572f7dd34c8227a439b9904b780302ce57bfa88a.

The actual attached JSONL was independently parsed in the delivery workspace and matched all eight known prefix fixture rows in order, including both apple definitions. The source database was not attached; its direct comparison is user-run evidence. No GUI screenshot or receipt was supplied for this operation. The native parent report is scoped to package version 151; this evidence does not qualify the later JSONL import feature.
