"""
Shopify-Inspired Advanced Retrieval Engine
===========================================
Implements production-grade multi-stage retrieval pipeline inspired by
Shopify's search architecture and Sidekick's RAG patterns.

Pipeline:
  Query → Multi-Vector Retrieval → RRF Score Fusion →
  Cross-Encoder Reranking → RFF Boost → Context Formatting

Key techniques:
1. Multi-query retrieval (original + expanded + HyDE + sub-queries)
2. Reciprocal Rank Fusion (RRF) with tunable weights
3. Real Cross-Encoder Reranking via sentence-transformers
4. Relevance Feedback Fusion (RFF) — boost chunks users found helpful
5. Context window optimization (dedup, compress, order)
6. Source-level citation tracking
7. Multi-signal confidence calibration
8. Stopword-filtered BM25 tokenization
"""

import asyncio
import json
import os
import numpy as np
import re
import hashlib
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import OrderedDict, defaultdict
from rank_bm25 import BM25Okapi
from app.core.logging import logger


# ── Stopwords for BM25 tokenization ────────────────────────────────
_STOPWORDS = frozenset({
    # English
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "of", "and",
    "or", "for", "by", "be", "as", "do", "if", "my", "no", "so", "up",
    "was", "are", "but", "not", "you", "all", "can", "had", "her", "his",
    "how", "its", "may", "our", "out", "has", "did", "get", "him", "let",
    "new", "now", "old", "see", "way", "who", "did", "got", "use", "say",
    "she", "too", "than", "that", "this", "what", "with", "will", "from",
    "have", "been", "they", "them", "then", "when", "your", "each", "make",
    "like", "just", "over", "such", "take", "also", "into", "some", "could",
    "very", "after", "about", "would", "these", "other", "which", "their",
    "there", "where", "being", "those",
    # Indonesian
    "dan", "di", "ke", "dari", "yang", "ini", "itu", "untuk", "dengan",
    "ada", "pada", "atau", "tidak", "sudah", "bisa", "akan", "oleh", "saya",
    "kami", "kita", "mereka", "anda", "nya", "lah", "kah", "pun",
})


@dataclass
class RetrievedChunk:
    """A single retrieved document chunk with scoring metadata"""
    content: str
    source_file: str
    upload_date: str
    chunk_id: str
    scores: Dict[str, float] = field(default_factory=dict)  # {method: score}
    final_score: float = 0.0
    rerank_score: float = 0.0


@dataclass
class RetrievalResult:
    """Complete result of the retrieval pipeline"""
    chunks: List[RetrievedChunk]
    retrieval_methods_used: List[str]
    total_candidates: int
    after_dedup: int
    after_rerank: int
    context_text: str           # Pre-formatted context for LLM
    confidence: float           # Calibrated confidence score
    source_citations: List[Dict[str, str]]  # [{file, date, relevance}]


# ════════════════════════════════════════════════════════════════════
#  RFF — Relevance Feedback Fusion Store
# ════════════════════════════════════════════════════════════════════

