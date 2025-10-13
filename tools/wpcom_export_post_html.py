# tools/wpcom_export_post_html.py
# 목적: WordPress.com 게시물의 content(HTML)를 API로 가져와 파일로 저장
# 사용:
#   python tools/wpcom_export_post_html.py --post <숫자ID> --out artifacts/paste.html
#   또는 --url https://won201.wordpress.com/?p=30 형태를 넣어도 됨(내부에서 ID 추출 시도)

from __future__ import annotations
import argparse, os, re
import requests
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

API_BASE = "https://public-api.wordpress.com/rest/v1.1"

def extract_post_id(url: str) -> int | None:
    # ?p=30 형태에서 30 추출
    try:
        qs = parse_qs(urlparse(url).query)
        if "p" in qs and qs["p"]:
            return int(qs["p"][0])
    except Exception:
        pass
    # /YYYY/MM/DD/slug/ 형태면 별도 로직 필요(단순화: None)
    return None

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="WP.com 글 HTML export")
    parser.add_argument("--post", type=int, default=None, help="포스트 ID")
    parser.add_argument("--url", default=None, help="예: https://won201.wordpress.com/?p=30")
    parser.add_argument("--out", default="artifacts/paste.html")
    args = parser.parse_args()

    site = os.getenv("WPCOM_SITE")
    token = os.getenv("WPCOM_TOKEN")
    if not site or not token:
        raise SystemExit("환경변수 WPCOM_SITE / WPCOM_TOKEN 필요")

    post_id = args.post
    if not post_id and args.url:
        post_id = extract_post_id(args.url)
    if not post_id:
        raise SystemExit("--post 또는 --url( ?p=ID 형태 ) 중 하나를 제공하세요.")

    url = f"{API_BASE}/sites/{site}/posts/{post_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    js = r.json()
    content = js.get("content", "")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(content)
    print(args.out)

if __name__ == "__main__":
    main()
