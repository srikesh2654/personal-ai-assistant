"""recall.py — given the user's latest message, gather what SERENE might
remember and format it for the system prompt.

Design philosophy (learned the hard way): don't trust math to decide what's
*relevant*. Embeddings and rerankers are great at "similar" and "answers the
question", but terrible at associative leaps like
    "I'm nervous about my game"  ->  "you play tennis every Thursday".
The thing that's brilliant at that is the LLM itself. So we:

  1. ALWAYS inject the CORE tier (identity, key people) — no search, no risk.
  2. Retrieve a GENEROUS candidate set from the AMBIENT tier via hybrid search
     (semantic + keyword, fused with RRF) — aim for recall, not precision.
  3. Hand it to the brain and let IT decide what's relevant when replying.

Two tiers (the `tier` column on serene_facts):
  - 'core'    -> permanent. Always injected. Never forgotten.
  - 'ambient' -> lenient. Surfaced only when relevant; decays over time.

A gentle semantic floor keeps obvious garbage out once the DB grows large,
but we deliberately do NOT over-filter.
"""
from serene.memory.db import get_conn
from serene.memory.embedder import embed_query

# --- tunables -------------------------------------------------------------
CANDIDATE_LIMIT = 20      # how many to pull from EACH search before fusing
SEM_MAX_DIST = 0.65       # drop semantic hits worse than this cosine distance
KEEP_FACTS = 6            # max searched (non-pinned) facts to inject
KEEP_EPISODES = 3         # max episodes to inject
RRF_K = 60                # reciprocal-rank-fusion constant (standard default)


def _semantic(cur, table, text_sql, qvec, cond=""):
    """Vector search; returns [(id, text), ...] nearest first, with a gentle
    distance floor so clearly-unrelated rows don't sneak in. `cond` is an
    optional extra SQL filter (e.g. "tier='ambient'")."""
    where = f"WHERE {cond} " if cond else ""
    cur.execute(
        f"SELECT id, {text_sql}, embedding <=> %s AS dist FROM {table} {where}"
        f"ORDER BY dist LIMIT %s",
        (qvec, CANDIDATE_LIMIT),
    )
    return [(i, t) for i, t, d in cur.fetchall() if d <= SEM_MAX_DIST]


def _keyword(cur, table, text_sql, query, cond=""):
    """Full-text search; returns [(id, text), ...] best match first.
    Catches exact names/terms that vector search blurs over."""
    extra = f"AND {cond} " if cond else ""
    cur.execute(
        f"SELECT id, {text_sql} FROM {table} "
        f"WHERE tsv @@ plainto_tsquery('english', %s) {extra}"
        f"ORDER BY ts_rank(tsv, plainto_tsquery('english', %s)) DESC LIMIT %s",
        (query, query, CANDIDATE_LIMIT),
    )
    return cur.fetchall()


def _rrf(*ranked_lists):
    """Reciprocal Rank Fusion: merge ranked [(id, text), ...] lists. Items
    ranked highly in either list rise; items in BOTH win."""
    scores, texts = {}, {}
    for lst in ranked_lists:
        for rank, (id_, text) in enumerate(lst, start=1):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (RRF_K + rank)
            texts[id_] = text
    return [(i, texts[i]) for i in sorted(scores, key=scores.get, reverse=True)]


def _hybrid(cur, table, text_sql, qvec, query, keep, cond=""):
    fused = _rrf(
        _semantic(cur, table, text_sql, qvec, cond),
        _keyword(cur, table, text_sql, query, cond),
    )
    return fused[:keep]


def recall(query):
    """Return a memory-context string to prepend to the system prompt
    (empty string if there's nothing to recall)."""
    qvec = embed_query(query)

    with get_conn() as conn:
        with conn.cursor() as cur:
            # CORE tier: always injected, no search — she just knows this.
            cur.execute(
                "SELECT key, value FROM serene_facts WHERE tier='core' "
                "ORDER BY importance DESC, updated_at DESC")
            core = [f"{k}: {v}" for k, v in cur.fetchall()]

            # AMBIENT tier: hybrid search, surfaced only when relevant.
            facts = _hybrid(cur, "serene_facts", "key || ': ' || value",
                            qvec, query, KEEP_FACTS, cond="tier='ambient'")
            episodes = _hybrid(cur, "serene_episodes", "summary",
                               qvec, query, KEEP_EPISODES)

    # don't repeat core facts in the searched section
    fact_texts = [t for _, t in facts if t not in core]
    episode_texts = [t for _, t in episodes]

    lines = []
    if core:
        lines.append("Core facts about the user (permanent — always true):")
        lines += [f"- {p}" for p in core]
    if fact_texts:
        lines.append("Things you may know about the user "
                     "(use what's relevant to their message, ignore the rest):")
        lines += [f"- {t}" for t in fact_texts]
    if episode_texts:
        lines.append("Possibly-relevant past moments:")
        lines += [f"- {t}" for t in episode_texts]

    return "\n".join(lines)
