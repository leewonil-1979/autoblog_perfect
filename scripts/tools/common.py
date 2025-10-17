# -*- coding: utf-8 -*-
# 공용 유틸: 로깅/저장/슬러그
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# 로깅 기본 설정
def setup_logging(name: str = "benchmark") -> None:
    logs_dir = Path("logs/plan")
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=logs_dir / f"{name}.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # 콘솔에도 출력
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logging.getLogger().addHandler(console)


def slugify(text: str) -> str:
    # 한글/영문/숫자/공백/하이픈만 남기고 하이픈으로 치환
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text.lower()


def ensure_dirs() -> None:
    for d in [
        "data/benchmark/raw",
        "data/benchmark/pattern_cards",
        "logs/plan",
    ]:
        Path(d).mkdir(parents=True, exist_ok=True)


def utc_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def save_json(obj: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_env(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if val is None:
        raise RuntimeError(f"환경변수 {key}가 설정되지 않았습니다.")
    return val
