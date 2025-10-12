# 변경 이력 (CHANGELOG)

## [2.0.0] - 2025-10-11

### 🎉 주요 변경사항

- 전체 코드베이스 리팩토링 및 최적화
- 프로젝트 구조 재구성
- 상세한 문서화 추가

### ✨ 개선사항

#### handler.py

- **함수명 표준화**:
  - `model()` → `get_llm()` (LLM 팩토리)
  - `db_conn()` → `get_db_connection()` (DB 연결)
  - `log_exec()` → `log_execution()` (로깅)
  - `wp_publish()` → `publish_to_wordpress()` (발행)
  - `s3_upload_text()` → `upload_to_s3()` (S3 업로드)
  - `notify()` → `send_notification()` (알림)
  - `handler()` → `lambda_handler()` (Lambda 핸들러)

- **코드 개선**:
  - 더 명확한 독스트링 추가
  - 로깅 메시지 개선 (진행 상황 표시)
  - 에러 핸들링 강화
  - 불필요한 import 제거 (json, base64, Union, cast, BeautifulSoup)
  - 타입 힌트 정리
  - SQL 쿼리 가독성 향상 (멀티라인 포매팅)

- **새 기능**:
  - 로컬 테스트 지원 (`if __name__ == "__main__"`)
  - 발행 결과에 URL 포함
  - 성공/실패 카운트 표시
  - 더 상세한 결과 반환 (statusCode, body 구조)

#### render.py

- **함수 분리**:
  - CSS 스타일을 `get_base_style()` 함수로 분리
  - 더 나은 모듈화 구조

- **스타일 개선**:
  - H3 헤더 스타일 추가
  - 표 hover 효과 추가
  - FAQ 섹션 스타일 개선 (좌측 파란 보더)
  - 이미지 플레이스홀더 스타일 추가
  - 모바일 반응형 개선 (@media query)
  - 더 나은 색상 대비 및 가독성

- **메타 정보**:
  - 메타 description 동적 생성

#### README.md

- **대폭 확장된 문서**:
  - 상세한 빠른 시작 가이드
  - 시스템 아키텍처 다이어그램
  - 데이터베이스 스키마 설명
  - Lambda 배포 가이드
  - EventBridge 스케줄 설정
  - 문제 해결 섹션
  - 개발 가이드 (커스터마이징 방법)

#### requirements.txt

- **버전 고정**: 범위 지정(`>=`) 대신 정확한 버전 명시
- **호환성 보장**: 테스트된 버전으로 고정하여 안정성 확보

### 🆕 새 파일

1. **`lambda/test_local.py`**
   - 로컬 환경에서 Lambda 핸들러 테스트
   - 환경 변수 검증
   - 모듈 임포트 확인
   - DB 연결 테스트
   - 전체 플로우 실행

2. **`scripts/deploy_lambda.ps1`**
   - Windows PowerShell 배포 스크립트
   - 자동 빌드 및 ZIP 생성
   - AWS Lambda 업데이트

3. **`scripts/deploy_lambda.sh`**
   - Linux/Mac Bash 배포 스크립트
   - 크로스 플랫폼 지원

4. **`sample_data.sql`**
   - 테스트용 샘플 블로그 데이터
   - WordPress, Tistory 예시

5. **`.vscode/tasks.json`** (확장)
   - 🐳 DB 시작/중지/리셋
   - 📊 DB 접속 (psql)
   - 🧪 로컬 테스트 실행
   - 🚀 Lambda 배포
   - 📦 의존성 설치
   - 🔍 render.py 테스트
   - 📝 샘플 데이터 삽입

### 🐛 버그 수정

- REGION 변수명을 AWS_REGION으로 통일
- 타입 체크 에러 해결
- SQL 문법 오류 수정

### 📝 문서화

- 모든 함수에 독스트링 추가
- 인라인 주석 개선
- README 대폭 확장
- CHANGELOG 추가 (이 파일)

### 🔒 보안

- `.gitignore` 확장 (임시 파일, OS 파일 등)
- 환경 변수 검증 강화

## [1.0.0] - 2025-10-10

### 초기 버전

- 기본 Lambda 핸들러 구현
- WordPress/Tistory 지원
- PostgreSQL 스키마
- Docker Compose 설정
- 기본 README

