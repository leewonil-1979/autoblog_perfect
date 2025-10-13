# tools/compose_tistory_post.py
# 목적: 로컬 HTML을 S3에 업로드하고, 티스토리 편집기에 붙여넣을 본문 HTML을
#       자동 생성하여 클립보드에 복사 + 브라우저로 관리 페이지를 연다.
# 전제: tools/s3_publish.py 존재, .env 설정(AWS_*, S3_BUCKET_TISTORY, TISTORY_BLOG_URL)
# 사용:
#   python tools/compose_tistory_post.py --file .\dist\post.html --slug hello-world --title "테스트 글"
# 결과: 1) 본문 HTML이 클립보드에 복사됨, 2) 브라우저로 티스토리 관리 페이지가 열림

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import textwrap
import webbrowser

from dotenv import load_dotenv

# 내부 모듈 재사용
try:
    from tools.s3_publish import get_s3_client, upload_file, presign_url
except Exception as e:
    raise SystemExit(f"s3_publish 모듈을 찾지 못했습니다: {e}")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def build_s3_key(slug: str, prefix: str = "posts") -> str:
    today = dt.datetime.now().strftime("%Y-%m-%d")
    return f"{prefix}/{today}-{slug}.html"

def build_content_html(title: str, presigned_url: str, local_html: str) -> str:
    # 티스토리 에디터에 그대로 붙여넣을 수 있는 간단 템플릿
    head = textwrap.dedent(f"""
    <h1>{title}</h1>
    <p>원본 HTML(임시 접근): <a href="{presigned_url}" rel="nofollow">{presigned_url}</a></p>
    <hr/>
    """).strip()
    return head + "\n" + local_html

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="티스토리 반자동 게시: S3 업로드 + 본문 생성 + 브라우저 열기")
    parser.add_argument("--file", required=True, help="업로드할 로컬 HTML 파일")
    parser.add_argument("--slug", required=True, help="파일/URL에 사용할 슬러그(영문/숫자/하이픈)")
    parser.add_argument("--title", required=True, help="티스토리 글 제목")
    parser.add_argument("--prefix", default="posts", help="S3 키 프리픽스(default: posts)")
    parser.add_argument("--expires", type=int, default=900, help="프리사인 URL 만료(초)")
    parser.add_argument("--profile", default=None, help="AWS CLI 프로파일명(옵션)")
    args = parser.parse_args()

    blog_url = os.getenv("TISTORY_BLOG_URL", "").rstrip("/")
    if not blog_url:
        raise SystemExit("환경변수 TISTORY_BLOG_URL 이 필요합니다. 예) https://privilege-to-succeed.tistory.com")

    bucket = os.getenv("S3_BUCKET_TISTORY", "blog-auto-mvp")

    # 1) S3 업로드
    s3 = get_s3_client(profile=args.profile)
    key = build_s3_key(args.slug, args.prefix)
    logging.info("업로드 대상: s3://%s/%s", bucket, key)
    upload_file(s3, bucket, args.file, key)

    # 2) 프리사인 URL
    url = presign_url(s3, bucket, key, args.expires)
    logging.info("프리사인 URL: %s", url)

    # 3) 로컬 HTML 읽기 → 본문 조립
    with open(args.file, "r", encoding="utf-8") as f:
        raw_html = f.read()
    content = build_content_html(args.title, url, raw_html)

    # 4) 클립보드 복사
    try:
        import pyperclip  # type: ignore
    except Exception:
        raise SystemExit("pyperclip가 필요합니다. `pip install pyperclip` 실행 후 다시 시도하세요.")
    pyperclip.copy(content)
    logging.info("본문 HTML을 클립보드에 복사했습니다. 티스토리 편집기에 바로 붙여넣으세요.")

    # 5) 브라우저 열기(관리 페이지로 이동 → '글쓰기' 클릭 후 붙여넣기)
    # 관리자 URL 패턴은 계정/환경에 따라 다를 수 있으므로 관리 홈으로 열어줍니다.
    manage_url = f"{blog_url}/manage"
    webbrowser.open(manage_url)
    print("\n[다음 순서]\n1) 브라우저에서 티스토리 로그인(필요 시)\n2) '글쓰기' 진입\n3) 에디터 본문 영역에 Ctrl+V 붙여넣기\n4) 제목/태그/카테고리 확인 후 발행\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error("실패: %s", e)
        raise
