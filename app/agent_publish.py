# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import logging
import psycopg2
from typing import Dict, Any
from app.publishers.wpcom_publisher import publish_post_wpcom, WpComError
from app.publishers.html_package import build_html_package

logger = logging.getLogger(__name__)

def _get_blog(conn, blog_id: int) -> Dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, platform, blog_url, wp_user, wp_app_password, wpcom_site, wpcom_access_token FROM blogs WHERE id=%s", (blog_id,))
        row = cur.fetchone()
    keys = ["id","platform","blog_url","wp_user","wp_app_password","wpcom_site","wpcom_access_token"]
    return dict(zip(keys, row)) if row else {}

def publish_router(blog_id: int, title: str, article_markdown: str) -> Dict[str, Any]:
    db_url = os.getenv("DATABASE_URL")
    assert db_url, "DATABASE_URL 미설정"
    conn = psycopg2.connect(db_url)
    blog = _get_blog(conn, blog_id)
    if not blog:
        raise RuntimeError(f"blogs.id={blog_id} 없음")

    platform = blog["platform"]
    logger.info("publish_router platform=%s", platform)

    if platform == "wpcom":
        site = blog["wpcom_site"]
        token = blog["wpcom_access_token"]
        if not site or not token:
            raise RuntimeError("wpcom_site/access_token 누락")
        # WordPress.com은 HTML 콘텐츠 권장
        r = publish_post_wpcom(site, token, title, content_html=article_markdown)
        return {"platform": "wpcom", "result": r}

    elif platform in ("tistory", "naver"):
        pkg = build_html_package(title, article_markdown)
        # 실제 운영: S3 업로드 또는 로컬 파일로 저장
        path = os.path.join("packages", pkg["filename"])
        os.makedirs("packages", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(pkg["html"])
        logger.info("%s HTML 패키지 생성: %s", platform, path)
        return {"platform": platform, "result": {"local_path": path}}

    elif platform == "wordpress":
        # 자체호스팅 WP.org는 기존 Basic Auth 코드 재사용
        # (여기서는 무료 기준이므로 생략)
        raise RuntimeError("현재 단계는 무료 플랜: wordpress(org) 자동발행은 비활성")

    elif platform == "blogger":
        # 선택 구현: Blogger OAuth2 토큰으로 posts.insert
        raise RuntimeError("Blogger 퍼블리셔는 이후 단계에서 활성화")

    else:
        raise RuntimeError(f"지원하지 않는 platform: {platform}")
