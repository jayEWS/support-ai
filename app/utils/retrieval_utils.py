import numpy as np
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any
from app.core.logging import logger

class HybridRetriever:
    def __init__(self, documents: List[Any]):
        """
        Expects a list of LangChain Document objects.
        """
        self.docs = documents
        if documents:
            # Tokenize for BM25
            tokenized_corpus = [doc.page_content.lower().split() for doc in documents]
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

    def get_bm25_scores(self, query: str, k: int = 5) -> List[int]:
        """Returns indices of top K documents using BM25."""
        if not self.bm25:
            return []
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        top_n = np.argsort(scores)[::-1][:k]
        return top_n.tolist()

def reciprocal_rank_fusion(vector_results: List[Any], bm25_results: List[Any], k: int = 60):
    """
    Fuses two ranked lists using RRF algorithm.
    vector_results: List of Document objects from FAISS.
    bm25_results: List of Document objects from BM25.
    """
    fused_scores = {}
    
    # Process Vector Results
    for rank, doc in enumerate(vector_results):
        doc_id = doc.page_content # Use content as unique ID for fusion
        if doc_id not in fused_scores:
            fused_scores[doc_id] = {"score": 0.0, "doc": doc}
        fused_scores[doc_id]["score"] += 1.0 / (rank + k)
        
    # Process BM25 Results
    for rank, doc in enumerate(bm25_results):
        doc_id = doc.page_content
        if doc_id not in fused_scores:
            fused_scores[doc_id] = {"score": 0.0, "doc": doc}
        fused_scores[doc_id]["score"] += 1.0 / (rank + k)
        
    # Sort by fused score
    reranked = sorted(fused_scores.values(), key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in reranked]

def calculate_confidence(query: str, context: str) -> float:
    """
    Crude but effective word-overlap confidence score.
    In a full enterprise system, this would use a Cross-Encoder model.
    """
    q_words = set(query.lower().split())
    c_words = set(context.lower().split())
    if not q_words: return 0.0
    overlap = q_words.intersection(c_words)
    return len(overlap) / len(q_words)
