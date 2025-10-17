# -*- coding: utf-8 -*-
"""
Notion 로깅 유틸리티
- .env에서 NOTION_TOKEN, NOTION_DB_CONTENT_LOG 사용
- create_log_page(): 게시물 메타를 Notion DB에 한 줄로 기록
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Dict, Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
NOTION_DB_ID = os.getenv("NOTION_DB_CONTENT_LOG", "").strip()

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"  # 안정적인 구버전. 스키마 충돌 방지용.


class NotionConfigError(RuntimeError):
    pass


def _assert_env():
    if not NOTION_TOKEN:
        raise NotionConfigError("NOTION_TOKEN 이 비어 있습니다(.env 확인).")
    if not NOTION_DB_ID:
        raise NotionConfigError("NOTION_DB_CONTENT_LOG 이 비어 있습니다(.env 확인).")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", NOTION_DB_ID):
        raise NotionConfigError("NOTION_DB_CONTENT_LOG 는 하이픈 없는 32자 hex 이어야 합니다.")


def _headers() -> Dict[str, str]:
    # 요청 헤더는 ASCII 사용. json=payload 사용.
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _backoff_sleep(retry: int) -> None:
    # 지수 백오프(최대 8초)
    time.sleep(min(2 ** retry, 8))


def ensure_db_properties() -> None:
    """
    DB 스키마 확인 및 안내 로그(강제 변환은 하지 않음).
    """
    url = f"{NOTION_API_BASE}/databases/{NOTION_DB_ID}"
    resp = requests.get(url, headers=_headers(), timeout=15)
    if resp.status_code != 200:
        logging.warning("DB 스키마 조회 실패(%s): %s", resp.status_code, resp.text[:300])
        return
    data = resp.json()
    # 참고용 안내
    logging.info(
        "Notion DB 확인: title=%s, properties=%s",
        data.get("title", [{}])[0].get("plain_text", ""),
        ", ".join(list(data.get("properties", {}).keys())[:10]),
    )


def _build_page_payload(meta: Dict[str, str]) -> Dict[str, Any]:
    """
    Notion Page 생성 payload. 여기서는 일반적인 속성 스키마를 가정.
    DB에 아래 속성들이 존재하면 매핑되고, 존재하지 않아도 생성은 진행됨(미매핑은 무시됨).
    - Title (title) : 게시물 제목
    - Slug (rich_text)
    - URL (url)
    - Status (select)
    - Keywords (multi_select or rich_text)
    - CreatedAt (date)
    """
    title = meta.get("title") or "Untitled"
    slug = meta.get("slug") or ""
    url = meta.get("url") or ""
    status = meta.get("status") or ""
    keywords = [s.strip() for s in (meta.get("keywords") or "").split(",") if s.strip()]

    props: Dict[str, Any] = {
        "Title": {"title": [{"type": "text", "text": {"content": title}}]},
    }

    if slug:
        props["Slug"] = {"rich_text": [{"type": "text", "text": {"content": slug}}]}

    if url:
        props["URL"] = {"url": url}

    if status:
        props["Status"] = {"select": {"name": status}}

    if keywords:
        # DB에 Keywords가 multi_select면 아래가 적용됨. 아니면 rich_text로도 기록 시도.
        props["Keywords"] = {"multi_select": [{"name": k} for k in keywords]}
        # 병행 텍스트 기록(스키마 불일치 대비)
        props["KeywordsText"] = {
            "rich_text": [{"type": "text", "text": {"content": ", ".join(keywords)}}]
        }

    # 생성 시간 기록
    from datetime import datetime, timezone

    props["CreatedAt"] = {
        "date": {"start": datetime.now(timezone.utc).isoformat()}
    }

    return {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": props,
    }


def create_log_page(meta: Dict[str, str], max_retries: int = 3) -> Optional[str]:
    """
    게시물 메타를 Notion DB에 1건 생성. 성공 시 page_id 반환.
    """
    _assert_env()
    payload = _build_page_payload(meta)
    url = f"{NOTION_API_BASE}/pages"

    for attempt in range(max_retries):
        resp = requests.post(url, headers=_headers(), json=payload, timeout=20)
        if resp.status_code in (200, 201):
            page_id = resp.json().get("id")
            logging.info("Notion 로그 생성 성공: page_id=%s", page_id)
            return page_id

        # 429/5xx 재시도
        if resp.status_code in (429, 500, 502, 503, 504):
            logging.warning(
                "Notion API 일시 오류(%s): %s", resp.status_code, resp.text[:300]
            )
            _backoff_sleep(attempt)
            continue

        # 그 외 오류 즉시 중단
        logging.error("Notion API 오류(%s): %s", resp.status_code, resp.text[:500])
        break

    return None


def parse_notion_id_from_url(url: str) -> Optional[str]:
    """
    다양한 Notion 링크에서 하이픈 없는 32자 DB/Page ID 추출.
    - Databases/Pages 모두에서 32자 hex 또는 하이픈 포함 UUID를 찾고 하이픈 제거.
    """
    if not url:
        return None
    # 하이픈 포함 UUID 우선
    m = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        url,
    )
    if m:
        return m.group(1).replace("-", "").lower()
    # 하이픈 없는 32자
    m2 = re.search(r"([0-9a-fA-F]{32})", url)
    if m2:
        return m2.group(1).lower()
    return None


if __name__ == "__main__":
    # 단독 테스트 실행 예:
    ensure_db_properties()
    sample = {
        "title": os.getenv("POST_TITLE", "Sample Title"),
        "slug": os.getenv("POST_SLUG", "sample-slug"),
        "url": os.getenv("POST_URL", "https://example.com/sample-slug"),
        "status": os.getenv("POST_STATUS", "SUCCESS"),
        "keywords": os.getenv("POST_KEYWORDS", "automation,blog,seo"),
    }
    create_log_page(sample)
