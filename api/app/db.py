import psycopg
from psycopg.rows import dict_row

from .config import settings

TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    ext TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    stored_path TEXT NOT NULL,
    space_id TEXT NOT NULL DEFAULT 'general',
    classification TEXT NOT NULL DEFAULT 'Internal'
        CHECK (classification IN ('Public', 'Internal', 'Confidential')),
    owner_id TEXT NOT NULL DEFAULT 'demo-user',
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'indexed', 'failed')),
    error_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""
INDEX = "CREATE INDEX IF NOT EXISTS idx_documents_space_sha ON documents (space_id, sha256)"


def get_conn() -> psycopg.Connection:
    """اتصال جديد لكل عملية. الخروج من with = commit، والاستثناء = rollback."""
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(TABLE)
        conn.execute(INDEX)