class RelevanceFeedbackStore:
    """
    Tracks user feedback (👍/👎) on answers and maps it back to the
    chunks that produced those answers.  On future queries the retrieval
    pipeline applies an RFF boost/penalty so that proven-helpful chunks
    float higher and unhelpful ones drop.

    Persistence: JSON file under data/ — survives container restarts.
    """

    def __init__(self, persist_path: str = "data/rff_feedback.json"):
        self._persist_path = persist_path
        # chunk_id → {"positive": int, "negative": int, "last_updated": float}
        self._store: Dict[str, Dict] = {}
        self._load()

    # ── Persistence ─────────────────────────────────────────────────

    def _load(self):
        try:
            if os.path.exists(self._persist_path):
                with open(self._persist_path, "r") as f:
                    self._store = json.load(f)
                logger.info(f"[RFF] Loaded feedback for {len(self._store)} chunks")
        except Exception as e:
            logger.warning(f"[RFF] Load failed, starting fresh: {e}")
            self._store = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "w") as f:
                json.dump(self._store, f)
        except Exception as e:
            logger.warning(f"[RFF] Save failed: {e}")

    # ── Record Feedback ─────────────────────────────────────────────

    def record(self, chunk_ids: List[str], is_positive: bool):
        """Record feedback for a list of chunk_ids used in a response"""
        field = "positive" if is_positive else "negative"
        for cid in chunk_ids:
            if cid not in self._store:
                self._store[cid] = {"positive": 0, "negative": 0, "last_updated": 0}
            self._store[cid][field] += 1
            self._store[cid]["last_updated"] = time.time()
        self._save()

    # ── Compute Boost ───────────────────────────────────────────────

    def get_boost(self, chunk_id: str) -> float:
        """
        Returns a multiplicative boost factor for the chunk.
        - No feedback → 1.0 (neutral)
        - Mostly positive → up to 1.3
        - Mostly negative → down to 0.7
        Uses Bayesian smoothing (prior of 1 positive, 1 negative) so
        a single vote doesn't swing things too hard.
        """
        entry = self._store.get(chunk_id)
        if not entry:
            return 1.0
        pos = entry["positive"] + 1   # Bayesian prior
        neg = entry["negative"] + 1
        ratio = pos / (pos + neg)     # 0.5 = neutral
        # Map [0, 1] → [0.7, 1.3]
        return 0.7 + 0.6 * ratio

    def get_stats(self) -> Dict:
        """Summary stats for monitoring"""
        total = len(self._store)
        if total == 0:
            return {"total_chunks": 0}
        pos_total = sum(e["positive"] for e in self._store.values())
        neg_total = sum(e["negative"] for e in self._store.values())
        return {
            "total_chunks_with_feedback": total,
            "total_positive": pos_total,
            "total_negative": neg_total,
        }


# ── Module-level singleton ──────────────────────────────────────────
_rff_store = RelevanceFeedbackStore()


def get_rff_store() -> RelevanceFeedbackStore:
    return _rff_store


# ════════════════════════════════════════════════════════════════════
#  Cross-Encoder Reranker (real sentence-transformers model)
# ════════════════════════════════════════════════════════════════════

class CrossEncoderReranker:
    """
    Lazy-loaded cross-encoder using sentence-transformers.
    Model: ms-marco-MiniLM-L-6-v2 — fast, accurate, <80 MB.
    Falls back to n-gram heuristic if model fails to load.
    """

    _instance = None          # Singleton
    _model = None
    _load_attempted = False

    @classmethod
    def get_instance(cls) -> "CrossEncoderReranker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_model(self):
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            from sentence_transformers import CrossEncoder
            from app.core.config import settings as _s
            model_name = getattr(_s, 'CROSS_ENCODER_MODEL', None) or os.getenv(
                "CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
            )
            self._model = CrossEncoder(model_name)
            logger.info(f"[CrossEncoder] Loaded model: {model_name}")
        except Exception as e:
            logger.warning(f"[CrossEncoder] Model load failed, using heuristic fallback: {e}")
            self._model = None

    def score(self, query: str, passages: List[str]) -> List[float]:
        """
        Score query-passage pairs.  Returns list of relevance scores (higher = better).
        Falls back to n-gram heuristic if model unavailable.
        """
        self._ensure_model()
        if self._model is not None and passages:
            try:
                pairs = [[query, p] for p in passages]
                scores = self._model.predict(pairs)
                # Normalize to [0, 1] with sigmoid
                scores = 1.0 / (1.0 + np.exp(-np.array(scores)))
                return scores.tolist()
            except Exception as e:
                logger.warning(f"[CrossEncoder] Predict failed, falling back: {e}")
        # Heuristic fallback (n-gram overlap)
        return self._heuristic_scores(query, passages)

    @staticmethod
    def _heuristic_scores(query: str, passages: List[str]) -> List[float]:
        """Lightweight n-gram scoring when cross-encoder model is unavailable"""
        q_lower = query.lower()
        q_words = set(re.split(r'\W+', q_lower))
        q_bigrams = set()
        wl = list(q_words)
        for i in range(len(wl) - 1):
            q_bigrams.add(f"{wl[i]} {wl[i+1]}")

        scores = []
        for passage in passages:
            p_lower = passage.lower()
            p_words = set(re.split(r'\W+', p_lower))
            unigram = len(q_words & p_words) / max(len(q_words), 1)
            p_bigrams = set()
            pw = p_lower.split()
            for i in range(len(pw) - 1):
                p_bigrams.add(f"{pw[i]} {pw[i+1]}")
            bigram = len(q_bigrams & p_bigrams) / max(len(q_bigrams), 1) if q_bigrams else 0
            exact = 1.0 if q_lower in p_lower else 0.0
            score = 0.40 * unigram + 0.35 * bigram + 0.25 * exact
            scores.append(score)
        return scores


