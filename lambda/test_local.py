#!/usr/bin/env python3
"""
로컬 테스트 스크립트
Lambda 핸들러를 로컬에서 실행하여 전체 플로우를 검증합니다.
"""
import os
import sys
from pathlib import Path

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    print("✅ .env 파일 로드 완료")
except ImportError:
    print("⚠️  python-dotenv가 설치되지 않았습니다. 환경 변수를 수동으로 설정하세요.")
    sys.exit(1)

# 환경 변수 검증
required_vars = ["DATABASE_URL"]
missing = [var for var in required_vars if not os.getenv(var)]

if missing:
    print(f"❌ 필수 환경 변수 누락: {', '.join(missing)}")
    sys.exit(1)

# 선택 변수 확인
optional_vars = {
    "OPENAI_API_KEY": "OpenAI GPT-4",
    "ANTHROPIC_API_KEY": "Anthropic Claude",
    "S3_BUCKET_TISTORY": "Tistory S3 패키징",
    "SLACK_WEBHOOK_URL": "Slack 알림",
    "MAKE_WEBHOOK_URL": "Make.com 알림"
}

print("\n📋 환경 변수 상태:")
for var, desc in optional_vars.items():
    status = "✅" if os.getenv(var) else "⚠️ "
    print(f"  {status} {desc} ({var})")

# 모듈 임포트 테스트
print("\n🔍 모듈 임포트 확인:")
modules = [
    ("psycopg2", "PostgreSQL"),
    ("requests", "HTTP 요청"),
    ("langchain", "LangChain"),
    ("langchain_openai", "OpenAI"),
    ("langchain_anthropic", "Anthropic"),
    ("boto3", "AWS SDK"),
]

for module_name, desc in modules:
    try:
        __import__(module_name)
        print(f"  ✅ {desc} ({module_name})")
    except ImportError:
        print(f"  ❌ {desc} ({module_name}) - 설치 필요")

# DB 연결 테스트
print("\n🔗 데이터베이스 연결 테스트:")
try:
    import psycopg2
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM blogs WHERE active = TRUE")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  ✅ 연결 성공! 활성 블로그: {count}개")

    if count == 0:
        print("  ⚠️  활성 블로그가 없습니다. blogs 테이블에 데이터를 추가하세요.")
        sys.exit(0)

except Exception as e:
    print(f"  ❌ 연결 실패: {e}")
    sys.exit(1)

# 핸들러 실행
print("\n🚀 Lambda 핸들러 실행:")
print("=" * 60)

try:
    from handler import lambda_handler

    result = lambda_handler({}, None)

    print("\n" + "=" * 60)
    print("✅ 실행 완료!")
    print(f"\n처리 결과: {result}")

except Exception as e:
    print("\n" + "=" * 60)
    print(f"❌ 실행 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
