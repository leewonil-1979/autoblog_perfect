# 🤖 Blog Automation System (LangGraph + Lambda)

AI 기반 블로그 자동 포스팅 시스템. LangChain을 활용하여 주제 생성, 글 작성, SEO 최적화, 그리고 WordPress/Tistory 발행을 자동화합니다.

## 🎯 주요 기능

- **AI 콘텐츠 생성**: GPT-4 mini / Claude Haiku를 활용한 주제 생성 및 초안 작성
- **SEO 최적화**: H1/H2 구조, 메타 태그, FAQ, 테이블, 이미지 플레이스홀더 자동 생성
- **멀티 플랫폼**: WordPress REST API, Tistory S3 패키징 지원
- **실행 로깅**: PostgreSQL 기반 실행 이력 및 비용 추적
- **알림 통합**: Slack, Make.com 웹훅 지원

## 📁 프로젝트 구조

```text
blog_auto_mvp/
├── lambda/                    # AWS Lambda 함수
│   ├── handler.py            # 메인 핸들러
│   ├── render.py             # HTML 템플릿 렌더러
│   └── requirements.txt      # Python 의존성
├── scripts/                   # 유틸리티 스크립트
│   ├── setup.ps1             # Windows 셋업
│   └── setup.sh              # Linux/Mac 셋업
├── .vscode/                   # VS Code 설정
├── init.sql                   # DB 초기화 스크립트
├── docker-compose.db.yml      # PostgreSQL Docker 구성
├── .env.example               # 환경 변수 템플릿
└── README.md                  # 이 파일
```

## 🚀 빠른 시작

### 1. 사전 요구사항

- **Docker Desktop** (PostgreSQL 실행용)
- **Python 3.9+** (로컬 테스트용)
- **VS Code** (권장)
- **API Keys**: OpenAI, Anthropic (선택)

### 2. 로컬 환경 셋업

```powershell
# Windows (PowerShell)
cd c:\blog_auto_mvp
.\scripts\setup.ps1

# Linux/Mac
cd ~/blog_auto_mvp
chmod +x scripts/setup.sh
./scripts/setup.sh
```

셋업 스크립트가 자동으로 수행하는 작업:

1. `.env` 파일 생성 (`.env.example` 복사)
2. PostgreSQL Docker 컨테이너 시작
3. 데이터베이스 스키마 초기화 (init.sql 실행)
4. Health Check 확인

### 3. 환경 변수 설정

`.env` 파일을 열어 필수 값을 입력하세요:

```bash
# 데이터베이스
DATABASE_URL=postgresql://blog_user:strong_password_here@localhost:5432/blog_automation

# AI 모델 키 (최소 하나 필요)
OPENAI_API_KEY=sk-xxxx                # GPT-4 mini 사용
ANTHROPIC_API_KEY=sk-ant-xxxx         # Claude Haiku 사용 (저렴)

# AWS (Tistory S3 패키징용)
AWS_REGION=ap-northeast-2
S3_BUCKET_TISTORY=your-bucket-name

# 알림 (선택사항)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
MAKE_WEBHOOK_URL=https://hook.make.com/xxx
```

### 4. 블로그 등록

PostgreSQL에 접속하여 블로그를 등록합니다:

```powershell
# Docker 컨테이너 접속
docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation

# 블로그 추가 (WordPress 예시)
INSERT INTO blogs (blog_name, blog_url, platform, wp_user, wp_app_password, active)
VALUES ('내 블로그', 'https://myblog.com', 'wordpress', 'admin', 'xxxx xxxx xxxx xxxx xxxx xxxx', true);

# 블로그 추가 (Tistory 예시)
INSERT INTO blogs (blog_name, blog_url, platform, active)
VALUES ('티스토리 블로그', 'https://myblog.tistory.com', 'tistory', true);
```

### 5. 로컬 테스트

```powershell
# 가상환경 활성화 (선택)
conda activate blog_auto_LangGraph

# 의존성 설치
cd lambda
pip install -r requirements.txt

# 핸들러 실행
python handler.py
```

## 🏗️ 시스템 아키텍처

```text
┌─────────────────┐
│  EventBridge    │  ← 정기 실행 (예: 매일 오전 9시)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Lambda Handler │  ← handler.py
└────────┬────────┘
         │
         ├─→ [LangChain] 주제 생성 (Claude Haiku)
         ├─→ [LangChain] 초안 작성 (GPT-4 mini)
         ├─→ [render.py] HTML 렌더링
         │
         ├─→ [WordPress] REST API 발행
         ├─→ [S3] Tistory 패키징
         │
         └─→ [PostgreSQL] 로그 저장
             [Slack/Make] 알림 전송
```

## 📊 데이터베이스 스키마

- **blogs**: 블로그 정보 (URL, 플랫폼, 인증)
- **articles**: 생성된 아티클 (제목, 본문, HTML, 상태)
- **execution_logs**: 실행 로그 (단계, 상태, 비용)
- **publishing_queue**: 재시도 큐 (실패 시 재시도)

자세한 스키마는 `init.sql` 참조.

## 🧪 테스트

### 렌더러 단독 테스트

```powershell
cd lambda
python render.py
```

### 핸들러 테스트 (DB 연결 필요)

```powershell
cd lambda
python handler.py
```

## 📦 Lambda 배포

### 배포 패키지 생성

```powershell
cd lambda

# 의존성 설치
pip install -r requirements.txt -t package/

# 코드 복사
copy handler.py package/
copy render.py package/

# 압축
cd package
tar -a -c -f ../lambda.zip *
cd ..
```

### AWS Lambda 생성

```bash
aws lambda create-function \
  --function-name blog-automation \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler handler.lambda_handler \
  --zip-file fileb://lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{DATABASE_URL=postgresql://...,OPENAI_API_KEY=sk-...}"
```

### EventBridge 스케줄 설정

```bash
# 매일 오전 9시 실행
aws events put-rule \
  --name blog-auto-daily \
  --schedule-expression "cron(0 0 * * ? *)"

aws events put-targets \
  --rule blog-auto-daily \
  --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:blog-automation"
```

## 🛠️ 문제 해결

### DB 연결 실패

```powershell
# 컨테이너 상태 확인
docker ps

# 로그 확인
docker compose -f docker-compose.db.yml logs postgres

# 재시작
docker compose -f docker-compose.db.yml restart
```

### Import 에러

```powershell
# 패키지 재설치
pip install --force-reinstall -r lambda/requirements.txt
```

### Pylance 타입 에러

`.vscode/settings.json`에서 이미 타입 체크를 비활성화했습니다. VS Code를 재시작하세요.

## 📝 개발 가이드

### 새 플랫폼 추가

1. `handler.py`의 `lambda_handler()` 함수에서 플랫폼 조건 추가
2. 발행 함수 구현 (예: `publish_to_naver()`)
3. `blogs` 테이블에 플랫폼별 필드 추가

### 프롬프트 커스터마이징

`handler.py`의 LLM 호출 부분에서 프롬프트 수정:

- 주제 생성: 228줄
- 초안 작성: 236줄

### 스타일 변경

`render.py`의 `get_base_style()` 함수에서 CSS 수정

## 📄 라이선스

MIT License

## 🤝 기여

이슈 및 PR 환영합니다!

---

Made with ❤️ using LangChain, AWS Lambda, and PostgreSQL
