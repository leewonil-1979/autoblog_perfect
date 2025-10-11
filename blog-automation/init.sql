-- Database initialization script for Blog Automation
-- PostgreSQL dialect

-- Table: blogs
CREATE TABLE IF NOT EXISTS blogs (
  id SERIAL PRIMARY KEY,
  blog_name VARCHAR(255) NOT NULL,
  blog_url VARCHAR(255) NOT NULL,
  platform VARCHAR(50) NOT NULL, -- 'wordpress' or 'tistory'
  wp_user VARCHAR(255), -- WordPress account for Application Password
  wp_app_password VARCHAR(255), -- WordPress Application Password
  category VARCHAR(255),
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: articles
CREATE TABLE IF NOT EXISTS articles (
  id SERIAL PRIMARY KEY,
  blog_id INTEGER REFERENCES blogs(id),
  title VARCHAR(500) NOT NULL,
  content TEXT NOT NULL,
  html_content TEXT,
  status VARCHAR(50) DEFAULT 'draft', -- 'draft', 'published', 'failed'
  wordpress_post_id INTEGER,
  tistory_package_s3 TEXT,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  published_at TIMESTAMP,
  attempted_at TIMESTAMP
);

-- Table: execution_logs
CREATE TABLE IF NOT EXISTS execution_logs (
  id SERIAL PRIMARY KEY,
  blog_id INTEGER REFERENCES blogs(id),
  step VARCHAR(100) NOT NULL,
  status VARCHAR(50) NOT NULL, -- 'success', 'failed', 'retry'
  message TEXT,
  duration_seconds FLOAT,
  tokens_used INTEGER,
  cost DECIMAL(10,4),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: publishing_queue
CREATE TABLE IF NOT EXISTS publishing_queue (
  id SERIAL PRIMARY KEY,
  article_id INTEGER REFERENCES articles(id),
  blog_id INTEGER REFERENCES blogs(id),
  priority INTEGER DEFAULT 0,
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  status VARCHAR(50) DEFAULT 'pending',
  next_retry_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_articles_blog_id ON articles(blog_id);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_execution_logs_blog_id ON execution_logs(blog_id);
CREATE INDEX IF NOT EXISTS idx_execution_logs_created_at ON execution_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_publishing_queue_status ON publishing_queue(status);
