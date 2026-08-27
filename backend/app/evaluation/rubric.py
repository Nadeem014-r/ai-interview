from typing import Dict, Any

RUBRIC_VERSION = "v2.0.0"

# Default balanced rubric
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

# Question-type tailored rubric weighting profiles
QUESTION_TYPE_RUBRICS = {
    "technical": {
        "correctness": 0.35,
        "relevance": 0.20,
        "reasoning": 0.20,
        "depth": 0.15,
        "communication": 0.10
    },
    "conceptual": {
        "correctness": 0.40,
        "relevance": 0.20,
        "reasoning": 0.15,
        "depth": 0.15,
        "communication": 0.10
    },
    "database": {
        "correctness": 0.35,
        "relevance": 0.15,
        "reasoning": 0.25,
        "depth": 0.15,
        "communication": 0.10
    },
    "system_design": {
        "correctness": 0.20,
        "relevance": 0.15,
        "reasoning": 0.30,
        "depth": 0.25,
        "communication": 0.10
    },
    "coding": {
        "correctness": 0.45,
        "relevance": 0.15,
        "reasoning": 0.20,
        "depth": 0.10,
        "communication": 0.10
    },
    "behavioral": {
        "correctness": 0.10, # Authenticity / consistency
        "relevance": 0.25, # Direct answer to the situation asked
        "reasoning": 0.30, # STAR rationale, action taken, decision making
        "depth": 0.15, # Outcome, metrics, reflection & learnings
        "communication": 0.20 # Clarity, ownership, structure
    },
    "hr": {
        "correctness": 0.10, # Authenticity / consistency
        "relevance": 0.30, # Alignment with question & role
        "reasoning": 0.20, # Self-awareness & rationale
        "depth": 0.15, # Concrete examples vs vague claims
        "communication": 0.25 # Professionalism, clarity & structure
    },
    "resume": {
        "correctness": 0.30, # Verifiable claim accuracy
        "relevance": 0.20, # Alignment with stated project/experience
        "reasoning": 0.25, # Architecture & implementation choices
        "depth": 0.15, # Concrete role contribution vs vague ownership
        "communication": 0.10 # Articulation
    }
}


def get_rubric_weights(question_type: str = "technical") -> Dict[str, float]:
    """Returns normalized dimension weights for a given question type."""
    qtype = (question_type or "technical").lower().strip()
    return QUESTION_TYPE_RUBRICS.get(qtype, QUESTION_TYPE_RUBRICS["technical"])
