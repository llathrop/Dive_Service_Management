"""Data management service — database statistics, backup, migration status.

Provides functions for the Admin > Data Management page to display
live database information and trigger backup downloads.
"""

import subprocess

from flask import current_app
from sqlalchemy import text

from app.extensions import db


def get_table_stats():
    """Return row counts for all application tables.

    Returns a list of dicts: [{"table": "customers", "rows": 42}, ...]
    Sorted by table name.
    """
    dialect = db.engine.dialect.name

    if dialect == "sqlite":
        return _get_sqlite_table_stats()
    return _get_mysql_table_stats()


def _get_mysql_table_stats():
    """Get table stats from MariaDB/MySQL information_schema."""
    result = db.session.execute(
        text(
            "SELECT TABLE_NAME, TABLE_ROWS "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY TABLE_NAME"
        )
    )
    return [
        {"table": row[0], "rows": row[1] or 0}
        for row in result.fetchall()
    ]


def _get_sqlite_table_stats():
    """Get table stats from SQLite (count each table individually)."""
    # Get all table names
    result = db.session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    )
    tables = [row[0] for row in result.fetchall()]

    stats = []
    for table in tables:
        if table.startswith("sqlite_") or table == "alembic_version":
            continue
        count_result = db.session.execute(
            text(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608
        )
        count = count_result.scalar()
        stats.append({"table": table, "rows": count})
    return stats


def get_db_version():
    """Return the database server version string."""
    dialect = db.engine.dialect.name
    if dialect == "sqlite":
        result = db.session.execute(text("SELECT sqlite_version()"))
        return f"SQLite {result.scalar()}"
    result = db.session.execute(text("SELECT VERSION()"))
    return result.scalar()


def get_db_size():
    """Return the total database size as a human-readable string.

    Only works for MariaDB/MySQL. Returns None for SQLite.
    """
    dialect = db.engine.dialect.name
    if dialect == "sqlite":
        return None

    result = db.session.execute(
        text(
            "SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE()"
        )
    )
    size_mb = result.scalar()
    if size_mb is not None:
        return f"{size_mb} MB"
    return None


def get_migration_status():
    """Return the current Alembic migration revision.

    Returns a dict: {"current": "abc123...", "heads": [...]}
    """
    try:
        result = db.session.execute(
            text("SELECT version_num FROM alembic_version")
        )
        row = result.fetchone()
        current = row[0] if row else "No migrations applied"
    except Exception:
        current = "Unable to determine"

    return {"current": current}


def create_backup_sql():
    """Generate a SQL dump of the database.

    For MariaDB: runs mariadb-dump via subprocess.
    For SQLite: uses the .dump command via sqlite3.

    Returns the SQL dump as a string, or raises RuntimeError on failure.
    """
    dialect = db.engine.dialect.name

    if dialect == "sqlite":
        return _sqlite_dump()
    return _mysql_dump()


def _mysql_dump():
    """Run mariadb-dump and return the output."""
    db_url = current_app.config["SQLALCHEMY_DATABASE_URI"]
    # Parse connection info from URL: mysql+mysqldb://user:pass@host:port/dbname
    from urllib.parse import urlparse
    parsed = urlparse(db_url.replace("mysql+mysqldb://", "mysql://"))

    cmd = [
        "mariadb-dump",
        f"--host={parsed.hostname or 'localhost'}",
        f"--port={parsed.port or 3306}",
        f"--user={parsed.username or 'root'}",
        f"--password={parsed.password or ''}",
        parsed.path.lstrip("/"),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError(
            "mariadb-dump command not found. "
            "Backup is only available when running inside the Docker container."
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Backup failed: {e.stderr}")


def _sqlite_dump():
    """Dump SQLite database to SQL text."""
    import sqlite3
    db_path = db.engine.url.database
    if db_path == ":memory:" or db_path is None:
        # In-memory DB: use the connection directly
        conn = db.engine.raw_connection()
        lines = []
        for line in conn.iterdump():
            lines.append(line)
        return "\n".join(lines)

    conn = sqlite3.connect(db_path)
    lines = []
    for line in conn.iterdump():
        lines.append(line)
    conn.close()
    return "\n".join(lines)
