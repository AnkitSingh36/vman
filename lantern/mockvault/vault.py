"""A local, SQLite-backed mock of an M-Files vault.

This mimics the M-Files *structure* (as described in internal Confluence docs),
not its APIs or data. No real vault is touched.

Concepts mimicked
-----------------
- Object types (Document, Equipment, Part, ...) and classes within them.
- Property definitions with well-known built-in IDs (0 = Name or title,
  100 = Class, 38 = Workflow, 39 = State) plus custom IDs from 1000 upward.
- Objects with versions. Every change creates a new version; old versions stay.
- Workflows and states (e.g. Draft -> In review -> Approved -> Obsolete).
- Access control lists built from components. A user needs every component
  (class-based "automatic" component and object-specific component) to grant
  access, as in M-Files.
- An audit log of every read and write done through this layer.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Built-in property IDs (mirroring M-Files conventions)
P_NAME = 0
P_CLASS = 100
P_WORKFLOW = 38
P_STATE = 39

SCHEMA = """
CREATE TABLE IF NOT EXISTS object_types (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS workflows (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS states (
    id INTEGER PRIMARY KEY, workflow_id INTEGER NOT NULL REFERENCES workflows(id),
    name TEXT NOT NULL, is_released INTEGER NOT NULL DEFAULT 0, is_open INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_groups (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS group_members (group_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (group_id, user_id));
CREATE TABLE IF NOT EXISTS nacls (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS nacl_entries (
    nacl_id INTEGER NOT NULL REFERENCES nacls(id), principal_type TEXT NOT NULL CHECK (principal_type IN ('user','group')),
    principal_id INTEGER NOT NULL, can_read INTEGER NOT NULL DEFAULT 1, can_edit INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, object_type_id INTEGER NOT NULL REFERENCES object_types(id),
    workflow_id INTEGER REFERENCES workflows(id), nacl_id INTEGER REFERENCES nacls(id));
CREATE TABLE IF NOT EXISTS property_defs (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, datatype TEXT NOT NULL
        CHECK (datatype IN ('text','multiline','integer','number','date','boolean','lookup','multilookup','valuelist')),
    lookup_object_type_id INTEGER REFERENCES object_types(id));
CREATE TABLE IF NOT EXISTS objects (
    id INTEGER PRIMARY KEY, object_type_id INTEGER NOT NULL REFERENCES object_types(id),
    created_at TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS object_versions (
    object_id INTEGER NOT NULL REFERENCES objects(id), version INTEGER NOT NULL,
    class_id INTEGER NOT NULL REFERENCES classes(id), title TEXT NOT NULL,
    workflow_id INTEGER REFERENCES workflows(id), state_id INTEGER REFERENCES states(id),
    object_nacl_id INTEGER REFERENCES nacls(id), content TEXT, created_at TEXT NOT NULL,
    created_by TEXT NOT NULL, comment TEXT, PRIMARY KEY (object_id, version));
CREATE TABLE IF NOT EXISTS property_values (
    object_id INTEGER NOT NULL, version INTEGER NOT NULL, property_def_id INTEGER NOT NULL REFERENCES property_defs(id),
    value_json TEXT NOT NULL, PRIMARY KEY (object_id, version, property_def_id));
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL, on_behalf_of TEXT,
    action TEXT NOT NULL, object_id INTEGER, version INTEGER, details_json TEXT);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ObjectVersion:
    """One version of one object, with its properties resolved by name."""

    object_id: int
    version: int
    object_type: str
    class_name: str
    title: str
    workflow: str | None
    state: str | None
    state_is_released: bool
    state_is_open: bool
    content: str | None
    created_at: str
    created_by: str
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def ref(self) -> str:
        """Human-readable reference, e.g. 'Document 12 v3'."""
        return f"{self.object_type} {self.object_id} v{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "version": self.version,
            "ref": self.ref,
            "object_type": self.object_type,
            "class": self.class_name,
            "title": self.title,
            "workflow": self.workflow,
            "state": self.state,
            "properties": self.properties,
        }


class PermissionDenied(Exception):
    pass


class MockVault:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    # ------------------------------------------------------------------ structure
    def add_object_type(self, id: int, name: str) -> None:
        self.db.execute("INSERT INTO object_types (id, name) VALUES (?, ?)", (id, name))

    def add_workflow(self, id: int, name: str, states: Iterable[tuple[int, str, bool, bool]]) -> None:
        """states: (state_id, name, is_released, is_open)."""
        self.db.execute("INSERT INTO workflows (id, name) VALUES (?, ?)", (id, name))
        for sid, sname, released, is_open in states:
            self.db.execute(
                "INSERT INTO states (id, workflow_id, name, is_released, is_open) VALUES (?,?,?,?,?)",
                (sid, id, sname, int(released), int(is_open)),
            )

    def add_class(self, id: int, name: str, object_type_id: int, workflow_id: int | None = None,
                  nacl_id: int | None = None) -> None:
        self.db.execute(
            "INSERT INTO classes (id, name, object_type_id, workflow_id, nacl_id) VALUES (?,?,?,?,?)",
            (id, name, object_type_id, workflow_id, nacl_id),
        )

    def add_property_def(self, id: int, name: str, datatype: str, lookup_object_type_id: int | None = None) -> None:
        self.db.execute(
            "INSERT INTO property_defs (id, name, datatype, lookup_object_type_id) VALUES (?,?,?,?)",
            (id, name, datatype, lookup_object_type_id),
        )

    def add_user(self, id: int, login: str, display_name: str, groups: Iterable[int] = ()) -> None:
        self.db.execute("INSERT INTO users (id, login, display_name) VALUES (?,?,?)", (id, login, display_name))
        for gid in groups:
            self.db.execute("INSERT INTO group_members (group_id, user_id) VALUES (?,?)", (gid, id))

    def add_group(self, id: int, name: str) -> None:
        self.db.execute("INSERT INTO user_groups (id, name) VALUES (?,?)", (id, name))

    def add_nacl(self, id: int, name: str, entries: Iterable[tuple[str, int, bool, bool]]) -> None:
        """entries: (principal_type 'user'|'group', principal_id, can_read, can_edit)."""
        self.db.execute("INSERT INTO nacls (id, name) VALUES (?,?)", (id, name))
        for ptype, pid, can_read, can_edit in entries:
            self.db.execute(
                "INSERT INTO nacl_entries (nacl_id, principal_type, principal_id, can_read, can_edit) VALUES (?,?,?,?,?)",
                (id, ptype, pid, int(can_read), int(can_edit)),
            )

    def commit(self) -> None:
        self.db.commit()

    # ------------------------------------------------------------------ lookups
    def _prop_id(self, name_or_id: str | int) -> int:
        if isinstance(name_or_id, int):
            return name_or_id
        row = self.db.execute("SELECT id FROM property_defs WHERE name = ?", (name_or_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown property definition: {name_or_id}")
        return row["id"]

    def _class_row(self, class_name_or_id: str | int) -> sqlite3.Row:
        if isinstance(class_name_or_id, int):
            row = self.db.execute("SELECT * FROM classes WHERE id = ?", (class_name_or_id,)).fetchone()
        else:
            row = self.db.execute("SELECT * FROM classes WHERE name = ?", (class_name_or_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown class: {class_name_or_id}")
        return row

    def _state_id(self, workflow_id: int, state_name: str) -> int:
        row = self.db.execute(
            "SELECT id FROM states WHERE workflow_id = ? AND name = ?", (workflow_id, state_name)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown state '{state_name}' in workflow {workflow_id}")
        return row["id"]

    def _user_id(self, login: str) -> int:
        row = self.db.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
        if row is None:
            raise PermissionDenied(f"Unknown user: {login}")
        return row["id"]

    # ------------------------------------------------------------------ permissions
    def _nacl_grants(self, nacl_id: int, user_id: int, need_edit: bool) -> bool:
        col = "can_edit" if need_edit else "can_read"
        row = self.db.execute(
            f"""SELECT 1 FROM nacl_entries e
                WHERE e.nacl_id = ? AND e.{col} = 1 AND (
                    (e.principal_type = 'user' AND e.principal_id = ?) OR
                    (e.principal_type = 'group' AND e.principal_id IN
                        (SELECT group_id FROM group_members WHERE user_id = ?)))
                LIMIT 1""",
            (nacl_id, user_id, user_id),
        ).fetchone()
        return row is not None

    def can_access(self, login: str, object_id: int, version: int, need_edit: bool = False) -> bool:
        """Every ACL component must grant access (M-Files component semantics)."""
        user_id = self._user_id(login)
        row = self.db.execute(
            """SELECT c.nacl_id AS class_nacl, v.object_nacl_id AS object_nacl
               FROM object_versions v JOIN classes c ON c.id = v.class_id
               WHERE v.object_id = ? AND v.version = ?""",
            (object_id, version),
        ).fetchone()
        if row is None:
            return False
        components = [n for n in (row["class_nacl"], row["object_nacl"]) if n is not None]
        return all(self._nacl_grants(n, user_id, need_edit) for n in components)

    # ------------------------------------------------------------------ writes
    def create_object(self, object_type_id: int, class_name: str, title: str, properties: dict[str, Any] | None = None,
                      state: str | None = None, content: str | None = None, object_nacl_id: int | None = None,
                      created_by: str = "system", created_at: str | None = None, comment: str | None = None) -> int:
        cls = self._class_row(class_name)
        if cls["object_type_id"] != object_type_id:
            raise ValueError(f"Class {class_name} does not belong to object type {object_type_id}")
        ts = created_at or _now()
        cur = self.db.execute("INSERT INTO objects (object_type_id, created_at) VALUES (?, ?)", (object_type_id, ts))
        object_id = cur.lastrowid
        self._insert_version(object_id, 1, cls, title, properties or {}, state, content, object_nacl_id,
                             created_by, ts, comment)
        return object_id

    def new_version(self, object_id: int, title: str | None = None, properties: dict[str, Any] | None = None,
                    state: str | None = None, content: str | None = None, created_by: str = "system",
                    created_at: str | None = None, comment: str | None = None, class_name: str | None = None) -> int:
        """Create a new version that starts as a copy of the latest one."""
        latest = self.latest_version(object_id)
        cls = self._class_row(class_name or latest.class_name)
        merged = dict(latest.properties)
        merged.update(properties or {})
        prev = self.db.execute(
            "SELECT object_nacl_id FROM object_versions WHERE object_id = ? AND version = ?",
            (object_id, latest.version),
        ).fetchone()
        new_v = latest.version + 1
        self._insert_version(object_id, new_v, cls, title or latest.title, merged,
                             state if state is not None else latest.state,
                             content if content is not None else latest.content,
                             prev["object_nacl_id"], created_by, created_at or _now(), comment)
        return new_v

    def _insert_version(self, object_id, version, cls, title, properties, state, content, object_nacl_id,
                        created_by, ts, comment) -> None:
        state_id = self._state_id(cls["workflow_id"], state) if (state and cls["workflow_id"]) else None
        self.db.execute(
            """INSERT INTO object_versions (object_id, version, class_id, title, workflow_id, state_id,
                   object_nacl_id, content, created_at, created_by, comment)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (object_id, version, cls["id"], title, cls["workflow_id"], state_id, object_nacl_id, content, ts,
             created_by, comment),
        )
        for name, value in properties.items():
            self.db.execute(
                "INSERT INTO property_values (object_id, version, property_def_id, value_json) VALUES (?,?,?,?)",
                (object_id, version, self._prop_id(name), json.dumps(value)),
            )

    def log(self, actor: str, action: str, on_behalf_of: str | None = None, object_id: int | None = None,
            version: int | None = None, details: dict[str, Any] | None = None) -> None:
        self.db.execute(
            "INSERT INTO audit_log (ts, actor, on_behalf_of, action, object_id, version, details_json) VALUES (?,?,?,?,?,?,?)",
            (_now(), actor, on_behalf_of, action, object_id, version, json.dumps(details or {})),
        )
        self.db.commit()

    # ------------------------------------------------------------------ reads
    def _load_version(self, object_id: int, version: int) -> ObjectVersion:
        row = self.db.execute(
            """SELECT v.*, c.name AS class_name, t.name AS type_name, w.name AS wf_name,
                      s.name AS state_name, s.is_released, s.is_open
               FROM object_versions v
               JOIN classes c ON c.id = v.class_id
               JOIN objects o ON o.id = v.object_id
               JOIN object_types t ON t.id = o.object_type_id
               LEFT JOIN workflows w ON w.id = v.workflow_id
               LEFT JOIN states s ON s.id = v.state_id
               WHERE v.object_id = ? AND v.version = ?""",
            (object_id, version),
        ).fetchone()
        if row is None:
            raise KeyError(f"No object {object_id} v{version}")
        props = {}
        for p in self.db.execute(
            """SELECT d.name, pv.value_json FROM property_values pv JOIN property_defs d ON d.id = pv.property_def_id
               WHERE pv.object_id = ? AND pv.version = ?""",
            (object_id, version),
        ):
            props[p["name"]] = json.loads(p["value_json"])
        return ObjectVersion(
            object_id=object_id, version=version, object_type=row["type_name"], class_name=row["class_name"],
            title=row["title"], workflow=row["wf_name"], state=row["state_name"],
            state_is_released=bool(row["is_released"]) if row["is_released"] is not None else False,
            state_is_open=bool(row["is_open"]) if row["is_open"] is not None else False,
            content=row["content"], created_at=row["created_at"], created_by=row["created_by"], properties=props,
        )

    def latest_version(self, object_id: int) -> ObjectVersion:
        row = self.db.execute("SELECT MAX(version) AS v FROM object_versions WHERE object_id = ?", (object_id,)).fetchone()
        if row is None or row["v"] is None:
            raise KeyError(f"No object {object_id}")
        return self._load_version(object_id, row["v"])

    def versions(self, object_id: int) -> list[ObjectVersion]:
        rows = self.db.execute(
            "SELECT version FROM object_versions WHERE object_id = ? ORDER BY version", (object_id,)
        ).fetchall()
        return [self._load_version(object_id, r["version"]) for r in rows]

    def objects_of_class(self, class_name: str) -> list[int]:
        cls = self._class_row(class_name)
        rows = self.db.execute(
            """SELECT DISTINCT o.id FROM objects o JOIN object_versions v ON v.object_id = o.id
               WHERE o.deleted = 0 AND v.class_id = ? ORDER BY o.id""",
            (cls["id"],),
        ).fetchall()
        return [r["id"] for r in rows]

    def objects_of_type(self, object_type_name: str) -> list[int]:
        rows = self.db.execute(
            """SELECT o.id FROM objects o JOIN object_types t ON t.id = o.object_type_id
               WHERE o.deleted = 0 AND t.name = ? ORDER BY o.id""",
            (object_type_name,),
        ).fetchall()
        return [r["id"] for r in rows]

    def audit_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) | {"details": json.loads(r["details_json"] or "{}")} for r in rows]
