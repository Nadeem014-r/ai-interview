"""Phase 9/10: Response Quality Gate & Non-Responsive Input Validation.

Distinguishes between valid candidate responses and empty, evasive, gibberish,
or off-topic inputs to enforce evidence-grounded scoring without false praise.
"""

import re
from typing import List, Tuple, Optional, Dict, Any


COMMON_VOWELS = set("aeiouy")

KEYBOARD_MASH_SEQUENCES = [
    "asdf", "sdfg", "dfgh", "fghj", "ghjk", "hjkl", "lkjh", "kjhg", "jhgf", "hgfd", "gfds", "fdsa",
    "qwer", "wert", "erty", "rtyu", "tyui", "yuio", "uiop", "poiu", "oiuy", "iuyt", "uytr", "ytre", "trew", "rewq",
    "zxcv", "xcvb", "cvbn", "vbnm", "mnbv", "nbvc", "bvcx", "vcxz",
    "1234", "2345", "3456", "4567", "5678", "6789", "0987", "9876", "8765"
]

EXPLICIT_UNKNOWN_KEYWORDS = [
    "don't know", "dont know", "no idea", "not sure", "pass", "skip",
    "i do not know", "i have no idea", "no clue", "can't remember", "cant remember",
    "never studied", "never heard of", "not familiar", "have no clue", "unsure",
    "i dont understand", "i do not understand", "no answer"
]

EXPLICIT_OFF_TOPIC_PATTERNS = [
    "paris", "capital of france", "capital of", "weather is", "recipe",
    "banana", "apple pie", "pizza", "eiffel tower", "random text", "unrelated topic",
    "how to cook", "football match", "cricket score", "movie review"
]

DOMAIN_KEYWORDS = {
    # General CS & Engineering
    "system", "systems", "data", "code", "coding", "algorithm", "algorithms",
    "design", "security", "database", "databases", "api", "apis", "network",
    "cache", "caching", "server", "servers", "memory", "function", "functions",
    "class", "classes", "table", "tables", "index", "indexes", "indexing",
    "btree", "b+ tree", "lock", "locks", "cpu", "disk", "thread", "threads",
    "concurrency", "distributed", "query", "queries", "latency", "throughput",
    "storage", "tree", "trees", "graph", "graphs", "array", "arrays", "list",
    "linked list", "hash", "hash table", "hash map", "lookup", "complexity",
    "o(1)", "o(n)", "o(log n)", "react", "fastapi", "python", "java", "node",
    "jwt", "token", "auth", "authentication", "authorization", "rest", "http",
    # HR / Behavioral / Professional
    "graduate", "student", "built", "build", "project", "projects", "university",
    "college", "experience", "learning", "learn", "interested", "interest",
    "engineer", "engineering", "software", "developer", "development", "team",
    "teamwork", "work", "worked", "application", "applications", "degree",
    "career", "strength", "weakness", "leadership", "initiative", "problem",
    "solution", "contributed", "implemented", "implementing", "role", "company"
}


def is_empty_response(text: Optional[str]) -> bool:
    """Check if input is None, empty, or whitespace only."""
    if text is None:
        return True
    return len(text.strip()) == 0


# "pass" and "skip" are refusals only when they are the whole answer. Matched as
# substrings they hit ordinary technical vocabulary -- "passwords", "passed by
# reference", "bypass", "passes through", "skip list" -- and because
# EXPLICIT_UNKNOWN short-circuits evaluate_answer() before the LLM is ever
# called, a correct answer was returned as a hard 0.0. The engine applies the
# same whole-answer rule to these two tokens in its own refusal check.
STANDALONE_UNKNOWN_TOKENS = {"pass", "skip"}

EXPLICIT_UNKNOWN_PHRASES = [
    kw for kw in EXPLICIT_UNKNOWN_KEYWORDS if kw not in STANDALONE_UNKNOWN_TOKENS
]


def _phrase_normalized(text: str) -> str:
    """Lowercase the text, flatten punctuation to spaces and pad both ends.

    Padding plus flattening gives whole-word/phrase matching without a regex:
    " pass " cannot match inside " passwords ", while " don't know " still
    matches "I don't know." Apostrophes are kept so contractions survive.
    """
    return " " + "".join(c if (c.isalnum() or c == "'") else " " for c in text.lower()) + " "


