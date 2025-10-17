# -*- coding: utf-8 -*-
"""
주간 리포트 자동 생성(권한 안전 폴백 최종판)
- 지난 기간(기본 7일) 집계 → 저장 우선순위:
  (1) NOTION_DB_REPORTS DB
  (2) NOTION_PARENT_PAGE
  (3) 콘텐츠 로그 DB의 부모 페이지(page_id)
  (4) 콘텐츠 로그 DB의 '첫 번째 행 페이지' 아래에 생성

옵션:
  --days, --start, --end, --export-csv, --dry-run, --verbose
필수: pip install python-dotenv requests
.env: NOTION_TOKEN, NOTION_DB_CONTENT_LOG, (선택) NOTION_DB_REPORTS, NOTION_PARENT_PAGE
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# ============== 설정/로깅 ==============
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
NET_TIMEOUT = int(os.getenv("NET_TIMEOUT", "15"))
NET_RETRIES = int(os.getenv("NET_RETRIES", "3"))
SUCCESS_STATUSES = [s.strip() for s in os.getenv("SUCCESS_STATUSES", "SUCCESS").split(",") if s.strip()]
PUBLISHED_STATUSES = [s.strip() for s in os.getenv("PUBLISHED_STATUSES", "PUBLISHED,SUCCESS").split(",") if s.strip()]

# ============== 공통 유틸 ==============
def _retry(method: str, url: str, **kwargs) -> requests.Response:
    last_err: Optional[Exception] = None
    for i in range(1, NET_RETRIES + 1):
        try:
            r = requests.request(method, url, timeout=NET_TIMEOUT, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                logger.warning("재시도 필요 status=%s attempt=%s url=%s", r.status_code, i, url)
                continue
            return r
        except requests.RequestException as e:
            last_err = e
            logger.warning("네트워크 예외 attempt=%s err=%s", i, e)
    if last_err:
        raise last_err
    raise RuntimeError("요청 실패(원인 불명)")

def _clamp_date_str(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    datetime.strptime(s, "%Y-%m-%d")  # 형식 검증
    return s

@dataclass
class ReportResult:
    total: int
    published: int
    success: int
    avg_last_ms: float
    start: str
    end: str

# ============== Notion 클라이언트 ==============
class Notion:
    def __init__(self, token: str):
        self.base = "https://api.notion.com/v1"
        self.h = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    # ---- DB 메타/부모 ----
    def get_db(self, db_id: str) -> Dict[str, Any]:
        r = _retry("GET", f"{self.base}/databases/{db_id}", headers=self.h)
        if r.status_code != 200:
            raise RuntimeError(f"DB 조회 실패: {r.status_code} {r.text[:200]}")
        return r.json()

    def get_db_parent_page_id(self, db_id: str) -> Optional[str]:
        meta = self.get_db(db_id)
        parent = meta.get("parent") or {}
        if parent.get("type") == "page_id":
            return parent.get("page_id")
        return None  # workspace 등은 사용하지 않음(권한 이슈)

    def has_property(self, db_id: str, prop: str) -> bool:
        try:
            meta = self.get_db(db_id)
            return prop in (meta.get("properties") or {})
        except Exception:
            return False

    # ---- 쿼리(페이지네이션) ----
    def query(self, db_id: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = f"{self.base}/databases/{db_id}/query"
        results: List[Dict[str, Any]] = []
        while True:
            r = _retry("POST", url, headers=self.h, data=json.dumps(payload))
            if r.status_code != 200:
                raise RuntimeError(f"Notion query 실패: {r.status_code} {r.text[:200]}")
            data = r.json()
            results += data.get("results", [])
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data.get("next_cursor")
        return results

    # ---- 쓰기 ----
    def create_in_db(self, db_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        r = _retry("POST", f"{self.base}/pages", headers=self.h,
                   data=json.dumps({"parent": {"database_id": db_id}, "properties": properties}))
        if r.status_code not in (200, 201):
            raise RuntimeError(f"리포트 생성(DB) 실패: {r.status_code} {r.text[:300]}")
        return r.json()

    def create_child_page(self, parent_page_id: str, title: str,
                         properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """일반 페이지의 자식 페이지 생성 (title만 사용)"""
        payload = {
            "parent": {"page_id": parent_page_id},
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            }
        }

        # 추가 속성이 있다면 children 블록으로 내용 추가
        if properties:
            children = self._build_content_blocks(properties)
            if children:
                payload["children"] = children

        r = _retry("POST", f"{self.base}/pages", headers=self.h,
                   data=json.dumps(payload))
        if r.status_code not in (200, 201):
            raise RuntimeError(f"하위 페이지 생성 실패: {r.status_code} {r.text[:300]}")
        return r.json()

    def _build_content_blocks(self, props: Dict[str, Any]) -> List[Dict[str, Any]]:
        """속성을 페이지 콘텐츠 블록으로 변환"""
        blocks = []

        # 기간 정보
        if "PeriodStart" in props and "PeriodEnd" in props:
            start = props["PeriodStart"].get("date", {}).get("start", "")
            end = props["PeriodEnd"].get("date", {}).get("start", "")
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": f"기간: {start} ~ {end}"}}]
                }
            })

        # 통계 정보를 테이블 형태로
        stats = []
        if "PublishedCount" in props:
            stats.append(f"• 발행 건수: {props['PublishedCount'].get('number', 0)}")
        if "SuccessCount" in props:
            stats.append(f"• 성공 건수: {props['SuccessCount'].get('number', 0)}")
        if "SuccessRate" in props:
            rate = props['SuccessRate'].get('number', 0) * 100
            stats.append(f"• 성공률: {rate:.2f}%")
        if "AvgLastRunMs" in props:
            stats.append(f"• 평균 실행시간: {props['AvgLastRunMs'].get('number', 0):.2f}ms")

        if stats:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(stats)}}]
                }
            })

        return blocks

# ============== 속성 헬퍼 ==============
def _get_prop(page: Dict[str, Any], key: str, kind: str) -> Any:
    try:
        p = page["properties"][key]
        if kind == "select":
            return (p.get("select") or {}).get("name")
        if kind == "number":
            return p.get("number")
        if kind == "date":
            dt = p.get("date") or {}
            return dt.get("start")
    except KeyError:
        return None
    return None

# ============== 집계 ==============
def collect_and_aggregate(n: Notion, src_db: str, start: str, end: str) -> ReportResult:
    """Ts(date) 우선 → 없거나 0건이면 Created time 폴백."""
    logger.info("집계 범위: %s ~ %s (UTC, inclusive)", start, end)

    pages: List[Dict[str, Any]] = []
    if n.has_property(src_db, "Ts"):
        payload = {"filter": {"and": [
            {"property": "Ts", "date": {"on_or_after": start}},
            {"property": "Ts", "date": {"on_or_before": end}},
        ]}, "page_size": 100}
        pages = n.query(src_db, payload)
        logger.info("Ts(date) 기준 조회 결과: %s건", len(pages))

    if not pages:
        payload = {"filter": {"and": [
            {"timestamp": "created_time", "created_time": {"on_or_after": start}},
            {"timestamp": "created_time", "created_time": {"on_or_before": end}},
        ]}, "page_size": 100}
        pages = n.query(src_db, payload)
        logger.info("Created time 기준 조회 결과: %s건", len(pages))

    total = len(pages)
    published = 0
    success = 0
    last_ms_vals: List[float] = []

    pub_set = {s.upper() for s in PUBLISHED_STATUSES}
    suc_set = {s.upper() for s in SUCCESS_STATUSES}

    for pg in pages:
        st = (_get_prop(pg, "Status", "select") or "").upper()
        if st in pub_set:
            published += 1
        if st in suc_set:
            success += 1
        ms = _get_prop(pg, "LastRunMs", "number")
        if isinstance(ms, (int, float)):
            last_ms_vals.append(float(ms))

    avg_ms = round(sum(last_ms_vals) / len(last_ms_vals), 2) if last_ms_vals else 0.0
    success_rate = round((success / total), 4) if total else 0.0

    logger.info("집계 요약: total=%s published=%s success=%s success_rate=%.2f%% avg_ms=%.2f",
                total, published, success, success_rate * 100, avg_ms)
    return ReportResult(total=total, published=published, success=success, avg_last_ms=avg_ms, start=start, end=end)

# ============== 저장/내보내기 ==============
def build_report_props(title: str, rr: ReportResult) -> Dict[str, Any]:
    return {
        "Name": {"title": [{"type": "text", "text": {"content": title}}]},
        "PeriodStart": {"date": {"start": rr.start}},
        "PeriodEnd": {"date": {"start": rr.end}},
        "PublishedCount": {"number": rr.published},
        "SuccessCount": {"number": rr.success},
        "SuccessRate": {"number": round((rr.success / rr.total), 4) if rr.total else 0.0},
        "AvgLastRunMs": {"number": rr.avg_last_ms},
    }

def export_csv(path: str, rr: ReportResult) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    headers = ["start", "end", "total", "published", "success", "success_rate", "avg_last_ms"]
    success_rate = round((rr.success / rr.total), 4) if rr.total else 0.0
    row = [rr.start, rr.end, rr.total, rr.published, rr.success, success_rate, rr.avg_last_ms]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(headers); w.writerow(row)
    logger.info("CSV 저장: %s", path)

# ============== CLI/메인 ==============
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="주간(또는 기간) 리포트 생성")
    p.add_argument("--days", type=int, default=7, help="오늘 기준 과거 N일(기본 7)")
    p.add_argument("--start", type=str, help="YYYY-MM-DD (UTC)")
    p.add_argument("--end", type=str, help="YYYY-MM-DD (UTC)")
    p.add_argument("--export-csv", type=str, help="CSV 저장 경로")
    p.add_argument("--dry-run", action="store_true", help="Notion에 쓰지 않고 콘솔/CSV만")
    p.add_argument("--verbose", action="store_true", help="로그 레벨 DEBUG")
    return p.parse_args()

def main() -> None:
    args = parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    token = os.getenv("NOTION_TOKEN", "").strip()
    src_db = os.getenv("NOTION_DB_CONTENT_LOG", "").strip()
    rep_db = os.getenv("NOTION_DB_REPORTS", "").strip()
    parent_page = os.getenv("NOTION_PARENT_PAGE", "").strip()

    if not token or not src_db:
        logger.error("NOTION_TOKEN 또는 NOTION_DB_CONTENT_LOG 누락")
        sys.exit(1)

    # 기간 계산
    if args.start:
        start_s = _clamp_date_str(args.start)
        end_s = _clamp_date_str(args.end) or date.today().isoformat()
    else:
        today = date.today()
        start_s = (today - timedelta(days=max(args.days, 1))).isoformat()
        end_s = today.isoformat()

    n = Notion(token)
    rr = collect_and_aggregate(n, src_db, start_s, end_s)
    title = f"Weekly Report {rr.start}~{rr.end}"

    if args.export_csv:
        export_csv(args.export_csv, rr)
    if args.dry_run:
        logger.info("드라이런: Notion 기록 생략")
        return

    db_props = build_report_props(title, rr)

    # 1) 리포트 DB가 있으면 DB에 생성
    if rep_db:
        try:
            created = n.create_in_db(rep_db, db_props)
            logger.info("✅ 리포트 생성(DB): %s", created.get("id"))
            return
        except RuntimeError as e:
            logger.warning("리포트 DB 생성 실패: %s", e)

    # 2) 지정 Parent Page 시도
    if parent_page:
        try:
            created = n.create_child_page(parent_page, title, db_props)
            logger.info("✅ 리포트 생성(지정 Parent Page): %s", created.get("id"))
            return
        except RuntimeError as e:
            logger.warning("지정 Parent Page 생성 실패: %s", e)

    # 3) 콘텐츠 로그 DB의 부모 페이지가 있으면 사용
    fallback_parent = n.get_db_parent_page_id(src_db)
    if fallback_parent:
        try:
            created = n.create_child_page(fallback_parent, title, db_props)
            logger.info("✅ 리포트 생성(DB의 부모 페이지): %s", created.get("id"))
            return
        except RuntimeError as e:
            logger.warning("DB 부모 페이지 생성 실패: %s", e)

    # 4) 마지막 폴백: 로그만 남기고 실패
    logger.error("❌ 리포트를 생성할 위치를 찾을 수 없습니다.")
    logger.error("해결 방법:")
    logger.error("  1. NOTION_DB_REPORTS 설정 (권장)")
    logger.error("  2. NOTION_PARENT_PAGE 설정 후 Integration 공유 확인")
    logger.error("  3. 콘텐츠 로그 DB가 페이지 안에 있는지 확인")
    sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("실패: %s", e)
        sys.exit(1)