#!/usr/bin/env python3
"""Generate a cryptographically secure secret key for Flask.

Usage:
    python scripts/generate_secret_key.py
"""

import secrets


def main():
    """Print a 64-character hex secret key to stdout."""
    print(secrets.token_hex(32))


if __name__ == "__main__":
    main()
