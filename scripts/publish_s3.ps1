<#
목적: 로컬 파일을 S3에 업로드하고 프리사인 URL을 받아 출력/파일 저장
사용:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish_s3.ps1 `
    -FilePath .\dist\post.html -Slug "hello-world" -Expires 900 -Profile "blog-auto"
필수: tools\s3_publish.py, .env(AWS_*, S3_BUCKET_TISTORY)
#>

param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $true)][string]$Slug,
    [int]$Expires = 900,
    [string]$Profile = ""
)

# ==== 출력 인코딩 UTF-8 강제 (param 아래로 이동) ====
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
}
catch { }

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# 날짜 기반 키 생성: posts/YYYY-MM-DD-slug.html
$today = Get-Date -Format "yyyy-MM-dd"
$key = "posts/$today-$Slug.html"

# 경로 검증
if (-not (Test-Path -LiteralPath $FilePath)) {
    Write-Error "파일이 없습니다: $FilePath"
    exit 2
}

# Python 실행기/스크립트 경로
$py = "python"
$tool = "tools/s3_publish.py"

# 실행 시작 로그
Write-Host ("업로드 시작: {0} -> {1}" -f $FilePath, $key)

# s3_publish 실행
try {
    if ($Profile) {
        $url = & $py $tool --file $FilePath --key $key --expires $Expires --profile $Profile
    }
    else {
        $url = & $py $tool --file $FilePath --key $key --expires $Expires
    }
    if ($LASTEXITCODE -ne 0) { throw "s3_publish.py 실패 (exit $LASTEXITCODE)" }

    $url = ($url | Out-String).Trim()

    Write-Host ("프리사인 URL: {0}" -f $url)

    # 결과 저장 (UTF-8)
    $outDir = "artifacts"
    if (-not (Test-Path -LiteralPath $outDir)) {
        New-Item -ItemType Directory -Path $outDir | Out-Null
    }
    $outFile = Join-Path $outDir ("presign-{0}-{1}.txt" -f $today, $Slug)
    Set-Content -Path $outFile -Value $url -Encoding UTF8

    Write-Host ("완료. URL 저장: {0}" -f $outFile)
    exit 0
}
catch {
    Write-Error $_
    exit 1
}
