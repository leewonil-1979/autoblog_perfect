# 🚀 Blog Auto MVP - 실행 완전 가이드

## 📋 목차

1. [현재 시스템 상태](#-현재-시스템-상태)
2. [실행 플로우](#-실행-플로우-step-by-step)
3. [예상 결과](#-예상-결과)
4. [문제 해결](#-문제-해결-체크리스트)

---

## 🎯 현재 시스템 상태

### ✅ 준비 완료 항목

```text
✓ PostgreSQL DB 실행 중 (blog_auto_db, healthy)
✓ Python 환경: conda blog_auto_LangGraph
✓ 환경 변수: .env 파일 설정 완료
  - DATABASE_URL ✓
  - OPENAI_API_KEY ✓
  - ANTHROPIC_API_KEY ✓
  - AWS_REGION ✓
✓ 등록된 블로그: 1개 (테스트 블로그 - WordPress)
```

---

## 🔄 실행 플로우 (Step-by-Step)

### **Step 1: 데이터베이스 상태 확인** 📊

```powershell
# DB 컨테이너 상태
docker ps --filter "name=blog_auto_db"

# 블로그 목록 확인
docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation -c "SELECT * FROM blogs;"

# 테이블 구조 확인
docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation -c "\dt"
```

**예상 출력:**

```text
✅ blog_auto_db: Up 23 hours (healthy)
✅ blogs 테이블: 1개 활성 블로그
✅ 테이블: blogs, articles, execution_logs, publishing_queue
```

---

### **Step 2: 로컬 테스트 실행** 🧪

#### **옵션 A: 전체 플로우 테스트 (권장)**

```powershell
# 1. 가상환경 활성화
conda activate blog_auto_LangGraph

# 2. lambda 디렉토리로 이동
cd lambda

# 3. 테스트 스크립트 실행
python test_local.py
```

**실행 과정:**
```
┌─────────────────────────────────────────────────┐
│ 1. 환경 변수 검증                                │
│    ✓ DATABASE_URL                               │
│    ✓ OPENAI_API_KEY                             │
│    ✓ ANTHROPIC_API_KEY                          │
│    ⚠ S3_BUCKET_TISTORY (Tistory용, 선택)        │
│    ⚠ SLACK_WEBHOOK_URL (알림, 선택)             │
├─────────────────────────────────────────────────┤
│ 2. 모듈 임포트 확인                              │
│    ✓ psycopg2 (PostgreSQL)                      │
│    ✓ requests (HTTP)                            │
│    ✓ langchain (LangChain 코어)                 │
│    ✓ langchain_openai (OpenAI)                  │
│    ✓ langchain_anthropic (Anthropic)            │
│    ✓ boto3 (AWS SDK)                            │
├─────────────────────────────────────────────────┤
│ 3. DB 연결 테스트                                │
│    ✓ PostgreSQL 연결 성공                        │
│    ✓ 활성 블로그: 1개 발견                       │
├─────────────────────────────────────────────────┤
│ 4. Lambda 핸들러 실행 🚀                        │
│    ├─ [테스트 블로그] 주제 생성 중...           │
│    │  └─ Claude Haiku 호출                       │
│    │     → "2025 AI 트렌드 완벽 정리" (예시)    │
│    │                                             │
│    ├─ [테스트 블로그] 초안 작성 중...           │
│    │  └─ GPT-4o-mini 호출                        │
│    │     → 1,500자 HTML 본문 생성                │
│    │                                             │
│    ├─ [테스트 블로그] HTML 렌더링 중...         │
│    │  └─ render.py 실행                          │
│    │     → SEO 최적화 HTML (CSS + FAQ + Table)  │
│    │                                             │
│    └─ [테스트 블로그] WordPress 발행 중...      │
│       └─ REST API 호출                           │
│          → POST /wp-json/wp/v2/posts            │
│          ✓ post_id: 123 (예시)                  │
├─────────────────────────────────────────────────┤
│ 5. 결과 저장                                     │
│    ✓ articles 테이블에 저장                      │
│    ✓ execution_logs 기록                        │
│    ✓ 알림 전송 (설정 시)                        │
└─────────────────────────────────────────────────┘
```

**예상 실행 시간:** 30~60초
- 주제 생성: 3~5초
- 초안 작성: 10~15초
- HTML 렌더링: 1초
- WordPress 발행: 5~10초

---

#### **옵션 B: render.py만 테스트**

```powershell
python render.py
```

**예상 출력:**
```html
=== HTML 미리보기 ===
<style>
  body { font-family: -apple-system... }
  h1 { font-size: 2.25em... }
  ...
</style>
<h1>AI 블로그 자동화 완벽 가이드</h1>
<p><strong>검색 의도:</strong> 정보...</p>
...

=== 메타 정보 ===
  title: AI 블로그 자동화 완벽 가이드 - 완전 가이드
  description: AI 블로그 자동화 완벽 가이드에 대한 상세 가이드...
  slug: ai-블로그-자동화-완벽-가이드
  author: Blog Auto Generator
  lang: ko
```

---

#### **옵션 C: handler.py 직접 실행**

```powershell
python handler.py
```

전체 Lambda 핸들러를 실행하여 실제 블로그에 포스팅합니다.

---

### **Step 3: 결과 확인** 📊

#### **A. 데이터베이스에서 확인**

```powershell
# 생성된 아티클 확인
docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation -c "SELECT id, title, status, created_at FROM articles ORDER BY created_at DESC LIMIT 5;"

# 실행 로그 확인
docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation -c "SELECT step, status, message, created_at FROM execution_logs ORDER BY created_at DESC LIMIT 10;"
```

**예상 출력:**
```
articles 테이블:
 id |          title           | status    |       created_at
----+--------------------------+-----------+------------------------
  1 | 2025 AI 트렌드 완벽 정리 | published | 2025-10-12 20:05:23

execution_logs 테이블:
      step        | status  |        message         |       created_at
------------------+---------+------------------------+------------------------
 topic_generation | success | 2025 AI 트렌드...      | 2025-10-12 20:05:15
 draft_writing    | success | 초안 1523자            | 2025-10-12 20:05:18
 publish_wordpress| success | post_id=123            | 2025-10-12 20:05:23
```

---

#### **B. WordPress에서 확인**

블로그 관리자 페이지로 이동:
```
https://테스트블로그.com/wp-admin/edit.php
```

**확인 사항:**
- ✅ 새 포스트가 "발행됨" 상태로 생성되었는지
- ✅ 제목, 본문, HTML 구조 확인
- ✅ SEO 메타 태그 확인

---

#### **C. 실제 블로그 페이지 확인**

생성된 포스트 URL:
```
https://테스트블로그.com/포스트-슬러그/
```

**체크리스트:**
- ✅ H1 제목 표시
- ✅ H2 소제목 3~6개
- ✅ 표(Table) 포함
- ✅ FAQ 섹션 (접기/펼치기)
- ✅ CTA 버튼 3개 위치
- ✅ 모바일 반응형 디자인

---

### **Step 4: VS Code Tasks로 실행** (선택사항)

```
Ctrl + Shift + P → "Tasks: Run Task"
```

**사용 가능한 작업:**
- 🐳 DB 시작
- 🛑 DB 중지
- 📊 DB 접속 (psql)
- 🧪 **로컬 테스트** ← 이것 선택!
- 🔍 render.py 테스트
- 📦 의존성 설치
- 📝 샘플 데이터 삽입

---

## 🎁 예상 결과

### ✅ 성공 시나리오

```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "processed": 1,
    "results": [
      {
        "blog": "테스트 블로그",
        "platform": "wordpress",
        "post_id": 123,
        "url": "https://테스트블로그.com/2025-ai-트렌드-완벽-정리/"
      }
    ]
  }
}
```

**생성된 콘텐츠 예시:**

#### HTML 구조:
```html
<style>/* SEO 최적화 CSS */</style>
<h1>2025 AI 트렌드 완벽 정리</h1>
<p><strong>검색 의도:</strong> 정보...</p>

<h2>AI 기술의 현재</h2>
<p>80~140자 단락...</p>

<h2>핵심 비교 표</h2>
<table>
  <thead>
    <tr><th>항목</th><th>내용</th></tr>
  </thead>
  <tbody>...</tbody>
</table>

<h2>자주 묻는 질문 (FAQ)</h2>
<details>
  <summary>1) 핵심 개념은?</summary>
  <p>답변...</p>
</details>

<div class="cta">🎁 [CTA_TOP] 제휴 링크...</div>
```

---

### ❌ 실패 시나리오 & 해결

#### **에러 1: DB 연결 실패**
```python
psycopg2.OperationalError: could not connect to server
```

**해결:**
```powershell
docker compose -f docker-compose.db.yml up -d
docker ps --filter "name=blog_auto_db"
```

---

#### **에러 2: API 키 없음**
```python
OpenAI API key not found
```

**해결:**
`.env` 파일에서 `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` 확인

---

#### **에러 3: WordPress 인증 실패**
```python
requests.exceptions.HTTPError: 401 Unauthorized
```

**해결:**
1. WordPress Application Password 재생성
2. DB의 `blogs` 테이블에서 `wp_user`, `wp_app_password` 업데이트

```sql
UPDATE blogs
SET wp_user = 'admin',
    wp_app_password = 'xxxx xxxx xxxx xxxx'
WHERE id = 1;
```

---

#### **에러 4: 모듈 임포트 실패**
```python
ModuleNotFoundError: No module named 'langchain_openai'
```

**해결:**
```powershell
conda activate blog_auto_LangGraph
pip install -r lambda/requirements.txt
```

---

## 📈 비용 추정 (참고)

### LLM API 호출 비용 (블로그 1개 기준)

| 단계 | 모델 | 토큰 | 비용 (USD) |
|------|------|------|------------|
| 주제 생성 | Claude Haiku | ~200 | $0.0001 |
| 초안 작성 | GPT-4o-mini | ~1,500 | $0.0008 |
| **합계** | | ~1,700 | **$0.0009** |

**월간 비용 (매일 1회 실행):**
- 30일 × $0.0009 = **$0.027** (약 35원)

---

## 🚀 프로덕션 배포 (AWS Lambda)

### **Step 1: Lambda 함수 생성**

```powershell
# 배포 패키지 생성
.\scripts\deploy_lambda.ps1

# 또는 수동으로:
cd lambda
pip install -r requirements.txt -t package/
copy handler.py package/
copy render.py package/
cd package
Compress-Archive -Path * -DestinationPath ../lambda.zip
```

### **Step 2: AWS Lambda 업로드**

```bash
aws lambda create-function \
  --function-name blog-automation \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler handler.lambda_handler \
  --zip-file fileb://lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{DATABASE_URL=...,OPENAI_API_KEY=...}"
```

### **Step 3: EventBridge 스케줄 설정**

```bash
# 매일 오전 9시 실행
aws events put-rule \
  --name blog-auto-daily \
  --schedule-expression "cron(0 0 * * ? *)"

aws events put-targets \
  --rule blog-auto-daily \
  --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:blog-automation"
```

---

## 🎯 요약: 5분 빠른 테스트

```powershell
# 1. 환경 활성화
conda activate blog_auto_LangGraph

# 2. 테스트 실행
cd lambda
python test_local.py

# 3. 결과 확인
docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation -c "SELECT * FROM articles ORDER BY created_at DESC LIMIT 1;"
```

**예상 시간:** 1~2분
**예상 비용:** $0.0009 (약 1.2원)
**예상 결과:** WordPress에 AI 생성 블로그 포스트 자동 발행 ✅

---

## 📞 문제 해결 체크리스트

- [ ] Docker Desktop 실행 중?
- [ ] DB 컨테이너 healthy 상태?
- [ ] `.env` 파일 존재 및 API 키 설정?
- [ ] Python 가상환경 활성화?
- [ ] 의존성 패키지 설치 완료?
- [ ] WordPress 블로그 접근 가능?
- [ ] Application Password 유효?

---

**Made with ❤️ using LangChain, AWS Lambda, and PostgreSQL**
