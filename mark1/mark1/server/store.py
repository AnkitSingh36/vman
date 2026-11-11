"""Single-node SQLite storage. Human commands and their effects share a transaction."""
from contextlib import contextmanager, closing
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from .contracts import canonical
from .errors import APIError


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def opaque():
    return uuid4().hex


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS principals (
 token_hash TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL,
 agent TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS grants (
 tenant TEXT NOT NULL, subject TEXT NOT NULL, resource TEXT NOT NULL,
 allowed INTEGER NOT NULL, PRIMARY KEY(tenant,subject,resource));
CREATE TABLE IF NOT EXISTS policies (
 tenant TEXT NOT NULL, workflow TEXT NOT NULL, state TEXT NOT NULL,
 PRIMARY KEY(tenant,workflow));
CREATE TABLE IF NOT EXISTS catalogs (
 version TEXT PRIMARY KEY, payload TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS resources (
 key TEXT PRIMARY KEY, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS catalog_records (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_hashes (key TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS authority_events (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, action TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commands (
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL, session_id TEXT NOT NULL,
 operation TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,
 record_id TEXT NOT NULL, image_result TEXT,
 UNIQUE(tenant,actor,session_id,operation,key));
CREATE TABLE IF NOT EXISTS events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
 session_id TEXT NOT NULL REFERENCES sessions(id), event_type TEXT NOT NULL,
 created_at TEXT NOT NULL, data TEXT NOT NULL, sources TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS images (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 sha256 TEXT NOT NULL, mime_type TEXT NOT NULL, data BLOB NOT NULL, purpose TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inferences (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 revision INTEGER NOT NULL, request TEXT NOT NULL, state TEXT NOT NULL,
 created_at TEXT NOT NULL, finished_at TEXT, reason TEXT);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
 BEGIN SELECT RAISE(ABORT, 'immutable event'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
 BEGIN SELECT RAISE(ABORT, 'immutable event'); END;
CREATE TRIGGER IF NOT EXISTS authority_no_update BEFORE UPDATE ON authority_events
 BEGIN SELECT RAISE(ABORT, 'immutable authority event'); END;
CREATE TRIGGER IF NOT EXISTS authority_no_delete BEFORE DELETE ON authority_events
 BEGIN SELECT RAISE(ABORT, 'immutable authority event'); END;
"""


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version','1')")
            if db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] != "1":
                raise ValueError("Unsupported database schema; restore a compatible backup")

    def _connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA secure_delete=ON")
        return db

    @contextmanager
    def connect(self):
        db = self._connection()
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        db = self._connection()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def issue_token(self, tenant="demo-org", actor="demo-operator", agent="demo-agent"):
        token = secrets.token_urlsafe(32)
        with self.transaction() as db:
            db.execute("INSERT INTO principals VALUES (?,?,?,?,1)",
                       (hashlib.sha256(token.encode()).hexdigest(), tenant, actor, agent))
            catalog = self.catalog(db)
            resources = {"workflow:" + c["workflow_id"] for c in catalog["checks"]}
            resources |= {"source:" + c["source"]["source_id"] for c in catalog["checks"]}
            for subject in (actor, agent):
                for resource in resources:
                    db.execute("INSERT OR IGNORE INTO grants VALUES (?,?,?,1)", (tenant, subject, resource))
            for check in catalog["checks"]:
                db.execute("INSERT OR IGNORE INTO policies VALUES (?,?,'ACTIVE')", (tenant, check["workflow_id"]))
            self.authority(db, "TOKEN_ISSUED", {"tenant": tenant, "actor": actor, "agent": agent})
        return token

    @staticmethod
    def authenticate(db, token):
        principal = db.execute("SELECT * FROM principals WHERE token_hash=? AND active=1",
                               (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not principal:
            raise APIError(401, "UNAUTHENTICATED", "A valid demo bearer token is required.")
        return dict(principal)

    @staticmethod
    def session(db, session_id, principal):
        row = db.execute("SELECT payload FROM sessions WHERE id=? AND tenant=? AND actor=?",
                         (session_id, principal["tenant"], principal["actor"])).fetchone()
        if not row:
            raise APIError(404, "NOT_FOUND", "Session or referenced object is unavailable.")
        return json.loads(row[0])

    @staticmethod
    def save(db, session):
        db.execute("UPDATE sessions SET payload=? WHERE id=?", (canonical(session), session["session_id"]))

    @staticmethod
    def catalog(db):
        rows = db.execute("SELECT payload FROM catalogs WHERE active=1").fetchall()
        if len(rows) != 1:
            raise APIError(503, "POLICY_UNAVAILABLE", "Approved knowledge is unavailable.")
        return json.loads(rows[0][0])

    @staticmethod
    def event(db, session, kind, data, sources=(), record=None):
        record = record or opaque()
        db.execute("INSERT INTO events(id,session_id,event_type,created_at,data,sources) VALUES (?,?,?,?,?,?)",
                   (record, session["session_id"], kind, now(), canonical(data), canonical(list(sources))))
        return record

    def backup(self, destination):
        destination = Path(destination).resolve()
        if destination == self.path.resolve() or destination.exists():
            raise ValueError("Backup destination must be a new file distinct from the database")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity check failed")

    @staticmethod
    def authority(db, action, data):
        db.execute("INSERT INTO authority_events VALUES (?,?,?,?)", (opaque(), now(), action, canonical(data)))
