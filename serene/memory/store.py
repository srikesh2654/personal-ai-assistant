from serene.memory.db import get_conn
from serene.memory.embedder import embed_document

# if (and only if) no key matches, a fact nearer than this is treated as the
# same fact and updated. Kept strict so distinct facts that merely share a name
# (e.g. "name is Srikesh" vs "Srikesh was born…") are NOT wrongly merged.
DEDUP_DISTANCE = 0.10

# --- forgetting policy (Ambient tier only; Core is never touched) ----------
DECAY_DAYS = 45              # ambient facts unused this long may fade...
DECAY_MAX_IMPORTANCE = 2     # ...but only the low-importance ones
AMBIENT_CAP = 200            # keep at most this many ambient facts
EPISODE_CAP = 150            # keep at most this many episodes


def save_episode(summary):
    emb = embed_document(summary)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO serene_episodes (summary, embedding) VALUES (%s, %s)",
                (summary, emb),
            )
        conn.commit()


def save_fact(key, value, importance=1, tier="ambient"):
    """Save a fact. `tier` is 'core' (permanent, always recalled) or 'ambient'
    (lenient). Dedups against the nearest existing fact; on update it NEVER
    downgrades a Core fact back to Ambient."""
    text = f"{key}: {value}"
    emb = embed_document(text)
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Same KEY => definitely the same fact -> update it.
            cur.execute("SELECT id, tier FROM serene_facts WHERE key=%s LIMIT 1", (key,))
            row = cur.fetchone()
            match = (row[0], row[1]) if row else None

            # 2. No key match -> only merge if an existing fact is a NEAR-duplicate
            #    (strict threshold), so distinct facts aren't clobbered.
            if match is None:
                cur.execute(
                    "SELECT id, tier, embedding <=> %s AS dist FROM serene_facts "
                    "ORDER BY dist LIMIT 1",
                    (emb,),
                )
                r = cur.fetchone()
                if r is not None and r[2] < DEDUP_DISTANCE:
                    match = (r[0], r[1])

            if match is not None:
                # update existing; once Core, stays Core (never silently downgraded)
                new_tier = "core" if (tier == "core" or match[1] == "core") else "ambient"
                cur.execute(
                    "UPDATE serene_facts "
                    "SET key=%s, value=%s, embedding=%s, importance=%s, tier=%s, "
                    "updated_at=now() WHERE id=%s",
                    (key, value, emb, importance, new_tier, match[0]),
                )
            else:
                # genuinely new -> insert
                cur.execute(
                    "INSERT INTO serene_facts (key, value, embedding, importance, tier) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (key, value, emb, importance, tier),
                )
        conn.commit()


def pin_fact(key, value, importance=5):
    """Promote a fact to the permanent Core tier (never forgotten)."""
    save_fact(key, value, importance=importance, tier="core")


def decay():
    """Gentle forgetting for the AMBIENT tier only (Core is never touched):
    drop stale low-importance facts, and cap the totals so memory stays fresh
    and bounded. Safe to run at the end of every session."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. prune stale, low-value ambient facts
            cur.execute(
                "DELETE FROM serene_facts WHERE tier='ambient' AND importance <= %s "
                "AND updated_at < now() - make_interval(days => %s)",
                (DECAY_MAX_IMPORTANCE, DECAY_DAYS),
            )
            # 2. cap ambient facts (keep the most important / recent)
            cur.execute(
                "DELETE FROM serene_facts WHERE tier='ambient' AND id NOT IN "
                "(SELECT id FROM serene_facts WHERE tier='ambient' "
                " ORDER BY importance DESC, updated_at DESC LIMIT %s)",
                (AMBIENT_CAP,),
            )
            # 3. cap episodes (keep the most recent)
            cur.execute(
                "DELETE FROM serene_episodes WHERE id NOT IN "
                "(SELECT id FROM serene_episodes ORDER BY created_at DESC LIMIT %s)",
                (EPISODE_CAP,),
            )
        conn.commit()
