"""Trigger RAG reindex on production."""
import sys, os, asyncio
sys.path.insert(0, '/home/j33ca/support-portal-edgeworks')
os.chdir('/home/j33ca/support-portal-edgeworks')

from app.services.rag_service import RAGService

async def reindex():
    rag = RAGService()
    await rag.reload_knowledge()
    doc_count = len(rag.all_documents) if rag.all_documents else 0
    print(f"Indexed {doc_count} chunks into vector store")

asyncio.run(reindex())
