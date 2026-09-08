#!/usr/bin/env python3
"""Atomically claim and record paid media submissions.

The provider may accept a request while the local client loses its response.
This small append-only ledger makes that state explicit so a timeout cannot
silently become a duplicate paid submission.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
TERMINAL_OR_SUBMITTED = {"claimed", "submitted", "submitted_unknown", "completed", "quarantined"}
ALLOWED_STATES = TERMINAL_OR_SUBMITTED | {"failed"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def empty_payload() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "created_at": now(), "entries": {}}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_payload()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("entries", {}), dict):
        raise ValueError(f"invalid submission ledger: {path}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported submission ledger schema: {payload.get('schema_version')!r}")
    return payload


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@contextmanager
def locked(path: Path) -> Iterator[dict[str, Any]]:
    """Lock a sibling file while loading and atomically rewriting the ledger."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        payload = load(path)
        try:
            yield payload
        finally:
            write_atomic(path, payload)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def claim(args: argparse.Namespace) -> int:
    with locked(args.ledger) as payload:
        entries = payload["entries"]
        existing = entries.get(args.submission_key)
        if existing:
            emit({"status": "existing", "submission_key": args.submission_key, "entry": existing})
            return 2
        entry: dict[str, Any] = {
            "submission_key": args.submission_key,
            "stage": args.stage,
            "cut": args.cut,
            "attempt": args.attempt,
            "state": "claimed",
            "claimed_at": now(),
        }
        for name in ("plan_hash", "start_image_hash", "model", "ratio", "duration", "sound", "provider", "route"):
            value = getattr(args, name, None)
            if value not in (None, ""):
                entry[name] = value
        entries[args.submission_key] = entry
        emit({"status": "claimed", "submission_key": args.submission_key, "entry": entry})
    return 0


def record(args: argparse.Namespace) -> int:
    if args.state not in ALLOWED_STATES:
        raise ValueError(f"invalid state: {args.state}")
    with locked(args.ledger) as payload:
        entry = payload["entries"].get(args.submission_key)
        if not entry:
            raise ValueError(f"cannot record unknown submission_key: {args.submission_key}")
        current = entry.get("state")
        if current in {"completed", "quarantined"} and args.state != current:
            raise ValueError(f"cannot move terminal entry {args.submission_key} from {current} to {args.state}")
        entry["state"] = args.state
        entry["updated_at"] = now()
        for name in ("provider_job_id", "provider", "route", "returned_model", "response_hash", "output_hash", "cost", "note"):
            value = getattr(args, name, None)
            if value not in (None, ""):
                entry[name] = value
        emit({"status": "recorded", "submission_key": args.submission_key, "entry": entry})
    return 0


def lookup(args: argparse.Namespace) -> int:
    payload = load(args.ledger)
    entry = payload["entries"].get(args.submission_key)
    emit({"status": "found" if entry else "missing", "submission_key": args.submission_key, "entry": entry})
    return 0 if entry else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    claim_parser = sub.add_parser("claim", help="claim a key before an external submission")
    claim_parser.add_argument("--submission-key", required=True)
    claim_parser.add_argument("--stage", required=True, choices=("image", "video", "tts"))
    claim_parser.add_argument("--cut", required=True)
    claim_parser.add_argument("--attempt", required=True, type=int)
    claim_parser.add_argument("--plan-hash")
    claim_parser.add_argument("--start-image-hash")
    claim_parser.add_argument("--model")
    claim_parser.add_argument("--ratio")
    claim_parser.add_argument("--duration")
    claim_parser.add_argument("--sound")
    claim_parser.add_argument("--provider")
    claim_parser.add_argument("--route")
    claim_parser.set_defaults(handler=claim)

    record_parser = sub.add_parser("record", help="record provider response or terminal outcome")
    record_parser.add_argument("--submission-key", required=True)
    record_parser.add_argument("--state", required=True)
    for name in ("provider-job-id", "provider", "route", "returned-model", "response-hash", "output-hash", "cost", "note"):
        record_parser.add_argument(f"--{name}", dest=name.replace("-", "_"))
    record_parser.set_defaults(handler=record)

    lookup_parser = sub.add_parser("lookup", help="read one submission entry without changing it")
    lookup_parser.add_argument("--submission-key", required=True)
    lookup_parser.set_defaults(handler=lookup)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.ledger = args.ledger.expanduser().resolve()
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
