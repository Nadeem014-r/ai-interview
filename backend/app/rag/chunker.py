"""Phase 7: Document Chunker.

Provides deterministic sliding-window text chunking with configurable chunk size,
overlap validation, rich metadata tracking, and edge-case handling.
"""

from typing import List, Dict, Any, Optional
from app.rag.exceptions import ChunkingError


class DocumentChunker:
    """Production-grade text chunker for vector search and RAG indexing."""

    @staticmethod
    def validate_chunk_params(chunk_size: int, overlap: int) -> None:
        """Validate that chunk_size and overlap are valid positive integers and overlap < chunk_size."""
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ChunkingError(f"chunk_size must be a positive integer > 0, got {chunk_size!r}")
        if not isinstance(overlap, int) or overlap < 0:
            raise ChunkingError(f"overlap must be a non-negative integer >= 0, got {overlap!r}")
        if overlap >= chunk_size:
            raise ChunkingError(
                f"overlap ({overlap}) must be strictly smaller than chunk_size ({chunk_size})."
            )

    @staticmethod
    def chunk_text(text: Optional[str], chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split text into sliding window word chunks with overlap.
        
        Args:
            text: Raw input text.
            chunk_size: Maximum number of words per chunk (default: 500).
            overlap: Number of overlapping words between consecutive chunks (default: 50).
            
        Returns:
            List of deterministic chunk strings.
        """
        DocumentChunker.validate_chunk_params(chunk_size, overlap)

        if text is None:
            return []
        
        cleaned = text.strip()
        if not cleaned:
            return []

        words = cleaned.split()
        if not words:
            return []

        if len(words) <= chunk_size:
            return [cleaned]

        chunks: List[str] = []
        start = 0
        step = chunk_size - overlap

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            if end >= len(words):
                break
            start += step

        return chunks

    @staticmethod
    def chunk_lines(text: Optional[str], chunk_size: int = 200, overlap: int = 30) -> List[str]:
        """
        Pack whole lines into chunks of at most chunk_size words, keeping line breaks.

        Unlike chunk_text, a chunk never starts or ends mid-sentence, so a section
        heading stays with its content. A short heading-like line is carried into
        the next chunk rather than left dangling at the end of the previous one.
        Consecutive chunks share trailing lines totalling at most `overlap` words.
        A single line longer than chunk_size falls back to chunk_text windows.
        """
        DocumentChunker.validate_chunk_params(chunk_size, overlap)
        if text is None or not text.strip():
            return []

        lines: List[str] = []
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            if not line:
                continue
            if len(line.split()) > chunk_size:
                lines.extend(DocumentChunker.chunk_text(line, chunk_size=chunk_size, overlap=overlap))
            else:
                lines.append(line)

        chunks: List[str] = []
        current: List[str] = []
        current_words = 0
        for line in lines:
            words = len(line.split())
            if current and current_words + words > chunk_size:
                carried: List[str] = []
                if len(current) > 1 and len(current[-1].split()) <= 4:
                    carried = [current.pop()]
                chunks.append("\n".join(current))
                tail: List[str] = []
                tail_words = 0
                for prev in reversed(current):
                    n = len(prev.split())
                    if tail_words + n > overlap:
                        break
                    tail.insert(0, prev)
                    tail_words += n
                current = tail + carried
                current_words = sum(len(x.split()) for x in current)
                while current and current_words + words > chunk_size:
                    current_words -= len(current.pop(0).split())
            current.append(line)
            current_words += words
        if current:
            chunks.append("\n".join(current))
        return chunks

    @staticmethod
    def chunk_document(
        text: Optional[str],
        chunk_size: int = 500,
        overlap: int = 50,
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk text and generate structured chunk dicts containing chunk metadata.
        """
        chunks = DocumentChunker.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        structured_chunks: List[Dict[str, Any]] = []
        meta = dict(base_metadata or {})

        for idx, chunk_str in enumerate(chunks):
            chunk_meta = {
                **meta,
                "chunk_index": idx,
                "chunk_size": chunk_size,
                "overlap": overlap,
                "word_count": len(chunk_str.split()),
                "char_count": len(chunk_str),
            }
            structured_chunks.append({
                "chunk_index": idx,
                "chunk_text": chunk_str,
                "metadata": chunk_meta
            })

        return structured_chunks