def is_explicit_unknown(text: Optional[str]) -> bool:
    """Check if candidate explicitly stated they don't know the answer."""
    if is_empty_response(text):
        return True
    normalized = _phrase_normalized(text)
    tokens = normalized.split()
    if tokens and all(t in STANDALONE_UNKNOWN_TOKENS for t in tokens):
        return True
    return any(f" {kw} " in normalized for kw in EXPLICIT_UNKNOWN_PHRASES)


KNOWN_TECH_ACRONYMS = {
    "http", "https", "grpc", "html", "smtp", "snmp", "rtsp", "sync", "async",
    "mysql", "postgresql", "regex", "crud", "uuid", "jwt", "rdbms", "cors", "csrf",
    "xpath", "json", "yaml", "xml", "wsdl", "ddos", "dhcp", "dns", "icmp", "ipsec",
    "nvme", "pcie", "scsi", "sata", "raid", "rbac", "abac", "tls", "ssl", "tcp", "udp",
    "ssh", "ftp", "sql", "wasm", "xss", "ssrf", "sqli", "orm", "sdk", "cli", "gui",
    "url", "uri", "rest", "soap", "api", "cpu", "gpu", "tpu", "ram", "rom", "io", "i/o"
}


def is_gibberish_or_nonlanguage(text: Optional[str]) -> bool:
    """
    Detects random keystrokes, non-language text, repetitive filler, or keyboard mashing.
    Examples: 'shdfghj', 'asdfgh', 'qwerty', 'blah blah', 'zzzz', '12345', 'sdfghjkl'.
    """
    if is_empty_response(text):
        return True

    clean = text.strip().lower()
    tokens = re.findall(r'\b[a-z0-9_]+\b', clean)
    if not tokens:
        # Punctuation/symbols only (e.g. '???', '...', '!!!@#$')
        return True

    # 1. Repetitive filler check (e.g., 'blah blah blah', 'na na na na', 'test test test')
    if len(tokens) >= 2 and all(t == tokens[0] for t in tokens):
        return True
    if any(filler in clean for filler in ["blah blah", "nanana", "asdfasdf", "qwertyuiop", "lalala"]):
        return True

    # 2. Check for keyboard mash sequence matches in short answers
    for seq in KEYBOARD_MASH_SEQUENCES:
        if seq in clean:
            # If the entire token is or contains the mash sequence and is not a valid english word
            for t in tokens:
                if seq in t and len(t) <= 10 and t not in DOMAIN_KEYWORDS and t not in KNOWN_TECH_ACRONYMS:
                    return True

    # 3. Check token character structure (vowel presence, consonant clustering)
    alpha_tokens = [t for t in tokens if t.isalpha()]
    if not alpha_tokens and all(t.isdigit() for t in tokens):
        # Pure random numbers where words are expected
        return True

    # Single-word / short input check for non-language words
    if len(alpha_tokens) <= 2:
        for t in alpha_tokens:
            if t in KNOWN_TECH_ACRONYMS or t in DOMAIN_KEYWORDS:
                continue
            t_len = len(t)
            vowel_count = sum(1 for ch in t if ch in COMMON_VOWELS)

            # Single word of length >= 4 with 0 vowels (e.g., 'shdfghj', 'dfgh', 'zxcv', 'qwrty')
            if t_len >= 4 and vowel_count == 0:
                return True

            # Extremely low vowel ratio in longer tokens (e.g., 1 vowel in 7+ consonants without being a domain word)
            if t_len >= 6 and (vowel_count / t_len) < 0.18:
                return True

            # High single-character repetition (e.g., 'aaaaaa', 'sdddd')
            if any(t.count(ch) / t_len >= 0.6 for ch in set(t)) and t_len >= 4:
                return True

    # Multi-token sentence check: check proportion of gibberish tokens
    if len(alpha_tokens) > 2:
        gibberish_count = 0
        for t in alpha_tokens:
            if t in KNOWN_TECH_ACRONYMS or t in DOMAIN_KEYWORDS:
                continue
            t_len = len(t)
            vowel_count = sum(1 for ch in t if ch in COMMON_VOWELS)
            if t_len >= 5 and vowel_count == 0:
                gibberish_count += 1
            elif t_len >= 7 and (vowel_count / t_len) < 0.15:
                gibberish_count += 1
        if gibberish_count / len(alpha_tokens) >= 0.5:
            return True

    return False


