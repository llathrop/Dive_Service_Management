"""MariaDB parity tests.

These tests verify the application works correctly against MariaDB (the
production database engine), catching behavioral differences between SQLite
(used for fast unit tests) and MariaDB.  Tests in this package are skipped
when MariaDB is not available.
"""