class AdvancedRetriever:
    """
    Multi-stage retrieval pipeline implementing Shopify-grade
    search quality with BM25 + Vector + RRF + Cross-Encoder + RFF.
    """

    def __init__(self, vector_store=None, documents=None, embeddings=None):
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.all_documents = documents or []
        self.bm25 = None
        self.doc_content_index = {}  # content_hash -> doc for dedup
        self._result_cache = OrderedDict()
        self._cache_maxsize = 128
        self._rff = _rff_store
        self._cross_encoder = CrossEncoderReranker.get_instance()
        self._file_chunk_map = {}   # Built lazily for parent-doc enrichment

        if self.all_documents:
            self._build_bm25_index()

        logger.info(f"[AdvancedRetriever] Initialized with {len(self.all_documents)} documents")

    def update_stores(self, vector_store, documents):
        """Update retriever with new vector store and documents after reindex"""
        self.vector_store = vector_store
        self.all_documents = documents or []
        self._result_cache.clear()
        self._file_chunk_map = {}   # Reset parent-doc index
        if self.all_documents:
            self._build_bm25_index()
        logger.info(f"[AdvancedRetriever] Updated with {len(self.all_documents)} documents")

    def _build_bm25_index(self):
        """Build BM25 index with stopword-filtered preprocessing"""
        if not self.all_documents:
            return
        
        tokenized_corpus = []
        self.doc_content_index = {}
        
        for doc in self.all_documents:
            text = doc.page_content.lower()
            # Better tokenization: split on non-alphanumeric, filter short + stopwords
            tokens = [t for t in re.split(r'\W+', text) if len(t) > 1 and t not in _STOPWORDS]
            tokenized_corpus.append(tokens)
            
            # Build content hash index for dedup
            content_hash = hashlib.md5(doc.page_content[:200].encode()).hexdigest()
            self.doc_content_index[content_hash] = doc

        self.bm25 = BM25Okapi(tokenized_corpus)

    async def retrieve(
        self,
        original_query: str,
        expanded_query: str = None,
        hyde_passage: str = None,
        sub_queries: List[str] = None,
        k_per_method: int = 8,
        k_final: int = 10,
        intent: str = "simple_faq",
    ) -> RetrievalResult:
        """
        Multi-stage retrieval pipeline:
        1. Multi-query retrieval (original + expanded + HyDE + sub-queries)
        2. Score fusion via Reciprocal Rank Fusion
        3. Deduplication
        4. Cross-encoder reranking
        5. Context formatting with citations
        """
        # Cache check
        cache_key = hashlib.md5(f"{original_query}:{expanded_query}".encode()).hexdigest()
        if cache_key in self._result_cache:
            return self._result_cache[cache_key]

        all_candidates: Dict[str, RetrievedChunk] = {}  # content_hash -> chunk
        methods_used = []

        # Adaptive k: intents that need more context get more candidates
        _intent_k_boost = {
            "how_to": 2, "troubleshooting": 2, "configuration": 2,
            "complex_multi": 3, "comparison": 2,
        }
        k_boost = _intent_k_boost.get(intent, 0)
        k_eff = k_per_method + k_boost

        # ── Stage 1: Multi-Query Retrieval (Parallelized) ──────────────────────────
        
        # Run BM25 and Vector search in parallel to save time
        tasks = []
        tasks.append(asyncio.to_thread(self._bm25_search, original_query, k=k_eff))
        tasks.append(self._vector_search(original_query, k=k_eff))
        
        if expanded_query and expanded_query != original_query:
            tasks.append(self._vector_search(expanded_query, k=k_eff // 2))
            tasks.append(asyncio.to_thread(self._bm25_search, expanded_query, k=k_eff // 2))
        
        if hyde_passage:
            tasks.append(self._vector_search(hyde_passage, k=k_eff // 2))
            
        results = await asyncio.gather(*tasks)
        
        # Merge results from all parallel tasks
        result_idx = 0
        
        bm25_results = results[result_idx]
        self._merge_candidates(all_candidates, bm25_results, "bm25_original", weight=0.35)
        if bm25_results: methods_used.append("bm25_original")
        result_idx += 1
        
        vector_results = results[result_idx]
        self._merge_candidates(all_candidates, vector_results, "vector_original", weight=0.40)
        if vector_results: methods_used.append("vector_original")
        result_idx += 1
        
        if expanded_query and expanded_query != original_query:
            expanded_results = results[result_idx]
            self._merge_candidates(all_candidates, expanded_results, "vector_expanded", weight=0.15)
            if expanded_results: methods_used.append("vector_expanded")
            result_idx += 1
            
            bm25_exp = results[result_idx]
            self._merge_candidates(all_candidates, bm25_exp, "bm25_expanded", weight=0.10)
            if bm25_exp: methods_used.append("bm25_expanded")
            result_idx += 1
            
        if hyde_passage:
            hyde_results = results[result_idx]
            self._merge_candidates(all_candidates, hyde_results, "hyde", weight=0.25)
            if hyde_results: methods_used.append("hyde")
            result_idx += 1

        total_candidates = len(all_candidates)

        # 1e. Sub-query retrieval (for complex multi-part queries)
        if sub_queries and len(sub_queries) > 1:
            for i, sq in enumerate(sub_queries[:3]):  # Max 3 sub-queries
                sq_results = await self._vector_search(sq, k=4)
                self._merge_candidates(all_candidates, sq_results, f"sub_query_{i}", weight=0.20)
                if sq_results:
                    methods_used.append(f"sub_query_{i}")

        total_candidates = len(all_candidates)

        if not all_candidates:
            return RetrievalResult(
                chunks=[], retrieval_methods_used=methods_used,
                total_candidates=0, after_dedup=0, after_rerank=0,
                context_text="", confidence=0.0, source_citations=[]
            )

        # ── Stage 2: Score Fusion (RRF) ─────────────────────────────

        ranked_chunks = sorted(all_candidates.values(), key=lambda c: c.final_score, reverse=True)

        # ── Stage 3: Deduplication ──────────────────────────────────

        deduped = self._deduplicate(ranked_chunks)
        after_dedup = len(deduped)

        # ── Stage 4: Cross-Encoder Reranking ────────────────────────

        reranked = await self._rerank(original_query, deduped, k=k_final)
        after_rerank = len(reranked)

        # ── Stage 5: Parent-Doc Context Window ──────────────────
        # Pull adjacent chunks from same source file to give LLM
        # fuller context (prevents mid-instruction splits)
        enriched = self._enrich_with_adjacent(reranked)

        # ── Stage 6: Confidence Calibration ─────────────────────────

        confidence = self._calibrate_confidence(original_query, enriched)

        # ── Stage 7: Context Formatting with Citations ──────────────

        context_text, citations = self._format_context(enriched, intent)

        result = RetrievalResult(
            chunks=enriched,
            retrieval_methods_used=methods_used,
            total_candidates=total_candidates,
            after_dedup=after_dedup,
            after_rerank=after_rerank,
            context_text=context_text,
            confidence=confidence,
            source_citations=citations,
        )

        # Cache result
        self._result_cache[cache_key] = result
        if len(self._result_cache) > self._cache_maxsize:
            self._result_cache.popitem(last=False)

        return result

    # ── Parent-Doc Context Enrichment ───────────────────────────────

    def _enrich_with_adjacent(self, chunks: List[RetrievedChunk], window: int = 1) -> List[RetrievedChunk]:
        """
        For each retrieved chunk, find adjacent chunks (±window) from the
        same source file and merge their content.  This gives the LLM the
        surrounding context that may have been split off during chunking.

        Only merges if the adjacent chunk is NOT already in the result set
        (avoids duplication).
        """
        if not self.all_documents or not chunks:
            return chunks

        # Build file→ordered-chunks index on first call
        if not hasattr(self, '_file_chunk_map') or not self._file_chunk_map:
            self._file_chunk_map: Dict[str, List] = defaultdict(list)
            for doc in self.all_documents:
                fname = doc.metadata.get('filename', 'unknown')
                cidx = doc.metadata.get('chunk_index', -1)
                self._file_chunk_map[fname].append({
                    'index': cidx,
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                })
            # Sort each file's chunks by index
            for fname in self._file_chunk_map:
                self._file_chunk_map[fname].sort(key=lambda x: x['index'])

        existing_ids = {c.chunk_id for c in chunks}
        enriched = []

        for chunk in chunks:
            fname = chunk.source_file
            file_chunks = self._file_chunk_map.get(fname, [])
            if not file_chunks:
                enriched.append(chunk)
                continue

            # Find this chunk's position in its file
            match_pos = None
            for pos, fc in enumerate(file_chunks):
                fc_id = hashlib.md5(fc['content'][:100].encode()).hexdigest()[:12]
                if fc_id == chunk.chunk_id:
                    match_pos = pos
                    break

            if match_pos is None:
                enriched.append(chunk)
                continue

            # Collect adjacent content (before and after)
            parts = []
            for offset in range(-window, window + 1):
                adj_pos = match_pos + offset
                if 0 <= adj_pos < len(file_chunks):
                    adj = file_chunks[adj_pos]
                    adj_id = hashlib.md5(adj['content'][:100].encode()).hexdigest()[:12]
                    if offset == 0:
                        parts.append(adj['content'])
                    elif adj_id not in existing_ids:
                        parts.append(adj['content'])

            # Merge into single enriched chunk
            merged_content = "\n\n".join(parts)
            enriched_chunk = RetrievedChunk(
                content=merged_content,
                source_file=chunk.source_file,
                upload_date=chunk.upload_date,
                chunk_id=chunk.chunk_id,
                scores=chunk.scores,
                final_score=chunk.final_score,
                rerank_score=chunk.rerank_score,
            )
            enriched.append(enriched_chunk)

        return enriched

    # ── BM25 Search ─────────────────────────────────────────────────

    def _bm25_search(self, query: str, k: int = 8) -> List[RetrievedChunk]:
        """BM25 keyword search with stopword-filtered tokenization"""
        if not self.bm25 or not self.all_documents:
            return []

        try:
            tokens = [t for t in re.split(r'\W+', query.lower()) if len(t) > 1 and t not in _STOPWORDS]
            if not tokens:
                return []

            scores = self.bm25.get_scores(tokens)
            
            # Normalize scores to [0, 1]
            max_score = max(scores) if max(scores) > 0 else 1.0
            
            top_indices = np.argsort(scores)[::-1][:k]
            results = []
            
            for rank, idx in enumerate(top_indices):
                if idx < len(self.all_documents) and scores[idx] > 0:
                    doc = self.all_documents[idx]
                    chunk = RetrievedChunk(
                        content=doc.page_content,
                        source_file=doc.metadata.get('filename', 'unknown'),
                        upload_date=doc.metadata.get('upload_date', 'unknown'),
                        chunk_id=hashlib.md5(doc.page_content[:100].encode()).hexdigest()[:12],
                        scores={"bm25": scores[idx] / max_score},
                        final_score=0.0,
                    )
                    results.append(chunk)

            return results
        except Exception as e:
            logger.warning(f"BM25 search error: {e}")
            return []

    # ── Vector Search ───────────────────────────────────────────────

    async def _vector_search(self, query: str, k: int = 8) -> List[RetrievedChunk]:
        """Qdrant vector similarity search"""
        if not self.vector_store:
            return []

        try:
            query_embedding = await asyncio.to_thread(
                self.embeddings.embed_query, query
            )
            
            # Use Qdrant similarity search
            search_results = await asyncio.to_thread(
                self.vector_store.similarity_search,
                query_embedding, k=k
            )

            results = []
            for doc, similarity in search_results:
                chunk = RetrievedChunk(
                    content=doc.page_content,
                    source_file=doc.metadata.get('filename', 'unknown'),
                    upload_date=doc.metadata.get('upload_date', 'unknown'),
                    chunk_id=doc.metadata.get('chunk_id', 
                        hashlib.md5(doc.page_content[:100].encode()).hexdigest()[:12]),
                    scores={"vector": similarity},
                    final_score=0.0,
                )
                results.append(chunk)

            return results
        except Exception as e:
            logger.warning(f"Vector search error: {e}")
            return []

    # ── Score Fusion ────────────────────────────────────────────────

    def _merge_candidates(
        self,
        all_candidates: Dict[str, RetrievedChunk],
        new_results: List[RetrievedChunk],
        method: str,
        weight: float = 1.0,
        rrf_k: int = 60,
    ):
        """Merge new results into candidate pool using weighted RRF"""
        for rank, chunk in enumerate(new_results):
            rrf_score = weight * (1.0 / (rank + rrf_k))
            content_key = chunk.chunk_id

            if content_key in all_candidates:
                existing = all_candidates[content_key]
                existing.final_score += rrf_score
                existing.scores[method] = chunk.scores.get(
                    list(chunk.scores.keys())[0] if chunk.scores else method, 0
                )
            else:
                chunk.final_score = rrf_score
                chunk.scores[method] = chunk.scores.get(
                    list(chunk.scores.keys())[0] if chunk.scores else method, 0
                )
                all_candidates[content_key] = chunk

    # ── Deduplication ───────────────────────────────────────────────

    def _deduplicate(self, chunks: List[RetrievedChunk], similarity_threshold: float = 0.85) -> List[RetrievedChunk]:
        """Remove near-duplicate chunks based on content similarity"""
        if not chunks:
            return []

        deduped = [chunks[0]]
        
        for chunk in chunks[1:]:
            is_dup = False
            for existing in deduped:
                # Fast Jaccard similarity check
                words_a = set(chunk.content.lower().split())
                words_b = set(existing.content.lower().split())
                if not words_a or not words_b:
                    continue
                intersection = len(words_a & words_b)
                union = len(words_a | words_b)
                if union > 0 and (intersection / union) > similarity_threshold:
                    # Keep the one with higher score
                    if chunk.final_score > existing.final_score:
                        deduped.remove(existing)
                        deduped.append(chunk)
                    is_dup = True
                    break
            
            if not is_dup:
                deduped.append(chunk)

        return deduped

    # ── Cross-Encoder Reranking ─────────────────────────────────────

    async def _rerank(self, query: str, chunks: List[RetrievedChunk], k: int = 10) -> List[RetrievedChunk]:
        """
        Optional cross-encoder reranking. 
        Controlled by ENABLE_CROSS_ENCODER environment variable.
        If disabled, uses original RRF scores which is MUCH faster.
        """
        if not chunks:
            return []

        enable_ce = os.getenv("ENABLE_CROSS_ENCODER", "false").lower() == "true"
        
        if enable_ce:
            # ── Full Cross-encoder logic ───────────────────────────
            passages = [c.content for c in chunks]
            ce_scores = await asyncio.to_thread(
                self._cross_encoder.score, query, passages
            )

            for chunk, ce_score in zip(chunks, ce_scores):
                chunk.rerank_score = float(ce_score)
                rff_boost = self._rff.get_boost(chunk.chunk_id)
                chunk.final_score = (
                    0.40 * chunk.final_score +
                    0.45 * chunk.rerank_score +
                    0.15 * max(chunk.scores.get("vector", 0), chunk.scores.get("bm25", 0))
                ) * rff_boost
        else:
            # ── Fast Path: Use existing scores ─────────────────────
            for chunk in chunks:
                rff_boost = self._rff.get_boost(chunk.chunk_id)
                chunk.final_score = chunk.final_score * rff_boost
                # Mock a rerank score for confidence calculation
                chunk.rerank_score = chunk.scores.get("vector", 0.5)

        # Sort by final blended score
        chunks.sort(key=lambda c: c.final_score, reverse=True)
        return chunks[:k]

    # ── Confidence Calibration ──────────────────────────────────────

    def _calibrate_confidence(self, query: str, chunks: List[RetrievedChunk]) -> float:
        """
        Multi-signal confidence calibration leveraging cross-encoder scores.
        """
        if not chunks:
            return 0.0

        query_words = set(re.split(r'\W+', query.lower())) - _STOPWORDS
        if not query_words:
            return 0.0

        # Signal 1: Best cross-encoder rerank score (0-1, most reliable)
        best_rerank = chunks[0].rerank_score if chunks else 0.0

        # Signal 2: Mean of top-3 rerank scores (consistency check)
        top3_rerank = np.mean([c.rerank_score for c in chunks[:3]]) if len(chunks) >= 3 else best_rerank

        # Signal 3: Score gap between #1 and #2 (higher = more certain)
        score_gap = 0.0
        if len(chunks) >= 2:
            score_gap = chunks[0].final_score - chunks[1].final_score

        # Signal 4: Coverage — how many query terms appear in top 3 chunks
        top_3_text = " ".join([c.content.lower() for c in chunks[:3]])
        top_3_words = set(re.split(r'\W+', top_3_text)) - _STOPWORDS
        coverage = len(query_words & top_3_words) / len(query_words) if query_words else 0

        # Signal 5: Source agreement — do multiple sources agree?
        unique_sources = len(set(c.source_file for c in chunks[:5]))
        source_diversity = min(unique_sources / 3.0, 1.0)

        # Signal 6: RFF feedback quality for top chunk
        rff_boost = self._rff.get_boost(chunks[0].chunk_id) if chunks else 1.0
        rff_signal = min(max((rff_boost - 0.7) / 0.6, 0.0), 1.0)  # Normalize 0.7-1.3 → 0-1

        # Weighted confidence (cross-encoder signals dominate)
        confidence = (
            0.30 * best_rerank +            # Cross-encoder #1 score
            0.15 * top3_rerank +             # Top-3 consistency
            0.10 * min(score_gap * 30, 1.0) + # Score gap signal
            0.20 * coverage +                # Query term coverage
            0.10 * source_diversity +        # Source agreement
            0.15 * rff_signal                # Historical feedback
        )

        return round(min(max(confidence, 0.0), 1.0), 4)

    # ── Context Formatting ──────────────────────────────────────────

    def _format_context(self, chunks: List[RetrievedChunk], intent: str) -> Tuple[str, List[Dict]]:
        """
        Format retrieved chunks into LLM-ready context with citations.
        Shopify pattern: structured context with explicit metadata.
        """
        if not chunks:
            return "", []

        context_items = []
        citations = []
        seen_sources = set()

        for i, chunk in enumerate(chunks):
            # Build structured context block
            context_items.append(
                f"[SOURCE {i+1}: {chunk.source_file} | DATE: {chunk.upload_date} | "
                f"RELEVANCE: {chunk.final_score:.3f}]\n{chunk.content}"
            )

            # Track citations
            if chunk.source_file not in seen_sources:
                citations.append({
                    "file": chunk.source_file,
                    "date": chunk.upload_date,
                    "relevance": f"{chunk.final_score:.3f}",
                    "rerank_score": f"{chunk.rerank_score:.3f}",
                })
                seen_sources.add(chunk.source_file)

        context_text = "\n\n---\n\n".join(context_items)
        return context_text, citations
