#!/usr/bin/env python3
"""Read company and product memory from the live local Cutroom bridge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_BRIDGE_ORIGIN = "http://127.0.0.1:47831"
DEFAULT_REQUEST_ORIGIN = "http://localhost:3000"
DEFAULT_STATE_ROOT = Path.home() / "Library" / "Application Support" / "Cutroom"


class CutroomMemoryError(RuntimeError):
    """Safe, user-facing error raised by the read-only memory client."""

    def __init__(self, code: str, message: str, *, details: object = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def normalized_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split()).casefold()


def public_record(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        raise CutroomMemoryError(
            "CUTROOM_RESPONSE_INVALID",
            "컷룸 메모리 응답 형식이 올바르지 않습니다.",
        )
    return {str(key): value for key, value in record.items()}


class CutroomMemoryClient:
    def __init__(
        self,
        *,
        bridge_origin: str,
        request_origin: str,
        state_root: Path,
        timeout: float,
    ) -> None:
        self.bridge_origin = bridge_origin.rstrip("/")
        self.request_origin = request_origin
        self.state_root = state_root.expanduser()
        self.timeout = timeout
        self.token_path = self.state_root / "bridge_token"

    def _token(self) -> str:
        try:
            token = self.token_path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise CutroomMemoryError(
                "CUTROOM_TOKEN_UNAVAILABLE",
                "컷룸 인증 정보를 읽을 수 없습니다. 컷룸 로컬 엔진을 먼저 실행해 주세요.",
            ) from error
        if not token:
            raise CutroomMemoryError(
                "CUTROOM_TOKEN_EMPTY",
                "컷룸 인증 정보가 비어 있습니다. 컷룸 로컬 엔진을 다시 실행해 주세요.",
            )
        return token

    def _get(self, path: str) -> dict[str, object]:
        request = Request(
            self.bridge_origin + path,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer " + self._token(),
                "Origin": self.request_origin,
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.load(response)
        except HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            message = (
                payload.get("error")
                if isinstance(payload, dict) and isinstance(payload.get("error"), str)
                else f"컷룸 메모리 요청이 거절되었습니다. (HTTP {error.code})"
            )
            raise CutroomMemoryError(
                "CUTROOM_HTTP_ERROR",
                message,
                details={"status": error.code},
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise CutroomMemoryError(
                "CUTROOM_BRIDGE_UNAVAILABLE",
                "컷룸 로컬 엔진에 연결할 수 없습니다. 컷룸을 실행한 뒤 다시 시도해 주세요.",
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CutroomMemoryError(
                "CUTROOM_RESPONSE_INVALID",
                "컷룸 메모리 응답을 읽을 수 없습니다.",
            ) from error
        return public_record(body)

    def companies(self) -> list[dict[str, object]]:
        body = self._get("/v1/knowledge/companies")
        companies = body.get("companies", [])
        if not isinstance(companies, list):
            raise CutroomMemoryError(
                "CUTROOM_RESPONSE_INVALID",
                "컷룸 업체 목록 형식이 올바르지 않습니다.",
            )
        return [public_record(company) for company in companies]

    def products(self, company_id: str) -> list[dict[str, object]]:
        body = self._get(
            "/v1/knowledge/companies/"
            + quote(company_id, safe="")
            + "/products"
        )
        products = body.get("products", [])
        if not isinstance(products, list):
            raise CutroomMemoryError(
                "CUTROOM_RESPONSE_INVALID",
                "컷룸 제품 목록 형식이 올바르지 않습니다.",
            )
        return [public_record(product) for product in products]


def match_exact(
    records: list[dict[str, object]],
    requested: str,
    *,
    kind: str,
) -> dict[str, object]:
    target = normalized_name(requested)
    matches = [
        record
        for record in records
        if isinstance(record.get("name"), str)
        and normalized_name(str(record["name"])) == target
    ]
    candidate_names = [
        str(record["name"])
        for record in records
        if isinstance(record.get("name"), str)
    ]
    if not matches:
        label = "업체" if kind == "company" else "제품"
        raise CutroomMemoryError(
            f"{kind.upper()}_NOT_FOUND",
            f"컷룸 메모리에서 정확히 일치하는 {label}명을 찾지 못했습니다.",
            details={"requested": requested, "candidates": candidate_names},
        )
    if len(matches) > 1:
        label = "업체" if kind == "company" else "제품"
        raise CutroomMemoryError(
            f"{kind.upper()}_AMBIGUOUS",
            f"정규화 후 같은 이름의 {label}가 여러 개입니다. 컷룸에서 이름을 구분해 주세요.",
            details={"requested": requested, "candidates": candidate_names},
        )
    return matches[0]


def without_ids(record: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"id", "companyId"}
    }


def make_client(args: argparse.Namespace) -> CutroomMemoryClient:
    return CutroomMemoryClient(
        bridge_origin=args.bridge_origin,
        request_origin=args.request_origin,
        state_root=Path(args.state_root),
        timeout=args.timeout,
    )


def command_list(args: argparse.Namespace) -> dict[str, object]:
    client = make_client(args)
    companies = client.companies()
    catalog: list[dict[str, object]] = []
    for company in companies:
        company_id = company.get("id")
        if not isinstance(company_id, str):
            continue
        products = client.products(company_id)
        catalog.append(
            {
                "company": company.get("name", ""),
                "companyRevision": company.get("revision"),
                "products": [
                    {
                        "name": product.get("name", ""),
                        "revision": product.get("revision"),
                    }
                    for product in products
                ],
            }
        )
    return {
        "source": "cutroom-local-knowledge",
        "readOnly": True,
        "catalog": catalog,
    }


def command_resolve(args: argparse.Namespace) -> dict[str, object]:
    client = make_client(args)
    company = match_exact(client.companies(), args.company, kind="company")
    company_id = company.get("id")
    if not isinstance(company_id, str):
        raise CutroomMemoryError(
            "CUTROOM_RESPONSE_INVALID",
            "선택한 컷룸 업체의 ID가 올바르지 않습니다.",
        )
    product = match_exact(
        client.products(company_id),
        args.product,
        kind="product",
    )
    return {
        "source": "cutroom-local-knowledge",
        "readOnly": True,
        "company": without_ids(company),
        "product": without_ids(product),
    }


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(
        description="컷룸이 사용하는 업체·제품 메모리를 읽기 전용으로 조회합니다."
    )
    main.add_argument(
        "--bridge-origin",
        default=os.environ.get("CUTROOM_BRIDGE_ORIGIN", DEFAULT_BRIDGE_ORIGIN),
        help="컷룸 로컬 브리지 주소",
    )
    main.add_argument(
        "--request-origin",
        default=os.environ.get("CUTROOM_REQUEST_ORIGIN", DEFAULT_REQUEST_ORIGIN),
        help="컷룸 브리지가 허용한 로컬 웹 출처",
    )
    main.add_argument(
        "--state-root",
        default=os.environ.get("CUTROOM_STATE_ROOT", str(DEFAULT_STATE_ROOT)),
        help="컷룸 로컬 상태 폴더",
    )
    main.add_argument("--timeout", type=float, default=7.0)

    commands = main.add_subparsers(dest="command", required=True)
    list_parser = commands.add_parser("list", help="등록된 업체와 제품명을 조회합니다.")
    list_parser.set_defaults(handler=command_list)

    resolve_parser = commands.add_parser(
        "resolve", help="업체명과 제품명을 정확히 매칭해 현재 메모리를 조회합니다."
    )
    resolve_parser.add_argument("--company", required=True)
    resolve_parser.add_argument("--product", required=True)
    resolve_parser.set_defaults(handler=command_resolve)
    return main


def main() -> int:
    args = parser().parse_args()
    try:
        payload = args.handler(args)
    except CutroomMemoryError as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": error.code,
                    "message": error.message,
                    "details": error.details,
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {"ok": True, **payload},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
