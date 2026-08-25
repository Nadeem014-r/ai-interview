from typing import Dict, Any

RUBRIC_VERSION = "v1.0.0"

EVALUATION_RUBRIC = {
    "correctness": {
        "weight": 0.35,
        "description": "Factual and technical accuracy of the answer compared to expected core concepts."
    },
    "relevance": {
        "weight": 0.20,
        "description": "Directness and alignment of candidate answer with the target question."
    },
    "reasoning": {
        "weight": 0.20,
        "description": "Logical problem-solving structure, step-by-step rationale, and trade-off analysis."
    },
    "depth": {
        "weight": 0.15,
        "description": "Level of technical depth, edge cases, underlying mechanics, and architectural insight."
    },
    "communication": {
        "weight": 0.10,
        "description": "Clarity, terminology correctness, and conciseness of response."
    }
}
