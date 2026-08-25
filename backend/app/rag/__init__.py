"""Phase 7: RAG (Retrieval-Augmented Generation) Knowledge & Vector Package."""

from app.rag.chunker import DocumentChunker
from app.rag.vector_store import VectorStore
from app.rag.rag_engine import RAGEngine
from app.rag.similarity import cosine_similarity, validate_vector
from app.rag.security import PromptInjectionDefense
from app.rag.exceptions import (
    RAGError,
    ChunkingError,
    InvalidVectorError,
    EmbeddingValidationError,
    EmbeddingProviderError,
    VectorStoreError,
    PromptInjectionDetected,
)

__all__ = [
    "DocumentChunker",
    "VectorStore",
    "RAGEngine",
    "cosine_similarity",
    "validate_vector",
    "PromptInjectionDefense",
    "RAGError",
    "ChunkingError",
    "InvalidVectorError",
    "EmbeddingValidationError",
    "EmbeddingProviderError",
    "VectorStoreError",
    "PromptInjectionDetected",
]
