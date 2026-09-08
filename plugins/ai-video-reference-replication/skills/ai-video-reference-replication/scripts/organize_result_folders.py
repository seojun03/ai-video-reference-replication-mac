#!/usr/bin/env python3
"""Daily Korean result layout. Legacy CLI entrypoint is retained."""
from daily_result_folders import build_parser, organize, main

if __name__ == "__main__":
    raise SystemExit(main())
