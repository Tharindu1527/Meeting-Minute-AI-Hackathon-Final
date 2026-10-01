# database/qdrant.py
"""
Qdrant vector index of transcript chunks, used for semantic search in chat.

QDRANT_URI can be an http(s) URL (Qdrant Cloud / server), ":memory:", or a
local folder path for embedded on-disk storage (no server needed).
"""
import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models

from api.llm import embed
from utils.config import EMBEDDING_SIZE, get_qdrant_api_key, get_qdrant_collection, get_qdrant_uri

logger = logging.getLogger(__name__)

_client = None
_collection_ready = False

# Fixed namespace so a chunk always maps to the same point id (re-indexing overwrites, never duplicates)
_POINT_NAMESPACE = uuid.UUID("6f1c8a52-3c2e-4d59-9a7e-0b8f2f9d4e11")


def is_configured():
    return bool(get_qdrant_uri())


def get_client():
    global _client
    if _client is None:
        uri = get_qdrant_uri()
        if uri.startswith(("http://", "https://")):
            _client = QdrantClient(url=uri, api_key=get_qdrant_api_key(), timeout=20)
        elif uri == ":memory:":
            _client = QdrantClient(location=":memory:")
        else:
            _client = QdrantClient(path=uri)
    return _client


def _meeting_filter(meeting_id):
    return models.Filter(must=[models.FieldCondition(key="meeting_id", match=models.MatchValue(value=meeting_id))])


def ensure_collection():
    global _collection_ready
    if _collection_ready:
        return
    client, name = get_client(), get_qdrant_collection()
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=EMBEDDING_SIZE, distance=models.Distance.COSINE),
        )
        client.create_payload_index(name, field_name="meeting_id", field_schema=models.PayloadSchemaType.KEYWORD)
    else:
        size = client.get_collection(name).config.params.vectors.size
        if size != EMBEDDING_SIZE:
            raise RuntimeError(
                f"Qdrant collection '{name}' holds {size}-dimension vectors, but the embedding model produces "
                f"{EMBEDDING_SIZE}. Set QDRANT_COLLECTION to a new name, or delete the old collection."
            )
    _collection_ready = True


def index_meeting(meeting_id, title, chunks):
    """
    Replace a meeting's transcript chunks in the index

    Args:
        meeting_id: MongoDB meeting id
        title: Meeting title (stored for citations)
        chunks: [{"text", "start_ms", "end_ms"}] from utils.transcript.chunk_utterances

    Returns:
        int: Number of chunks indexed
    """
    ensure_collection()
    delete_meeting_vectors(meeting_id)
    if not chunks:
        return 0

    vectors = embed([chunk["text"] for chunk in chunks])
    points = [
        models.PointStruct(
            id=str(uuid.uuid5(_POINT_NAMESPACE, f"{meeting_id}:{index}")),
            vector=vector,
            payload={
                "meeting_id": meeting_id,
                "title": title,
                "chunk_index": index,
                "text": chunk["text"],
                "start_ms": chunk.get("start_ms"),
                "end_ms": chunk.get("end_ms"),
            },
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    get_client().upsert(collection_name=get_qdrant_collection(), points=points)
    return len(points)


def search(query, meeting_ids, limit=6):
    """
    Semantic search over transcript chunks

    Args:
        query: Question or search text
        meeting_ids: The meetings to search (always the asking user's own meetings)
        limit: Maximum number of chunks

    Returns:
        list: Chunk payload dicts with an added "score"
    """
    if not meeting_ids:
        return []
    ensure_collection()
    vector = embed([query])[0]
    response = get_client().query_points(
        collection_name=get_qdrant_collection(),
        query=vector,
        query_filter=models.Filter(must=[models.FieldCondition(key="meeting_id", match=models.MatchAny(any=list(meeting_ids)))]),
        limit=limit,
        with_payload=True,
    )
    return [dict(point.payload, score=point.score) for point in response.points]


def delete_meeting_vectors(meeting_id):
    ensure_collection()
    get_client().delete(
        collection_name=get_qdrant_collection(),
        points_selector=models.FilterSelector(filter=_meeting_filter(meeting_id)),
    )
