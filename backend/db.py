"""
db.py — Unified Resilient Database Access Layer for AIOps Sentinel
===================================================================
Supports:
  1. PostgreSQL (Primary production engine with psycopg2)
  2. SQLite (Automatic zero-config fallback if PostgreSQL is unconfigured)

Ensures zero crashes for local testing, evaluation, or offline demos.
All queries use safe parameterized queries to prevent SQL injection.
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("sentinel-db")

class DatabaseManager:
    def __init__(self):
        self.engine_type = "unknown"
        self._sqlite_path = Path("database/sentinel.db")
        self._init_connection()

    def _init_connection(self):
        force_sqlite = os.getenv("USE_SQLITE", "false").lower() in ("true", "1", "yes")
        if not force_sqlite:
            try:
                import psycopg2
                import psycopg2.extras
                conn = psycopg2.connect(
                    host=os.getenv("POSTGRES_HOST", "localhost"),
                    port=int(os.getenv("POSTGRES_PORT", 5432)),
                    dbname=os.getenv("POSTGRES_DB", "sentinel"),
                    user=os.getenv("POSTGRES_USER", "sentinel_user"),
                    password=os.getenv("POSTGRES_PASSWORD", "changeme_in_production"),
                    connect_timeout=2
                )
                conn.close()
                self.engine_type = "postgresql"
                logger.info("Database: Connected to PostgreSQL engine successfully.")
                self._run_migrations_postgres()
                return
            except Exception as e:
                logger.warning(
                    f"PostgreSQL connection unavailable ({e}). "
                    f"Falling back to local SQLite database at {self._sqlite_path}"
                )

        # Fallback to SQLite
        self.engine_type = "sqlite"
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._run_migrations_sqlite()
        logger.info(f"Database: Active engine is SQLite ({self._sqlite_path})")

    def _run_migrations_postgres(self):
        import psycopg2
        conn = self._get_raw_postgres()
        cur = conn.cursor()
        migration_dir = Path("database/migrations")
        if migration_dir.exists():
            for sql_file in sorted(migration_dir.glob("*.sql")):
                try:
                    cur.execute(sql_file.read_text())
                except Exception as ex:
                    logger.debug(f"Migration {sql_file.name} notice: {ex}")
        conn.commit()
        cur.close()
        conn.close()

    def _run_migrations_sqlite(self):
        conn = sqlite3.connect(str(self._sqlite_path))
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            cpu_percent REAL NOT NULL,
            memory_percent REAL NOT NULL,
            disk_io_bytes_sec REAL NOT NULL,
            network_bytes_sec REAL NOT NULL,
            request_latency_ms REAL NOT NULL,
            error_rate REAL NOT NULL,
            ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_host_obs ON metrics (host_id, observed_at);

        CREATE TABLE IF NOT EXISTS hosts (
            host_id TEXT PRIMARY KEY,
            hostname TEXT,
            registered_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_id TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            anomaly_score REAL NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            model_version TEXT,
            evidence TEXT,
            acknowledged_at TEXT,
            acknowledged_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_detected ON alerts (detected_at);

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            resolved_at TEXT,
            incident_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Ops Engineer',
            full_name TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_login TEXT
        );
        """)
        conn.commit()
        conn.close()
        self._seed_default_users_sqlite()

    def _get_raw_postgres(self):
        import psycopg2
        return psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "sentinel"),
            user=os.getenv("POSTGRES_USER", "sentinel_user"),
            password=os.getenv("POSTGRES_PASSWORD", "changeme_in_production")
        )

    def execute_query(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return list of dictionaries."""
        if self.engine_type == "postgresql":
            import psycopg2.extras
            conn = self._get_raw_postgres()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            finally:
                cur.close()
                conn.close()
        else:
            # SQLite query adaptation
            sql_query = query.replace("%s", "?")
            # Replace Postgres specific functions if any
            sql_query = sql_query.replace("NOW() - INTERVAL '5 minutes'", "datetime('now', '-5 minutes')")
            sql_query = sql_query.replace("date_trunc('minute', observed_at)", "strftime('%Y-%m-%d %H:%M:00', observed_at)")

            conn = sqlite3.connect(str(self._sqlite_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            try:
                cur.execute(sql_query, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            finally:
                cur.close()
                conn.close()

    def execute_insert(self, query: str, params: Tuple = ()) -> int:
        """Execute an INSERT query and return inserted ID."""
        if self.engine_type == "postgresql":
            conn = self._get_raw_postgres()
            cur = conn.cursor()
            try:
                # Ensure RETURNING id is present
                if "RETURNING id" not in query.upper():
                    query += " RETURNING id"
                cur.execute(query, params)
                inserted_id = cur.fetchone()[0]
                conn.commit()
                return inserted_id
            finally:
                cur.close()
                conn.close()
        else:
            # SQLite insertion: strip RETURNING clause and retrieve lastrowid
            import re
            clean_query = re.sub(r'(?i)\s*RETURNING\s+id\b', '', query).strip()
            clean_query = clean_query.replace("%s", "?")

            conn = sqlite3.connect(str(self._sqlite_path))
            cur = conn.cursor()
            try:
                cur.execute(clean_query, params)
                inserted_id = cur.lastrowid
                conn.commit()
                return int(inserted_id) if inserted_id else 1
            finally:
                cur.close()
                conn.close()

    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute UPDATE or DELETE query and return affected rows."""
        if self.engine_type == "postgresql":
            conn = self._get_raw_postgres()
            cur = conn.cursor()
            try:
                cur.execute(query, params)
                affected = cur.rowcount
                conn.commit()
                return affected
            finally:
                cur.close()
                conn.close()
        else:
            clean_query = query.replace("%s", "?")
            conn = sqlite3.connect(str(self._sqlite_path))
            cur = conn.cursor()
            try:
                cur.execute(clean_query, params)
                affected = cur.rowcount
                conn.commit()
                return affected
            finally:
                cur.close()
                conn.close()

    def upsert_host(self, host_id: str, hostname: str):
        if self.engine_type == "postgresql":
            query = """
            INSERT INTO hosts (host_id, hostname) VALUES (%s, %s)
            ON CONFLICT (host_id) DO UPDATE SET last_seen_at = NOW(), hostname = EXCLUDED.hostname;
            """
            self.execute_update(query, (host_id, hostname))
        else:
            query = """
            INSERT INTO hosts (host_id, hostname, last_seen_at) VALUES (?, ?, datetime('now'))
            ON CONFLICT(host_id) DO UPDATE SET last_seen_at = datetime('now'), hostname = excluded.hostname;
            """
            conn = sqlite3.connect(str(self._sqlite_path))
            cur = conn.cursor()
            cur.execute(query, (host_id, hostname))
            conn.commit()
            conn.close()

    @staticmethod
    def hash_password(password: str) -> str:
        import hashlib
        # Standard salted SHA-256 for secure local auth
        salt = "sentinel_auth_salt_v1"
        return hashlib.sha256((salt + password).encode()).hexdigest()

    def _seed_default_users_sqlite(self):
        try:
            conn = sqlite3.connect(str(self._sqlite_path))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]
            if count == 0:
                now = datetime.now(timezone.utc).isoformat()
                admin_hash = self.hash_password("sentinel2026")
                aksha_hash = self.hash_password("aksha2026")
                cur.execute("""
                    INSERT INTO users (username, email, password_hash, role, full_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("admin", "admin@sentinel.io", admin_hash, "Lead SRE / SecOps Admin", "System Administrator", now))
                cur.execute("""
                    INSERT INTO users (username, email, password_hash, role, full_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("aksha", "aksha@sentinel.io", aksha_hash, "Infrastructure Ops", "Aksha (Owner)", now))
                conn.commit()
                logger.info("Database: Seeded default user accounts (admin, aksha).")
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to seed users: {e}")

    def register_user(self, username: str, email: str, password: str, role: str = "Ops Engineer", full_name: str = "") -> Dict[str, Any]:
        """Register a new user account."""
        username = username.strip().lower()
        email = email.strip().lower()
        pwd_hash = self.hash_password(password)
        now = datetime.now(timezone.utc).isoformat()

        # Check existing
        existing = self.execute_query(
            "SELECT id FROM users WHERE username = %s OR email = %s",
            (username, email)
        )
        if existing:
            raise ValueError("Username or email already exists in system.")

        query = """
            INSERT INTO users (username, email, password_hash, role, full_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        inserted_id = self.execute_insert(query, (username, email, pwd_hash, role, full_name, now))
        return {
            "id": inserted_id,
            "username": username,
            "email": email,
            "role": role,
            "full_name": full_name or username.capitalize(),
            "created_at": now
        }

    def authenticate_user(self, username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
        """Validate credentials and return user dict without password hash."""
        login_id = username_or_email.strip().lower()
        pwd_hash = self.hash_password(password)

        query = """
            SELECT id, username, email, password_hash, role, full_name, created_at
            FROM users
            WHERE (username = %s OR email = %s)
        """
        rows = self.execute_query(query, (login_id, login_id))
        if not rows:
            return None

        user = rows[0]
        if user["password_hash"] != pwd_hash:
            return None

        # Update last login
        now = datetime.now(timezone.utc).isoformat()
        self.execute_update(
            "UPDATE users SET last_login = %s WHERE id = %s",
            (now, user["id"])
        )

        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "full_name": user.get("full_name") or user["username"].capitalize(),
            "created_at": user["created_at"],
            "last_login": now
        }

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        rows = self.execute_query(
            "SELECT id, username, email, role, full_name, created_at, last_login FROM users WHERE id = %s",
            (user_id,)
        )
        return rows[0] if rows else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        rows = self.execute_query(
            "SELECT id, username, email, role, full_name, created_at, last_login FROM users WHERE username = %s",
            (username.strip().lower(),)
        )
        return rows[0] if rows else None

db_manager = DatabaseManager()
