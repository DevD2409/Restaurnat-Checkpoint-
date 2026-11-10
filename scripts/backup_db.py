#!/usr/bin/env python3
"""
Database Backup Utility for Smart Restaurant Management Platform
Supports both SQLite (local development/pilot fallback) and PostgreSQL (production).
Generates timestamped backups, SHA-256 checksums, and metadata.
"""

import os
import sys
import shutil
import hashlib
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Add backend to path to import settings
sys.path.insert(0, str(BACKEND_DIR))
try:
    from app.core.config import settings
except ImportError:
    settings = None

def compute_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()

def backup_sqlite(db_path: Path) -> dict:
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found at {db_path}")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"smart_restaurant_backup_{timestamp}.db"
    backup_target = BACKUP_DIR / backup_filename

    # Copy with flush/integrity
    import sqlite3
    src_conn = sqlite3.connect(str(db_path))
    dst_conn = sqlite3.connect(str(backup_target))
    with dst_conn:
        src_conn.backup(dst_conn, pages=100)
    dst_conn.close()
    src_conn.close()

    checksum = compute_sha256(backup_target)
    size_bytes = backup_target.stat().st_size

    metadata = {
        "engine": "sqlite",
        "timestamp": timestamp,
        "backup_file": str(backup_target.name),
        "source_file": str(db_path.name),
        "size_bytes": size_bytes,
        "sha256": checksum,
        "status": "COMPLETED"
    }

    meta_file = BACKUP_DIR / f"smart_restaurant_backup_{timestamp}.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[SUCCESS] SQLite backup created: {backup_target}")
    print(f"          Size: {size_bytes} bytes | SHA256: {checksum[:12]}...")
    return metadata

def backup_postgres(database_url: str) -> dict:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"smart_restaurant_pg_{timestamp}.dump"
    backup_target = BACKUP_DIR / backup_filename

    cmd = ["pg_dump", "-Fc", "--no-owner", "--no-acl", "-d", database_url, "-f", str(backup_target)]
    print(f"[INFO] Executing PostgreSQL pg_dump to {backup_target}...")
    subprocess.run(cmd, check=True)

    checksum = compute_sha256(backup_target)
    size_bytes = backup_target.stat().st_size

    metadata = {
        "engine": "postgresql",
        "timestamp": timestamp,
        "backup_file": str(backup_target.name),
        "size_bytes": size_bytes,
        "sha256": checksum,
        "status": "COMPLETED"
    }

    meta_file = BACKUP_DIR / f"smart_restaurant_pg_{timestamp}.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[SUCCESS] PostgreSQL backup created: {backup_target}")
    return metadata

def main():
    print("==================================================")
    print("  SRMP DATABASE BACKUP UTILITY")
    print("==================================================")

    db_url = settings.DATABASE_URL if settings else "sqlite:///./smart_restaurant.db"

    if db_url.startswith("sqlite"):
        sqlite_file = db_url.replace("sqlite:///", "")
        db_path = Path(sqlite_file)
        if not db_path.is_absolute():
            db_path = (BACKEND_DIR / db_path).resolve()
        backup_sqlite(db_path)
    elif db_url.startswith("postgresql"):
        backup_postgres(db_url)
    else:
        print(f"[ERROR] Unsupported DATABASE_URL protocol: {db_url}")
        sys.exit(1)

if __name__ == "__main__":
    main()
