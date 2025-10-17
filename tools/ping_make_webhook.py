# -*- coding: utf-8 -*-
# Make.com Webhook 사전 점검용 스크립트
import os
import json
import time
import logging
from pathlib import Path
from typing import Dict
import requests
from dotenv import load_dotenv  # pip install python-dotenv, requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
load_dotenv()

WEBHOOK = os.getenv("MAKE_WEBHOOK_URL", "").strip().strip("'").strip('"')

def validate_url(url: str) -> None:
    import re
    if not re.match(r"^https://hook\.[a-z0-9-]+\.make\.com/[A-Za-z0-9_-]{20,}$", url):
        raise ValueError("웹훅 URL 형식이 올바르지 않습니다. 예: https://hook.us2.make.com/xxxxxxxx")

def post(url: str, payload: Dict):
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r

def main():
    if not WEBHOOK:
        raise SystemExit("환경변수 MAKE_WEBHOOK_URL이 비어 있습니다.")
    validate_url(WEBHOOK)
    payload = {"test":"ok","keyword":"벤치마킹 테스트","ts":int(time.time())}
    logging.info("POST %s", WEBHOOK)
    try:
        res = post(WEBHOOK, payload)
        logging.info("OK status=%s", res.status_code)
        print(res.text[:500] if res.text else "(no body)")
    except requests.HTTPError as e:
        logging.error("HTTPError: %s %s", e.response.status_code, e.response.text[:200])
        print("\n[해결 가이드]")
        print("1) Make 시나리오의 Webhook 모듈 열기 → 'Copy address to clipboard'로 새 URL 복사")
        print("2) 시나리오를 ON(활성화)하고 'Run once'로 큐 소진")
        print("3) Webhook 모듈을 삭제/재생성했다면 이전 URL은 404가 납니다 → 새 URL로 교체")
        print("4) URL에 공백/개행/따옴표가 포함돼 있지 않은지 확인")
        raise
    except Exception as e:
        logging.exception("요청 실패")
        raise

if __name__ == "__main__":
    main()