def is_off_topic_response(
    text: Optional[str],
    topic: str,
    expected_concepts: Optional[List[str]] = None,
    question_text: str = ""
) -> bool:
    """
    Detects if the candidate's answer is completely irrelevant to the interview question/topic.
    """
    if is_empty_response(text):
        return False  # Handled as empty/unknown, not off-topic

    clean = text.strip().lower()
    tokens = re.findall(r'\b[a-z0-9_]+\b', clean)
    if len(tokens) == 0:
        return False

    # 1. Explicit off-topic markers
    if any(pat in clean for pat in EXPLICIT_OFF_TOPIC_PATTERNS):
        return True

    # 2. Check overlap with expected concepts
    matched_concepts = False
    if expected_concepts:
        for c in expected_concepts:
            c_words = [w.lower() for w in re.findall(r'\b\w{3,}\b', c) if len(w) > 3]
            if any(cw in clean for cw in c_words):
                matched_concepts = True
                break

    if matched_concepts:
        return False

    # 3. Check overlap with topic words or question words
    topic_words = [w.lower() for w in re.findall(r'\b\w{3,}\b', topic) if len(w) > 3]
    if any(tw in clean for tw in topic_words):
        return False

    q_words = [
        w.lower() for w in re.findall(r'\b\w{3,}\b', question_text)
        if len(w) > 3 and w.lower() not in [
            "explain", "what", "how", "why", "tell", "does", "with", "from",
            "when", "into", "called", "about", "your", "this", "that"
        ]
    ]
    if any(qw in clean for qw in q_words):
        return False

    # 4. Check overlap with general domain vocabulary
    has_domain_word = any(dw in clean for dw in DOMAIN_KEYWORDS)
    if has_domain_word:
        return False

    # If answer has > 3 words and has 0 topic, 0 concept, 0 question, and 0 domain overlap
    if len(tokens) >= 3:
        return True

    return False


MINIMAL_NON_SUBSTANTIVE_TOKENS = {
    "yes", "no", "ok", "okay", "nope", "yeah", "yep", "sure", "na", "n/a", "none", "fine", "cool", "maybe", "idk"
}


def is_minimal_or_non_substantive_response(text: Optional[str]) -> bool:
    """
    Detects 1-2 word non-explanatory answers like 'yes', 'no', 'ok', 'nope', 'yeah'
    which contain insufficient substance to demonstrate knowledge or communication competence.
    """
    if is_empty_response(text):
        return False
    clean = text.strip().lower()
    tokens = re.findall(r'\b[a-z0-9_]+\b', clean)
    if len(tokens) == 1 and tokens[0] in MINIMAL_NON_SUBSTANTIVE_TOKENS:
        return True
    if len(tokens) == 2 and all(t in MINIMAL_NON_SUBSTANTIVE_TOKENS for t in tokens):
        return True
    return False


def classify_response_quality_state(
    safe_answer: str,
    topic: str,
    expected_concepts: Optional[List[str]] = None,
    question_type: str = "technical",
    question_text: str = ""
) -> str:
    """
    Classifies candidate answer into distinct response quality states:
    - EMPTY
    - EXPLICIT_UNKNOWN
    - GIBBERISH
    - MINIMAL_NON_SUBSTANTIVE
    - OFF_TOPIC
    - EVASIVE
    - VALID_CANDIDATE_ANSWER
    """
    if is_empty_response(safe_answer):
        return "EMPTY"
    if is_explicit_unknown(safe_answer):
        return "EXPLICIT_UNKNOWN"
    if is_gibberish_or_nonlanguage(safe_answer):
        return "GIBBERISH"
    if is_minimal_or_non_substantive_response(safe_answer):
        return "MINIMAL_NON_SUBSTANTIVE"
    if is_off_topic_response(safe_answer, topic, expected_concepts, question_text):
        return "OFF_TOPIC"
    return "VALID_CANDIDATE_ANSWER"
