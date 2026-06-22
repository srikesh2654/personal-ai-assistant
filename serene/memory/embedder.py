from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

def embed_document(text):
    # return the numpy array directly — the pgvector adapter turns a numpy
    # array into a real Postgres `vector`. A plain list would become a
    # double-precision array and break the `<=>` cosine operator.
    return _model.encode(text, normalize_embeddings=True)

def embed_query(text):
    return _model.encode(QUERY_PREFIX + text, normalize_embeddings=True)
