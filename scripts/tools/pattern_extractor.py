# -*- coding: utf-8 -*-
# 목적: raw JSON을 읽어 "성공 패턴 카드"로 가공하여 pattern_cards/*.json에 저장
# 사용:
#   python tools/pattern_extractor.py --input data/benchmark/raw/20251013T000000Z_키워드.json
from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tools.common import ensure_dirs, save_json, setup_logging, slugify


HOOK_RULES: List[Tuple[str, str]] = [
    (r"^\d+(\s|\.|-)", "숫자형 리스트"),                 # "7가지", "10가지 방법"
    (r"(완벽|궁극|사기급|필수|비밀)", "강한 수식어"),     # 강한 어휘
    (r"(초보|입문|처음|왕초보)", "입문자 타깃"),          # 타깃 지시
    (r"(실패|함정|주의|피해야|손해)", "위험 경고"),        # 손실/경고
    (r"(가이드|튜토리얼|공식|정리)", "가이드/정리"),      # 가이드형
    (r"(체크리스트|목록|리스트)", "체크리스트"),           # 체크리스트
    (r"(케이스 스터디|사례|후기|리뷰)", "사례/후기"),       # 사례형
    (r"(비교|vs\.|차이|장단점)", "비교/대안"),             # 비교형
]


STRUCTURE_RULES: List[Tuple[str, str]] = [
    (r"(단계|Step|순서)", "단계형"),
    (r"(리스트|목록|\d+가지)", "리스트형"),
    (r"(가이드|튜토리얼|방법)", "가이드형"),
    (r"(사례|케이스|경험담|후기)", "사례형"),
    (r"(체크리스트|점검)", "체크리스트형"),
]


STOPWORDS = set(
    """
    그리고 그러나 그래서 또는 또한 등이 즉 즉시 매우 그냥 정말 것 것들 수 있다 없다 같은 등의
    방법 관리 재무 사업 개인 블로그 글 제목 정보 뉴스 유튜브 네이버 티스토리 소개 정리 가이드
    """.split()
)


def tokenize(text: str) -> List[str]:
    # 매우 단순 토크나이저(공백/기호 기준)
    text = re.sub(r"[^\w\s]", " ", text)
    toks = [t for t in text.lower().split() if t and t not in STOPWORDS and len(t) > 1]
    return toks


def detect_hook(title: str) -> str:
    for pat, label in HOOK_RULES:
        if re.search(pat, title, flags=re.IGNORECASE):
            return label
    return "일반형"


def detect_structure(snippet: str | None, title: str) -> str:
    text = f"{title} {snippet or ''}"
    for pat, label in STRUCTURE_RULES:
        if re.search(pat, text, flags=re.IGNORECASE):
            return label
    return "일반형"


def top_keywords(items: List[Dict[str, Any]], k: int = 10) -> List[str]:
    c = Counter()
    for it in items:
        for field in ("title", "snippet"):
            val = (it.get(field) or "").strip()
            c.update(tokenize(val))
    return [w for w, _ in c.most_common(k)]


def main() -> None:
    setup_logging("pattern_extractor")
    ensure_dirs()

    parser = argparse.ArgumentParser(description="패턴 추출기")
    parser.add_argument("--input", required=True, help="raw JSON 경로")
    parser.add_argument("--topk", type=int, default=10, help="키워드 상위 K")
    args = parser.parse_args()

    raw_path = Path(args.input)
    if not raw_path.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {raw_path}")

    with raw_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    items = raw.get("items", [])
    analyses: List[Dict[str, Any]] = []
    for it in items:
        title = (it.get("title") or "").strip()
        snippet = (it.get("snippet") or "").strip()
        if not title:
            continue
        analyses.append(
            {
                "title": title,
                "url": it.get("url"),
                "source": it.get("source"),
                "title_length": len(title),
                "hook_type": detect_hook(title),
                "structure": detect_structure(snippet, title),
            }
        )

    # 전역 키워드 상위 K
    kw = top_keywords(items, k=args.topk)

    card = {
        "keyword": raw.get("keyword"),
        "total": len(analyses),
        "summary": {
            "top_keywords": kw,
            "hook_type_dist": Counter([a["hook_type"] for a in analyses]),
            "structure_dist": Counter([a["structure"] for a in analyses]),
            "avg_title_length": round(sum(a["title_length"] for a in analyses) / max(len(analyses), 1), 2),
        },
        "items": analyses,
    }

    # 저장
    base = raw_path.stem  # 예: 20251013T..._slug
    out = Path("data/benchmark/pattern_cards") / f"{base}_pattern.json"

    # Counter는 직렬화 불가 → dict로 변환
    if isinstance(card["summary"]["hook_type_dist"], Counter):
        card["summary"]["hook_type_dist"] = dict(card["summary"]["hook_type_dist"])
    if isinstance(card["summary"]["structure_dist"], Counter):
        card["summary"]["structure_dist"] = dict(card["summary"]["structure_dist"])

    save_json(card, out)
    logging.info("패턴 카드 저장 완료: %s", out)
    print(f"[OK] 패턴 카드 저장: {out}")


if __name__ == "__main__":
    main()
