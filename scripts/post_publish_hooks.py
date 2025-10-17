# -*- coding: utf-8 -*-
"""
발행 후 훅(통합·단일 파일):
- Slack(Webhook→Bot 폴백, 멘션, 스레드, 상태 변경 댓글), 썸네일 업로드
- Notion 업서트(Slug/URL 키) + SlackTS/LastRunMs/ErrorMsg/Thumbnail 동기화
- 상태 전이 전용 모드(--status-update-only, --status)
- 재시도/타임아웃/지표 로깅

필수:
  pip install python-dotenv requests

환경변수(요약):
  # 입력 메타(필수)
  POST_TITLE, POST_SLUG, POST_URL, POST_STATUS
  # 선택 메타
  POST_KEYWORDS, POST_THUMBNAIL  # 파일 경로 또는 외부 URL(둘 다 허용)

  # Slack
  SLACK_WEBHOOK_URL, SLACK_BOT_TOKEN, SLACK_CHANNEL(#blog-alert 기본), SLACK_THREAD_TS(선택)
  ALERT_MENTION=@channel   # 오류 시 멘션

  # Notion
  NOTION_TOKEN=ntn_...
  NOTION_DB_CONTENT_LOG=<32자 hex>
  NOTION_INDEX_PROPERTY=Slug  # 또는 URL

  # 네트워크
  NET_TIMEOUT=15
  NET_RETRIES=3

CLI:
  # 일반 실행(업서트 + Slack + 썸네일 + 지표)
  python scripts/post_publish_hooks.py

  # 상태만 갱신(기존 Row 필요) + Slack 스레드에 '상태 변경' 댓글
  python scripts/post_publish_hooks.py --status-update-only --status SUCCESS

  # Notion 링크에서 32자 ID 추출
  python scripts/post_publish_hooks.py --parse-id "https://www.notion.so/workspace/DB-xxxxx?p=..."
"""
from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv

# =========================
# 초기화/설정
# =========================
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# 입력 메타 (필수)
POST_TITLE = os.getenv("POST_TITLE", "").strip()
POST_SLUG = os.getenv("POST_SLUG", "").strip()
POST_URL = os.getenv("POST_URL", "").strip()
POST_STATUS = os.getenv("POST_STATUS", "").strip()  # e.g., SUCCESS/FAILED/DRAFT
POST_KEYWORDS = os.getenv("POST_KEYWORDS", "").strip()

# 썸네일: 파일 경로 또는 외부 URL 모두 허용
POST_THUMBNAIL = os.getenv("POST_THUMBNAIL", "").strip()

# Slack
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "").strip()
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "#blog-alert").strip()
SLACK_THREAD_TS = os.getenv("SLACK_THREAD_TS", "").strip()  # 기존 스레드에 붙이고 싶을 때
ALERT_MENTION = os.getenv("ALERT_MENTION", "").strip()  # 예: @channel 또는 <@U123456>

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
NOTION_DB_ID = os.getenv("NOTION_DB_CONTENT_LOG", "").strip()
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
NOTION_INDEX_PROPERTY = os.getenv("NOTION_INDEX_PROPERTY", "Slug").strip()  # 업서트 키

# 네트워크 공통
NET_TIMEOUT = int(os.getenv("NET_TIMEOUT", "15"))
NET_RETRIES = int(os.getenv("NET_RETRIES", "3"))

ISO8601 = "%Y-%m-%dT%H:%M:%S%z"

# =========================
# 유틸/검증/지표
# =========================
def _status_color(status: str) -> str:
    s = (status or "").upper()
    if s in {"FAILED", "ERROR"}:
        return "#E01E5A"  # red
    if s in {"DRAFT", "PENDING"}:
        return "#ECB22E"  # yellow
    if s in {"SUCCESS", "PUBLISHED", "OK"}:
        return "#2EB67D"  # green
    return "#9CA3AF"  # gray

def _now_ms() -> int:
    return int(time.time() * 1000)

def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime(ISO8601)

def validate_inputs() -> Dict[str, str]:
    missing = [k for k, v in {
        "POST_TITLE": POST_TITLE,
        "POST_SLUG": POST_SLUG,
        "POST_URL": POST_URL,
        "POST_STATUS": POST_STATUS,
    }.items() if not v]
    if missing:
        raise ValueError(f"필수 환경변수 누락: {', '.join(missing)}")
    return {
        "title": POST_TITLE,
        "slug": POST_SLUG,
        "url": POST_URL,
        "status": POST_STATUS,
        "keywords": POST_KEYWORDS,
    }

