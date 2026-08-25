"""Phase 7: Cosine Similarity and Vector Computation.

Provides mathematically rigorous, numerically stable vector similarity calculation
with defense against zero-division, mismatched dimensions, NaNs, and infinite values.
"""

import math
from typing import List, Optional, Any
from app.rag.exceptions import InvalidVectorError


def validate_vector(vec: Any, expected_dim: Optional[int] = None, allow_empty: bool = False) -> List[float]:
    """
    Validate that an input is a valid list of numeric floats.
    Raises InvalidVectorError if malformed.
    """
    if vec is None:
        raise InvalidVectorError("Vector cannot be None.")
    
    if not isinstance(vec, (list, tuple)):
        raise InvalidVectorError(f"Vector must be a list or tuple, got {type(vec).__name__}.")
    
    if len(vec) == 0:
        if allow_empty:
            return []
        raise InvalidVectorError("Vector cannot be empty.")
    
    if expected_dim is not None and len(vec) != expected_dim:
        raise InvalidVectorError(f"Vector dimension mismatch: expected {expected_dim}, got {len(vec)}.")
    
    cleaned_vec: List[float] = []
    for idx, val in enumerate(vec):
        if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
            raise InvalidVectorError(f"Vector element at index {idx} is non-numeric: {val!r}")
        
        num_val = float(val)
        if math.isnan(num_val) or math.isinf(num_val):
            raise InvalidVectorError(f"Vector element at index {idx} is NaN or Inf.")
        cleaned_vec.append(num_val)
        
    return cleaned_vec


def cosine_similarity(
    vec1: Optional[List[float]],
    vec2: Optional[List[float]],
    raise_on_error: bool = False
) -> float:
    """
    Compute mathematically correct cosine similarity between two numeric vectors.
    
    Cosine similarity:
        sim(u, v) = (u . v) / (||u|| * ||v||)
    
    Returns:
        float in [-1.0, 1.0]. Returns 0.0 if either vector is empty, zero-norm,
        or invalid (when raise_on_error is False).
    """
    if vec1 is None or vec2 is None:
        if raise_on_error:
            raise InvalidVectorError("Input vector cannot be None.")
        return 0.0

    try:
        cleaned_v1 = validate_vector(vec1, allow_empty=False)
        cleaned_v2 = validate_vector(vec2, expected_dim=len(cleaned_v1), allow_empty=False)
    except InvalidVectorError:
        if raise_on_error:
            raise
        return 0.0

    dot_product = sum(a * b for a, b in zip(cleaned_v1, cleaned_v2))
    norm_a = math.sqrt(sum(a * a for a in cleaned_v1))
    norm_b = math.sqrt(sum(b * b for b in cleaned_v2))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    sim = dot_product / (norm_a * norm_b)
    # Clamp float precision errors (e.g., 1.0000000000000002 -> 1.0)
    return max(-1.0, min(1.0, float(sim)))
