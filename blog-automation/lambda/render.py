# lambda/render.py
# 목적: 본문 규격 템플릿 + 메타 생성
from __future__ import annotations
from typing import List, Dict, Any
import re

def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9\\- ]+", "", s)
    s = re.sub(r"\\s+", "-", s).strip("-")
    return s or "post"

def render_html(topic: str, intent: str, outline: List[str], images: int = 4) -> Dict[str, Any]:
    style = """
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans KR',sans-serif;line-height:1.75}
  table{width:100%;border-collapse:collapse;margin:1em 0}
  th,td{border:1px solid #e5e7eb;padding:10px}
  .cta{border:1px dashed #9ca3af;padding:14px;margin:18px 0;background:#f9fafb}
  .caption{font-size:.9em;color:#6b7280}
</style>
""".strip()
    h = [f"<h1>{topic}</h1>", f"<p>검색 의도: {intent}. 본 문서는 자동화 파이프라인으로 생성되었습니다.</p>"]
    for h2 in outline[:6]:
        h += [f"<h2>{h2}</h2>", "<p>80–140자 단락 예시. 과장 없이 핵심만 설명합니다.</p>"]
    h += [
        "<h2>핵심 비교 표</h2>",
        "<table><thead><tr><th>항목</th><th>내용</th><th>메모</th></tr></thead><tbody>"
        "<tr><td>검색 의도</td><td>정보/상업/거래</td><td>키워드 성격</td></tr>"
        "<tr><td>벤치마킹</td><td>상위 문서 요약</td><td>중복 제거</td></tr>"
        "<tr><td>본문 규격</td><td>H1=1,H2=3–6,표1,리스트1,FAQ3</td><td></td></tr>"
        "</tbody></table>",
        "<h2>작성 체크리스트</h2>",
        "<ul><li>연관질의 커버</li><li>격차 보완</li><li>이미지 3–5장 alt/캡션/출처</li><li>CTA 2–3개</li><li>메타 타이틀/설명</li></ul>",
        "<h2>이미지 삽입 위치</h2>",
    ]
    for i in range(images):
        h.append(f"<p>[IMG{i+1}] — 캡션·출처·alt 기입</p>")
    h += [
        "<h2>FAQ</h2>",
        "<details><summary>1) 핵심 개념?</summary><p>간단 설명.</p></details>",
        "<details><summary>2) 적용법?</summary><p>단계별 절차.</p></details>",
        "<details><summary>3) 흔한 오류?</summary><p>원인/해결.</p></details>",
        '<div class="cta" id="CTA_TOP">[CTA_TOP] 제휴 링크 (rel="nofollow sponsored")</div>',
        '<div class="cta" id="CTA_MID">[CTA_MID] 체크리스트 다운로드</div>',
        '<div class="cta" id="CTA_BOTTOM">[CTA_BOTTOM] 상담/데모</div>',
    ]
    meta = {
        "title": f"{topic} 완전 가이드: 핵심 요약과 실전 팁",
        "description": "검색의도부터 본문/이미지/메타/CTA까지 한 번에 구성한 실전 가이드.",
        "tags": ["SEO","블로그자동화","워드프레스","티스토리","콘텐츠마케팅"],
        "slug": slugify(topic),
    }
    return {"html": style + "\n" + "\n".join(h), "meta": meta}
