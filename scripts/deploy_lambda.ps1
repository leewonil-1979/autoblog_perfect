#!/usr/bin/env pwsh
# Lambda 배포 스크립트 (PowerShell)
param(
    [string]$FunctionName = "blog-automation",
    [string]$Region = "ap-northeast-2"
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Lambda 배포 시작..." -ForegroundColor Cyan

# 1. 디렉토리 설정
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LambdaDir = Join-Path $ProjectRoot "lambda"
$PackageDir = Join-Path $LambdaDir "package"
$ZipFile = Join-Path $LambdaDir "lambda.zip"

Set-Location $LambdaDir

# 2. 이전 빌드 정리
Write-Host "`n[1/5] 이전 빌드 정리..." -ForegroundColor Yellow
if (Test-Path $PackageDir) {
    Remove-Item -Recurse -Force $PackageDir
    Write-Host "  ✅ package/ 삭제됨"
}
if (Test-Path $ZipFile) {
    Remove-Item -Force $ZipFile
    Write-Host "  ✅ lambda.zip 삭제됨"
}

# 3. 의존성 설치
Write-Host "`n[2/5] 의존성 설치..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $PackageDir | Out-Null
pip install -r requirements.txt -t $PackageDir --no-cache-dir
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ pip install 실패" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ 패키지 설치 완료"

# 4. 코드 복사
Write-Host "`n[3/5] 코드 복사..." -ForegroundColor Yellow
Copy-Item "handler.py" $PackageDir
Copy-Item "render.py" $PackageDir
Write-Host "  ✅ handler.py, render.py 복사됨"

# 5. ZIP 생성
Write-Host "`n[4/5] ZIP 패키지 생성..." -ForegroundColor Yellow
Set-Location $PackageDir
Compress-Archive -Path * -DestinationPath $ZipFile -Force
Set-Location $LambdaDir
$ZipSize = (Get-Item $ZipFile).Length / 1MB
Write-Host "  ✅ lambda.zip 생성 ($([math]::Round($ZipSize, 2)) MB)"

# 6. AWS 배포
Write-Host "`n[5/5] AWS Lambda 업데이트..." -ForegroundColor Yellow
try {
    aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file "fileb://lambda.zip" `
        --region $Region | Out-Null

    Write-Host "  ✅ 배포 완료: $FunctionName ($Region)" -ForegroundColor Green
}
catch {
    Write-Host "  ⚠️  update-function-code 실패. 함수가 없으면 create-function을 실행하세요." -ForegroundColor Yellow
}

Write-Host "`n✅ 배포 프로세스 완료!" -ForegroundColor Green
Write-Host "`n다음 단계:" -ForegroundColor Cyan
Write-Host "  1. Lambda 콘솔에서 환경 변수 설정"
Write-Host "  2. EventBridge 스케줄 생성"
Write-Host "  3. CloudWatch Logs 확인"
