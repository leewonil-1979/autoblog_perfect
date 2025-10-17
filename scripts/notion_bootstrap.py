# -*- coding: utf-8 -*-
"""
콘텐츠 로그 DB 스키마 부트스트랩(수정판):
- 기존 title 속성 이름을 감지하여 사용, 새 title 생성 시도 금지
- 누락 속성만 추가
- Status(select) 옵션 병합 추가

필수: pip install python-dotenv requests
.env: NOTION_TOKEN, NOTION_DB_CONTENT_LOG
"""
import json
import os
import sys
from typing import Dict, Any

import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("NOTION_TOKEN", "").strip()
DB_ID = os.getenv("NOTION_DB_CONTENT_LOG", "").strip()
BASE = "https://api.notion.com/v1"
HEAD = {"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

# title은 API로 새로 만들 수 없음. 여기선 title 제외.
REQUIRED_NO_TITLE = {
    "Slug": {"type": "rich_text", "rich_text": {}},
    "URL": {"type": "url", "url": {}},
    "Status": {"type": "select", "select": {"options": []}},  # 옵션은 아래에서 병합
    "Keywords": {"type": "multi_select", "multi_select": {}},
    "Ts": {"type": "date", "date": {}},
    "LastRunMs": {"type": "number", "number": {"format": "number"}},
    "SlackTS": {"type": "rich_text", "rich_text": {}},
    "Thumbnail": {"type": "files", "files": {}},
}
NEEDED_STATUS = [{"name": "DRAFT"}, {"name": "PUBLISHED"}, {"name": "SUCCESS"}, {"name": "FAILED"}]

def main() -> None:
    if not TOKEN or not DB_ID:
        print("NOTION_TOKEN/NOTION_DB_CONTENT_LOG 누락", file=sys.stderr)
        sys.exit(1)

    # DB 메타 조회
    r = requests.get(f"{BASE}/databases/{DB_ID}", headers=HEAD, timeout=15)
    if r.status_code != 200:
        print(f"DB 조회 실패: {r.status_code} {r.text[:200]}", file=sys.stderr)
        sys.exit(1)
    db = r.json()
    props: Dict[str, Any] = db.get("properties", {})

    # 현재 title 속성 이름 확인(참고용)
    title_name = next((n for n, meta in props.items() if meta.get("type") == "title"), None)
    if not title_name:
        print("경고: title 속성을 찾지 못했습니다. Notion UI에서 Name과 같은 title 속성이 반드시 1개 존재해야 합니다.", file=sys.stderr)

    # 누락 속성 모으기
    missing: Dict[str, Any] = {k: v for k, v in REQUIRED_NO_TITLE.items() if k not in props}

    # Status 옵션 병합
    if "Status" in props and props["Status"].get("type") == "select":
        existing = props["Status"]["select"].get("options", [])
        existing_names = {o.get("name") for o in existing}
        add_opts = [o for o in NEEDED_STATUS if o["name"] not in existing_names]
        if add_opts:
            body = {"properties": {"Status": {"select": {"options": existing + add_opts}}}}
            r3 = requests.patch(f"{BASE}/databases/{DB_ID}", headers=HEAD, data=json.dumps(body), timeout=15)
            if r3.status_code != 200:
                print(f"Status 옵션 추가 실패: {r3.status_code} {r3.text[:200]}", file=sys.stderr)
                sys.exit(1)
            print(f"Status 옵션 추가: {', '.join(o['name'] for o in add_opts)}")

    # 누락 속성 추가
    if missing:
        body = {"properties": missing}
        r2 = requests.patch(f"{BASE}/databases/{DB_ID}", headers=HEAD, data=json.dumps(body), timeout=15)
        if r2.status_code != 200:
            print(f"스키마 업데이트 실패: {r2.status_code} {r2.text[:200]}", file=sys.stderr)
            sys.exit(1)
        print(f"추가된 속성: {', '.join(missing.keys())}")
    else:
        print("추가할 속성 없음: 스키마 OK")

if __name__ == "__main__":
    main()
