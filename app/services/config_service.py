"""Configuration service layer — read/write database-stored settings.

Provides ``get_config()`` and ``set_config()`` for typed access to the
``system_config`` table, with automatic environment variable override
detection.  When an ENV var controls a setting, the DB value is ignored
and the setting is treated as read-only in the admin UI.

ENV override mapping
--------------------
Some system_config keys map to environment variables.  If the ENV var is
set, it takes precedence and the setting cannot be changed via the UI.
The mapping is defined in ``ENV_OVERRIDES``.
"""

import os
from typing import Any

from app.extensions import db
from app.models.system_config import SystemConfig, _coerce_value


# Maps config_key -> environment variable name.
# When the ENV var is set, the DB value is ignored.
ENV_OVERRIDES: dict[str, str] = {
    "company.name": "DSM_COMPANY_NAME",
    "display.pagination_size": "DSM_PAGINATION_SIZE",
    "security.password_min_length": "DSM_PASSWORD_MIN_LENGTH",
    "security.session_lifetime_hours": "DSM_SESSION_LIFETIME_HOURS",
    "email.smtp_server": "DSM_MAIL_SERVER",
    "email.smtp_port": "DSM_MAIL_PORT",
    "email.smtp_use_tls": "DSM_MAIL_USE_TLS",
    "email.smtp_username": "DSM_MAIL_USERNAME",
    "email.smtp_password": "DSM_MAIL_PASSWORD",
    "email.from_address": "DSM_MAIL_DEFAULT_SENDER",
}


# =========================================================================
# Read
# =========================================================================

def get_config(key: str, default: Any = None) -> Any:
    """Return the typed value for *key*.

    Resolution order:
    1. Environment variable (if mapped in ENV_OVERRIDES and set)
    2. Database ``system_config`` row
    3. *default*
    """
    # 1. ENV override
    env_var = ENV_OVERRIDES.get(key)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val is not None:
            # Determine config_type from the DB row if it exists
            row = SystemConfig.query.filter_by(config_key=key).first()
            config_type = row.config_type if row else "string"
            return _coerce_value(env_val, config_type)

    # 2. Database
    row = SystemConfig.query.filter_by(config_key=key).first()
    if row is not None:
        return row.typed_value

    # 3. Default
    return default


def get_all_in_category(category: str) -> list[SystemConfig]:
    """Return all SystemConfig rows for a given category, ordered by key."""
    return (
        SystemConfig.query
        .filter_by(category=category)
        .order_by(SystemConfig.config_key)
        .all()
    )


def is_env_locked(key: str) -> bool:
    """Return True if *key* is controlled by an environment variable."""
    env_var = ENV_OVERRIDES.get(key)
    if not env_var:
        return False
    return os.environ.get(env_var) is not None


# =========================================================================
# Write
# =========================================================================

def set_config(key: str, value: Any, user_id: int | None = None) -> SystemConfig:
    """Set a config value in the database.

    Raises ``ValueError`` if the key is ENV-locked.

    Returns the updated (or newly created) SystemConfig row.
    """
    if is_env_locked(key):
        raise ValueError(
            f"Config key '{key}' is locked by environment variable "
            f"'{ENV_OVERRIDES[key]}'. Change the ENV var instead."
        )

    row = SystemConfig.query.filter_by(config_key=key).first()
    if row is None:
        raise KeyError(f"Config key '{key}' does not exist.")

    row.typed_value = value
    row.updated_by = user_id
    db.session.commit()
    return row


def bulk_set(updates: dict[str, Any], user_id: int | None = None) -> int:
    """Set multiple config values at once.

    *updates* maps config_key -> new value.  ENV-locked keys are silently
    skipped.  Returns the number of keys actually updated.
    """
    count = 0
    for key, value in updates.items():
        if is_env_locked(key):
            continue
        row = SystemConfig.query.filter_by(config_key=key).first()
        if row is None:
            continue
        row.typed_value = value
        row.updated_by = user_id
        count += 1
    if count:
        db.session.commit()
    return count
