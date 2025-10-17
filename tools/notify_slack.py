# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()
WEBHOOK = (os.getenv("SLACK_WEBHOOK_URL") or "").strip()
BOT_TOKEN = (os.getenv("SLACK_BOT_TOKEN") or "").strip()
CHANNEL = os.getenv("SLACK_CHANNEL", "#general").strip()

def send_via_webhook(text: str, blocks: Optional[list] = None) -> None:
    if not WEBHOOK:
        raise RuntimeError("SLACK_WEBHOOK_URL 누락")
    payload: Dict[str, Any] = {"text": text}
    if blocks: payload["blocks"] = blocks
    r = requests.post(WEBHOOK, data=json.dumps(payload), headers={"Content-Type":"application/json"}, timeout=10)
    if r.status_code >= 300: raise RuntimeError(f"Slack Webhook 실패: {r.status_code} {r.text}")

def send_via_bot(text: str, blocks: Optional[list] = None) -> None:
    if not BOT_TOKEN: raise RuntimeError("SLACK_BOT_TOKEN 누락")
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {BOT_TOKEN}", "Content-Type":"application/json; charset=utf-8"}
    payload: Dict[str, Any] = {"channel": CHANNEL, "text": text}
    if blocks: payload["blocks"] = blocks
    r = requests.post(url, headers=headers, json=payload, timeout=10).json()
    if not r.get("ok"): raise RuntimeError(f"Slack API 실패: {r}")

def notify(title: str, status: str, meta: Dict[str, Any]) -> None:
    blocks = [
        {"type":"header","text":{"type":"plain_text","text":f"{status} - {title}"}},
        {"type":"section","fields":[
            {"type":"mrkdwn","text":f"*slug:*\n{meta.get('slug','-')}"},
            {"type":"mrkdwn","text":f"*site:*\n{meta.get('site','-')}"},
            {"type":"mrkdwn","text":f"*time:*\n{meta.get('ts','-')}"},
            {"type":"mrkdwn","text":f"*env:*\n{os.getenv('ENVIRONMENT','local')}"},
        ]},
    ]
    text = f"{status} - {title} | {meta.get('url','')}"
    if WEBHOOK: send_via_webhook(text, blocks)
    elif BOT_TOKEN: send_via_bot(text, blocks)
    else: raise RuntimeError("Slack 자격정보가 없습니다.")