def _retry_request(method: str, url: str, **kwargs) -> requests.Response:
    """429/5xx 재시도."""
    last_err = None
    for attempt in range(1, NET_RETRIES + 1):
        try:
            r = requests.request(method, url, timeout=NET_TIMEOUT, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                logging.warning("재시도 필요 status=%s attempt=%s url=%s", r.status_code, attempt, url)
                time.sleep(min(1.5 * attempt, 6))
                continue
            return r
        except requests.RequestException as e:
            last_err = e
            logging.warning("네트워크 예외 attempt=%s err=%s", attempt, e)
            time.sleep(min(1.5 * attempt, 6))
    if last_err:
        raise last_err
    raise RuntimeError("요청 실패(알 수 없음)")

# =========================
# Slack
# =========================
def _slack_blocks(meta: Dict[str, str]) -> list:
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*새 글 발행* • *{meta['status']}*\n<{meta['url']}|{meta['title']}>"}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"`{meta['slug']}`"},
                {"type": "mrkdwn", "text": (meta.get("keywords") or "")},
            ],
        },
    ]

def _with_mention(text: str, is_error: bool) -> str:
    # 오류/실패 케이스에만 멘션을 붙임(알림 피로도 감소)
    if not is_error or not ALERT_MENTION:
        return text
    return f"{ALERT_MENTION} {text}"

def send_slack_webhook(meta: Dict[str, str], is_error: bool = False) -> Tuple[bool, Optional[str]]:
    """Slack Incoming Webhook 전송(스레드 ts 반환 불가)."""
    if not SLACK_WEBHOOK_URL:
        return (False, None)
    payload = {
        "text": _with_mention(f"새 글 발행: <{meta['url']}|{meta['title']}>", is_error),
        "blocks": _slack_blocks(meta),
        "attachments": [{"color": _status_color(meta.get("status", "")), "text": f"status={meta.get('status', '')}"}],
    }
    t0 = _now_ms()
    try:
        resp = _retry_request("POST", SLACK_WEBHOOK_URL, json=payload)
        logging.info("Slack Webhook time_ms=%s status=%s", _now_ms() - t0, resp.status_code)
        return (resp.status_code == 200, None)
    except Exception as e:
        logging.warning("Slack Webhook 예외: %s", e)
        return (False, None)

