# Blog Automation (LangGraph + Lambda)

## 빠른 시작
1) Docker Desktop 설치
2) .env 생성: .env.example 복사 후 값 입력
3) DB 기동: `docker compose -f docker-compose.db.yml up -d`
4) 테이블 확인: `docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation -c "\dt"`
5) VS Code에서 이 폴더 열기 → 아래 "VS Code 명령" 사용