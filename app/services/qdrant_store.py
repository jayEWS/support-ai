"""
Qdrant Vector Store Integration for Advanced Retriever
======================================================
Production-ready Qdrant integration replacing FAISS for scalable vector storage.
Implements multi-stage retrieval with Qdrant's hybrid search capabilities.
"""

import os
import uuid
import hashlib
from typing import List, Dict, Optional, Any, Tuple
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from app.core.config import settings
from app.core.logging import logger

class QdrantVectorStore:
    """
    Qdrant Vector Database wrapper with enterprise features:
    - Automatic collection management
    - Metadata filtering
    - Batch operations
    - Connection pooling
    """
    
    def __init__(self, collection_name: str = "knowledge_base"):
        self.collection_name = collection_name
        self.client = None
        self.vector_size = 384  # all-MiniLM-L6-v2 embedding size
        self._connect()
        
    def _connect(self):
        """Initialize Qdrant client connection"""
        try:
            if settings.QDRANT_URL:
                self.client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                    timeout=30
                )
                logger.info(f"[Qdrant] Connected to {settings.QDRANT_URL}")
            elif settings.QDRANT_HOST == "local":
                # Ensure directory exists
                os.makedirs("data/qdrant_storage", exist_ok=True)
                self.client = QdrantClient(path="data/qdrant_storage")
                logger.info("[Qdrant] Using local file-based storage at data/qdrant_storage")
            else:
                self.client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                    timeout=30
                )
                logger.info(f"[Qdrant] Connected to {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
            
            # Ensure collection exists
            self._ensure_collection()
            
        except Exception as e:
            logger.error(f"[Qdrant] Connection failed: {e}")
            self.client = None
            
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        if not self.client:
            return
            
        try:
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"[Qdrant] Created collection: {self.collection_name}")
            else:
                logger.info(f"[Qdrant] Using existing collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"[Qdrant] Collection setup failed: {e}")
            
    def add_documents(self, documents: List[Any], embeddings: List[List[float]]):
        """Batch insert documents with embeddings"""
        if not self.client or not documents or not embeddings:
            return
            
        try:
            points = []
            for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
                point_id = str(uuid.uuid4())
                
                # Extract metadata
                metadata = getattr(doc, 'metadata', {})
                content = getattr(doc, 'page_content', str(doc))
                
                # Create chunk ID for consistency with advanced_retriever
                chunk_id = hashlib.md5(content[:100].encode()).hexdigest()[:12]
                
                payload = {
                    "content": content,
                    "filename": metadata.get('filename', 'unknown'),
                    "chunk_index": metadata.get('chunk_index', 0),
                    "chunk_id": chunk_id,
                    "source": metadata.get('source', 'unknown'),
                    "category": metadata.get('category', 'general')
                }
                
                points.append(PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                ))
                
            # Batch upsert
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"[Qdrant] Indexed {len(points)} documents")
            
        except Exception as e:
            logger.error(f"[Qdrant] Document indexing failed: {e}")
            
    def similarity_search(self, query_embedding: List[float], k: int = 10, 
                         filter_dict: Optional[Dict] = None) -> List[Tuple[Any, float]]:
        """Vector similarity search with optional metadata filtering"""
        if not self.client:
            return []
            
        try:
            # Build filter if provided
            query_filter = None
            if filter_dict:
                conditions = []
                for key, value in filter_dict.items():
                    conditions.append(FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    ))
                if conditions:
                    query_filter = Filter(must=conditions)
            
            # Search
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=k,
                with_payload=True,
                with_vectors=False
            )
            
            # Convert to expected format
            results = []
            for point in search_result:
                # Create mock document object
                class MockDocument:
                    def __init__(self, content, metadata):
                        self.page_content = content
                        self.metadata = metadata
                
                doc = MockDocument(
                    content=point.payload.get("content", ""),
                    metadata={
                        "filename": point.payload.get("filename", "unknown"),
                        "chunk_index": point.payload.get("chunk_index", 0),
                        "source": point.payload.get("source", "unknown"),
                        "category": point.payload.get("category", "general"),
                        "chunk_id": point.payload.get("chunk_id", "")
                    }
                )
                
                # Qdrant cosine returns a similarity score in [-1, 1] (1 = most similar)
                # Normalise to [0, 1] — do NOT subtract from 1 (that would invert ranking)
                similarity = (point.score + 1.0) / 2.0
                
                results.append((doc, similarity))
                
            return results
            
        except Exception as e:
            logger.error(f"[Qdrant] Search failed: {e}")
            return []
            
    def clear_collection(self):
        """Clear all documents from collection"""
        if not self.client:
            return
            
        try:
            self.client.delete_collection(self.collection_name)
            self._ensure_collection()  # Recreate empty collection
            logger.info(f"[Qdrant] Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"[Qdrant] Clear collection failed: {e}")
            
    def get_collection_info(self) -> Dict:
        """Get collection statistics"""
        if not self.client:
            return {}
            
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status
            }
        except Exception as e:
            logger.error(f"[Qdrant] Get collection info failed: {e}")
            return {}

# Global instance for application use
_qdrant_store = None

def get_qdrant_store() -> QdrantVectorStore:
    """Get singleton Qdrant store instance"""
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantVectorStore()
    return _qdrant_store