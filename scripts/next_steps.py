# -*- coding: utf-8 -*-
# 목적: 핵심 단계를 주차별로 출력하고 기본 디렉터리/산출물 스캐폴딩을 생성
# 사용: python scripts/next_steps.py --week 1
import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml  # pip install pyyaml

LOG_DIR = Path("logs/plan")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_DIR / "next_steps.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

PLAN_PATH = Path("plan/core_steps.yaml")
REQUIRED_DIRS = [
    "data/benchmark/raw",
    "data/benchmark/pattern_cards",
    "data/calendar",
    "artifacts",
    "logs/run_daily",
    "templates",
    "tools",
    "dashboards",
]


def load_plan(path: Path) -> Dict[str, Any]:
    """YAML 계획 로드."""
    if not path.exists():
        logging.error("계획 파일 누락: %s", path)
        raise FileNotFoundError(f"계획 파일을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_scaffold() -> None:
    """필수 디렉터리 생성."""
    for d in REQUIRED_DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)
    logging.info("기본 스캐폴딩 생성 완료")


def print_week(plan: Dict[str, Any], week: int) -> None:
    """주차별 태스크 출력."""
    key = f"week_{week}"
    if key not in plan:
        raise KeyError(f"{week}주차 계획이 없습니다.")
    tasks: List[Dict[str, Any]] = plan[key]
    print(f"# {week}주차 핵심 단계")
    for t in tasks:
        print(f"- [{t['id']}] {t['title']}")
        if "deliverables" in t:
            print(f"  · 산출물: {', '.join(t['deliverables'])}")
        if "acceptance" in t:
            print(f"  · 검증기준: {', '.join(t['acceptance'])}")


def save_week_json(plan: Dict[str, Any], week: int) -> Path:
    """주차별 계획을 JSON으로 저장."""
    key = f"week_{week}"
    out = Path(f"plan/week_{week}.json")
    with out.open("w", encoding="utf-8") as f:
        json.dump(plan[key], f, ensure_ascii=False, indent=2)
    logging.info("주차 계획 JSON 저장: %s", out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="핵심 단계 실행 플랜 출력기")
    parser.add_argument("--week", type=int, default=1, help="주차(기본=1)")
    args = parser.parse_args()

    try:
        ensure_scaffold()
        plan = load_plan(PLAN_PATH)
        print_week(plan, args.week)
        out = save_week_json(plan, args.week)
        print(f"\n[안내] 주차 계획 JSON 저장: {out}")
    except Exception as e:
        logging.exception("실행 오류")
        print(f"[에러] {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
