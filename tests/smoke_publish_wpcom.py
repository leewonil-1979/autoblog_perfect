# -*- coding: utf-8 -*-
"""
WP.com 스모크 발행 테스트
- blogs.id(BLOG_ID)의 wpcom_site / wpcom_access_token을 DB에서 읽어서
  https://public-api.wordpress.com/wp/v2/sites/{site}/posts 로 글 1건 발행
"""
from __future__ import annotations
import os
import sys
import json
import psycopg2
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BLOG_ID = int(os.getenv("TEST_BLOG_ID", "3"))  # 필요시 .env에서 TEST_BLOG_ID=3 지정
DB_URL = os.getenv("DATABASE_URL")
assert DB_URL, "DATABASE_URL 미설정"

def get_blog_cred(blog_id: int):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT wpcom_site, wpcom_access_token
        FROM blogs WHERE id=%s AND platform='wpcom'
    """, (blog_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row or not row[0] or not row[1]:
        raise SystemExit(f"blogs.id={blog_id} 의 wpcom_site/access_token 누락")
    return {"site": row[0], "token": row[1]}

def publish(site: str, token: str, title: str, html: str):
    url = f"https://public-api.wordpress.com/wp/v2/sites/{site}/posts"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"title": title, "content": html, "status": "publish"}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        print("HTTP ERROR:", r.status_code, r.text[:500])
        raise
    return r.json()

def main():
    cred = get_blog_cred(BLOG_ID)
    title = f"[스모크] 자동 발행 테스트 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    body = "<p>WP.com API를 통한 자동 발행 스모크 테스트입니다.</p><p>정상 노출되면 성공입니다.</p>"
    print("Posting to:", cred["site"])
    res = publish(cred["site"], cred["token"], title, body)
    print("OK\n", json.dumps({"id": res.get("id"), "link": res.get("link")}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