def send_slack_bot(meta: Dict[str, str], is_error: bool = False, thread_ts: Optional[str] = None, text_override: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Slack Bot(chat.postMessage) 전송. 성공 시 ts 반환 → 스레드 고정에 사용."""
    if not SLACK_BOT_TOKEN:
        return (False, None)
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    data = {
        "channel": SLACK_CHANNEL,
        "text": _with_mention(text_override or f"새 글 발행: {meta['title']}", is_error),
        "blocks": json.dumps(_slack_blocks(meta), ensure_ascii=False),
        "attachments": json.dumps(
            [{"color": _status_color(meta.get("status", "")), "text": f"status={meta.get('status', '')}"}],
            ensure_ascii=False,
        ),
    }
    if thread_ts or SLACK_THREAD_TS:
        data["thread_ts"] = thread_ts or SLACK_THREAD_TS
    t0 = _now_ms()
    try:
        resp = _retry_request("POST", "https://slack.com/api/chat.postMessage", headers=headers, data=data)
        j = resp.json()
        logging.info("Slack Bot time_ms=%s ok=%s", _now_ms() - t0, j.get("ok"))
        if not j.get("ok"):
            return (False, None)
        return (True, j.get("ts"))
    except Exception as e:
        logging.warning("Slack Bot 예외: %s", e)
        return (False, None)

def upload_thumbnail_if_any(channel: str, thread_ts: Optional[str]) -> bool:
    """
    썸네일 업로드(파일 경로일 때만 Slack files.upload).
    외부 URL이면 업로드 생략(메시지 내 링크로 충분).
    """
    if not POST_THUMBNAIL or not os.path.isfile(POST_THUMBNAIL) or not SLACK_BOT_TOKEN:
        return False
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    mime = mimetypes.guess_type(POST_THUMBNAIL)[0] or "application/octet-stream"
    with open(POST_THUMBNAIL, "rb") as f:
        files = {"file": (os.path.basename(POST_THUMBNAIL), f, mime)}
        data = {"channels": channel, "initial_comment": "썸네일 미리보기"}
        if thread_ts:
            data["thread_ts"] = thread_ts
        t0 = _now_ms()
        try:
            resp = _retry_request("POST", "https://slack.com/api/files.upload", headers=headers, data=data, files=files)
            j = resp.json()
            logging.info("Slack Upload time_ms=%s ok=%s", _now_ms() - t0, j.get("ok"))
            return bool(j.get("ok"))
        except Exception as e:
            logging.warning("썸네일 업로드 예외: %s", e)
            return False

# =========================
# Notion (업서트 + SlackTS/LastRunMs/ErrorMsg/Thumbnail 동기화)
# =========================
def _notion_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}

def _assert_notion_env() -> None:
    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN 이 비어 있습니다")
    if not NOTION_DB_ID:
        raise RuntimeError("NOTION_DB_CONTENT_LOG 이 비어 있습니다")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", NOTION_DB_ID):
        raise RuntimeError("NOTION_DB_CONTENT_LOG 는 32자 hex")

def _fetch_db_info() -> Tuple[str, Dict[str, Any]]:
    url = f"{NOTION_API_BASE}/databases/{NOTION_DB_ID}"
    r = _retry_request("GET", url, headers=_notion_headers())
    if r.status_code != 200:
        raise RuntimeError(f"DB 조회 실패({r.status_code}): {r.text[:200]}")
    data = r.json()
    props = data.get("properties", {})
    title_name = next((n for n, meta in props.items() if meta.get("type") == "title"), "Name")
    return title_name, props

def _rt(v: str) -> Dict[str, Any]:
    """rich_text helper(길이 안전)."""
    if not v:
        return {"rich_text": []}
    return {"rich_text": [{"type": "text", "text": {"content": v[:1900]}}]}

def _build_props(
    meta: Dict[str, str],
    title_name: str,
    props_meta: Dict[str, Any],
    slack_ts: Optional[str],
    elapsed_ms: Optional[int],
    err_msg: Optional[str],
) -> Dict[str, Any]:
    """DB에 존재하는 속성만 기록 + 관측/스레드 속성 동기화."""
    slug = meta.get("slug") or ""
    url = meta.get("url") or ""
    status = meta.get("status") or ""
    keywords = [s.strip() for s in (meta.get("keywords") or "").split(",") if s.strip()]

    props: Dict[str, Any] = {title_name: {"title": [{"type": "text", "text": {"content": meta.get("title") or "Untitled"}}]}}
    if "Slug" in props_meta and slug:
        props["Slug"] = {"rich_text": [{"type": "text", "text": {"content": slug}}]}
    if "URL" in props_meta and url:
        props["URL"] = {"url": url}
    if "Status" in props_meta and status:
        props["Status"] = {"select": {"name": status}}
    if "Keywords" in props_meta and keywords:
        props["Keywords"] = {"multi_select": [{"name": k} for k in keywords]}
    if "KeywordsText" in props_meta and keywords:
        props["KeywordsText"] = {"rich_text": [{"type": "text", "text": {"content": ", ".join(keywords)}}]}
    if "Ts" in props_meta:
        props["Ts"] = {"date": {"start": _now_iso_utc()}}
    if "CreatedAt" in props_meta:
        props["CreatedAt"] = {"date": {"start": _now_iso_utc()}}

    # 관측/스레드
    if "SlackTS" in props_meta and slack_ts:
        props["SlackTS"] = _rt(slack_ts)
    if "LastRunMs" in props_meta and elapsed_ms is not None:
        props["LastRunMs"] = {"number": float(elapsed_ms)}
    if "ErrorMsg" in props_meta and err_msg:
        props["ErrorMsg"] = _rt(err_msg)

    return props

def _query_page_by_index(value: str) -> Optional[Dict[str, Any]]:
    """Slug 또는 URL 등 인덱스 속성으로 페이지 검색 → 첫 결과 반환."""
    if not value:
        return None
    url = f"{NOTION_API_BASE}/databases/{NOTION_DB_ID}/query"
    if NOTION_INDEX_PROPERTY == "URL":
        body = {"filter": {"property": "URL", "url": {"equals": value}}, "page_size": 1}
    else:
        body = {"filter": {"property": NOTION_INDEX_PROPERTY, "rich_text": {"equals": value}}, "page_size": 1}

    for attempt in range(NET_RETRIES):
        t0 = _now_ms()
        r = _retry_request("POST", url, headers=_notion_headers(), json=body)
        logging.info("Notion Query time_ms=%s status=%s", _now_ms() - t0, r.status_code)
        if r.status_code == 200:
            results = r.json().get("results", [])
            return results[0] if results else None
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(2**attempt, 8))
            continue
        break
    return None

def _page_id_from_item(page: Dict[str, Any]) -> Optional[str]:
    return page.get("id") if page else None

def _get_rich_text_value(page: Dict[str, Any], key: str) -> Optional[str]:
    try:
        arr = page["properties"][key]["rich_text"]
        if arr and isinstance(arr, list):
            return arr[0].get("plain_text") or arr[0].get("text", {}).get("content")
    except KeyError:
        return None
    return None

def _patch_page(page_id: str, properties: Dict[str, Any]) -> bool:
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    body = {"properties": properties}
    for attempt in range(NET_RETRIES):
        t0 = _now_ms()
        r = _retry_request("PATCH", url, headers=_notion_headers(), json=body)
        logging.info("Notion Update time_ms=%s status=%s", _now_ms() - t0, r.status_code)
        if r.status_code == 200:
            return True
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(2**attempt, 8))
            continue
    logging.error("Notion 업데이트 실패: %s", r.text[:500] if r else "no response")
    return False

def _create_page(properties: Dict[str, Any], children: Optional[list] = None) -> Optional[str]:
    url = f"{NOTION_API_BASE}/pages"
    body: Dict[str, Any] = {"parent": {"database_id": NOTION_DB_ID}, "properties": properties}
    if children:
        body["children"] = children
    for attempt in range(NET_RETRIES):
        t0 = _now_ms()
        r = _retry_request("POST", url, headers=_notion_headers(), json=body)
        logging.info("Notion Create time_ms=%s status=%s", _now_ms() - t0, r.status_code)
        if r.status_code in (200, 201):
            return r.json().get("id")
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(2**attempt, 8))
            continue
    logging.error("Notion 생성 실패: %s", r.text[:500] if r else "no response")
    return None

def _set_notion_thumbnail_files(page_id: str, thumb_url: str) -> bool:
    """Notion 파일 속성(Thumbnail)에 external URL 저장."""
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    body = {
        "properties": {
            "Thumbnail": {
                "files": [
                    {"type": "external", "name": "thumbnail", "external": {"url": thumb_url}}
                ]
            }
        }
    }
    r = _retry_request("PATCH", url, headers=_notion_headers(), json=body)
    ok = (r.status_code == 200)
    if not ok:
        logging.warning("Notion 썸네일(files) 저장 실패: %s", r.text[:300])
    return ok

def upsert_notion_page(meta: Dict[str, str], slack_ts: Optional[str], elapsed_ms: int, err_msg: str) -> Optional[str]:
    """Slug(or URL)로 업서트: 있으면 PATCH, 없으면 POST. 관측/스레드/썸네일 동기화."""
    _assert_notion_env()
    title_name, props_meta = _fetch_db_info()
    props = _build_props(meta, title_name, props_meta, slack_ts, elapsed_ms, err_msg)

    index_val = meta.get("slug") if NOTION_INDEX_PROPERTY == "Slug" else meta.get("url", "")
    page = _query_page_by_index(index_val) if index_val else None
    page_id = _page_id_from_item(page) if page else None

    if page_id:
        ok = _patch_page(page_id, props)
        if not ok:
            return None
    else:
        # 생성 + 메타 백업(children)
        children = [
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Auto Log"}}]}},
            {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": f"Slug: {meta.get('slug', '')}"}}]}},
            {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": f"URL: {meta.get('url', '')}"}}]}},
            {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": f"Status: {meta.get('status', '')}"}}]}},
        ]
        page_id = _create_page(props, children)
        if not page_id:
            return None

    # 썸네일 동기화(외부 URL이면 Notion files에 기록)
    if POST_THUMBNAIL and POST_THUMBNAIL.startswith(("http://", "https://")):
        try:
            _set_notion_thumbnail_files(page_id, POST_THUMBNAIL)
        except Exception as e:
            logging.warning("썸네일(files) 동기화 예외: %s", e)

    return page_id

def update_status_only(new_status: str, comment_text: Optional[str] = None) -> bool:
    """
    상태 전용 패치 + Slack 스레드에 '상태 변경' 댓글.
    1) 인덱스 속성으로 페이지 조회 → Status만 PATCH
    2) SlackTS(또는 SLACK_THREAD_TS) 확보 → 스레드 댓글 전송
    """
    _assert_notion_env()
    index_val = POST_SLUG if NOTION_INDEX_PROPERTY == "Slug" else POST_URL
    if not index_val:
        raise RuntimeError("상태 갱신에는 업서트 키(POST_SLUG 또는 POST_URL)가 필요합니다.")

    page = _query_page_by_index(index_val)
    if not page:
        logging.warning("기존 Row 없음: 상태만 갱신 모드에서 새로 생성하지 않습니다.")
        return False

    page_id = _page_id_from_item(page)
    if not page_id:
        return False

    # Status만 패치
    ok = _patch_page(page_id, {"Status": {"select": {"name": new_status}}})
    if not ok:
        return False

    # Slack 스레드 TS
    thread_ts = _get_rich_text_value(page, "SlackTS") or SLACK_THREAD_TS
    if SLACK_BOT_TOKEN and SLACK_CHANNEL and thread_ts:
        meta = {
            "title": POST_TITLE or "(no title)",
            "slug": POST_SLUG,
            "url": POST_URL,
            "status": new_status,
            "keywords": POST_KEYWORDS,
        }
        text = comment_text or f"[상태 변경] `{POST_SLUG or POST_URL}` → *{new_status}*"
        send_slack_bot(meta, is_error=False, thread_ts=thread_ts, text_override=text)
    else:
        logging.info("Slack 스레드 댓글 생략(bot/token/channel/thread_ts 확인).")

    return True

# =========================
# 메인 흐름
# =========================
def run_hook(args: argparse.Namespace) -> int:
    # 상태만 갱신 모드
    if args.status_update_only:
        if args.status:
            # --status가 있으면 환경 상태를 그 값으로 간주
            os.environ["POST_STATUS"] = args.status
        new_status = os.getenv("POST_STATUS", "").strip()
        if not new_status:
            logging.error("--status-update-only에는 --status 또는 POST_STATUS가 필요합니다.")
            return 2
        try:
            ok = update_status_only(new_status, comment_text=args.status_comment)
            logging.info("Status-only 갱신 결과: %s", ok)
            return 0 if ok else 3
        except Exception as e:
            logging.error("Status-only 처리 실패: %s", e)
            return 4

    # 일반 모드
    t0 = _now_ms()
    err_msg = ""
    try:
        meta = validate_inputs()
    except Exception as e:
        logging.error("입력 검증 실패: %s", e)
        return 2

    # 1) Slack 전송(Webhook 우선 → Bot 폴백/ts 확보)
    ok_webhook, _ = send_slack_webhook(meta, is_error=False)
    ts = None
    if not ok_webhook:
        ok_bot, ts = send_slack_bot(meta, is_error=False)
        if not ok_bot:
            logging.warning("Slack 전송 실패(Webhook/Bot).")

    # 2) 썸네일 업로드(선택, 파일 경로일 때만)
    try:
        if SLACK_BOT_TOKEN and POST_THUMBNAIL and os.path.isfile(POST_THUMBNAIL):
            upload_thumbnail_if_any(SLACK_CHANNEL, ts)
    except Exception as e:
        logging.warning("썸네일 업로드 예외: %s", e)

    # 3) Notion 업서트(+ SlackTS/LastRunMs/ErrorMsg/Thumbnail)
    if NOTION_TOKEN and NOTION_DB_ID:
        try:
            page_id = upsert_notion_page(meta, slack_ts=ts, elapsed_ms=_now_ms() - t0, err_msg=err_msg)
            if page_id:
                logging.info("Notion 업서트 성공: %s", page_id)
            else:
                logging.warning("Notion 업서트 실패")
                # 실패 알림(멘션 포함, Bot 경로)
                send_slack_bot({**meta, "status": "FAILED"}, is_error=True, thread_ts=ts)
        except Exception as e:
            logging.warning("Notion 처리 예외: %s", e)
            send_slack_bot({**meta, "status": "FAILED"}, is_error=True, thread_ts=ts)
    else:
        logging.info("Notion 미설정: 건너뜀")

    logging.info("post_publish_hooks 완료 (elapsed_ms=%s)", _now_ms() - t0)
    return 0

# =========================
# CLI 유틸: Notion 링크에서 32자 DB/Page ID 추출
# =========================
def parse_notion_id(url: str) -> Optional[str]:
    if not url:
        return None
    m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", url)
    if m:
        return m.group(1).replace("-", "").lower()
    m2 = re.search(r"([0-9a-fA-F]{32})", url)
    if m2:
        return m2.group(1).lower()
    return None

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--parse-id", dest="parse_id", help="Notion 링크에서 32자 ID 추출")
    p.add_argument("--status-update-only", action="store_true", help="동일 Row의 Status만 갱신하고 Slack 스레드에 댓글")
    p.add_argument("--status", type=str, default=None, help="--status-update-only와 함께 사용할 강제 상태 값 (예: SUCCESS)")
    p.add_argument("--status-comment", type=str, default=None, help="상태 변경 댓글 문구(없으면 기본 문구)")
    return p

def main() -> int:
    args = build_arg_parser().parse_args()
    if args.parse_id:
        val = parse_notion_id(args.parse_id)
        print(val if val else "ID 추출 실패")
        return 0 if val else 1
    return run_hook(args)

if __name__ == "__main__":
    raise SystemExit(main())
