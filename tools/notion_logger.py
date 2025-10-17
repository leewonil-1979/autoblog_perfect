# -*- coding: utf-8 -*-
# 목적: 발행 메타데이터를 Notion DB에 1행으로 기록
from __future__ import annotations
import os, requests, time
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
NOTION_DB = os.getenv("NOTION_DB_CONTENT_LOG", "").strip()

def _headers() -> Dict[str,str]:
    if not NOTION_TOKEN: raise RuntimeError("NOTION_TOKEN 누락")
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

def log_content(meta: Dict[str, Any]) -> str:
    """meta: {title, slug, url, site, status, ts, keywords(list)}"""
    if not NOTION_DB: raise RuntimeError("NOTION_DB_CONTENT_LOG 누락")
    title = meta.get("title","Untitled")
    keywords = ", ".join(meta.get("keywords", [])) if isinstance(meta.get("keywords"), list) else (meta.get("keywords") or "")
    payload = {
        "parent": {"database_id": NOTION_DB},
        "properties": {
            "Title": {"title": [{"text": {"content": title}}]},
            "Slug": {"rich_text": [{"text": {"content": meta.get("slug","")}}]},
            "URL": {"url": meta.get("url")},
            "Site": {"select": {"name": meta.get("site","wp")}},
            "Status": {"select": {"name": meta.get("status","SUCCESS")}},
            "PublishedAt": {"date": {"start": meta.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%S")}},
            "Keywords": {"rich_text": [{"text": {"content": keywords}}]},
        },
    }
    r = requests.post("https://api.notion.com/v1/pages", headers=_headers(), json=payload, timeout=15)
    if r.status_code >= 300:
        raise RuntimeError(f"Notion 기록 실패: {r.status_code} {r.text}")
    return r.json().get("id","")
