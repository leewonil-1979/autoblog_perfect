# -*- coding: utf-8 -*-
"""
Notion 통합 진단 스크립트
- 토큰 유효성(/users/me)
- Parent Page/DB 접근성
- DB 스키마 필수 속성 존재 여부 확인
- 상세 로그를 콘솔 + logs/notion_diag.log 에 기록

필수: pip install requests python-dotenv
환경변수(.env):
  NOTION_TOKEN=secret_xxx
  NOTION_PARENT_PAGE=<선택: 새 DB를 만들 parent page ID>
  NOTION_DB_CONTENT_LOG=<선택: 기존 DB ID>
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Set

import requests
from requests.adapters import HTTPAdapter, Retry
from dotenv import load_dotenv

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "notion_diag.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("notion_diag")

NOTION_VERSION = "2022-06-28"
REQ_TIMEOUT = 15

REQUIRED_PROPS: Set[str] = {
    "title", "slug", "status", "url", "site", "keywords",
    "avg_ms", "created_at", "updated_at", "published_at", "succeeded_at"
}

def make_session() -> requests.Session:
    sess = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST", "PATCH"])
    )
    sess.mount("https://", HTTPAdapter(max_retries=retry))
    return sess

def headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def check_token(sess: requests.Session, token: str) -> bool:
    url = "https://api.notion.com/v1/users/me"
    r = sess.get(url, headers=headers(token), timeout=REQ_TIMEOUT)
    if r.status_code == 200:
        logger.info("토큰 유효성 OK: /users/me 접근 성공")
        return True
    logger.error("토큰 유효성 실패: %s %s", r.status_code, r.text[:500])
    return False

def get_db_schema(sess: requests.Session, token: str, db_id: str) -> Optional[Dict[str, Any]]:
    url = f"https://api.notion.com/v1/databases/{db_id}"
    r = sess.get(url, headers=headers(token), timeout=REQ_TIMEOUT)
    if r.status_code == 200:
        return r.json()
    logger.error("DB 읽기 실패: %s %s", r.status_code, r.text[:500])
    return None

def get_page(sess: requests.Session, token: str, page_id: str) -> bool:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    r = sess.get(url, headers=headers(token), timeout=REQ_TIMEOUT)
    if r.status_code == 200:
        logger.info("Parent Page 접근 OK")
        return True
    logger.error("Parent Page 접근 실패: %s %s", r.status_code, r.text[:500])
    return False

def main():
    load_dotenv(override=False)
    token = os.getenv("NOTION_TOKEN", "")
    parent_page = os.getenv("NOTION_PARENT_PAGE", "")
    db_id = os.getenv("NOTION_DB_CONTENT_LOG", "")

    if not token:
        logger.error("환경변수 누락: NOTION_TOKEN")
        sys.exit(2)

    sess = make_session()

    # 1) 토큰
    if not check_token(sess, token):
        sys.exit(3)

    # 2) Parent Page(선택)
    if parent_page:
        get_page(sess, token, parent_page)
    else:
        logger.info("NOTION_PARENT_PAGE 미설정(신규 DB 생성이 필요 없다면 무시 가능)")

    # 3) 기존 DB(선택)
    if db_id:
        schema = get_db_schema(sess, token, db_id)
        if schema:
            props: Dict[str, Any] = schema.get("properties", {})
            have = set(props.keys())
            missing = REQUIRED_PROPS - have
            logger.info("DB 속성 수: %d / 필수 누락: %s", len(have), ", ".join(sorted(missing)) or "없음")
            # 상태 속성의 옵션 유효성도 힌트 제공
            status_prop = props.get("status", {})
            if status_prop.get("type") == "status":
                names = [o.get("name") for o in (status_prop.get("status", {}).get("options") or [])]
                ned = {"DRAFT", "PUBLISHED", "SUCCESS", "FAILED"}
                if not ned.issubset(set(names)):
                    logger.warning("status 옵션 불완전: 현재=%s, 필요=%s", names, list(ned))
            else:
                logger.warning("status 속성이 status 타입이 아닙니다. 현재 타입=%s", status_prop.get("type"))
    else:
        logger.info("NOTION_DB_CONTENT_LOG 미설정(신규 DB 생성 예정이라면 정상)")

    logger.info("진단 완료. 상세 로그: %s", LOG_DIR / "notion_diag.log")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.error("중단됨")
        sys.exit(130)
    except Exception as e:
        logger.exception("치명적 오류: %s", e)
        sys.exit(1)
