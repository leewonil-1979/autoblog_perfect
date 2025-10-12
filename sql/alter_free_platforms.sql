-- ===================================================================
-- 무료 플랫폼(WordPress.com/Blogger)용 컬럼 추가 스크립트 (PostgreSQL)
-- 실행 대상 테이블: blogs
-- 안전 실행: 존재 시 무시(IF NOT EXISTS), 트랜잭션 사용
-- ===================================================================

BEGIN;

-- WordPress.com(무료)용
ALTER TABLE IF EXISTS blogs ADD COLUMN IF NOT EXISTS wpcom_site VARCHAR(255);
ALTER TABLE IF EXISTS blogs ADD COLUMN IF NOT EXISTS wpcom_access_token TEXT;
ALTER TABLE IF EXISTS blogs ADD COLUMN IF NOT EXISTS wpcom_refresh_token TEXT;
ALTER TABLE IF EXISTS blogs ADD COLUMN IF NOT EXISTS wpcom_token_expires_at TIMESTAMP;

-- Blogger(선택)용
ALTER TABLE IF EXISTS blogs ADD COLUMN IF NOT EXISTS blogger_blog_id VARCHAR(64);
ALTER TABLE IF EXISTS blogs ADD COLUMN IF NOT EXISTS google_access_token TEXT;
ALTER TABLE IF EXISTS blogs ADD COLUMN IF NOT EXISTS google_refresh_token TEXT;
ALTER TABLE IF EXISTS blogs ADD COLUMN IF NOT EXISTS google_token_expires_at TIMESTAMP;

COMMIT;

-- 플랫폼 값 가이드(주석):
-- 'wpcom' | 'tistory' | 'naver' | 'blogger' | 'wordpress'
