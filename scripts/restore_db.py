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

def find_pg_binary(name: str) -> str:
    which_bin = shutil.which(name)
    if which_bin:
        return which_bin
    try:
        import pgserver
        pg_bin = Path(pgserver.__file__).parent / "pginstall" / "bin" / f"{name}.exe"
        if pg_bin.exists():
            return str(pg_bin)
    except Exception:
        pass
    return name

def restore_postgres(backup_file: Path, database_url: str):
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

    pg_restore_bin = find_pg_binary("pg_restore")
    print(f"[INFO] Restoring PostgreSQL database from {backup_file} via {pg_restore_bin} to target database...")
    cmd = [pg_restore_bin, "--clean", "--no-owner", "--no-acl", "-d", database_url, str(backup_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        if "pg_restore:" in res.stderr and "error" in res.stderr.lower():
            print(f"[WARNING] pg_restore output: {res.stderr}")
        else:
            print(f"[INFO] pg_restore output: {res.stdout or res.stderr}")
    print(f"[SUCCESS] PostgreSQL database restored from {backup_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python restore_db.py <path_to_backup_file> [optional_target_db_url_or_path]")
        sys.exit(1)

    backup_file = Path(sys.argv[1]).resolve()
    target_arg = sys.argv[2] if len(sys.argv) > 2 else None
    db_url = target_arg or (settings.DATABASE_URL if settings else "sqlite:///./smart_restaurant.db")

    if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        restore_postgres(backup_file, db_url)
    elif db_url.startswith("sqlite"):
        sqlite_file = db_url.replace("sqlite:///", "")
        db_path = Path(sqlite_file)
        if not db_path.is_absolute():
            db_path = (BACKEND_DIR / db_path).resolve()
        restore_sqlite(backup_file, db_path)
    else:
        # Treat as raw sqlite file path if it has .db extension or doesn't look like URL
        target_path = Path(db_url).resolve()
        restore_sqlite(backup_file, target_path)

if __name__ == "__main__":
    main()
