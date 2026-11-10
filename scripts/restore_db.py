#!/usr/bin/env python3
"""
Database Restore Utility for Smart Restaurant Management Platform
Safely validates and restores SQLite or PostgreSQL database backups.
"""

import os
import sys
import shutil
import hashlib
import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
BACKUP_DIR = BASE_DIR / "backups"

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

def restore_sqlite(backup_file: Path, db_target: Path):
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file does not exist: {backup_file}")

    # Verify checksum if metadata json exists
    meta_file = backup_file.with_suffix(".json")
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
            expected_sha = meta.get("sha256")
            actual_sha = compute_sha256(backup_file)
            if expected_sha and actual_sha != expected_sha:
                raise ValueError(f"Checksum mismatch! Expected {expected_sha}, got {actual_sha}")
            print(f"[VERIFIED] SHA-256 checksum matched: {actual_sha[:12]}...")

    # Create safety backup of current target before overwriting
    if db_target.exists():
        safety_copy = db_target.with_suffix(f".pre_restore_bak")
        shutil.copy2(db_target, safety_copy)
        print(f"[SAFETY] Existing database preserved at {safety_copy}")

    import sqlite3
    src_conn = sqlite3.connect(str(backup_file))
    dst_conn = sqlite3.connect(str(db_target))
    with dst_conn:
        src_conn.backup(dst_conn, pages=100)
    dst_conn.close()
    src_conn.close()

    print(f"[SUCCESS] Database successfully restored from {backup_file} -> {db_target}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python restore_db.py <path_to_backup_file>")
        sys.exit(1)

    backup_file = Path(sys.argv[1]).resolve()
    db_url = settings.DATABASE_URL if settings else "sqlite:///./smart_restaurant.db"

    if db_url.startswith("sqlite"):
        sqlite_file = db_url.replace("sqlite:///", "")
        db_path = Path(sqlite_file)
        if not db_path.is_absolute():
            db_path = (BACKEND_DIR / db_path).resolve()
        restore_sqlite(backup_file, db_path)
    else:
        print("[INFO] PostgreSQL restore requires pg_restore command")

if __name__ == "__main__":
    main()
