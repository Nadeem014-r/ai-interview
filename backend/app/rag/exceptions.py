"""Phase 7: RAG Exception Hierarchy.

Provides controlled, descriptive exceptions for chunking, embedding validation,
vector storage, similarity calculations, and retrieval operations.
"""

class RAGError(Exception):
    """Base exception for all RAG-related errors."""
    pass


class ChunkingError(RAGError):
    """Raised when text chunking parameters or operations fail validation."""
    pass


class InvalidVectorError(RAGError):
    """Raised when an embedding vector is malformed, has invalid dimensions, or non-numeric values."""
    pass


class EmbeddingValidationError(RAGError):
    """Raised when an embedding returned by the provider fails structural validation."""
    pass


class EmbeddingProviderError(RAGError):
    """Raised when an AI embedding provider fails to generate an embedding."""
    pass


class VectorStoreError(RAGError):
    """Raised when database or vector persistence operations encounter an error."""
    pass


class PromptInjectionDetected(RAGError):
    """Raised or logged when active prompt injection patterns are identified in retrieved documents."""
    pass
