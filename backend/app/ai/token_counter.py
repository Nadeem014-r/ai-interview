"""Phase 8: Token Measurement & Estimation Utilities.

Provides fast, deterministic token estimation without hard external tokenizer dependencies,
conforming to standard ~4 characters / 0.75 words per token heuristic.
"""

from typing import List, Dict, Any, Union


def estimate_tokens(text: Union[str, Any]) -> int:
    """
    Estimate token count for a text string.
    Rule of thumb: ~4 characters per token for English text and code, with a word-based lower bound.
    """
    if not text:
        return 0
    if not isinstance(text, str):
        text = str(text)
    
    char_count = len(text)
    word_count = len(text.split())
    
    # Combined heuristic: weighted average of char/4 and word*1.33
    char_estimate = char_count / 4.0
    word_estimate = word_count * 1.33
    
    estimate = int(max(char_estimate, word_estimate))
    return max(1, estimate) if char_count > 0 else 0


def estimate_messages_tokens(messages: List[Dict[str, str]]) -> int:
    """
    Estimate token count for chat-style message lists (including role framing overhead).
    """
    total = 0
    for msg in messages:
        # 4 tokens overhead per message for framing (<role>, <content>, etc.)
        total += 4
        for key, val in msg.items():
            total += estimate_tokens(val)
    total += 2  # priming token overhead
    return total
