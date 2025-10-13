# tools/publish_wpcom.py
# 목적:
#  1) 로컬 HTML을 읽어 워드프레스(WordPress.com) REST API로 글을 자동 발행(초안/비공개/공개)
#  2) 이미지 파일들을 미디어 라이브러리에 업로드하고, 본문 <img> 경로를 업로드된 URL로 치환
#  3) 지정한 이미지로 대표 이미지(썸네일) 설정
#
# 전제:
#  - .env: WPCOM_SITE, WPCOM_TOKEN (필수)
#  - requests, python-dotenv 설치
#  - WordPress.com REST 참고:
#    - posts/new: featured_image 매개변수(첨부 ID), media/media_urls 지원
#    - media/new: multipart/form-data로 파일 업로드
#
# 사용 예:
#  python tools/publish_wpcom.py \
#    --file .\dist\post.html \
#    --images .\dist\images \
#    --featured .\dist\images\cover.jpg \
#    --slug hello-world \
#    --title "테스트 글" \
#    --tags "automation,blog" \
#    --status draft
#
# 결과:
#  - 표준출력에 워드프레스 글 URL 1줄
#  - 본문은 <img> 경로가 WP CDN으로 치환되어 티스토리/네이버에 그대로 붙여넣기 가능

from __future__ import annotations

import argparse
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

WPCOM_API_BASE = "https://public-api.wordpress.com/rest/v1.1"  # 1.1 문서 기준

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

def guess_mime(path: Path) -> str:
    ctype, _ = mimetypes.guess_type(str(path))
    return ctype or "application/octet-stream"

def wp_media_upload(site: str, token: str, filepath: Path, title: Optional[str] = None, caption: Optional[str] = None) -> Dict:
    """
    워드프레스 미디어 업로드 (media/new).
    성공 시 첨부파일 객체(JSON) 반환. ID, URL 필드를 사용.
    """
    url = f"{WPCOM_API_BASE}/sites/{site}/media/new"
    headers = {"Authorization": f"Bearer {token}"}
    files = {"media[]": (filepath.name, open(filepath, "rb"), guess_mime(filepath))}
    data = {}
    if title:
        data["media_attrs[0][title]"] = title
    if caption:
        data["media_attrs[0][caption]"] = caption

    try:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
        resp.raise_for_status()
        js = resp.json()
        # media/new는 업로드 결과를 'media' 배열로 반환
        items = js.get("media", [])
        if not items:
            raise RuntimeError(f"Upload response missing media: {js}")
        return items[0]
    except requests.RequestException as e:
        logging.error("미디어 업로드 실패: %s", e)
        raise

def wp_post_new(
    site: str,
    token: str,
    title: str,
    content_html: str,
    slug: str,
    status: str = "draft",
    tags_csv: str = "",
    categories_csv: str = "",
    featured_attachment_id: Optional[int] = None,
) -> Dict:
    """
    워드프레스 새 글 생성(posts/new).
    featured_image: 첨부(attachment)의 ID 필요.
    """
    url = f"{WPCOM_API_BASE}/sites/{site}/posts/new"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "title": title,
        "content": content_html,
        "slug": slug,
        "status": status,  # publish | draft | private | pending | future ...
        "tags": tags_csv,
        "categories": categories_csv,
    }
    if featured_attachment_id is not None:
        data["featured_image"] = str(featured_attachment_id)

    try:
        resp = requests.post(url, headers=headers, data=data, timeout=60)
        resp.raise_for_status()
        js = resp.json()
        if not js.get("ID"):
            raise RuntimeError(f"Unexpected posts/new response: {js}")
        return js
    except requests.RequestException as e:
        logging.error("포스트 생성 실패: %s", e)
        raise

