"""Phase 8: Hardened Mock & Offline AI Providers.

Provides deterministic, offline-capable implementations of LLM, Embedding, STT, and TTS
for development, local testing, and air-gapped environments without external API calls.
"""

import json
import hashlib
import time
from typing import List, Dict, Any, Optional
from app.ai.base import LLMProvider, EmbeddingProvider, STTProvider, TTSProvider
from app.ai.schemas import validate_structured_data


class MockLLMProvider(LLMProvider):
    """Deterministic offline mock LLM provider."""

    def __init__(self, model_name: str = "mock-llm-v1"):
        self.model_name = model_name

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        prompt_lower = prompt.lower()
        if "evaluate" in prompt_lower or "score" in prompt_lower:
            return "The candidate provided a structured and technically accurate answer demonstrating solid grasp of core fundamentals."
        elif "question" in prompt_lower:
            return "Could you explain how indexing improves query performance in relational databases?"
        elif "summary" in prompt_lower or "report" in prompt_lower:
            return "Overall strong candidate showing proficiency in system design and data structures with minor gaps in distributed consensus."
        elif "research" in prompt_lower or "company" in prompt_lower:
            return "Company focuses on high-scale distributed backend systems with strong engineering culture."
        return "Standard mock LLM response for demonstration."

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        data: Dict[str, Any] = {}

        # 1. Evaluation mock fallback
        if "evaluat" in prompt_lower:
            data = {
                "correctness_score": 8.5,
                "relevance_score": 9.0,
                "reasoning_score": 8.0,
                "depth_score": 7.5,
                "communication_score": 8.5,
                "evidence": [
                    "Correctly identified B-Tree indexing mechanism",
                    "Mentioned time complexity reduction from O(N) to O(log N)"
                ],
                "feedback_text": "Excellent explanation of B-Trees and query execution plans. To make it even stronger, mention composite indexes and write performance trade-offs.",
                "confidence_score": 0.95,
                "human_review_required": False
            }

        # 2. Report generation mock fallback
        elif "report" in prompt_lower or "synthesis" in prompt_lower:
            data = {
                "strengths": [
                    "Strong grasp of relational database fundamentals",
                    "Clear articulation of asymptotic time complexity",
                    "Structured problem-solving approach"
                ],
                "weaknesses": [
                    "Could deepen knowledge of distributed system fault tolerance",
                    "Minor gaps in write-heavy optimization trade-offs"
                ],
                "difficult_topics": ["Distributed Systems", "Write Amplification"],
                "recommendations": [
                    "Review CAP Theorem and Paxos/Raft consensus algorithms",
                    "Practice designing write-optimized LSM-tree data structures"
                ],
                "executive_summary": "The candidate performed exceptionally well across core backend topics. Demonstrates clear viva readiness and strong technical foundation suitable for entry/mid software engineering roles."
            }

        # 3. Question generation mock fallback
        elif "question" in prompt_lower:
            data = {
                "question_text": "How do database indexes improve query execution speed, and what are the trade-offs on write operations?",
                "expected_concepts": ["B-Tree indexing", "Disk I/O reduction", "Write overhead / index maintenance"],
                "follow_ups": ["When would you choose a hash index over a B-Tree index?"]
            }

        # 4. Research synthesis mock fallback
        elif "research" in prompt_lower or "company" in prompt_lower:
            data = {
                "description": "Global technology company specializing in cloud computing, developer platforms, and distributed systems.",
                "required_skills": ["Python", "Go", "Distributed Systems", "PostgreSQL"],
                "key_topics": ["System Design", "Concurrency", "Database Optimization"],
                "interview_categories": ["System Design", "Coding Algorithms", "Behavioral Leadership"],
                "culture_keywords": ["Customer Obsession", "Ownership", "Technical Excellence"],
                "confidence_level": "high"
            }

        # 5. Resume parsing mock fallback - dynamically parse from prompt text without inventing data
        elif "resume" in prompt_lower or "extract" in prompt_lower:
            from app.resume.parser import ResumeParser
            resume_text = prompt
            if "RESUME TEXT:" in prompt:
                parts = prompt.split("RESUME TEXT:", 1)[1]
                if "Return a valid JSON" in parts:
                    resume_text = parts.split("Return a valid JSON", 1)[0]
                elif "Return a JSON" in parts:
                    resume_text = parts.split("Return a JSON", 1)[0]
                elif "Return JSON" in parts:
                    resume_text = parts.split("Return JSON", 1)[0]
                else:
                    resume_text = parts
            data = ResumeParser.deterministic_rule_parse(resume_text.strip())

        else:
            data = {"result": "mock_json_response", "status": "success"}

        # Validate against schema if schema was supplied
        if schema is not None:
            return validate_structured_data(data, schema, provider="mock")
        return data


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic offline mock embedding provider."""

    def __init__(self, dimension: int = 128, model_name: str = "mock-embed-v1"):
        self.dimension = dimension
        self.model_name = model_name

    async def embed_text(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate deterministic normalized float vector for input text."""
        if text is None:
            text = ""
        # Deterministic pseudo-embedding generator of configured dimension
        hash_val = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        vec = [((hash_val >> (i % 32)) & 0xFF) / 255.0 for i in range(self.dimension)]
        # Normalize vector magnitude
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            return [round(x / norm, 6) for x in vec]
        return vec

    async def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """Preserve exact batch ordering."""
        if not texts:
            return []
        return [await self.embed_text(t, model=model) for t in texts]


class MockSTTProvider(STTProvider):
    """Offline speech-to-text mock provider."""

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> Dict[str, Any]:
        return {
            "transcript": "Database indexes use B-Trees to speed up data retrieval operations by reducing disk I/O.",
            "confidence": 0.98,
            "duration_sec": 4.5
        }


class MockTTSProvider(TTSProvider):
    """Offline text-to-speech mock provider."""

    async def synthesize_speech(self, text: str, voice_id: str = "default") -> bytes:
        # Return standard dummy WAV audio header bytes
        return b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
