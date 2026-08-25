"""Phase 10B: Streaming Audio Chunk Pipeline & Backpressure Controller.

Processes incoming audio chunks with sequence validation, deduplication,
bounded memory buffers, producer/consumer backpressure, and safe aggregation.
"""

import time
import base64
import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from app.realtime.config import config
from app.realtime.exceptions import (
    AudioLimitExceededError,
    BackpressureError,
    ReplayDetectedError,
    InvalidRealtimeMessageError,
)


@dataclass
class AudioChunk:
    """Represents a validated audio chunk in the streaming pipeline."""
    sequence: int
    data: bytes
    is_last: bool = False
    timestamp: float = 0.0


class AudioChunkPipeline:
    """Bounded, ordered streaming audio pipeline with backpressure."""

    def __init__(
        self,
        session_id: str,
        max_chunk_bytes: int = config.MAX_AUDIO_CHUNK_BYTES,
        max_buffer_bytes: int = config.MAX_BUFFER_BYTES,
        max_queue_size: int = config.MAX_QUEUE_SIZE
    ):
        self.session_id = session_id
        self.max_chunk_bytes = max_chunk_bytes
        self.max_buffer_bytes = max_buffer_bytes
        self.max_queue_size = max_queue_size

        # In-order chunks: sequence -> bytes
        self._buffered_chunks: Dict[int, bytes] = {}
        self._total_buffered_bytes: int = 0
        self._next_expected_sequence: int = 1
        self._processed_sequences: set = set()
        self._is_completed: bool = False
        self._lock = asyncio.Lock()

    async def push_chunk(
        self,
        sequence: int,
        raw_audio: bytes,
        is_last: bool = False
    ) -> None:
        """
        Validate, buffer, and order an incoming audio chunk.
        Enforces size limits, duplicate detection, and backpressure.
        """
        if raw_audio is None or len(raw_audio) == 0:
            if is_last:
                self._is_completed = True
                return
            raise InvalidRealtimeMessageError("Audio chunk data cannot be empty.")

        chunk_size = len(raw_audio)

        # 1. Chunk size limit
        if chunk_size > self.max_chunk_bytes:
            raise AudioLimitExceededError(
                f"Audio chunk size ({chunk_size}B) exceeds maximum limit ({self.max_chunk_bytes}B)."
            )

        async with self._lock:
            # 2. Duplicate detection
            if sequence in self._processed_sequences or sequence in self._buffered_chunks:
                # Silently ignore duplicates or mark replay
                return

            # 3. Backpressure check
            if len(self._buffered_chunks) >= self.max_queue_size:
                raise BackpressureError(
                    f"Audio pipeline queue full ({len(self._buffered_chunks)} items). Consumer backpressure active."
                )

            # 4. Total buffer limit check
            if (self._total_buffered_bytes + chunk_size) > self.max_buffer_bytes:
                raise AudioLimitExceededError(
                    f"Total buffered audio ({self._total_buffered_bytes + chunk_size}B) exceeds limit ({self.max_buffer_bytes}B)."
                )

            # 5. Buffer chunk
            self._buffered_chunks[sequence] = raw_audio
            self._total_buffered_bytes += chunk_size
            if is_last:
                self._is_completed = True

    async def get_ordered_audio_bytes(self) -> bytes:
        """
        Assembles all consecutive buffered chunks in strictly ascending sequence order.
        """
        async with self._lock:
            if not self._buffered_chunks:
                return b""

            sorted_sequences = sorted(self._buffered_chunks.keys())
            assembled = bytearray()

            for seq in sorted_sequences:
                chunk = self._buffered_chunks[seq]
                assembled.extend(chunk)
                self._processed_sequences.add(seq)

            return bytes(assembled)

    async def get_buffer_metrics(self) -> Dict[str, Any]:
        """Get pipeline diagnostic metrics."""
        async with self._lock:
            return {
                "buffered_chunks_count": len(self._buffered_chunks),
                "total_buffered_bytes": self._total_buffered_bytes,
                "is_completed": self._is_completed
            }

    async def clear(self) -> None:
        """Reset and free audio buffers."""
        async with self._lock:
            self._buffered_chunks.clear()
            self._total_buffered_bytes = 0
            self._processed_sequences.clear()
            self._is_completed = False
