#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Slack 전송 유틸리티
- Bot Token 기반 chat.postMessage 전송
- 채널 이름을 ID로 해석(가능 시). 실패해도 그대로 진행
- 예외/오류 로깅 포함
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(_handler)


@dataclass
class SlackConfig:
    bot_token: str
    channel: str  # "#name" 또는 "Cxxxx"
    timeout: int = 10


class SlackClient:
    def __init__(self, cfg: SlackConfig) -> None:
        self.cfg = cfg
        self.api_base = "https://slack.com/api"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.cfg.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _is_channel_id(self, value: str) -> bool:
        return value.startswith("C") or value.startswith("G")

    def resolve_channel(self, channel: str) -> str:
        """
        채널이 "#name"이면 conversations.list로 ID를 조회(선택).
        channels:read / groups:read 스코프가 없으면 실패할 수 있으므로, 실패 시 원본 반환.
        """
        if self._is_channel_id(channel):
            return channel
        if channel.startswith("#"):
            name = channel[1:]
        else:
            name = channel

        try:
            url = f"{self.api_base}/conversations.list?limit=200&types=public_channel,private_channel"
            r = requests.get(url, headers=self._headers(), timeout=self.cfg.timeout)
            data = r.json()
            if not data.get("ok"):
                logger.warning("채널 조회 실패(계속 진행): %s", json.dumps(data, ensure_ascii=False))
                return channel
            for ch in data.get("channels", []):
                if ch.get("name") == name:
                    return ch.get("id") or channel
            logger.warning("채널 이름 '%s'을 ID로 찾지 못했음(계속 진행)", name)
            return channel
        except Exception as e:
            logger.warning("채널 해석 중 예외(계속 진행): %s", e)
            return channel

    def post_message(
        self,
        text: str,
        channel: Optional[str] = None,
        blocks: Optional[list] = None,
        thread_ts: Optional[str] = None,
    ) -> Tuple[bool, dict]:
        payload = {
            "channel": self.resolve_channel(channel or self.cfg.channel),
            "text": text,
        }
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts
        try:
            url = f"{self.api_base}/chat.postMessage"
            r = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=self.cfg.timeout)
            data = r.json()
            if not data.get("ok"):
                logger.error("Slack 전송 실패: %s", json.dumps(data, ensure_ascii=False))
                return False, data
            logger.info("Slack 전송 성공: channel=%s ts=%s", data.get("channel"), data.get("ts"))
            return True, data
        except requests.RequestException as e:
            logger.exception("Slack 요청 예외: %s", e)
            return False, {"ok": False, "error": str(e)}
