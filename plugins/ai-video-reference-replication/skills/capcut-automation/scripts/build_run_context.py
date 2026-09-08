#!/usr/bin/env python3
"""Run the fresh-chat edit-context compiler with the project's isolated venv."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


DEFAULT_ENGINE_ROOT = Path.home() / "Documents" / "서준 AI" / "캡컷 자동화"


def resolve_engine_root(value: str | None) -> Path:
    candidates: list[Path] = []
    if value:
        candidates.append(Path(value))
    configured = os.environ.get("CAPCUT_AUTOMATION_ROOT")
    if configured:
        candidates.append(Path(configured))
    candidates.append(DEFAULT_ENGINE_ROOT)
    for candidate in candidates:
        root = candidate.expanduser().resolve()
        if (
            (root / ".venv" / "bin" / "python").is_file()
            and (root / "scripts" / "build_edit_run_context.py").is_file()
        ):
            return root
    checked = ", ".join(str(item.expanduser()) for item in candidates)
    raise FileNotFoundError(
        "RUN_CONTEXT_ENGINE_MISSING: fresh-chat context compiler를 찾지 못했습니다: "
        + checked
    )


def _clean_environment() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    return env


def main(argv: Sequence[str] | None = None) -> int:
    passthrough = list(sys.argv[1:] if argv is None else argv)
    preflight = argparse.ArgumentParser(add_help=False)
    preflight.add_argument("--engine-root")
    known, remaining = preflight.parse_known_args(passthrough)
    root = resolve_engine_root(known.engine_root)
    command = [
        str(root / ".venv" / "bin" / "python"),
        str(root / "scripts" / "build_edit_run_context.py"),
        *remaining,
    ]
    return subprocess.run(
        command,
        cwd=root,
        env=_clean_environment(),
        check=False,
    ).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
