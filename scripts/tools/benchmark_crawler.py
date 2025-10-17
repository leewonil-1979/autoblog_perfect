# -*- coding: utf-8 -*-
# 목적: 키워드로 Google/Web/News/YouTube 상위 결과를 SerpAPI로 30개 수집하여 raw JSON 저장
# 사용:
#   python tools/benchmark_crawler.py --keyword "개인 사업자 재무 관리" --limit 30
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv  # pip install python-dotenv

from tools.common import ensure_dirs, save_json, setup_logging, slugify, utc_ts, load_env

SEARCH_ENGINES = [
    {"engine": "google", "label": "google_web"},
    {"engine": "google_news", "label": "google_news"},
    {"engine": "youtube", "label": "youtube"},
]


def serpapi_search(
    engine: str,
    q: str,
    api_key: str,
    gl: str,
    hl: str,
    num: int,
) -> Dict[str, Any]:
    base = "https://serpapi.com/search.json"
    params = {"engine": engine, "q": q, "api_key": api_key, "gl": gl, "hl": hl, "num": min(num, 100)}
    # YouTube는 기본적으로 검색 수가 다르게 동작하므로 그대로 전달
    resp = requests.get(base, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def normalize_items(engine_label: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if engine_label == "google_web":
        for i in data.get("organic_results", []):
            items.append(
                {
                    "title": i.get("title"),
                    "url": i.get("link"),
                    "snippet": i.get("snippet"),
                    "position": i.get("position"),
                    "source": "google_web",
                }
            )
    elif engine_label == "google_news":
        for i in data.get("news_results", []):
            items.append(
                {
                    "title": i.get("title"),
                    "url": i.get("link"),
                    "snippet": i.get("snippet"),
                    "source": "google_news",
                }
            )
    elif engine_label == "youtube":
        for i in data.get("video_results", []):
            items.append(
                {
                    "title": i.get("title"),
                    "url": i.get("link"),
                    "snippet": i.get("description"),
                    "channel": i.get("channel", {}).get("name") if isinstance(i.get("channel"), dict) else None,
                    "views": i.get("views"),
                    "source": "youtube",
                }
            )
    return items


def main() -> None:
    load_dotenv()
    setup_logging("benchmark_crawler")
    ensure_dirs()

    parser = argparse.ArgumentParser(description="벤치마킹 수집기 (SerpAPI)")
    parser.add_argument("--keyword", required=True, help="검색 키워드")
    parser.add_argument("--limit", type=int, default=30, help="총 수집 개수(기본=30)")
    parser.add_argument("--site-filters", nargs="*", default=["site:tistory.com", "site:blog.naver.com"], help="선호 도메인 필터")
    args = parser.parse_args()

    api_key = load_env("SERPAPI_KEY")
    gl = os.getenv("SEARCH_GL", "kr")
    hl = os.getenv("SEARCH_HL", "ko")

    q = args.keyword.strip()
    site_q = " OR ".join(args.site_filters) if args.site_filters else ""
    composed_q = f"{q} {site_q}".strip()

    all_items: List[Dict[str, Any]] = []
    for eng in SEARCH_ENGINES:
        try:
            logging.info("검색 실행: engine=%s, q=%s", eng["engine"], composed_q)
            data = serpapi_search(eng["engine"], composed_q, api_key, gl, hl, args.limit)
            items = normalize_items(eng["label"], data)
            all_items.extend(items)
        except Exception as e:
            logging.exception("엔진 실패: %s", eng["engine"])

    # 상위 limit개로 절단
    all_items = all_items[: args.limit]

    # 저장
    stamp = utc_ts()
    out_name = f"{stamp}_{slugify(q)}.json"
    out_path = Path("data/benchmark/raw") / out_name

    payload = {
        "keyword": q,
        "site_filters": args.site_filters,
        "total": len(all_items),
        "items": all_items,
        "meta": {"gl": gl, "hl": hl},
    }
    save_json(payload, out_path)
    logging.info("원본 저장 완료: %s (총 %d개)", out_path, len(all_items))
    print(f"[OK] 원본 저장: {out_path} (총 {len(all_items)}개)")


if __name__ == "__main__":
    main()
