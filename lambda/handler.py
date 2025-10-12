# lambda/handler.py
# type: ignore
"""
AWS Lambda 메인 함수: 블로그 자동 포스팅
- LangChain을 이용한 주제 생성 및 초안 작성
- WordPress REST API / Tistory S3 패키징 지원
- 실행 로그 및 알림 전송
"""
import os
import time
import logging
from typing import Dict, Any, List, Optional

import psycopg2
import requests

# LangChain 임포트
try:
    from langchain_openai import ChatOpenAI  # type: ignore
except ImportError:
    ChatOpenAI = None

try:
    from langchain_anthropic import ChatAnthropic  # type: ignore
except ImportError:
    ChatAnthropic = None

# render 모듈 임포트
try:
    from render import render_html
except ImportError:
    render_html = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger("blog-automation")

# ===== 환경 변수 =====
DATABASE_URL = os.getenv("DATABASE_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
S3_BUCKET_TISTORY = os.getenv("S3_BUCKET_TISTORY", "")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


# ===== LLM 팩토리 =====
def get_llm(stage: str) -> Any:  # type: ignore
    """
    비용 최적화 LLM 선택
    - topic/bench: Claude Haiku (저렴)
    - draft/review: GPT-4 mini (품질)
    """
    if stage in {"topic", "bench"} and ANTHROPIC_API_KEY and ChatAnthropic:
        return ChatAnthropic(  # type: ignore
            model="claude-3-5-haiku-latest",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0.2,
            max_tokens=800
        )

    if not ChatOpenAI:
        raise ImportError("ChatOpenAI를 임포트할 수 없습니다")

    return ChatOpenAI(  # type: ignore
        model="gpt-4o-mini",
        api_key=OPENAI_API_KEY,
        temperature=0.3,
        max_tokens=2000
    )

# ===== 데이터베이스 =====
def get_db_connection():
    """PostgreSQL 연결 생성"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다")
    return psycopg2.connect(DATABASE_URL)

def log_execution(
    blog_id: int,
    step: str,
    status: str,
    message: str = "",
    cost: float = 0.0
) -> None:
    """실행 로그를 DB에 기록"""
    try:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO execution_logs
                    (blog_id, step, status, message, cost)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (blog_id, step, status, message[:1000], cost),
                )
                conn.commit()
            finally:
                cur.close()
        finally:
            conn.close()
    except Exception as e:
        log.warning(f"로그 기록 실패: {e}")


def fetch_active_blogs() -> List[Dict[str, Any]]:
    """활성화된 블로그 목록 조회"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT id, blog_name, blog_url, platform,
                       wp_user, wp_app_password, COALESCE(category, '') as category
                FROM blogs
                WHERE active = TRUE
            """)
            rows = cur.fetchall()
        finally:
            cur.close()
    finally:
        conn.close()

    keys = ["id", "blog_name", "blog_url", "platform",
            "wp_user", "wp_app_password", "category"]
    return [dict(zip(keys, row)) for row in rows]

# ===== WordPress & S3 =====
def publish_to_wordpress(blog: Dict[str, Any], title: str, html: str) -> Dict[str, Any]:
    """WordPress REST API로 포스트 발행"""
    url = f"{blog['blog_url'].rstrip('/')}/wp-json/wp/v2/posts"
    auth = (blog["wp_user"], blog["wp_app_password"])
    data = {
        "title": title,
        "content": html,
        "status": "publish"
    }

    response = requests.post(url, json=data, auth=auth, timeout=30)
    response.raise_for_status()
    return response.json()


def upload_to_s3(key: str, content: str) -> str:
    """S3에 HTML 파일 업로드"""
    import boto3

    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.put_object(
        Bucket=S3_BUCKET_TISTORY,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="text/html; charset=utf-8"
    )
    return f"s3://{S3_BUCKET_TISTORY}/{key}"


def save_article(
    blog_id: int,
    title: str,
    content: str,
    html: str,
    status: str,
    wp_post_id: Optional[int] = None,
    s3_uri: Optional[str] = None
) -> None:
    """아티클을 DB에 저장"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO articles
                (blog_id, title, content, html_content, status,
                 wordpress_post_id, tistory_package_s3, published_at, attempted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s = 'published' THEN NOW() ELSE NULL END,
                        NOW())
                """,
                (blog_id, title, content, html, status,
                 wp_post_id, s3_uri, status)
            )
            conn.commit()
        finally:
            cur.close()
    finally:
        conn.close()


def send_notification(message: str) -> None:
    """Slack/Make 웹훅으로 알림 전송"""
    try:
        if SLACK_WEBHOOK_URL:
            requests.post(
                SLACK_WEBHOOK_URL,
                json={"text": message},
                timeout=10
            )
        if MAKE_WEBHOOK_URL:
            requests.post(
                MAKE_WEBHOOK_URL,
                json={"message": message},
                timeout=10
            )
    except Exception as e:
        log.debug(f"알림 전송 실패: {e}")


# ===== Lambda 핸들러 =====
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda 메인 핸들러

    프로세스:
    1. 활성 블로그 목록 조회
    2. 각 블로그별로:
       - LLM으로 주제 생성
       - 초안 작성
       - HTML 렌더링
       - WordPress 발행 or S3 패키징
    3. 결과 알림 전송
    """
    log.info("블로그 자동화 시작")
    blogs = fetch_active_blogs()
    results: List[Dict[str, Any]] = []

    for blog in blogs:
        blog_id = blog["id"]
        blog_name = blog["blog_name"]

        try:
            # 1) 주제 생성
            log.info(f"[{blog_name}] 주제 생성 중...")
            topic_llm = get_llm("topic")
            topic_response = topic_llm.invoke(
                f"블로그 '{blog_name}'에 적합한 한국어 트렌디 글 주제를 1개만 제시하세요. "
                f"12~20자 이내로 작성해주세요."
            )
            topic = str(topic_response.content).strip()
            log_execution(blog_id, "topic_generation", "success", topic)
            log.info(f"[{blog_name}] 주제: {topic}")

            # 2) 초안 작성
            log.info(f"[{blog_name}] 초안 작성 중...")
            draft_llm = get_llm("draft")
            draft_response = draft_llm.invoke(
                f"""
주제: {topic}

아래 규격에 맞춰 블로그 글을 작성해주세요:
- H1 제목 1개
- H2 소제목 3~6개
- 각 문단은 80~140자
- 표 1개 포함
- 리스트 1개 포함
- FAQ 3개 포함
- 이미지 플레이스홀더 [IMG1], [IMG2] 등 포함
- CTA (Call-To-Action) 위치 표시

과장 금지, 정보 제공 목적임을 명시하세요.
HTML 형식으로 작성해주세요 (마크다운 아님).
"""
            )
            draft_content = str(draft_response.content)
            log_execution(blog_id, "draft_writing", "success", f"초안 {len(draft_content)}자")

            # 3) SEO 렌더링
            log.info(f"[{blog_name}] HTML 렌더링 중...")
            if render_html is None:
                raise ImportError("render 모듈을 찾을 수 없습니다")

            rendered = render_html(
                topic=topic,
                intent="정보",
                outline=["개요", "핵심 단계", "실전 사례", "주의사항"],
                images=4
            )

            # 초안 내용을 렌더링된 HTML에 통합
            final_html = rendered["html"].replace(
                f"<h1>{topic}</h1>",
                f"<h1>{topic}</h1>\n{draft_content}"
            )

            # 4) 발행/패키징
            platform = blog.get("platform", "").lower()

            if platform == "wordpress":
                log.info(f"[{blog_name}] WordPress 발행 중...")
                wp_response = publish_to_wordpress(blog, topic, final_html)
                wp_post_id = wp_response.get("id")

                save_article(
                    blog_id=blog_id,
                    title=topic,
                    content=draft_content,
                    html=final_html,
                    status="published",
                    wp_post_id=wp_post_id
                )
                log_execution(blog_id, "publish_wordpress", "success", f"post_id={wp_post_id}")

                results.append({
                    "blog": blog_name,
                    "platform": "wordpress",
                    "post_id": wp_post_id,
                    "url": wp_response.get("link", "")
                })

            else:  # Tistory
                log.info(f"[{blog_name}] S3 패키징 중...")
                timestamp = int(time.time())
                s3_key = f"{blog_id}/{timestamp}_{topic[:20]}.html"
                s3_uri = upload_to_s3(s3_key, final_html)

                save_article(
                    blog_id=blog_id,
                    title=topic,
                    content=draft_content,
                    html=final_html,
                    status="draft",
                    s3_uri=s3_uri
                )
                log_execution(blog_id, "tistory_package", "success", s3_uri)

                results.append({
                    "blog": blog_name,
                    "platform": "tistory",
                    "package": s3_uri
                })

        except Exception as e:
            error_msg = f"[{blog_name}] 실패: {e}"
            log.exception(error_msg)
            log_execution(blog_id, "error", "failed", str(e))
            send_notification(error_msg)

            results.append({
                "blog": blog_name,
                "error": str(e)
            })

    # 완료 알림
    success_count = len([r for r in results if "error" not in r])
    summary = f"블로그 자동화 완료: {success_count}/{len(results)}건 성공"
    log.info(summary)
    send_notification(summary)

    return {
        "statusCode": 200,
        "body": {
            "success": True,
            "processed": len(results),
            "results": results
        }
    }


# 로컬 테스트용
if __name__ == "__main__":
    # .env 파일 로드
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    result = lambda_handler({}, None)
    print("\n=== 실행 결과 ===")
    print(result)