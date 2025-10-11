#!/usr/bin/env bash
set -euo pipefail
echo "[1/4] .env 생성(.env.example 복사)"
if [ ! -f ".env" ]; then cp .env.example .env; echo "-> .env 생성됨"; else echo "-> .env 이미 존재"; fi

echo "[2/4] Docker로 Postgres 기동"
docker compose -f docker-compose.db.yml up -d

echo "[3/4] Health 대기"
for i in {1..20}; do
  status=$(docker inspect --format='{{json .State.Health.Status}}' blog_auto_db 2>/dev/null || echo '"starting"')
  echo "  상태: ${status}"
  [[ $status == "\"healthy\"" ]] && break
  sleep 2
done

echo "[4/4] 테이블 확인"
docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation -c "\dt" || true
echo "완료. VS Code로 폴더를 열어 작업을 계속하세요."
