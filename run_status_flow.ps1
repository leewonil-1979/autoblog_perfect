# 발행 직후(게시 성공 시점)
$env:POST_TITLE = $Title
$env:POST_SLUG = $Slug
$env:POST_URL = $WpUrl
$env:POST_STATUS = "PUBLISHED"
python scripts/post_publish_hooks.py --status-update-only

# QA/크롤링 검증 통과 후
$env:POST_STATUS = "SUCCESS"
python scripts/post_publish_hooks.py --status-update-only