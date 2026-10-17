#!/usr/bin/env python3
"""Explicit local PostgreSQL backup/restore. No automatic overwrite or password output."""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy.engine import make_url
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import get_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("path", nargs="?")
    parser.add_argument("--confirm-replace", action="store_true", help="Explicitly authorize replacing the configured DB from this backup")
    args = parser.parse_args()
    settings = get_settings()
    url = make_url(settings.sqlalchemy_url)
    if url.get_backend_name() != "postgresql":
        parser.error("Only the configured PostgreSQL database is supported")
    tool = "pg_dump" if args.action == "backup" else "pg_restore"
    environment = os.environ.copy()
    # Password is passed only through the subprocess environment, never an argv or log.
    environment.update(PGHOST=url.host or "127.0.0.1", PGPORT=str(url.port or 5432),
                       PGUSER=url.username or "", PGPASSWORD=url.password or "", PGDATABASE=url.database or "")
    for key in ("sslmode", "sslrootcert", "sslcert", "sslkey"):
        if key in url.query:
            environment["PG" + key.upper()] = str(url.query[key])
    if os.environ.get("DEMO_DB_CLIENT") == "compose":
        if settings.database_url or settings.postgres_host not in ("localhost", "127.0.0.1"):
            parser.error("Compose client requires the project's local POSTGRES_* database configuration")
        if not shutil.which("docker"):
            parser.error("docker unavailable; use installed PostgreSQL clients")
        command = ["docker", "compose", "exec", "-T", "postgres", tool, "--username", settings.postgres_user, "--dbname", settings.postgres_db]
    else:
        if not shutil.which(tool):
            parser.error(f"{tool} unavailable. Install matching PostgreSQL client tools before offline use, or explicitly set DEMO_DB_CLIENT=compose for the project container")
        command = [tool]
    if args.action == "backup":
        path = Path(args.path) if args.path else ROOT / "backups" / f"demo-{datetime.now():%Y%m%d-%H%M%S}.dump"
        if path.exists():
            parser.error("Backup path already exists; refusing to overwrite")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as output:
                subprocess.run(command + ["--format=custom", "--no-owner", "--no-acl"], env=environment, cwd=ROOT, stdout=output, check=True)
        except subprocess.CalledProcessError:
            path.unlink(missing_ok=True)
            print("Backup failed; partial output removed.", file=sys.stderr)
            return 1
        print(f"Backup created: {path.resolve()}")
    else:
        if not args.path or not Path(args.path).is_file():
            parser.error("Supply an existing custom-format backup file")
        path = Path(args.path)
        with path.open("rb") as handle:
            if handle.read(5) != b"PGDMP":
                parser.error("Expected a PostgreSQL custom-format backup")
        print(f"Restore target: database {url.database!r} on {url.host or '127.0.0.1'}:{url.port or 5432}. Stop demo services and back up current data first.")
        if not args.confirm_replace:
            if not sys.stdin.isatty():
                parser.error("Refusing unattended overwrite. Explicit --confirm-replace is required")
            answer = input(f"This replaces existing objects/history. Type database name {url.database!r} to confirm: ")
            if answer != url.database:
                print("Restore cancelled; database unchanged.")
                return 1
        with path.open("rb") as source:
            subprocess.run(command + ["--clean", "--if-exists", "--single-transaction", "--no-owner", "--no-acl"],
                           env=environment, cwd=ROOT, stdin=source, check=True)
        print("Restore complete. Run ./prepare-demo.sh before starting the demo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
