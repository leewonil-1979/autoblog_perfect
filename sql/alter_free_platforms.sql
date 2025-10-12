-- WordPress.com용 칼럼
ALTER TABLE blogs
  ADD COLUMN IF NOT EXISTS wpcom_site VARCHAR(255),             -- 예: won201.wordpress.com
  ADD COLUMN IF NOT EXISTS wpcom_access_token TEXT,
  ADD COLUMN IF NOT EXISTS wpcom_refresh_token TEXT,
  ADD COLUMN IF NOT EXISTS wpcom_token_expires_at TIMESTAMP;

-- Blogger(선택)용 칼럼
ALTER TABLE blogs
  ADD COLUMN IF NOT EXISTS blogger_blog_id VARCHAR(64),          -- 예: 1234567890123456789
  ADD COLUMN IF NOT EXISTS google_access_token TEXT,
  ADD COLUMN IF NOT EXISTS google_refresh_token TEXT,
  ADD COLUMN IF NOT EXISTS google_token_expires_at TIMESTAMP;

-- platform 값 가이드: 'wpcom' | 'tistory' | 'naver' | 'blogger' | 'wordpress' (자체호스팅일 때)
