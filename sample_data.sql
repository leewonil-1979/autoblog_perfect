-- 샘플 데이터 삽입 스크립트
-- 테스트 및 데모용 데이터
-- PostgreSQL dialect

-- 1. 샘플 블로그 추가 (WordPress)
INSERT INTO blogs (blog_name, blog_url, platform, wp_user, wp_app_password, category, active)
VALUES
('테크 블로그', 'https://tech-blog.example.com', 'wordpress', 'admin', 'abcd 1234 efgh 5678 ijkl 9012', 'Technology', true),
('라이프스타일 블로그', 'https://lifestyle.example.com', 'wordpress', 'blogger', 'mnop 3456 qrst 7890 uvwx 1234', 'Lifestyle', true);

-- 2. 샘플 블로그 추가 (Tistory)
INSERT INTO blogs (blog_name, blog_url, platform, category, active)
VALUES
('개발 일기', 'https://devlog.tistory.com', 'tistory', 'Development', true),
('여행 기록', 'https://travel.tistory.com', 'tistory', 'Travel', false);

-- 3. 비활성 블로그 (테스트용)
INSERT INTO blogs (blog_name, blog_url, platform, active)
VALUES
('보관 블로그', 'https://archived.example.com', 'wordpress', false);

-- 확인 쿼리
SELECT
    id,
    blog_name,
    platform,
    active,
    CASE active
        WHEN true THEN '✅ 활성'
        WHEN false THEN '❌ 비활성'
        ELSE '❓ 알 수 없음'
    END as status
FROM blogs
ORDER BY id;