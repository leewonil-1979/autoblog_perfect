Param()
$ErrorActionPreference = "Stop"

Write-Host "[1/4] .env 생성(.env.example 복사)"
if (-Not (Test-Path ".env")) { Copy-Item ".env.example" ".env" ; Write-Host "-> .env 생성됨" } else { Write-Host "-> .env 이미 존재" }

Write-Host "[2/4] Docker로 Postgres 기동"
docker compose -f docker-compose.db.yml up -d

Write-Host "[3/4] Health 대기"
for ($i=0; $i -lt 20; $i++) {
  try {
    $status = docker inspect --format='{{json .State.Health.Status}}' blog_auto_db 2>$null
  } catch { $status = '"starting"' }
  Write-Host "  상태: $status"
  if ($status -eq '"healthy"') { break }
  Start-Sleep -Seconds 2
}

Write-Host "[4/4] 테이블 확인"
docker compose -f docker-compose.db.yml exec postgres psql -U blog_user -d blog_automation -c "\dt"
Write-Host "완료. VS Code로 폴더를 열어 작업을 계속하세요."
