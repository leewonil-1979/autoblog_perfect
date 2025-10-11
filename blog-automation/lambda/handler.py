# lambda/handler.py
# 목적: AWS Lambda에서 실행되는 메인 함수
import os
import json
import time
import logging
import base64
from typing import Dict, Any, List, Optional, Union

import psycopg2
import requests
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# render 모듈 임포트 (로컬에서는 상대경로, Lambda에서는 함께 패키징)
try:
    from render import render_html
except ImportError:
    render_html = None

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lambda-blog")

# ===== 환경 =====
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
S3_BUCKET_TISTORY: str = os.getenv("S3_BUCKET_TISTORY", "")
REGION: str = os.getenv("AWS_REGION", "ap-northeast-2")
MAKE_WEBHOOK_URL: str = os.getenv("MAKE_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

# ===== LLM 선택 =====
def model(stage: str) -> Union[ChatAnthropic, ChatOpenAI]:
    """비용 최적화: 요약/벤치=Claude, 집필/검수=GPT-4 mini"""
    if stage in {"topic", "bench"} and ANTHROPIC_API_KEY:
        return ChatAnthropic(
            model="claude-3-5-haiku-latest",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.2,
            max_tokens=800
        )
    return ChatOpenAI(
        model="gpt-4.1-mini",
        api_key=OPENAI_API_KEY,
        temperature=0.3,
        max_tokens=1800
    )

# ===== 유틸 =====
def db_conn() -> psycopg2.extensions.connection:
    """PostgreSQL 연결"""
    return psycopg2.connect(DATABASE_URL)

def log_exec(
    blog_id: int,
    step: str,
    status: str,
    message: str = "",
    cost: float = 0.0
) -> None:
    """실행 로그 기록"""
    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO execution_logs (blog_id, step, status, message, cost) VALUES (%s,%s,%s,%s,%s)",
                    (blog_id, step, status, message[:1000], cost),
                )
    except Exception as e:
        log.warning("로그 기록 실패: %s", e)

def fetch_active_blogs() -> List[Dict[str, Any]]:
    """활성화된 블로그 목록 조회"""
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, blog_name, blog_url, platform, wp_user, wp_app_password, COALESCE(category,'') FROM blogs WHERE active = TRUE"
            )
            rows = cur.fetchall()
    keys = ["id", "blog_name", "blog_url", "platform", "wp_user", "wp_app_password", "category"]
    return [dict(zip(keys, r)) for r in rows]

def wp_publish(blog: Dict[str, Any], title: str, html: str) -> Dict[str, Any]:
    """WordPress REST API로 발행"""
    url: str = blog["blog_url"].rstrip("/") + "/wp-json/wp/v2/posts"
    auth: tuple[str, str] = (blog["wp_user"], blog["wp_app_password"])
    data: Dict[str, str] = {"title": title, "content": html, "status": "publish"}
    r = requests.post(url, json=data, auth=auth, timeout=30)
    r.raise_for_status()
    return r.json()

def s3_upload_text(key: str, text: str) -> str:
    """S3에 텍스트 파일 업로드"""
    import boto3
    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(
        Bucket=S3_BUCKET_TISTORY,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType="text/html; charset=utf-8"
    )
    return f"s3://{S3_BUCKET_TISTORY}/{key}"

def save_article(
    blog_id: int,
    title: str,
    content: str,
    html: str,
    status: str,
    wp_id: Optional[int],
    tistory_s3: Optional[str]
) -> None:
    """DB에 아티클 저장"""
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO articles (blog_id,title,content,html_content,status,wordpress_post_id,tistory_package_s3,published_at,attempted_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s, CASE WHEN %s='published' THEN NOW() ELSE NULL END, NOW())
                """,
                (blog_id, title, content, html, status, wp_id, tistory_s3, status)
            )
            conn.commit()

def notify(text: str) -> None:
    """Slack/Make 알림"""
    try:
        if SLACK_WEBHOOK_URL:
            requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=10)
        if MAKE_WEBHOOK_URL:
            requests.post(MAKE_WEBHOOK_URL, json={"message": text}, timeout=10)
    except Exception:
        pass

# ===== 메인 핸들러 =====
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda 핸들러"""
    blogs = fetch_active_blogs()
    results: List[Dict[str, Any]] = []
    
    for blog in blogs:
        b_id: int = blog["id"]
        b_name: str = blog["blog_name"]
        
        try:
            # 1) 주제 생성
            llm = model("topic")
            topic_response = llm.invoke(
                f"블로그 '{b_name}' 주제로 한국어 트렌디 글 주제 1개만 제시. 12~20자."
            )
            topic: str = topic_response.content.strip()
            log_exec(b_id, "topic_generation", "success", topic)

            # 2) 초안 작성
            writer = model("draft")
            draft_response = writer.invoke(
                f"""
주제: {topic}
규격: H1=1, H2=3–6, 문단 80–140자, 표1, 리스트1, FAQ3, [IMG1..], CTA 상/중/하.
과장 금지, 정보 제공 고지 포함.
한국어로 마크다운이 아니라 HTML 본문을 생성하되, 표/FAQ/리스트/IMG 플레이스홀더 포함.
"""
            )
            draft: str = draft_response.content

            title: str = topic  # 간단화; 필요시 추가 추출

            # 3) SEO 렌더(메타/스타일/CTA/IMG 자리 포함)
            if render_html is None:
                raise ImportError("render 모듈을 찾을 수 없습니다")
            
            rendered: Dict[str, Any] = render_html(
                topic=title,
                intent="정보",
                outline=["개요", "핵심 단계", "사례"],
                images=4
            )
            html: str = rendered["html"].replace(
                "<h1>" + title + "</h1>",
                f"<h1>{title}</h1>\n{draft}"
            )

            # 4) 발행/패키징
            if blog["platform"] == "wordpress":
                wp = wp_publish(blog, title, html)
                save_article(b_id, title, draft, html, "published", wp.get("id"), None)
                log_exec(b_id, "publish_wordpress", "success", f"post_id={wp.get('id')}")
                results.append({
                    "blog": b_name,
                    "platform": "wordpress",
                    "post_id": wp.get("id")
                })
            else:
                key: str = f"{b_id}/{int(time.time())}_{title}.html"
                s3_uri: str = s3_upload_text(key, html)
                save_article(b_id, title, draft, html, "draft", None, s3_uri)
                log_exec(b_id, "tistory_package", "success", s3_uri)
                results.append({
                    "blog": b_name,
                    "platform": "tistory",
                    "package": s3_uri
                })

        except Exception as e:
            msg = f"[{b_name}] 실패: {e}"
            log.exception(msg)
            log_exec(b_id, "error", "failed", str(e))
            notify(msg)
            results.append({"blog": b_name, "error": str(e)})

    notify(f"블로그 자동화 완료: {len(results)}건 처리")
    return {"ok": True, "results": results}