"""Decides whether an interview should include a coding exercise, and builds it.

Coding is not a default stage. A behavioural round, an HR round or a role with
no programming requirement should never produce one, and a single word on a
resume is not evidence that a candidate expects to write code -- "Java" appears
in resumes belonging to testers, analysts and project managers. So eligibility
needs agreement from more than one source of context, and the interview must
already be underway before it is offered.

No provider call is made here. Everything is read from context the interview
already holds, so adding this stage costs nothing per interview.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

# Interview types where writing code is a normal part of the conversation.
_CODING_INTERVIEW_TYPES = {"technical", "role_specific", "mixed"}

# Role titles that are expected to write code. Matched as substrings against a
# lowercased title, so "Senior Backend Software Engineer" matches "engineer".
_CODING_ROLE_HINTS = (
    "engineer", "developer", "programmer", "sde", "swe", "architect",
    "data scientist", "machine learning", "backend", "frontend", "full stack",
    "fullstack", "android", "ios", "mobile",
)

# Titles that must never be treated as coding roles even if a hint matches.
_NON_CODING_ROLE_HINTS = (
    "sales engineer", "solutions engineer", "customer engineer",
    "engineering manager", "recruiter", "hr ", "human resources",
    "product manager", "program manager", "project manager",
    "technical writer", "support engineer",
)

# Programming languages and core CS topics. A skill only counts as evidence of
# programming ability if it is one of these -- "Excel", "Jira" and "Figma" are
# skills too.
_PROGRAMMING_SIGNALS = {
    "c", "c++", "cpp", "java", "python", "javascript", "typescript", "go",
    "golang", "rust", "kotlin", "swift", "scala", "ruby", "php", "c#", "csharp",
    "data structures", "algorithms", "dsa", "problem solving", "leetcode",
    "oops", "oop", "object oriented programming", "competitive programming",
}

_CODING_TOPIC_SIGNALS = (
    "data structure", "algorithm", "dsa", "array", "string", "hash",
    "tree", "graph", "recursion", "dynamic programming", "sorting",
    "searching", "complexity", "problem solving",
)

# The exercise is offered mid-interview, once the conversation has settled and
# while there is still time to write something. Both bounds matter: too early
# and it interrupts the warm-up, too late and the candidate is rushed.
MIN_QUESTIONS_BEFORE_CODING = 3
MIN_SECONDS_REMAINING_FOR_CODING = 480  # 8 minutes

# Stages where interrupting with a coding exercise would be wrong.
_BLOCKED_STAGES = {"recovery", "early_conclusion", "wrapup", "intro"}

SUPPORTED_LANGUAGES = ("C++", "Java")


def _normalise(values: Optional[Sequence[Any]]) -> List[str]:
    if not values:
        return []
    return [str(v).strip().lower() for v in values if str(v).strip()]


def _has_programming_signal(values: Sequence[str]) -> bool:
    for v in values:
        if v in _PROGRAMMING_SIGNALS:
            return True
        if any(topic in v for topic in _CODING_TOPIC_SIGNALS):
            return True
    return False


def role_expects_code(role_title: Optional[str], required_skills: Optional[Sequence[Any]]) -> bool:
    """Whether the role itself is a programming role."""
    title = (role_title or "").strip().lower()
    if any(block in title for block in _NON_CODING_ROLE_HINTS):
        return False
    if any(hint in title for hint in _CODING_ROLE_HINTS):
        return True
    return _has_programming_signal(_normalise(required_skills))


def is_coding_eligible(
    *,
    interview_type: Optional[str],
    role_title: Optional[str],
    required_skills: Optional[Sequence[Any]] = None,
    role_key_topics: Optional[Sequence[Any]] = None,
    candidate_skills: Optional[Sequence[Any]] = None,
    questions_asked_count: int = 0,
    time_remaining_seconds: int = 0,
    interview_stage: Optional[str] = None,
    already_asked: bool = False,
) -> Tuple[bool, str]:
    """Return (eligible, reason). The reason is for logs, never for the candidate.

    Three independent things must agree before a coding exercise is offered:
    the interview type allows it, the role is a programming role, and the
    candidate's own background shows programming ability. Any one of them alone
    is not enough -- that is the "one resume keyword" failure mode.
    """
    if already_asked:
        return False, "coding_already_asked"

    if (interview_type or "technical").strip().lower() not in _CODING_INTERVIEW_TYPES:
        return False, "interview_type_excludes_coding"

    if (interview_stage or "").strip().lower() in _BLOCKED_STAGES:
        return False, "stage_excludes_coding"

    if questions_asked_count < MIN_QUESTIONS_BEFORE_CODING:
        return False, "too_early_in_interview"

    if time_remaining_seconds < MIN_SECONDS_REMAINING_FOR_CODING:
        return False, "insufficient_time_remaining"

    if not role_expects_code(role_title, required_skills):
        return False, "role_does_not_require_coding"

    candidate_signal = _has_programming_signal(_normalise(candidate_skills))
    role_topic_signal = _has_programming_signal(_normalise(role_key_topics))
    if not (candidate_signal or role_topic_signal):
        return False, "no_programming_background_evidence"

    return True, "eligible"


def _match_candidate_language(candidate_skills: Optional[Sequence[Any]]) -> str:
    """Suggest a starting language from what the candidate actually lists."""
    skills = set(_normalise(candidate_skills))
    if skills & {"c++", "cpp", "c"}:
        return "C++"
    if skills & {"java", "kotlin"}:
        return "Java"
    return "C++"


def build_coding_question(
    *,
    topic: str,
    difficulty: str,
    company_name: Optional[str] = None,
    role_title: Optional[str] = None,
    candidate_skills: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """Build the coding exercise payload.

    Provenance is stated honestly. The platform holds no verified record of what
    any company actually asked, so the question is labelled as representative of
    the role rather than attributed to the company, which would be a claim it
    cannot support.
    """
    where = " and ".join(p for p in [company_name, role_title] if p) or "this role"
    prompt = _CODING_PROMPTS.get((difficulty or "medium").strip().lower(), _CODING_PROMPTS["medium"])

    question_text = (
        f"Interview-style coding question relevant to {where}.\n\n"
        f"{prompt['statement']}\n\n"
        "Write a complete, compilable solution in C++ or Java. Explain your approach "
        "in comments, and state the time and space complexity. You get one submission, "
        "so review it before you send it."
    )

    return {
        "topic": topic or prompt["topic"],
        "subtopic": prompt["topic"],
        "difficulty": difficulty or "medium",
        "question_type": "coding",
        "question_text": question_text,
        "expected_concepts": prompt["expected_concepts"],
        "follow_ups": [],
        "suggested_language": _match_candidate_language(candidate_skills),
    }


# A small fixed set, chosen so the exercise is solvable inside an interview and
# gradable from the code alone. These are standard textbook exercises, not
# anyone's proprietary interview material.
_CODING_PROMPTS: Dict[str, Dict[str, Any]] = {
    "easy": {
        "topic": "Arrays & Hashing",
        "statement": (
            "Given an array of integers and a target value, return the indices of the two "
            "numbers that add up to the target. Assume exactly one valid pair exists. "
            "Aim for better than the obvious quadratic solution."
        ),
        "expected_concepts": [
            "Hash map for constant-time lookup",
            "Single pass over the array",
            "O(n) time and O(n) space trade-off",
            "Handling of edge cases and input validation",
        ],
    },
    "medium": {
        "topic": "Strings & Sliding Window",
        "statement": (
            "Given a string, find the length of the longest substring that contains no "
            "repeated characters. Describe why your approach avoids re-scanning the string."
        ),
        "expected_concepts": [
            "Sliding window with two pointers",
            "Tracking last-seen index per character",
            "O(n) time complexity",
            "Correct window shrink condition",
        ],
    },
    "hard": {
        "topic": "Trees & Recursion",
        "statement": (
            "Given the root of a binary tree, return the length of its diameter -- the "
            "number of edges on the longest path between any two nodes. The path need not "
            "pass through the root. Explain how your recursion avoids recomputing subtree heights."
        ),
        "expected_concepts": [
            "Post-order traversal returning subtree height",
            "Combining left and right heights at each node",
            "Single-pass O(n) solution without repeated height computation",
            "Handling of empty and single-node trees",
        ],
    },
}
