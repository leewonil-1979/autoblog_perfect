# check_notion_schema.py
from dotenv import load_dotenv
import os, requests, json

load_dotenv()
token = os.getenv("NOTION_TOKEN")
db_id = os.getenv("NOTION_DB_CONTENT_LOG")

if not token or not db_id:
    raise SystemExit("환경변수 확인: NOTION_TOKEN / NOTION_DB_CONTENT_LOG 누락")

headers = {
    "Authorization": f"Bearer {token}",
    "Notion-Version": "2022-06-28",
}

r = requests.get(f"https://api.notion.com/v1/databases/{db_id}", headers=headers, timeout=15)
if r.status_code != 200:
    raise SystemExit(f"조회 실패({r.status_code}): {r.text[:300]}")

props = r.json().get("properties", {})
print(json.dumps({k: v.get("type") for k, v in props.items()}, ensure_ascii=False, indent=2))
