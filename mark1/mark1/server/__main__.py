"""Local operator tooling; administrative actions are never model tools or public routes."""
import argparse
import hashlib
import json
from pathlib import Path

from .catalog import publish
from .config import Settings
from .service import Service
from .state import TERMINAL


def erase_session(service, session_id):
    """Delete demo content, retaining minimal command tombstones to prevent replay effects."""
    with service.store.transaction() as db:
        row = db.execute("SELECT payload FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row or json.loads(row[0])["status"] not in TERMINAL:
            raise ValueError("Only an existing terminal demo session can be erased")
        # Exclusive write transaction: normal application events remain append-only.
        db.execute("DROP TRIGGER events_no_delete")
        db.execute("DELETE FROM events WHERE session_id=?", (session_id,))
        db.execute("CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'immutable event'); END")
        db.execute("DELETE FROM images WHERE session_id=?", (session_id,))
        db.execute("DELETE FROM inferences WHERE session_id=?", (session_id,))
        db.execute("UPDATE commands SET image_result=? WHERE session_id=? OR json_extract(image_result,'$.session_id')=?",
                   ('{"erased":true}', session_id, session_id))
        db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        service.store.authority(db, "SESSION_ERASED", {"session_id": session_id})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Initialize synthetic data and print a newly generated demo bearer token once")
    init.add_argument("--tenant", default="demo-org")
    init.add_argument("--actor", default="demo-operator")
    init.add_argument("--agent", default="demo-agent")
    backup = commands.add_parser("backup")
    backup.add_argument("destination", type=Path)
    policy = commands.add_parser("policy", help="Set local workflow kill switch or simulate a policy outage")
    policy.add_argument("tenant")
    policy.add_argument("workflow")
    policy.add_argument("state", choices=["ACTIVE", "BLOCKED", "UNAVAILABLE"])
    resource = commands.add_parser("withdraw", help="Irreversibly revoke a version in the current local authority ledger")
    resource.add_argument("key")
    resource.add_argument("--state", choices=["Withdrawn", "Obsolete", "Superseded"], default="Withdrawn")
    revoke = commands.add_parser("revoke-token", help="Revoke by token hash, never put raw tokens in shell history")
    revoke.add_argument("token_hash")
    access = commands.add_parser("access", help="Set an explicit user or agent resource grant")
    access.add_argument("tenant")
    access.add_argument("subject")
    access.add_argument("resource", help="workflow:ID or source:ID")
    access.add_argument("permission", choices=["ALLOW", "DENY"])
    publication = commands.add_parser("publish", help="Publish an immutable synthetic catalog with a source-file manifest")
    publication.add_argument("catalog", type=Path)
    publication.add_argument("manifest", type=Path, help='JSON list of source_id, version, file (relative to manifest)')
    erase = commands.add_parser("erase-session", help="Erase terminal demo content; backups expire separately")
    erase.add_argument("session_id")
    erase.add_argument("--confirm-id", required=True)
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.database:
        from dataclasses import replace
        settings = replace(settings, database=args.database)
    service = Service(settings)
    if args.command == "init":
        print("Synthetic local demo only. Store this bearer token privately; it is shown once:")
        token = service.store.issue_token(args.tenant, args.actor, args.agent)
        print(token)
        print("Token hash for revocation: " + hashlib.sha256(token.encode()).hexdigest())
    elif args.command == "backup":
        service.store.backup(args.destination)
        print("Backup created and integrity checked; rehearse restore into a separate database.")
    elif args.command == "publish":
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        sources = {(r["source_id"], r["version"]): (args.manifest.parent / r["file"]).read_bytes() for r in manifest}
        publish(service.store, service.contracts, json.loads(args.catalog.read_text(encoding="utf-8")), sources)
        print("Synthetic catalog published; existing session bindings will be revalidated.")
    elif args.command == "erase-session":
        if args.confirm_id != args.session_id:
            parser.error("Confirmation ID must match the target session")
        erase_session(service, args.session_id)
        print("Session content erased. Minimal command hashes/IDs remain as replay tombstones. Expire backup copies separately.")
    else:
        with service.store.transaction() as db:
            if args.command == "policy":
                db.execute("INSERT INTO policies VALUES (?,?,?) ON CONFLICT(tenant,workflow) DO UPDATE SET state=excluded.state",
                           (args.tenant, args.workflow, args.state))
            elif args.command == "withdraw":
                if not db.execute("SELECT 1 FROM resources WHERE key=?", (args.key,)).fetchone():
                    parser.error("Unknown resource key")
                db.execute("UPDATE resources SET state=? WHERE key=?", (args.state, args.key))
            elif args.command == "access":
                db.execute("INSERT INTO grants VALUES (?,?,?,?) ON CONFLICT(tenant,subject,resource) DO UPDATE SET allowed=excluded.allowed",
                           (args.tenant, args.subject, args.resource, int(args.permission == "ALLOW")))
            else:
                db.execute("UPDATE principals SET active=0 WHERE token_hash=?", (args.token_hash,))
            service.store.authority(db, "ADMIN_" + args.command.upper(),
                                    {k: str(v) for k, v in vars(args).items() if k not in ("database", "command")})
        print("Local authority record updated.")


if __name__ == "__main__":
    main()
