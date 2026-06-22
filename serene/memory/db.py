import psycopg
from pgvector.psycopg import register_vector
from serene.config import DB_URL


def get_conn():
    """Open a DB connection with the pgvector type registered.

    register_vector teaches psycopg how to turn a Python list into a
    Postgres `vector` and back, so store.py / recall.py can just pass
    plain lists around instead of hand-formatting vector strings.
    """
    conn = psycopg.connect(DB_URL)
    register_vector(conn)
    return conn


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # FACTS: long-lived truths about the user.
            #  - importance: pinned/core facts (name, key people, goals) get a
            #    high number so recall can ALWAYS inject them, query or not.
            #  - tsv: a full-text column auto-derived from key+value. Postgres
            #    keeps it in sync ("GENERATED ALWAYS ... STORED"). This powers
            #    the keyword half of hybrid search.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS serene_facts (
                    id          SERIAL PRIMARY KEY,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    importance  INT NOT NULL DEFAULT 1,
                    embedding   vector(384),
                    tsv         tsvector GENERATED ALWAYS AS (
                                    to_tsvector('english',
                                        coalesce(key, '') || ' ' || coalesce(value, ''))
                                ) STORED,
                    created_at  TIMESTAMPTZ DEFAULT now(),
                    updated_at  TIMESTAMPTZ DEFAULT now()
                )
            """)

            # TWO MEMORY TIERS, marked by `tier`:
            #   'core'    -> permanent identity (name, key people). ALWAYS
            #                injected into every prompt; never decayed or deleted.
            #   'ambient' -> everything else. Surfaced by search when relevant,
            #                and gently pruned over time (see store.decay()).
            cur.execute(
                "ALTER TABLE serene_facts "
                "ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'ambient'")

            # EPISODES: summaries of past conversations.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS serene_episodes (
                    id          SERIAL PRIMARY KEY,
                    summary     TEXT NOT NULL,
                    embedding   vector(384),
                    tsv         tsvector GENERATED ALWAYS AS (
                                    to_tsvector('english', coalesce(summary, ''))
                                ) STORED,
                    created_at  TIMESTAMPTZ DEFAULT now()
                )
            """)

            # Indexes:
            #  - HNSW on the embedding => fast cosine (semantic) search.
            #  - GIN on the tsv      => fast full-text (keyword) search.
            cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_embedding "
                        "ON serene_facts USING hnsw (embedding vector_cosine_ops)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_tsv "
                        "ON serene_facts USING gin (tsv)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_episodes_embedding "
                        "ON serene_episodes USING hnsw (embedding vector_cosine_ops)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_episodes_tsv "
                        "ON serene_episodes USING gin (tsv)")
        conn.commit()


init_db()
