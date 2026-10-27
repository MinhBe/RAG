-- Chạy một lần khi khởi tạo volume postgres.
-- Bật pgvector trên DB chính và tạo DB riêng cho Langfuse.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

SELECT 'CREATE DATABASE langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec
