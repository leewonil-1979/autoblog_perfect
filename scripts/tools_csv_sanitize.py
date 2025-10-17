# -*- coding: utf-8 -*-
"""
CSV 정규화 도구
- BOM 제거, 구분자 자동 감지(csv.Sniffer), 헤더 소문자/공백 제거
- 표준 UTF-8(무BOM), 쉼표(,) 구분자로 재저장
사용:
  python scripts/tools_csv_sanitize.py --in data/publish_batch.csv --out data/publish_batch.cleaned.csv
"""
import argparse, csv, io, sys
from pathlib import Path

def normalize_header(name: str) -> str:
    return name.strip().lower().lstrip("\ufeff")  # BOM 제거 + 소문자 + 공백 제거

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", dest="dst", required=True)
    args = p.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    raw = src.read_bytes()
    text = raw.decode("utf-8-sig")  # BOM 자동 제거
    # 구분자 추정
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0] + "\n" + text.splitlines()[1])
    except Exception:
        dialect = csv.excel  # 실패 시 기본(쉼표)
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    # 헤더 정규화
    reader.fieldnames = [normalize_header(h) for h in (reader.fieldnames or [])]

    rows = [ {k.strip(): (v or "").strip() for k, v in row.items()} for row in reader if any(row.values()) ]
    # 표준 CSV로 저장(쉼표, UTF-8 무BOM)
    with dst.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["slug","url"])
        writer.writeheader()
        for r in rows:
            writer.writerow({"slug": r.get("slug",""), "url": r.get("url","")})
    print(f"OK: cleaned -> {dst}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
