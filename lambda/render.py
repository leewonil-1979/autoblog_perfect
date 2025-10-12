# lambda/render.py
"""
HTML 템플릿 렌더링 모듈
- SEO 최적화된 HTML 생성
- 메타 정보 자동 생성
- 반응형 디자인 스타일 포함
"""
import re
from typing import List, Dict, Any


# ===== 유틸리티 함수 =====
def slugify(title: str) -> str:
    """제목을 URL-safe slug로 변환"""
    s = title.lower()
    # 한글, 영문, 숫자, 하이픈만 유지
    s = re.sub(r"[^a-z0-9\s\-가-힣]+", "", s)
    # 공백을 하이픈으로 변환
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "post"


def get_base_style() -> str:
    """반응형 CSS 스타일 반환"""
    return """<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif;
    line-height: 1.75;
    color: #1f2937;
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
    background-color: #ffffff;
  }

  h1 {
    font-size: 2.25em;
    margin: 0.5em 0;
    color: #111827;
    font-weight: 700;
  }

  h2 {
    font-size: 1.75em;
    margin: 1.2em 0 0.6em;
    color: #1f2937;
    border-bottom: 2px solid #e5e7eb;
    padding-bottom: 0.3em;
    font-weight: 600;
  }

  h3 {
    font-size: 1.25em;
    margin: 1em 0 0.5em;
    color: #374151;
    font-weight: 600;
  }

  p {
    margin: 1em 0;
    line-height: 1.8;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5em 0;
    border: 1px solid #d1d5db;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }

  th, td {
    border: 1px solid #e5e7eb;
    padding: 12px 16px;
    text-align: left;
  }

  th {
    background-color: #f3f4f6;
    font-weight: 600;
    color: #374151;
  }

  tbody tr:hover {
    background-color: #f9fafb;
  }

  ul, ol {
    margin: 1em 0;
    padding-left: 2em;
  }

  li {
    margin: 0.6em 0;
    line-height: 1.7;
  }

  .cta {
    border: 2px dashed #9ca3af;
    padding: 20px;
    margin: 24px 0;
    background-color: #f9fafb;
    border-radius: 8px;
    text-align: center;
  }

  .cta strong {
    color: #dc2626;
    font-size: 1.1em;
  }

  .image-placeholder {
    background-color: #f3f4f6;
    border: 2px dashed #d1d5db;
    padding: 40px 20px;
    margin: 20px 0;
    text-align: center;
    color: #6b7280;
    border-radius: 4px;
  }

  .caption {
    font-size: 0.9em;
    color: #6b7280;
    margin-top: 0.5em;
    font-style: italic;
  }

  details {
    margin: 1em 0;
    padding: 16px;
    background-color: #f3f4f6;
    border-radius: 8px;
    border-left: 4px solid #3b82f6;
  }

  summary {
    font-weight: 600;
    cursor: pointer;
    color: #1f2937;
    padding: 4px 0;
  }

  summary:hover {
    color: #3b82f6;
  }

  details[open] {
    background-color: #eff6ff;
  }

  details p {
    margin-top: 12px;
    padding-left: 8px;
  }

  @media (max-width: 768px) {
    body {
      padding: 12px;
    }

    h1 {
      font-size: 1.75em;
    }

    h2 {
      font-size: 1.5em;
    }

    table {
      font-size: 0.9em;
    }

    th, td {
      padding: 8px 10px;
    }
  }
</style>"""

