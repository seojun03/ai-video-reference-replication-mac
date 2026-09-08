#!/usr/bin/env python3
"""Run the local product-context manager with the bundled engine Python."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


DEFAULT_ENGINE_ROOT = Path.home() / "Documents" / "서준 AI" / "캡컷 자동화"


def resolve_engine_root(value: str | None) -> Path:
    candidates = []
    if value:
        candidates.append(Path(value))
    configured = os.environ.get("CAPCUT_AUTOMATION_ROOT")
    if configured:
        candidates.append(Path(configured))
    candidates.append(DEFAULT_ENGINE_ROOT)
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if (
            (resolved / "capcut_auto" / "product_context.py").is_file()
            and (resolved / ".venv" / "bin" / "python").is_file()
        ):
            return resolved
    raise FileNotFoundError(
        "제품 컨텍스트 엔진을 찾지 못했습니다. --engine-root 또는 "
        "CAPCUT_AUTOMATION_ROOT를 지정하세요."
    )


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--engine-root")
    known, passthrough = parser.parse_known_args(raw)
    root = resolve_engine_root(known.engine_root)
    command = [
        str(root / ".venv" / "bin" / "python"),
        "-m",
        "capcut_auto.product_context",
        *(passthrough or ["--help"]),
    ]
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
