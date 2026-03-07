# RAG Pipeline Architecture

Retrieval-Augmented Generation ensures AI answers are grounded in real
knowledge.

------------------------------------------------------------------------

Pipeline Steps

User Query ↓ Query Rewriting ↓ Hybrid Retrieval ↓ Document Reranking ↓
Context Selection ↓ LLM Answer Generation

------------------------------------------------------------------------

## Hybrid Retrieval

Combine:

Vector Search Keyword Search

Purpose: - semantic similarity - exact keyword match

------------------------------------------------------------------------

## Reranking

Top 20 retrieved documents are re-ranked using a cross-encoder model.

Final top 3--5 documents passed to the LLM.

------------------------------------------------------------------------

## Benefits

-   reduced hallucinations
-   higher answer accuracy
-   better knowledge coverage
