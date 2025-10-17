# -*- coding: utf-8 -*-
"""
Notion DB 스키마 프로비저닝 스크립트(통합판, 재실행 안전)

통합 내용:
- 레거시 스키마 유지: PascalCase, Status=select
- 캐노니컬 스키마 지원: snake_case, status=status 타입 (중요: options는 API로 설정 불가)

동작:
- 기존 DB 보강(우선): NOTION_DB_CONTENT_LOG 설정 시
- 신규 생성: NOTION_DB_CONTENT_LOG 없고 NOTION_PARENT_PAGE 있으면 Parent Page 하위 생성
- 스타일: --style legacy|canonical|both (기본 legacy)

주의:
- Notion status 타입은 API로 옵션을 보낼 수 없습니다(에러 400). UI에서만 편집 가능.
- 타이틀 속성은 DB당 1개만 허용. 기존 타이틀(예: Name)이 있으면 'title' 신규 생성 시도를 건너뜁니다.

사용:
  pip install requests python-dotenv
  python scripts/notion_provision_db.py --style legacy
  python scripts/notion_provision_db.py --style canonical
  python scripts/notion_provision_db.py --style both
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter, Retry
from dotenv import load_dotenv

# ===== 로깅 =====
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "notion_provision.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("notion_provision")

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NET_TIMEOUT = 20

# ===== ENV =====
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
NOTION_DB_ID = os.getenv("NOTION_DB_CONTENT_LOG", "").strip()
NOTION_PARENT_PAGE = os.getenv("NOTION_PARENT_PAGE", "").strip()

# ===== 공통 =====
def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def _assert_token() -> None:
    if not NOTION_TOKEN:
        raise SystemExit("환경변수 누락: NOTION_TOKEN")

def _validate_db_id(db_id: str) -> None:
    if not re.fullmatch(r"[0-9a-fA-F]{32}", db_id):
        raise SystemExit("NOTION_DB_CONTENT_LOG 는 하이픈 없는 32자 hex 여야 합니다.")

def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST", "PATCH"]),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def check_token() -> None:
    r = _session().get(f"{NOTION_API_BASE}/users/me", headers=_headers(), timeout=NET_TIMEOUT)
    if r.status_code != 200:
        raise SystemExit(f"토큰 유효성 실패({r.status_code}): {r.text[:500]}")
    logger.info("토큰 유효성 OK")

# ===== API 래퍼 =====
def fetch_db(db_id: str) -> Dict[str, Any]:
    r = _session().get(f"{NOTION_API_BASE}/databases/{db_id}", headers=_headers(), timeout=NET_TIMEOUT)
    if r.status_code != 200:
        raise SystemExit(f"DB 조회 실패({r.status_code}): {r.text[:800]}")
    return r.json()

def patch_db_properties(db_id: str, patch_body: Dict[str, Any]) -> Dict[str, Any]:
    r = _session().patch(f"{NOTION_API_BASE}/databases/{db_id}", headers=_headers(), json=patch_body, timeout=NET_TIMEOUT+10)
    if r.status_code != 200:
        raise SystemExit(f"DB 스키마 갱신 실패({r.status_code}): {r.text[:800]}")
    return r.json()

def create_database(parent_page: str, title: str, properties: Dict[str, Any]) -> Optional[str]:
    body = {
        "parent": {"type": "page_id", "page_id": parent_page},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": properties,
    }
    r = _session().post(f"{NOTION_API_BASE}/databases", headers=_headers(), json=body, timeout=NET_TIMEOUT+10)
    if r.status_code != 200:
        logger.error("DB 생성 실패(%s): %s", r.status_code, r.text[:800])
        return None
    dbid = r.json()["id"]
    logger.info("새 DB 생성 성공: %s", dbid)
    return dbid

# ===== 스키마 정의 =====
def schema_legacy_base() -> Dict[str, Any]:
    return {
        "Slug": {"rich_text": {}},
        "URL": {"url": {}},
        "Status": {
            "select": {
                "options": [
                    {"name": "SUCCESS", "color": "green"},
                    {"name": "DRAFT", "color": "yellow"},
                    {"name": "FAILED", "color": "red"},
                    {"name": "PUBLISHED", "color": "blue"},
                ]
            }
        },
        "Keywords": {"multi_select": {}},
        "KeywordsText": {"rich_text": {}},
        "CreatedAt": {"date": {}},
    }

def schema_legacy_observability() -> Dict[str, Any]:
    return {
        "SlackTS": {"rich_text": {}},
        "LastRunMs": {"number": {}},
        "ErrorMsg": {"rich_text": {}},
    }

def schema_canonical_full() -> Dict[str, Any]:
    """
    캐노니컬 스키마 주의:
    - status 타입은 options를 API로 설정하면 400 에러가 납니다.
      => 'status': {'status': {}} 만 보냅니다.
    - 타이틀은 DB당 1개만 허용. 기존 타이틀이 있으면 'title' 추가를 건너뜁니다(아래 build_patch_missing에서 처리).
    """
    return {
        "title": {"title": {}},
        "slug": {"rich_text": {}},
        "status": {"status": {}},  # options 금지!
        "url": {"url": {}},
        "site": {"rich_text": {}},
        "keywords": {"rich_text": {}},
        "avg_ms": {"number": {}},
        "created_at": {"date": {}},
        "updated_at": {"date": {}},
        "published_at": {"date": {}},
        "succeeded_at": {"date": {}},
    }

def ensure_legacy_status_options(props_meta: Dict[str, Any]) -> None:
    if "Status" not in props_meta:
        return
    st = props_meta["Status"]
    if st.get("type") != "select":
        logger.warning("Status 속성 타입이 select 가 아닙니다(수정 생략). type=%s", st.get("type"))
        return
    existing = (st.get("select") or {}).get("options", []) or []
    names = {o.get("name") for o in existing if isinstance(o, dict)}
    required = [
        {"name": "SUCCESS", "color": "green"},
        {"name": "DRAFT", "color": "yellow"},
        {"name": "FAILED", "color": "red"},
        {"name": "PUBLISHED", "color": "blue"},
    ]
    missing = [o for o in required if o["name"] not in names]
    if not missing:
        logger.info("Status 옵션 완비(legacy): %s", ", ".join(sorted(names)))
        return
    patch = {"properties": {"Status": {"select": {"options": existing + missing}}}}
    patch_db_properties(NOTION_DB_ID, patch)
    logger.info("Status 옵션 보강 완료(legacy): %s", ", ".join([o["name"] for o in missing]))

def ensure_canonical_status_options(props_meta: Dict[str, Any]) -> None:
    """
    status(status) 옵션은 API로 수정 불가 → 아무 것도 하지 않고 안내만 남김.
    """
    if "status" in props_meta and props_meta.get("status", {}).get("type") == "status":
        logger.info("status 속성 존재(canonical). 옵션 수정은 UI에서만 가능(API 불가).")
    else:
        logger.info("status 속성이 없거나 타입이 다릅니다(필요 시 새로 추가됨).")

# ===== 보강/생성 로직 =====
def _current_title_prop_name(props: Dict[str, Any]) -> str:
    for name, meta in props.items():
        if meta.get("type") == "title":
            return name
    return "Name"  # 관례적 기본

def build_patch_missing(curr_props: Dict[str, Any], target_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    - curr_props 에 없는 항목만 추가
    - 타이틀은 단 하나만 허용되므로, 이미 타이틀이 있으면 target_schema의 'title' 키 제거
    """
    patch_props: Dict[str, Any] = {}
    have_title_already = any(m.get("type") == "title" for m in curr_props.values())
    for k, v in target_schema.items():
        if k in curr_props:
            continue
        if v.get("title") is not None and have_title_already:
            # 다른 이름의 타이틀이 이미 있음 → 'title' 추가 시도 금지
            continue
        patch_props[k] = v
    return {"properties": patch_props} if patch_props else {}

