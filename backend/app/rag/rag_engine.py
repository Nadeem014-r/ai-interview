"""Phase 7: RAG Engine.

Provides high-level knowledge retrieval orchestration, prompt-injection defense,
source grounding, and context construction for downstream interview question generation.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.vector_store import VectorStore
from app.rag.security import PromptInjectionDefense

logger = logging.getLogger("ai_interviewer.rag.engine")


class RAGEngine:
    """Knowledge retrieval and context grounding engine."""

    def __init__(self, db: AsyncSession, vector_store: Optional[VectorStore] = None):
        self.db = db
        self.vector_store = vector_store or VectorStore(db)

    async def retrieve_chunks(
        self,
        query: str,
        company_id: Optional[int] = None,
        role_id: Optional[int] = None,
        source_id: Optional[int] = None,
        document_id: Optional[int] = None,
        trust_level: Optional[str] = None,
        source_type: Optional[str] = None,
        top_k: int = 3,
        min_similarity: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve raw structured chunk records with provenance and similarity scores."""
        return await self.vector_store.similarity_search(
            query=query,
            company_id=company_id,
            role_id=role_id,
            source_id=source_id,
            document_id=document_id,
            trust_level=trust_level,
            source_type=source_type,
            top_k=top_k,
            min_similarity=min_similarity
        )

    async def get_relevant_context(
        self,
        query: str,
        company_id: Optional[int] = None,
        role_id: Optional[int] = None,
        source_id: Optional[int] = None,
        document_id: Optional[int] = None,
        trust_level: Optional[str] = None,
        source_type: Optional[str] = None,
        top_k: int = 3,
        min_similarity: Optional[float] = None
    ) -> str:
        """
        Retrieve minimal, source-grounded context formatted safely with delimiter boundaries
        and prompt-injection protection for downstream LLM prompts.
        """
        results = await self.retrieve_chunks(
            query=query,
            company_id=company_id,
            role_id=role_id,
            source_id=source_id,
            document_id=document_id,
            trust_level=trust_level,
            source_type=source_type,
            top_k=top_k,
            min_similarity=min_similarity
        )

        return PromptInjectionDefense.construct_grounded_boundary(results)
