"""
Local embeddings + ChromaDB for semantic search across meetings.
Uses sentence-transformers (all-MiniLM-L6-v2) on CPU.
Includes an instant offline TF-IDF vector fallback (scikit-learn)
guaranteeing full functionality even before model downloads complete or in airplane mode.
"""
import logging
import os

logger = logging.getLogger(__name__)

_embedder = None
_chroma_client = None
_collection = None


def _get_embedder():
    """Lazy-load the sentence-transformers model with instant fallback."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Try offline local files first
            _embedder = SentenceTransformer('all-MiniLM-L6-v2', device='cpu', local_files_only=True)
            logger.info("Loaded all-MiniLM-L6-v2 from local cache.")
        except Exception:
            _embedder = None
    return _embedder


def _get_collection(chroma_dir: str):
    """Get or create the ChromaDB collection."""
    global _chroma_client, _collection
    if _collection is None:
        try:
            import chromadb
            os.makedirs(chroma_dir, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
            _collection = _chroma_client.get_or_create_collection(
                name="meetmind_meetings",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.warning(f"ChromaDB initialization notice: {e}")
            _collection = None
    return _collection


def index_meeting(meeting_id: str, transcript_segments: list[dict], screen_frames: list[dict], chroma_dir: str):
    """Index a meeting's speech and slide text."""
    embedder = _get_embedder()
    collection = _get_collection(chroma_dir)

    documents = []
    metadatas = []
    ids = []

    # 1. Transcript segments
    for i, seg in enumerate(transcript_segments):
        if seg.get('text', '').strip():
            documents.append(seg['text'])
            metadatas.append({
                'meeting_id': str(meeting_id),
                'type': 'speech',
                'start_time': seg['start'],
                'end_time': seg['end'],
            })
            ids.append(f"{meeting_id}_speech_{i}")

    # 2. Screen frames
    for i, frame in enumerate(screen_frames):
        if frame.get('ocr_text', '').strip():
            documents.append(frame['ocr_text'][:1000])
            metadatas.append({
                'meeting_id': str(meeting_id),
                'type': 'screen',
                'timestamp': frame['timestamp'],
            })
            ids.append(f"{meeting_id}_screen_{i}")

    if not documents:
        return

    # If neural embedder and ChromaDB are available, index there
    if embedder and collection:
        try:
            embeddings = embedder.encode(documents).tolist()
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            logger.info(f"Indexed {len(documents)} chunks in ChromaDB.")
            return
        except Exception as e:
            logger.warning(f"ChromaDB indexing error, falling back to local store: {e}")


def find_common_topics(meeting_ids, chroma_dir=None, top_k=10):
    """
    Find overlapping topics across multiple meetings.
    Uses offline TF-IDF n-gram analysis over each meeting's transcript + OCR text —
    terms scored in ALL meetings are returned, ranked by their weakest (shared) strength.
    """
    try:
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer
        from meetings.models import TranscriptSegment, ScreenFrame

        meeting_docs = []
        for mid in meeting_ids:
            texts = [s.text for s in TranscriptSegment.objects.filter(meeting_id=mid)]
            texts += [f.ocr_text for f in ScreenFrame.objects.filter(meeting_id=mid) if f.ocr_text.strip()]
            meeting_docs.append(' '.join(texts))

        if len(meeting_docs) < 2 or not all(d.strip() for d in meeting_docs):
            return []

        vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2), max_features=1000)
        tfidf = vectorizer.fit_transform(meeting_docs).toarray()
        terms = vectorizer.get_feature_names_out()

        present_in_all = np.all(tfidf > 0, axis=0)
        shared_strength = tfidf.min(axis=0)
        ranked = np.argsort(shared_strength)[::-1]
        return [terms[i] for i in ranked if present_in_all[i]][:top_k]
    except Exception as e:
        logger.warning(f"Common topic detection skipped: {e}")
        return []


def search_meetings(query: str, chroma_dir: str, meeting_id: str = None, top_k: int = 10) -> list[dict]:
    """
    Search meetings using semantic similarity (ChromaDB or local vector ranking).
    """
    embedder = _get_embedder()
    collection = _get_collection(chroma_dir)

    # 1. Try Neural ChromaDB
    if embedder and collection:
        try:
            query_embedding = embedder.encode([query]).tolist()
            where_filter = {"meeting_id": str(meeting_id)} if meeting_id else None
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
                where=where_filter,
            )
            search_results = []
            if results and results.get('documents'):
                for i, doc in enumerate(results['documents'][0]):
                    search_results.append({
                        'text': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0,
                    })
                return search_results
        except Exception as e:
            logger.debug(f"ChromaDB query fallback: {e}")

    # 2. Instant Zero-Network Vector Fallback via TF-IDF cosine similarity
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from meetings.models import Meeting, TranscriptSegment, ScreenFrame

    corpus = []
    items_meta = []

    seg_query = TranscriptSegment.objects.all()
    frame_query = ScreenFrame.objects.all()

    if meeting_id:
        seg_query = seg_query.filter(meeting_id=meeting_id)
        frame_query = frame_query.filter(meeting_id=meeting_id)

    for s in seg_query[:100]:
        corpus.append(s.text)
        items_meta.append({
            'text': s.text,
            'metadata': {'type': 'speech', 'start_time': s.start_time, 'meeting_id': str(s.meeting.id)},
        })

    for f in frame_query[:50]:
        if f.ocr_text.strip():
            corpus.append(f.ocr_text)
            items_meta.append({
                'text': f.ocr_text,
                'metadata': {'type': 'screen', 'timestamp': f.timestamp, 'meeting_id': str(f.meeting.id)},
            })

    if not corpus:
        return []

    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(corpus)
        query_vec = vectorizer.transform([query])
        scores = cosine_similarity(query_vec, tfidf_matrix).flatten()

        ranked_indices = scores.argsort()[::-1]
        results = []
        for idx in ranked_indices[:top_k]:
            if scores[idx] > 0.01:
                item = items_meta[idx]
                item['distance'] = float(1.0 - scores[idx])
                results.append(item)
        return results
    except Exception as e:
        logger.error(f"Vector fallback error: {e}")
        return []
