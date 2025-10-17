# -*- coding: utf-8 -*-
"""
리포트용 Notion 데이터베이스 생성기(검증 강화판)
- 부모는 반드시 '일반 페이지(Page)' 여야 하며 DB를 부모로 사용할 수 없음.
.env: NOTION_TOKEN, NOTION_PARENT_PAGE
사용:
  python scripts/create_reports_db.py
"""
import json
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("NOTION_TOKEN", "").strip()
PARENT_ID = os.getenv("NOTION_PARENT_PAGE", "").strip()
BASE = "https://api.notion.com/v1"
HEAD = {"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

def _get(url: str):
    return requests.get(url, headers=HEAD, timeout=15)

def _is_database(notion_id: str) -> bool:
    r = _get(f"{BASE}/databases/{notion_id}")
    return r.status_code == 200

def _is_page(notion_id: str) -> bool:
    r = _get(f"{BASE}/pages/{notion_id}")
    return r.status_code == 200

def main() -> None:
    if not TOKEN or not PARENT_ID:
        print("NOTION_TOKEN 또는 NOTION_PARENT_PAGE 누락", file=sys.stderr)
        sys.exit(1)

    # 친절한 검증: DB ID를 넣었는지 확인
    if _is_database(PARENT_ID):
        print(
            "오류: NOTION_PARENT_PAGE에는 '페이지(Page) ID'를 넣어야 합니다.\n"
            "현재 값은 '데이터베이스 ID'로 보입니다. Page를 하나 만든 뒤 링크에서 32자 ID를 추출해 넣어주세요.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not _is_page(PARENT_ID):
        print("오류: NOTION_PARENT_PAGE가 유효한 페이지가 아닙니다(권한 또는 ID 확인).", file=sys.stderr)
        sys.exit(3)

    body = {
        "parent": {"type": "page_id", "page_id": PARENT_ID},
        "title": [{"type": "text", "text": {"content": "Reports"}}],
        "properties": {
            "Name": {"title": {}},
            "PeriodStart": {"date": {}},
            "PeriodEnd": {"date": {}},
            "PublishedCount": {"number": {"format": "number"}},
            "SuccessCount": {"number": {"format": "number"}},
            "SuccessRate": {"number": {"format": "percent"}},
            "AvgLastRunMs": {"number": {"format": "number"}},
        },
    }
    r = requests.post(f"{BASE}/databases", headers=HEAD, data=json.dumps(body), timeout=15)
    if r.status_code not in (200, 201):
        print(f"DB 생성 실패: {r.status_code} {r.text[:300]}", file=sys.stderr)
        sys.exit(4)
    db_id = r.json().get("id", "").replace("-", "")
    print(f"리포트 DB 생성 완료. ID(32자): {db_id}")

if __name__ == "__main__":
    main()
