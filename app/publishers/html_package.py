# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict

BASE_STYLE = """
body { font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; line-height:1.7; color:#222; max-width:860px; margin:0 auto; padding:24px; }
h1,h2,h3 { color:#1f2937; }
blockquote { border-left:4px solid #3b82f6; padding-left:12px; color:#555; }
img { max-width:100%; height:auto; }
.cta { margin:24px 0; padding:16px; border:1px dashed #aaa; }
"""

def build_html_package(title: str, markdown_body: str) -> Dict[str, str]:
    # 간단: 이미 LangGraph에서 마크다운을 생성한다고 가정하고, 그대로 HTML 래핑
    # [IMG1] 등 플레이스홀더는 티스토리/네이버 편집기에서 수동 교체
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>{BASE_STYLE}</style></head>
<body>
<h1>{title}</h1>
<div class="cta">[CTA_TOP] 제휴/배너 자리 (rel="nofollow sponsored")</div>
{markdown_body}
<div class="cta">[CTA_MID] 중간 배치 CTA</div>
<p>[IMG1] [IMG2] [IMG3] (업로드 후 alt/캡션 입력)</p>
<div class="cta">[CTA_BOTTOM] 하단 배치 CTA</div>
</body></html>"""
    return {"filename": f"{title}.html", "html": html}
