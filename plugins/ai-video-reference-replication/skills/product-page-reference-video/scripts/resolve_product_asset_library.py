#!/usr/bin/env python3
"""Resolve or explicitly scaffold one company/product asset-library path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _product_asset_library import (
    AssetLibraryError,
    COMPANY_COMMON_DIRECTORY,
    DEFAULT_LIBRARY_ROOT,
    FilesystemConflictError,
    MATCH_MODE,
    create_directory_exclusive,
    ensure_canonical_product_tree,
    find_single_exact_directory,
    initial_manifest,
    initialize_manifest_atomic,
    normalized_match_key,
    product_paths,
    validate_requested_name,
    validate_root,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve company/product folders using NFC + collapsed-space + casefold "
            "exact matching. Creation requires --create; fuzzy matching is never used."
        )
    )
    parser.add_argument("--company", required=True, help="mandatory company name")
    parser.add_argument("--product", required=True, help="mandatory product name")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_LIBRARY_ROOT,
        help=f"absolute library root (default: {DEFAULT_LIBRARY_ROOT})",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="explicitly create missing paths and their canonical scaffold",
    )
    return parser.parse_args()


def _ensure_company_common(company_path: Path) -> bool:
    path = company_path / COMPANY_COMMON_DIRECTORY
    if path.is_symlink():
        raise FilesystemConflictError(
            "company common-expression path cannot be a symbolic link",
            path=str(path),
        )
    if path.exists():
        if not path.is_dir():
            raise FilesystemConflictError(
                "company common-expression path exists but is not a directory",
                path=str(path),
            )
        return False
    create_directory_exclusive(path, "company common-expression")
    return True


def resolve(args: argparse.Namespace) -> dict[str, Any]:
    requested_company = validate_requested_name(args.company, "company")
    requested_product = validate_requested_name(args.product, "product")
    company_key = normalized_match_key(requested_company)
    product_key = normalized_match_key(requested_product)
    root = validate_root(args.root)

    created_root = False
    root_existed = root.is_dir()
    if not root_existed and args.create:
        try:
            root.mkdir(mode=0o755, parents=True, exist_ok=False)
            created_root = True
        except FileExistsError:
            validate_root(root)
        except OSError as exc:
            raise FilesystemConflictError(
                "could not create asset library root",
                path=str(root),
                os_error=str(exc),
            ) from exc

    company_path = (
        find_single_exact_directory(root, company_key, "company")
        if root.is_dir()
        else None
    )
    company_existed = company_path is not None
    created_company = False
    if company_path is None:
        company_path = root / requested_company

    product_path = (
        find_single_exact_directory(company_path, product_key, "product")
        if company_existed
        else None
    )
    product_existed = product_path is not None
    created_product = False
    if product_path is None:
        product_path = company_path / requested_product

    if product_existed:
        status = "existing_product"
    elif company_existed:
        status = "existing_company_new_product"
    else:
        status = "new_company_product"

    if args.create:
        if not company_existed:
            create_directory_exclusive(company_path, "company")
            created_company = True
        if not product_existed:
            create_directory_exclusive(product_path, "product")
            created_product = True

    created_company_common = False
    created_subdirectories: list[Path] = []
    manifest_created = False
    manifest_path = Path(product_paths(product_path)["manifest"])
    if args.create:
        created_company_common = _ensure_company_common(company_path)
        created_subdirectories = ensure_canonical_product_tree(product_path)
        manifest_created = initialize_manifest_atomic(
            manifest_path, initial_manifest(root, company_path, product_path)
        )

    paths = product_paths(product_path)
    paths["company_common_expressions"] = str(
        company_path / COMPANY_COMMON_DIRECTORY
    )
    path_states = {key: Path(value).exists() for key, value in paths.items()}
    changed = bool(
        created_root
        or created_company
        or created_product
        or created_company_common
        or created_subdirectories
        or manifest_created
    )
    return {
        "ok": True,
        "status": status,
        "changed": changed,
        "create_requested": bool(args.create),
        "match_mode": MATCH_MODE,
        "fuzzy_matching": False,
        "root": str(root),
        "company": {
            "requested_name": requested_company,
            "resolved_name": company_path.name,
            "match_key": company_key,
            "path": str(company_path),
            "existed": company_existed,
            "created": created_company,
        },
        "product": {
            "requested_name": requested_product,
            "resolved_name": product_path.name,
            "match_key": product_key,
            "path": str(product_path),
            "existed": product_existed,
            "created": created_product,
        },
        "paths": paths,
        "path_exists": path_states,
        "company_common_created": created_company_common,
        "created_subdirectories": [str(path) for path in created_subdirectories],
        "manifest_created": manifest_created,
    }


def main() -> int:
    args = parse_args()
    try:
        result = resolve(args)
    except AssetLibraryError as exc:
        print(json.dumps(exc.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return exc.exit_code
    except OSError as exc:
        result = {
            "ok": False,
            "error": "filesystem_error",
            "message": str(exc),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 6

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
