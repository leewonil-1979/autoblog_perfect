# -*- coding: utf-8 -*-
"""
로컬 OAuth2 도우미 (WordPress.com)
1) .env에 CLIENT_ID/SECRET/REDIRECT_URI 설정
2) 실행 후 출력되는 인증 URL을 브라우저에서 열고 승인
3) 콜백이 /callback 으로 오면 토큰 교환하여 콘솔/파일 출력
옵션: 특정 blogs.id에 토큰을 저장하려면 --blog-id 1 옵션 사용
"""
from __future__ import annotations
import os
import json
import argparse
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from fastapi import FastAPI, Request
import uvicorn
from dotenv import load_dotenv
import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wpcom_oauth")
load_dotenv()

CLIENT_ID = os.getenv("WPCOM_CLIENT_ID")
CLIENT_SECRET = os.getenv("WPCOM_CLIENT_SECRET")
REDIRECT_URI = os.getenv("WPCOM_REDIRECT_URI", "http://localhost:8787/callback")
TOKEN_URL = "https://public-api.wordpress.com/oauth2/token"
AUTH_URL = "https://public-api.wordpress.com/oauth2/authorize"

app = FastAPI()
args_ns = None

def _save_tokens_to_db(blog_id: int, site: str, access_token: str, refresh_token: str, expires_in: int) -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL 미설정: DB 저장 건너뜀")
        return
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    cur.execute(
        """
        UPDATE blogs
        SET wpcom_site=%s, wpcom_access_token=%s, wpcom_refresh_token=%s, wpcom_token_expires_at=%s, platform='wpcom'
        WHERE id=%s
        """,
        (site, access_token, refresh_token, expires_at, blog_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    logger.info("DB 저장 완료: blogs.id=%s", blog_id)

@app.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return {"error": "no_code"}
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    res = requests.post(TOKEN_URL, data=data, timeout=20)
    res.raise_for_status()
    tok = res.json()
    # { access_token, token_type, blog_id?, scope, expires_in, refresh_token }
    logger.info("토큰 발급 성공: %s", {k: tok[k] for k in tok.keys() if k != "access_token"})
    # 옵션: 블로그 테이블에 저장
    if args_ns and args_ns.blog_id and args_ns.site:
        _save_tokens_to_db(args_ns.blog_id, args_ns.site, tok["access_token"], tok.get("refresh_token", ""), tok.get("expires_in", 0))
    # 로컬 백업
    os.makedirs("secrets", exist_ok=True)
    with open("secrets/wpcom_tokens.json", "w", encoding="utf-8") as f:
        json.dump(tok, f, ensure_ascii=False, indent=2)
    return {"status": "ok", "message": "tokens saved to secrets/wpcom_tokens.json"}

def main():
    global args_ns
    parser = argparse.ArgumentParser()
    parser.add_argument("--blog-id", type=int, help="blogs.id (저장 대상)")
    parser.add_argument("--site", type=str, help="wpcom site 예: won201.wordpress.com")
    parser.add_argument("--port", type=int, default=8787)
    args_ns = parser.parse_args()

    if not CLIENT_ID or not CLIENT_SECRET:
        raise SystemExit("WPCOM_CLIENT_ID/SECRET 를 .env에 설정하세요")

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "global",
    }
    url = f"{AUTH_URL}?{urlencode(params)}"
    print("\n[브라우저에서 아래 URL 열고 승인하세요]\n", url, "\n")
    uvicorn.run(app, host="0.0.0.0", port=args_ns.port, log_level="info")

if __name__ == "__main__":
    main()