# ===== 메인 렌더링 함수 =====
def render_html(
    topic: str,
    intent: str,
    outline: List[str],
    images: int = 4
) -> Dict[str, Any]:
    """
    SEO 최적화된 HTML 템플릿 생성

    Args:
        topic: 글의 제목/주제
        intent: 검색 의도 (정보/상업/거래)
        outline: H2 헤더 리스트
        images: 삽입할 이미지 개수

    Returns:
        html과 meta를 포함한 딕셔너리
    """
    html_parts: List[str] = []

    # 제목 및 소개
    html_parts.extend([
        f"<h1>{topic}</h1>",
        f"<p><strong>검색 의도:</strong> {intent}. "
        f"본 문서는 자동화된 AI 파이프라인으로 생성되었으며, 정보 제공 목적입니다.</p>"
    ])

    # 아웃라인 섹션 (H2 최대 6개)
    for h2_title in outline[:6]:
        html_parts.extend([
            f"<h2>{h2_title}</h2>",
            "<p>80–140자 단락 예시. 과장 없이 핵심만 설명합니다. 실제 콘텐츠는 여기에 삽입됩니다.</p>"
        ])

    # 비교 표
    html_parts.extend([
        "<h2>핵심 비교 표</h2>",
        """<table>
  <thead>
    <tr>
      <th>항목</th>
      <th>내용</th>
      <th>메모</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>검색 의도</td>
      <td>정보 / 상업 / 거래</td>
      <td>키워드 성격 분류</td>
    </tr>
    <tr>
      <td>벤치마킹</td>
      <td>상위 문서 요약</td>
      <td>중복 제거 및 개선 포인트</td>
    </tr>
    <tr>
      <td>본문 규격</td>
      <td>H1=1, H2=3–6, 표1, 리스트1, FAQ3</td>
      <td>SEO 최적화 기준</td>
    </tr>
  </tbody>
</table>""",
    ])

    # 체크리스트
    html_parts.extend([
        "<h2>작성 체크리스트</h2>",
        """<ul>
  <li>연관질의 (related queries) 커버</li>
  <li>상위 문서와의 격차 보완</li>
  <li>이미지 3–5장 (alt, 캡션, 출처 포함)</li>
  <li>CTA (Call-To-Action) 2–3개 배치</li>
  <li>메타 타이틀/설명/키워드 작성</li>
  <li>모바일 반응형 테스트</li>
</ul>"""
    ])

    # 이미지 삽입 위치
    html_parts.append("<h2>이미지 삽입 위치</h2>")
    for i in range(max(1, images)):
        html_parts.append(
            f'<p>[IMG{i+1}] — 캡션, 출처, alt 텍스트 기입 필수</p>'
        )

    # FAQ 섹션
    html_parts.extend([
        "<h2>자주 묻는 질문 (FAQ)</h2>",
        """<details>
  <summary>1) 핵심 개념은 무엇인가요?</summary>
  <p>간단하고 명확한 설명을 작성합니다. 전문 용어는 최소화합니다.</p>
</details>""",
        """<details>
  <summary>2) 어떻게 적용하나요?</summary>
  <p>단계별 절차를 순서대로 제시합니다. 실제 예시를 포함하면 좋습니다.</p>
</details>""",
        """<details>
  <summary>3) 흔한 오류는?</summary>
  <p>자주 발생하는 문제의 원인과 해결 방법을 명시합니다.</p>
</details>"""
    ])

    # CTA (Call-To-Action) 섹션
    html_parts.extend([
        '<div class="cta" id="CTA_TOP"><strong>🎁 [CTA_TOP]</strong> 제휴 링크 또는 리소스 (rel="nofollow sponsored")</div>',
        '<div class="cta" id="CTA_MID"><strong>📥 [CTA_MID]</strong> 체크리스트 또는 템플릿 다운로드</div>',
        '<div class="cta" id="CTA_BOTTOM"><strong>💬 [CTA_BOTTOM]</strong> 상담 / 데모 신청</div>',
    ])

    # 메타정보
    meta: Dict[str, Any] = {
        "title": f"{topic} - 완전 가이드",
        "description": f"{topic}에 대한 상세 가이드. SEO 최적화된 콘텐츠로 핵심 정보를 빠르게 확인하세요.",
        "keywords": ["SEO", "블로그자동화", "워드프레스", "티스토리", "콘텐츠마케팅"],
        "slug": slugify(topic),
        "author": "Blog Auto Generator",
        "lang": "ko"
    }

    return {
        "html": get_base_style() + "\n" + "\n".join(html_parts),
        "meta": meta
    }


# ===== 로컬 테스트 =====
if __name__ == "__main__":
    result = render_html(
        topic="AI 블로그 자동화 완벽 가이드",
        intent="정보",
        outline=["개요", "원리", "실전 사례", "주의사항"],
        images=4
    )

    print("=== HTML 미리보기 ===")
    print(result["html"][:800] + "...\n")

    print("=== 메타 정보 ===")
    for key, value in result["meta"].items():
        print(f"  {key}: {value}")