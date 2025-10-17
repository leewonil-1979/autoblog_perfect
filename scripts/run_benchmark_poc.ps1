param(
  [Parameter(Mandatory=$true)][string]$Keyword,
  [int]$Limit = 30
)

$ErrorActionPreference = "Stop"

Write-Host "[1/2] 수집 시작..." -ForegroundColor Cyan
python tools/benchmark_crawler.py --keyword "$Keyword" --limit $Limit
if ($LASTEXITCODE -ne 0) { throw "benchmark_crawler 실패" }

# 가장 최근 raw 파일 찾기
$rawDir = "data/benchmark/raw"
$latest = Get-ChildItem $rawDir -Filter *.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) { throw "raw JSON을 찾을 수 없습니다: $rawDir" }

Write-Host "[2/2] 패턴 추출: $($latest.FullName)" -ForegroundColor Cyan
python tools/pattern_extractor.py --input $latest.FullName
if ($LASTEXITCODE -ne 0) { throw "pattern_extractor 실패" }

Write-Host "`n[완료] 결과:"
Write-Host "  - 원본: $($latest.FullName)"
$pattern = $latest.FullName -replace "data\\benchmark\\raw", "data\\benchmark\\pattern_cards" -replace ".json$", "_pattern.json"
Write-Host "  - 패턴카드: $pattern"