def find_local_imgs_in_html(html: str) -> List[str]:
    """
    간단한 정규식으로 img src 추출(로컬상대경로/파일명 중심).
    URL(https://...)은 무시.
    """
    pattern = re.compile(r'<img\s+[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)
    results = []
    for m in pattern.finditer(html):
        src = m.group(1).strip()
        if not src.lower().startswith(("http://", "https://", "data:")):
            results.append(src)
    return results

def rewrite_img_src(html: str, mapping: Dict[str, str]) -> str:
    """
    파일명/상대경로 -> 업로드된 WP CDN URL 로 치환.
    mapping 키는 '파일명'과 '상대경로' 모두를 포괄하도록 구성.
    """
    # 긴 경로부터 먼저 치환하여 부분 일치 문제를 줄임
    sorted_keys = sorted(mapping.keys(), key=lambda k: (-len(k), k))
    for key in sorted_keys:
        url = mapping[key]
        # 따옴표 안의 src만 치환
        html = re.sub(
            rf'(<img\s+[^>]*src=["\']){re.escape(key)}(["\'])',
            rf'\1{url}\2',
            html,
            flags=re.IGNORECASE,
        )
    return html

def collect_images(images_dir: Optional[Path], image_files: List[Path]) -> List[Path]:
    """
    --images 디렉토리 또는 --image FILE ... 들을 하나의 리스트로 수집
    """
    collected: List[Path] = []
    if images_dir and images_dir.exists():
        for p in images_dir.rglob("*"):
            if p.is_file() and guess_mime(p).startswith(("image/",)):
                collected.append(p)
    for f in image_files:
        if f.exists() and f.is_file():
            collected.append(f)
    # 중복 제거
    uniq = []
    names = set()
    for p in collected:
        if p.resolve() not in names:
            uniq.append(p)
            names.add(p.resolve())
    return uniq

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="WP.com 자동 발행: 이미지 업로드/치환 + 썸네일 설정")
    parser.add_argument("--file", required=True, help="본문 HTML 파일 경로")
    parser.add_argument("--slug", required=True, help="슬러그(영문/숫자/하이픈)")
    parser.add_argument("--title", required=True, help="글 제목")
    parser.add_argument("--status", default="draft", choices=["publish", "draft", "private"], help="게시 상태")
    parser.add_argument("--tags", default="", help="태그 CSV")
    parser.add_argument("--categories", default="", help="카테고리 CSV")
    parser.add_argument("--images", default=None, help="이미지 폴더(재귀 수집)")
    parser.add_argument("--image", action="append", default=[], help="개별 이미지 파일(여러 개 지정 가능)")
    parser.add_argument("--featured", default=None, help="대표 이미지로 지정할 파일 경로(업로드 대상 중 하나)")
    args = parser.parse_args()

    site = os.getenv("WPCOM_SITE")  # 예: won201.wordpress.com
    token = os.getenv("WPCOM_TOKEN")
    if not site or not token:
        raise SystemExit("환경변수 WPCOM_SITE / WPCOM_TOKEN 이 필요합니다.")

    html_path = Path(args.file).resolve()
    if not html_path.exists():
        raise SystemExit(f"본문 파일을 찾을 수 없습니다: {html_path}")

    images_dir = Path(args.images).resolve() if args.images else None
    image_files = [Path(i).resolve() for i in args.image]
    images = collect_images(images_dir, image_files)

    # 1) 본문 로드
    html = html_path.read_text(encoding="utf-8")

    # 2) 본문에서 상대경로 <img> 수집 (없어도 진행)
    local_imgs = find_local_imgs_in_html(html)
    logging.info("본문 내 로컬 이미지 참조: %s", local_imgs)

    # 3) 업로드 대상 이미지 합치기: (a) --images/--image 입력 + (b) 본문에서 감지된 상대경로
    #    상대경로는 --images 기준으로 찾는 것을 권장
    candidates: List[Path] = list(images)
    if images_dir:
        for rel in local_imgs:
            cand = (images_dir / rel).resolve()
            if cand.exists() and cand.is_file():
                candidates.append(cand)
    # 중복 제거
    uniq: List[Path] = []
    seen = set()
    for p in candidates:
        rp = p.resolve()
        if rp not in seen:
            uniq.append(p)
            seen.add(rp)

    # 4) 미디어 업로드 및 맵핑(파일명/상대경로 -> CDN URL)
    filename_to_url: Dict[str, str] = {}
    fullrel_to_url: Dict[str, str] = {}
    featured_id: Optional[int] = None
    featured_resolved: Optional[Path] = Path(args.featured).resolve() if args.featured else None

    for p in uniq:
        title = p.stem
        uploaded = wp_media_upload(site, token, p, title=title, caption=None)
        attach_id = uploaded.get("ID") or uploaded.get("id")
        url = uploaded.get("URL") or uploaded.get("url")
        if not url:
            raise RuntimeError(f"업로드 응답에 URL 없음: {uploaded}")
        filename_to_url[p.name] = url

        # images_dir 기준 상대경로 key도 추가
        if images_dir and str(p).startswith(str(images_dir)):
            rel = str(p.relative_to(images_dir)).replace("\\", "/")
            fullrel_to_url[rel] = url

        # 대표 이미지 매칭
        if featured_resolved and p.resolve() == featured_resolved:
            try:
                featured_id = int(attach_id)
            except Exception:
                logging.warning("대표 이미지 ID 파싱 실패: %s", attach_id)

        logging.info("업로드 완료: %s -> %s (ID=%s)", p.name, url, attach_id)

    # 5) HTML의 <img src> 치환
    mapping: Dict[str, str] = {}
    mapping.update(filename_to_url)
    mapping.update(fullrel_to_url)
    html_rewritten = rewrite_img_src(html, mapping)

    # 6) 글 생성(대표 이미지 지정)
    post = wp_post_new(
        site=site,
        token=token,
        title=args.title,
        content_html=html_rewritten,
        slug=args.slug,
        status=args.status,              # draft/private 권장
        tags_csv=args.tags,
        categories_csv=args.categories,
        featured_attachment_id=featured_id,
    )
    link = post.get("URL") or post.get("short_URL") or ""
    logging.info("발행 완료: %s", link)
    print(link or post.get("ID"))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error("실패: %s", e)
        raise
