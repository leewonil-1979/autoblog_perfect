param(
    [Parameter(Mandatory = $true)][string]$Slug,              # 예: 2025-10-15-first-post
    [Parameter(Mandatory = $true)][string]$Title,             # 예: "첫 테스트 글"
    [string]$HtmlPath = ".\dist\post.html",
    [string]$ImagesDir = ".\dist\images",
    [string]$Featured = ".\dist\images\cover.jpg",
    [string]$Tags = "automation,blog,seo",
    [ValidateSet("publish", "draft", "private")][string]$Status = "draft"
)

$ErrorActionPreference = "Stop"

function Send-Webhook($Url, $BodyObj) {
    try {
        if ([string]::IsNullOrWhiteSpace($Url)) { return }
        $json = $BodyObj | ConvertTo-Json -Depth 5
        Invoke-RestMethod -Uri $Url -Method Post -Body $json -ContentType "application/json" | Out-Null
        Write-Host "[알림] Webhook 전송 완료 → $Url" -ForegroundColor DarkCyan
    }
    catch {
        Write-Warning "[경고] Webhook 전송 실패: $($_.Exception.Message)"
    }
}

try {
    Write-Host "== 1) WordPress 초안/발행 실행 ==" -ForegroundColor Cyan
    # WordPress.com 발행 (이미지 업로드/치환/대표이미지)
    & python "tools/publish_wpcom.py" `
        --file $HtmlPath `
        --images $ImagesDir `
        --featured $Featured `
        --slug $Slug `
        --title $Title `
        --tags $Tags `
        --status $Status
    if ($LASTEXITCODE -ne 0) { throw "publish_wpcom.py 실패" }

    # 방금 글 URL을 입력받거나(간단), 로그에서 가져오는 방식도 가능
    $WpUrl = Read-Host "WordPress 글 URL을 붙여넣으세요(예: https://won201.wordpress.com/?p=123)"

    Write-Host "== 2) 붙여넣기용 HTML 생성(paste.html) ==" -ForegroundColor Cyan
    New-Item -ItemType Directory -Path ".\artifacts" -Force | Out-Null
    & python "tools/wpcom_export_post_html.py" --url $WpUrl --out "artifacts\paste.html"
    if ($LASTEXITCODE -ne 0) { throw "wpcom_export_post_html.py 실패" }

    # 선택: 티스토리/네이버 에디터 자동 오픈(반자동 붙여넣기)
    Start-Process "artifacts\paste.html"

    Write-Host "== 3) Slack/Notion 알림(선택) ==" -ForegroundColor Cyan
    # 여기서 '환경변수 설정 → post_publish_hooks.py 실행' 이 한 덩어리입니다.
    $env:POST_TITLE = $Title
    $env:POST_SLUG = $Slug
    $env:POST_URL = $WpUrl
    $env:POST_STATUS = "SUCCESS"
    $env:POST_KEYWORDS = $Tags
    python "scripts/post_publish_hooks.py"  # tools/notify_slack.py + tools/notion_logger.py 사용

    Write-Host "== 4) Make.com Webhook 알림(선택) ==" -ForegroundColor Cyan
    # .env에 MAKE_WEBHOOK_URL이 있는 경우에만 전송
    $makeUrl = $env:MAKE_WEBHOOK_URL
    Send-Webhook -Url $makeUrl -BodyObj @{
        event = "publish_complete"
        slug  = $Slug
        title = $Title
        url   = $WpUrl
        ts    = (Get-Date).ToString("s")
        site  = $env:WPCOM_SITE
        env   = $env:ENVIRONMENT
    }

    Write-Host "`n[완료] 발행 루프 정상 종료" -ForegroundColor Green
}
catch {
    Write-Error "[에러] $_"
    # 실패 알림도 남겨둡니다.
    $env:POST_TITLE = $Title
    $env:POST_SLUG = $Slug
    $env:POST_URL = $WpUrl
    $env:POST_STATUS = "FAILED"
    python "scripts/post_publish_hooks.py" 2>$null
    Send-Webhook -Url $env:MAKE_WEBHOOK_URL -BodyObj @{
        event = "publish_failed"; slug = $Slug; title = $Title; url = $WpUrl; ts = (Get-Date).ToString("s")
    }
    exit 1
}
