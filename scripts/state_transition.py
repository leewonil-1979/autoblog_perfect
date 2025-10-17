# -*- coding: utf-8 -*-
"""
상태 전이 자동화 (Slug/Status 대문자 전용)
- Notion DB 컬럼: Slug(rich_text), Status(select)만 사용
- 상태 전이: DRAFT → PUBLISHED → SUCCESS, FAILED(예외 흐름)
- CSV 일괄 처리: Slug,url 헤더, UTF-8(BOM 허용), 구분자 자동 감지
- URL 가용성 검증 옵션(--validate-url)
- Slack Webhook 알림(선택)
- 재시도/타임아웃/에러 처리 + 상세 로깅(--verbose)

필수 설치:
  pip install python-dotenv requests
환경변수(.env):
  NOTION_TOKEN=secret_xxx
  NOTION_DB_CONTENT_LOG=<32자 hex 또는 Notion 반환 ID>
  NET_TIMEOUT=15
  NET_RETRIES=3
  SLACK_WEBHOOK_URL=
  ALERT_MENTION=@channel

사용 예:
  python scripts/state_transition.py --Slug "my-post" --to PUBLISHED --validate-url "https://site/my-post"
  python scripts/state_transition.py --bulk data/publish_batch.csv --to SUCCESS --dry-run
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter, Retry

# ===== 로깅 =====
logger = logging.getLogger("state_transition")


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(message)s")


# ===== 상수/타입 =====
ALLOWED_STATES = ("DRAFT", "PUBLISHED", "SUCCESS", "FAILED")
VALID_TRANSITIONS = {
    "DRAFT": {"PUBLISHED", "SUCCESS"},
    "PUBLISHED": {"SUCCESS", "FAILED"},
    "SUCCESS": set(),
    "FAILED": {"PUBLISHED"},  # 재시도 허용
}


# ===== 유틸 =====
def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_url_alive(url: str, timeout: int = 10) -> bool:
    """간단 가용성 체크: 200 OK + 본문 100자 이상"""
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return False
        return len(r.text or "") > 100
    except Exception:
        return False


def send_slack(text: str) -> None:
    """Slack Webhook 알림(선택)"""
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        return
    mention = os.getenv("ALERT_MENTION", "").strip()
    payload = {"text": f"{mention} {text}".strip()}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.warning("Slack 알림 실패: %s", e)


# ===== Notion 클라이언트 =====
@dataclass
class NotionConfig:
    token: str
    db_id: str
    timeout: int = 15
    retries: int = 3


class NotionClient:
    """
    대문자 전용 스키마:
      - Slug : rich_text
      - Status : select
      - created_at/published_at/succeeded_at/updated_at 등은 자유롭게 사용
    """

    def __init__(self, cfg: NotionConfig):
        self.cfg = cfg
        self.base = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {cfg.token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        retry = Retry(
            total=cfg.retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "POST", "PATCH"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)

    # --- 내부 URL ---
    def _pages_url(self, page_id: str) -> str:
        return f"{self.base}/pages/{page_id}"

    def _db_query_url(self) -> str:
        return f"{self.base}/databases/{self.cfg.db_id}/query"

    # --- 조회 ---
    def find_by_Slug(self, Slug: str) -> Optional[str]:
        """
        대문자 'Slug' 컬럼만 사용.
        Notion rich_text equals 비교는 공백/대소문자 정확히 일치해야 함.
        """
        body = {
            "filter": {"property": "Slug", "rich_text": {"equals": Slug}},
            "page_size": 1,
        }
        logger.debug("Slug 검색: %s", Slug)
        r = self.session.post(
            self._db_query_url(),
            headers=self.headers,
            data=json.dumps(body),
            timeout=self.cfg.timeout,
        )
        r.raise_for_status()
        items = r.json().get("results", [])
        page_id = items[0]["id"] if items else None
        logger.debug("Slug 검색 결과: %s", page_id)
        return page_id

    def get_status(self, page_id: str) -> Optional[str]:
        """대문자 'Status' select만 읽음."""
        r = self.session.get(self._pages_url(page_id), headers=self.headers, timeout=self.cfg.timeout)
        r.raise_for_status()
        props: Dict[str, Any] = r.json().get("properties", {})
        s = props.get("Status", {}).get("select", {}).get("name")
        logger.debug("현재 Status: %s", s)
        return s

    # --- 쓰기 ---
    def set_status(self, page_id: str, new_status: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """대문자 'Status' select에만 설정."""
        assert new_status in ALLOWED_STATES
        props: Dict[str, Any] = {"updated_at": {"date": {"start": now_iso()}}}
        if extra:
            props.update(extra)
        props["Status"] = {"select": {"name": new_status}}

        r = self.session.patch(
            self._pages_url(page_id),
            headers=self.headers,
            data=json.dumps({"properties": props}),
            timeout=self.cfg.timeout,
        )
        r.raise_for_status()

    def upsert_row(self, meta: Dict[str, Any]) -> str:
        """Slug로 기존 Row 검색 → 있으면 업데이트, 없으면 생성"""
        page_id = self.find_by_Slug(meta["Slug"])
        if page_id:
            self.update_properties(page_id, meta)
            return page_id
        return self.create_row(meta)

    def create_row(self, meta: Dict[str, Any]) -> str:
        props = self._props_from_meta(meta, create=True)
        body = {"parent": {"database_id": self.cfg.db_id}, "properties": props}
        r = self.session.post(f"{self.base}/pages", headers=self.headers, data=json.dumps(body), timeout=self.cfg.timeout)
        r.raise_for_status()
        return r.json()["id"]

    def update_properties(self, page_id: str, meta: Dict[str, Any]) -> None:
        props = self._props_from_meta(meta, create=False)
        body = {"properties": props}
        r = self.session.patch(self._pages_url(page_id), headers=self.headers, data=json.dumps(body), timeout=self.cfg.timeout)
        r.raise_for_status()

    def _props_from_meta(self, meta: Dict[str, Any], create: bool) -> Dict[str, Any]:
        """
        대문자 전용 속성:
          - Name(title), Slug(rich_text), URL(url), Status(select)
          - created_at/updated_at/published_at/succeeded_at 는 소문자라도 DB에 있으면 반영됨
        """
        title_txt = meta.get("title", meta.get("Slug", ""))
        props: Dict[str, Any] = {
            "Name": {"title": [{"type": "text", "text": {"content": title_txt}}]},
            "Slug": {"rich_text": [{"type": "text", "text": {"content": meta["Slug"]}}]},
            "URL": {"url": meta.get("url")},
            "updated_at": {"date": {"start": now_iso()}},
        }
        if create:
            props["created_at"] = {"date": {"start": now_iso()}}
        if meta.get("status"):
            props["Status"] = {"select": {"name": meta["status"]}}
        if meta.get("avg_ms") is not None:
            props["avg_ms"] = {"number": float(meta["avg_ms"])}
        return props


# ===== 설정 로드 =====
def load_cfg() -> NotionConfig:
    load_dotenv(override=False)
    token = os.getenv("NOTION_TOKEN")
    dbid = os.getenv("NOTION_DB_CONTENT_LOG")
    timeout = int(os.getenv("NET_TIMEOUT", "15"))
    retries = int(os.getenv("NET_RETRIES", "3"))
    if not token or not dbid:
        logger.error("환경변수 누락: NOTION_TOKEN, NOTION_DB_CONTENT_LOG")
        sys.exit(2)
    return NotionConfig(token=token, db_id=dbid, timeout=timeout, retries=retries)


# ===== CSV 파싱(견고) =====
def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lstrip("\ufeff").strip()  # BOM/공백 제거


def iter_csv_rows(path: str) -> Iterable[Dict[str, str]]:
    """
    - UTF-8 with BOM 허용
    - csv.Sniffer로 구분자 자동 감지(쉼표/세미콜론/탭 등)
    - 헤더 소문자 정규화(Slug, url)
    """
    raw = open(path, "rb").read()
    text = raw.decode("utf-8-sig")  # BOM 제거
    try:
        sample = "\n".join(text.splitlines()[:2]) or ","
        dialect = csv.Sniffer().sniff(sample)
    except Exception:
        dialect = csv.excel
    rdr = csv.DictReader(io.StringIO(text), dialect=dialect)
    if rdr.fieldnames:
        rdr.fieldnames = [_norm(h) for h in rdr.fieldnames]
    for row in rdr:
        if not row:
            continue
        Slug = _norm(row.get("Slug", ""))
        url = _norm(row.get("url", ""))
        if not Slug:
            logger.warning("행 건너뜀: Slug 없음")
            continue
        yield {"Slug": Slug, "url": url}


# ===== 전이 로직 =====
def ensure_transition_okay(old: Optional[str], new: str) -> None:
    if old is None:
        return
    allowed = VALID_TRANSITIONS.get(old, set())
    if new not in allowed:
        raise ValueError(f"허용되지 않은 전이: {old} -> {new}")


def transition_single(
    nc: NotionClient, Slug: str, to_state: str, validate_url: Optional[str], dry_run: bool
) -> str:
    page_id = nc.find_by_Slug(Slug)
    if not page_id:
        raise RuntimeError(f"Slug를 찾을 수 없습니다: {Slug}")

    current = nc.get_status(page_id)
    logger.info("현재 상태: %s (%s)", current, Slug)
    ensure_transition_okay(current, to_state)

    extra: Dict[str, Any] = {}
    if to_state == "PUBLISHED":
        extra["published_at"] = {"date": {"start": now_iso()}}
    if to_state == "SUCCESS":
        extra["succeeded_at"] = {"date": {"start": now_iso()}}

    if validate_url:
        ok = validate_url_alive(validate_url)
        logger.info("URL 검증(%s): %s", validate_url, ok)
        if not ok:
            send_slack(f"전이 차단: {Slug} → {to_state} (URL 검증 실패)")
            raise RuntimeError("URL 검증 실패(200/본문 길이 조건 불충족)")

    if dry_run:
        logger.info("dry-run: 상태 전이 미적용 (%s → %s)", current, to_state)
        return page_id

    nc.set_status(page_id, to_state, extra=extra)
    logger.info("상태 전이 완료: %s → %s", current, to_state)
    return page_id


def transition_bulk(nc: NotionClient, path: str, to_state: str, dry_run: bool) -> List[str]:
    done: List[str] = []
    for row in iter_csv_rows(path):
        Slug = row["Slug"]
        vurl = row.get("url") or None
        try:
            pid = transition_single(nc, Slug, to_state, validate_url=vurl, dry_run=dry_run)
            done.append(pid)
            time.sleep(0.2)  # API rate 보호
        except Exception as e:
            logger.error("전이 실패(Slug=%s): %s", Slug, e)
            send_slack(f"전이 실패: {Slug} → {to_state} ({e})")
    return done


# ===== CLI =====
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="블로그 상태 전이 자동화 (Slug/Status 대문자 전용)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--Slug", help="단일 Slug")
    g.add_argument("--bulk", help="CSV 경로(Slug,url)")
    p.add_argument("--to", required=True, choices=list(ALLOWED_STATES), help="전이 목표 상태")
    p.add_argument("--validate-url", help="전이 전 URL 검증(200 + 본문>100자)")
    p.add_argument("--dry-run", action="store_true", help="실제 업데이트 없이 점검만")
    p.add_argument("--verbose", action="store_true", help="디버그 로그 활성화")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)
    cfg = load_cfg()
    nc = NotionClient(cfg)
    try:
        if args.Slug:
            transition_single(nc, args.Slug, args.to, validate_url=args.validate_url, dry_run=args.dry_run)
        else:
            transition_bulk(nc, args.bulk, args.to, dry_run=args.dry_run)
        return 0
    except KeyboardInterrupt:
        logger.error("중단됨")
        return 130
    except Exception as e:
        logger.exception("치명적 오류: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