def provision_existing_db(style: str) -> str:
    global NOTION_DB_ID
    _validate_db_id(NOTION_DB_ID)
    db = fetch_db(NOTION_DB_ID)
    props = db.get("properties", {})

    title_prop = _current_title_prop_name(props)
    logger.info("현재 타이틀 속성: %s", title_prop)
    logger.info("현재 속성 목록: %s", ", ".join(props.keys()))

    if style in ("legacy", "both"):
        legacy = {}
        legacy.update(schema_legacy_base())
        legacy.update(schema_legacy_observability())
        patch = build_patch_missing(props, legacy)
        if patch:
            patch_db_properties(NOTION_DB_ID, patch)
            logger.info("레거시 보강 완료: %s", ", ".join(patch["properties"].keys()))
        props = fetch_db(NOTION_DB_ID).get("properties", {})
        ensure_legacy_status_options(props)

    if style in ("canonical", "both"):
        canonical = schema_canonical_full()
        patch = build_patch_missing(props, canonical)
        if patch:
            patch_db_properties(NOTION_DB_ID, patch)
            logger.info("캐노니컬 보강 완료: %s", ", ".join(patch["properties"].keys()))
        props = fetch_db(NOTION_DB_ID).get("properties", {})
        ensure_canonical_status_options(props)

    final_props = fetch_db(NOTION_DB_ID).get("properties", {}).keys()
    logger.info("최종 속성 목록: %s", ", ".join(final_props))
    return NOTION_DB_ID

def provision_new_db(style: str) -> str:
    if not NOTION_PARENT_PAGE:
        raise SystemExit("NOTION_DB_CONTENT_LOG 가 없고 NOTION_PARENT_PAGE 도 없습니다.")
    if style == "legacy":
        base = {**schema_legacy_base(), **schema_legacy_observability()}
    elif style == "canonical":
        base = schema_canonical_full()
    else:  # both
        base = {**schema_legacy_base(), **schema_legacy_observability(), **schema_canonical_full()}
    dbid = create_database(NOTION_PARENT_PAGE, title="Content Log", properties=base)
    if not dbid:
        raise SystemExit("DB 생성 실패")
    # 생성 직후 보강(옵션 안내 등)
    global NOTION_DB_ID
    NOTION_DB_ID = dbid
    props = fetch_db(NOTION_DB_ID).get("properties", {})
    if style in ("legacy", "both"):
        ensure_legacy_status_options(props)
    if style in ("canonical", "both"):
        ensure_canonical_status_options(props)
    return dbid

# ===== CLI =====
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Notion DB 스키마 프로비저닝(통합판)")
    p.add_argument("--style", choices=["legacy", "canonical", "both"], default="legacy")
    return p.parse_args()

def main() -> int:
    _assert_token()
    check_token()
    args = parse_args()
    logger.info("프로비저닝 스타일: %s", args.style)

    if NOTION_DB_ID:
        dbid = provision_existing_db(args.style)
        print(dbid)
        logger.info("프로비저닝 완료(기존 DB 보강): %s", dbid)
        return 0

    dbid = provision_new_db(args.style)
    print(dbid)
    logger.info("프로비저닝 완료(신규 생성): %s", dbid)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.error("중단됨")
        sys.exit(130)
    except Exception as e:
        logger.exception("치명적 오류: %s", e)
        sys.exit(1)
