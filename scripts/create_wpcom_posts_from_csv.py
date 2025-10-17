# -*- coding: utf-8 -*-
"""
WordPress.com 글 일괄 생성기(슬러그 기준, 재실행 안전)
- CSV 견고 파싱(BOM 제거/구분자 자동감지/헤더 정규화)
- slug가 없으면 건너뜀, 이미 존재하면 건너뜀
- status: publish|draft|private 선택

.env:
  WPCOM_SITE=won201.wordpress.com
  WPCOM_TOKEN=<OAuth2 토큰>
  NET_TIMEOUT=15
  NET_RETRIES=3
사용:
  python scripts/create_wpcom_posts_from_csv.py --csv data/publish_batch.csv --status draft
"""
from __future__ import annotations
import argparse, csv, io, logging, os, sys
from typing import Dict, Any, Optional, Iterable
import requests
from requests.adapters import HTTPAdapter, Retry
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("wpcom_bulk_create")

def _norm(s: str) -> str:
    return (s or "").strip().lstrip("\ufeff").strip()  # BOM + 공백 제거

def iter_csv_rows(path: str) -> Iterable[Dict[str,str]]:
    raw = open(path, "rb").read()
    text = raw.decode("utf-8-sig")  # BOM 제거
    try:
        dialect = csv.Sniffer().sniff("\n".join(text.splitlines()[:2]) or ",")
    except Exception:
        dialect = csv.excel
    rdr = csv.DictReader(io.StringIO(text), dialect=dialect)
    if rdr.fieldnames:
        rdr.fieldnames = [_norm(h).lower() for h in rdr.fieldnames]
    for row in rdr:
        if not row:
            continue
        slug = _norm(row.get("slug",""))
        url  = _norm(row.get("url",""))
        if not slug:
            logger.warning("행 건너뜀: slug 없음 (row=%s)", row)
            continue
        yield {"slug": slug, "url": url}

def make_session(retries: int) -> requests.Session:
    s = requests.Session()
    retry = Retry(total=retries, backoff_factor=0.5, status_forcelist=[429,500,502,503,504],
                  allowed_methods=frozenset(["GET","POST"]))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def to_title(slug: str) -> str:
    return " ".join(p.capitalize() for p in slug.replace("-", " ").split())

def get_existing_by_slug(sess: requests.Session, base: str, headers: Dict[str,str], slug: str, timeout: int) -> Optional[int]:
    r = sess.get(f"{base}/posts", headers=headers, params={"slug": slug, "per_page": 1}, timeout=timeout)
    if r.status_code == 200 and isinstance(r.json(), list) and r.json():
        return int(r.json()[0]["id"])
    return None

def create_post(sess: requests.Session, base: str, headers: Dict[str,str], slug: str, status: str, timeout: int) -> int:
    payload: Dict[str,Any] = {
        "title": to_title(slug),
        "slug": slug,
        "status": status,
        "content": "<p>자동 생성된 자리표시자 본문입니다. 이후 렌더링으로 대체됩니다.</p>",
    }
    r = sess.post(f"{base}/posts", headers=headers, json=payload, timeout=timeout)
    if r.status_code not in (200,201):
        raise RuntimeError(f"생성 실패(slug={slug}): {r.status_code} {r.text[:300]}")
    post = r.json()
    logger.info("생성 성공: id=%s link=%s", post.get("id"), post.get("link"))
    return int(post["id"])

def main():
    load_dotenv(override=False)
    site = os.getenv("WPCOM_SITE","").strip()
    token = os.getenv("WPCOM_TOKEN","").strip()
    timeout = int(os.getenv("NET_TIMEOUT","15"))
    retries = int(os.getenv("NET_RETRIES","3"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--status", choices=["publish","draft","private"], default="publish")
    args = ap.parse_args()
    if not site or not token:
        logger.error("환경변수 누락: WPCOM_SITE, WPCOM_TOKEN")
        sys.exit(2)
    base = f"https://public-api.wordpress.com/wp/v2/sites/{site}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type":"application/json; charset=utf-8"}
    sess = make_session(retries)

    created=skipped=0
    for row in iter_csv_rows(args.csv):
        slug = row["slug"]
        try:
            exists = get_existing_by_slug(sess, base, headers, slug, timeout)
            if exists:
                logger.info("건너뜀: 이미 존재(id=%s, slug=%s)", exists, slug)
                skipped += 1
                continue
            create_post(sess, base, headers, slug, args.status, timeout)
            created += 1
        except Exception as e:
            logger.error("실패(slug=%s): %s", slug, e)
    logger.info("완료: created=%d, skipped=%d", created, skipped)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.error("중단됨")
        sys.exit(130)
    except Exception as e:
        logger.exception("치명적 오류: %s", e)
        sys.exit(1)
