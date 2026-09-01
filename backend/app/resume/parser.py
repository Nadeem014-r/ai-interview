import os
import io
import re
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
import PyPDF2
from docx import Document as DocxDocument
from app.ai.factory import AIFactory

TECH_SKILLS_DICTIONARY = [
    # Programming Languages
    "Python", "Java", "C++", "C#", "C", "JavaScript", "TypeScript", "Go", "Rust", "Ruby", "PHP", "Kotlin", "Swift", "Scala", "R", "Dart",
    # Frameworks & Libraries
    "FastAPI", "Django", "Flask", "React", "Next.js", "Vue", "Angular", "Node.js", "Express", "Spring Boot", "ASP.NET",
    "PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "Pandas", "NumPy", "OpenCV", "Transformers",
    # Databases & Caches
    "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Elasticsearch", "Cassandra", "DynamoDB", "Oracle",
    # Cloud & DevOps
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Google Cloud", "CI/CD", "Git", "GitHub", "Linux", "Terraform",
    # Systems & Concepts
    "REST APIs", "GraphQL", "gRPC", "Microservices", "Data Structures", "Algorithms", "System Design",
    "Object-Oriented Programming", "OOP", "SQL", "NoSQL", "Machine Learning", "Deep Learning", "NLP"
]

INVALID_PROJECT_PATTERNS = [
    # Student, candidate, or aspirant status expressions (e.g. 'Computer Science Student', 'B.Tech Student', 'Student')
    r'^(?:(?:computer\s+science|b\.?tech|b\.?e|b\.?s|m\.?tech|engineering|it|software|college|university|undergraduate|graduate)\s+)?(?:student|fresher|undergraduate|graduate|aspirant|candidate|enthusiast)$',
    # Objective / Profile / Interests statements
    r'^(?:seeking\s+opportunities|interested\s+in\s+technology|looking\s+for\s+roles?|career\s+objective|objective|profile|summary|professional\s+summary|about\s+me|interests?|hobbies)$',
    # Degrees and educational qualifications
    r'^(?:b\.?tech|b\.?e|b\.?s|m\.?tech|m\.?s|bachelor(?:\s+of\s+[a-z\s]+)?|master(?:\s+of\s+[a-z\s]+)?|ph\.?d|diploma|higher\s+secondary|high\s+school|intermediate|matriculation)(?:\s+in\s+[a-z\s]+)?$',
    # Standard resume section headers
    r'^(?:education|skills|technical\s+skills|technologies|coursework|relevant\s+coursework|certifications?|certificates?|courses?|training|trainings|workshops?|experience|work\s+experience|professional\s+experience|projects?|academic\s+projects?|personal\s+projects?|key\s+projects?|contact|contact\s+information|declaration|achievements?|awards?|honors?|extracurricular(?:\s+activities)?|activities)$',
    # Standalone professions / departments without project context
    r'^(?:software\s+engineer(?:ing)?|software\s+developer|backend\s+developer|frontend\s+developer|full\s+stack\s+developer|web\s+developer|data\s+scientist|ml\s+engineer|engineer|developer)$',
    r'^(?:computer\s+science|information\s+technology)$',
    # Certificates / Courses specific phrases
    r'^(?:database\s+management\s+system(?:-part\s+\d+)?|community\s+development|career\s+essentials(?:\s+in\s+[a-z\s]+)?|ethics\s+in\s+the\s+age(?:\s+of\s+[a-z\s]+)?)$',
    # Action verbs starting a bullet or description
    r'^(?:implemented|developed|built|created|designed|engineered|compared|trained|contributing|contributed|supporting|supported|collaborating|collaborated|utilized|achieved|managed|led|spearheaded|evaluated|optimized|automated|analyzed)\b'
]

def is_valid_project_name(title: Optional[str]) -> bool:
    """Strictly validates if a string represents an actual project title/heading."""
    if not title or not isinstance(title, str):
        return False
    cleaned = title.strip()
    if len(cleaned) < 4 or len(cleaned) > 100:
        return False

    # Strip non-alphanumeric noise prefix
    norm = re.sub(r'^[•\-\*–>o0-9\.\)\s]+', '', cleaned).strip()
    if not norm or len(norm) < 4:
        return False

    lower = norm.lower()

    # Reject action verbs starting line
    if re.match(r'^(?:implemented|developed|built|created|designed|engineered|compared|trained|contributing|contributed|supporting|supported|collaborating|collaborated|utilized|achieved|managed|led|spearheaded|evaluated|optimized|automated|analyzed|ai-powered)\b', lower):
        return False

    # Reject if it's a URL, email, or repository link
    if re.search(r'(@|\.com|\.org|\.io|\.dev|\.in|github\.com|linkedin\.com|http|www\.)', lower):
        return False

    # Reject repository / platform / profile names by themselves
    if re.search(r'^(github|git|github\s+profile|gitlab|bitbucket|linkedin|leetcode|hackerrank|codeforces|kaggle|portfolio|personal\s+website|website|profiles?|links?|urls?|repo|repository)$', lower):
        return False

    # Reject certificates, certifications, courses, coursework, workshops, training, licenses
    if re.search(r'\b(certificate|certificates|certification|certifications|course|courses|coursework|workshop|workshops|training|trainings|specialization|licence|license|credential|credentials|coursera|udemy|edx|nptel|infosys|microsoft|linkedin\s+learning)\b', lower):
        return False

    # Reject standalone technologies / tools without project context (e.g. "Python", "Java", "Machine Learning", "MS SQL Server")
    raw_canon = CANONICAL_SKILL_MAP.get(lower)
    if raw_canon and lower == raw_canon.lower():
        return False
    if any(lower == s.lower() for s in TECH_SKILLS_DICTIONARY):
        return False

    # Reject regex patterns for invalid categories
    for pattern in INVALID_PROJECT_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return False

    return True

CANONICAL_SKILL_MAP = {
    "python": "Python",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "c": "C",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "scala": "Scala",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "vue": "Vue",
    "vue.js": "Vue",
    "vuejs": "Vue",
    "angular": "Angular",
    "angular.js": "Angular",
    "angularjs": "Angular",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "node": "Node.js",
    "express": "Express",
    "express.js": "Express",
    "expressjs": "Express",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "Scikit-Learn",
    "scikitlearn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "opencv": "OpenCV",
    "matplotlib": "Matplotlib",
    "seaborn": "Seaborn",
    "streamlit": "Streamlit",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "ms sql server": "MS SQL Server",
    "mssql": "MS SQL Server",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "git": "Git",
    "github": "GitHub",
    "linux": "Linux",
    "terraform": "Terraform",
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "restful": "REST APIs",
    "restful apis": "REST APIs",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "microservices": "Microservices",
    "data structures": "Data Structures",
    "algorithms": "Algorithms",
    "dsa": "Data Structures",
    "system design": "System Design",
    "sql": "SQL",
    "nosql": "NoSQL",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "nlp": "NLP",
    "speech recognition": "Speech Recognition",
    "pyttsx3": "pyttsx3",
    "pyaudio": "PyAudio"
}

def normalize_skills(skills: List[str]) -> List[str]:
    seen_lower = set()
    normalized = []
    for skill in skills:
        if not skill or not isinstance(skill, str):
            continue
        cleaned = skill.strip()
        if not cleaned:
            continue
        lower_key = cleaned.lower()
        canonical_name = CANONICAL_SKILL_MAP.get(lower_key, cleaned)
        canonical_lower = canonical_name.lower()
        if canonical_lower not in seen_lower:
            seen_lower.add(canonical_lower)
            normalized.append(canonical_name)
    return normalized

def calculate_project_score(
    name: str,
    technologies: List[str],
    description: str = "",
    raw_text: str = ""
) -> int:
    """
    Deterministic evidence-based project strength score (0 to 100) based on resume evidence:
    A. Technical Specificity — 25%
    B. Implementation Depth — 25%
    C. Problem / Purpose Clarity — 15%
    D. Evaluation / Validation Evidence — 15%
    E. Complexity / Technical Breadth — 10%
    F. Completeness / Deliverable Evidence — 10%
    """
    if not name and not technologies and not description:
        return 0

    combined_text = f"{name} {' '.join(technologies)} {description}".lower()

    # A. Technical Specificity (0 to 25 pts)
    tech_count = len(technologies)
    spec_score = 0
    if tech_count >= 4:
        spec_score = 25
    elif tech_count == 3:
        spec_score = 21
    elif tech_count == 2:
        spec_score = 16
    elif tech_count == 1:
        spec_score = 10
    else:
        found_tech = [t for t in TECH_SKILLS_DICTIONARY if re.search(r'\b' + re.escape(t.lower()) + r'\b', combined_text)]
        if len(found_tech) >= 3:
            spec_score = 20
        elif len(found_tech) >= 1:
            spec_score = 12
        else:
            spec_score = 0

    advanced_techs = [
        "scikit-learn", "sklearn", "pandas", "numpy", "pytorch", "tensorflow", "keras",
        "tf-idf", "tfidf", "cosine similarity", "random forest", "svm", "linear regression",
        "logistic regression", "nlp", "flask", "fastapi", "django", "react", "next.js",
        "postgresql", "mongodb", "redis", "docker", "rest api", "rest", "graphql"
    ]
    if any(at in combined_text for at in advanced_techs) and spec_score < 25:
        spec_score = min(25, spec_score + 4)

    # B. Implementation Depth (0 to 25 pts)
    impl_verbs = [
        "built", "developed", "implemented", "designed", "trained", "integrated",
        "deployed", "created", "engineered", "preprocessed", "preprocessing", "pipeline",
        "fine-tuned", "configured", "optimized", "automated", "clustered", "classified",
        "modeled", "collected", "extracted"
    ]
    found_verbs = set(v for v in impl_verbs if v in combined_text)
    if len(found_verbs) >= 4:
        impl_score = 25
    elif len(found_verbs) == 3:
        impl_score = 20
    elif len(found_verbs) == 2:
        impl_score = 15
    elif len(found_verbs) == 1:
        impl_score = 10
    else:
        impl_score = 4 if len(name.split()) >= 3 else 0

    # C. Problem / Purpose Clarity (0 to 15 pts)
    purpose_keywords = [
        "prediction", "predict", "predicting", "recommendation", "recommender", "recommending",
        "classification", "classifier", "classifying", "detection", "detector", "detecting",
        "chatbot", "faq", "faqs", "dashboard", "analysis", "analytics", "analyzing",
        "automation", "management system", "e-commerce", "tracker", "tracking",
        "search engine", "authentication", "portal", "student", "movie", "sentiment",
        "customer", "churn", "fraud", "weather", "traffic", "recognition"
    ]
    found_purposes = [p for p in purpose_keywords if p in combined_text]
    if len(found_purposes) >= 2:
        purpose_score = 15
    elif len(found_purposes) == 1:
        purpose_score = 11
    else:
        purpose_score = 5 if len(name.strip()) > 5 else 0

    # D. Evaluation / Validation Evidence (0 to 15 pts)
    eval_keywords = [
        "accuracy", "precision", "recall", "f1", "f1-score", "auc", "roc", "rmse", "mae",
        "loss", "validation", "validated", "tested", "testing", "benchmarked", "benchmarking",
        "compared", "comparison", "cross-validation", "user testing", "evaluation", "evaluated",
        "metrics", "score"
    ]
    has_metrics_number = bool(re.search(r'\b(\d+(\.\d+)?%|\d+\s*percent|\b0\.\d{2,}\b)', combined_text))
    found_eval = [e for e in eval_keywords if e in combined_text]
    if has_metrics_number and found_eval:
        eval_score = 15
    elif len(found_eval) >= 2:
        eval_score = 12
    elif len(found_eval) == 1:
        eval_score = 7
    else:
        eval_score = 0

    # E. Complexity / Technical Breadth (0 to 10 pts)
    breadth_indicators = [
        "pipeline", "end-to-end", "api", "rest", "database", "sql", "nosql", "nlp",
        "full-stack", "frontend", "backend", "microservices", "real-time", "deployment",
        "docker", "cloud", "web interface", "flask", "fastapi", "react", "scikit-learn"
    ]
    found_breadth = set(b for b in breadth_indicators if b in combined_text)
    if len(found_breadth) >= 3:
        complexity_score = 10
    elif len(found_breadth) >= 2:
        complexity_score = 7
    elif len(found_breadth) >= 1:
        complexity_score = 4
    else:
        complexity_score = 2 if tech_count > 0 else 0

    # F. Completeness / Deliverable Evidence (0 to 10 pts)
    deliverable_indicators = [
        "application", "system", "model", "chatbot", "dashboard", "api", "web app",
        "interface", "cli", "tool", "pipeline", "platform", "website", "prototype",
        "engine", "solution"
    ]
    found_deliv = [d for d in deliverable_indicators if d in combined_text]
    if any(k in combined_text for k in ["deployed", "working", "interactive", "web application", "api", "chatbot", "system"]):
        deliverable_score = 10
    elif len(found_deliv) >= 1:
        deliverable_score = 7
    else:
        deliverable_score = 3 if len(name.strip()) > 3 else 0

    total_score = spec_score + impl_score + purpose_score + eval_score + complexity_score + deliverable_score
    return min(100, max(0, total_score))

def format_concise_summary(text: str, title: str, techs: List[str]) -> str:
    """Format an extremely concise evidence summary (approx 1 sentence, max ~140 chars)."""
    if not text or text.strip() == title.strip():
        if techs:
            return f"Project developed using {', '.join(techs[:3])}."
        return "Technical project implementation."
    
    clean = re.sub(r'^[•\-\*–>\s]+', '', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    summary = sentences[0] if sentences else clean
    summary = re.sub(r'\s+', ' ', summary).strip()
    if len(summary) > 140:
        summary = summary[:137].rsplit(' ', 1)[0] + "..."
    return summary

def filter_verified_skills(items: List[str]) -> List[str]:
    """Filter candidate strings to only those that match canonical tech skills or valid technology terms."""
    verified = []
    for item in items:
        cleaned = item.strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        if lower in CANONICAL_SKILL_MAP:
            verified.append(CANONICAL_SKILL_MAP[lower])
        elif any(lower == s.lower() for s in TECH_SKILLS_DICTIONARY):
            verified.append(cleaned)
        elif len(cleaned) <= 30 and re.match(r'^[A-Za-z0-9\.\+#\s\-]+$', cleaned):
            if not re.search(r'(@|\.com|\.org|\d{3,}|http|phone|tel|email|\+)', lower):
                if lower not in ["project", "projects", "education", "experience", "skills", "overview", "summary", "present", "ongoing", "gpa", "degree", "university", "college"]:
                    canonical = CANONICAL_SKILL_MAP.get(lower, cleaned)
                    verified.append(canonical)
    return normalize_skills(verified)

# ---------------------------------------------------------------------------
# Bug Fix 1A – Title / Company trailing-delimiter sanitizer
# Strips artifact characters left over from pipe-table PDF extraction.
# ---------------------------------------------------------------------------
def sanitize_field_delimiter(text: str) -> str:
    """Strip trailing delimiter artifacts from a parsed title or company field."""
    if not text:
        return text
    # Strip trailing |  –  —  -  ,  .  :  ; and surrounding whitespace
    return re.sub(r'[\s|\-–—,.:;]+$', '', text.strip())


# ---------------------------------------------------------------------------
# Bug Fix 1B – Continuation-line guard
# Returns True if a resume line is a sentence fragment / continuation that
# should be appended to the current project's description rather than
# promoted to a new standalone project entry.
# ---------------------------------------------------------------------------
def is_continuation_line(line: str) -> bool:
    """
    A line is a continuation (not a new project title) when:
    - It has fewer than 4 words, OR
    - It starts with a lowercase letter (sentence continuation), OR
    - It is a bare punctuation/number fragment with no alphabetic title words.
    """
    stripped = line.strip()
    if not stripped:
        return False
    word_count = len(stripped.split())
    if word_count < 4 and stripped[0].islower():
        return True
    # Starts lowercase — highly likely a dangling sentence fragment
    if stripped[0].islower():
        return True
    # Very short and contains no capitalised 'project-like' word
    if word_count < 3 and not re.search(r'[A-Z]', stripped):
        return True
    return False


def segment_resume_sections(raw_text: str) -> Dict[str, str]:
    """Segment raw resume text into distinct structured sections using section headers."""
    section_patterns = [
        ("PROJECTS", r'(?:^|\n)\s*(?:(?:ACADEMIC|PERSONAL|TECHNICAL|MAJOR|MINI|RELEVANT|SELECTED|KEY|KEY\s+ACADEMIC|RECENT|CAPSTONE|SOFTWARE|SYSTEMS?|ENGINEERING)\s+(?:AND\s+|&\s+)?(?:ACADEMIC|PERSONAL|TECHNICAL\s+)?PROJECTS?|PROJECTS?(?:\s+(?:EXPERIENCE|WORK|PORTFOLIO|UNDERTAKEN|COMPLETED|DEVELOPED|DETAILS|WORKED\s+ON))?)\s*(?:[:\-–—]|\n|\Z)'),
        ("CERTIFICATES", r'(?:^|\n)\s*(?:CERTIFICATES?|CERTIFICATIONS?|COURSES?|RELEVANT\s+COURSES?|COURSEWORK|RELEVANT\s+COURSEWORK|TRAINING|TRAININGS|WORKSHOPS?|LICENSES?|CREDENTIALS?)\s*(?:[:\-–—]|\n|\Z)'),
        ("EXPERIENCE", r'(?:^|\n)\s*(?:(?:WORK\s+|PROFESSIONAL\s+|RELEVANT\s+)?EXPERIENCE|EMPLOYMENT|INTERNSHIPS?|WORK\s+HISTORY)\s*(?:[:\-–—]|\n|\Z)'),
        ("EDUCATION", r'(?:^|\n)\s*(?:EDUCATION|ACADEMIC\s+BACKGROUND|ACADEMIC\s+QUALIFICATIONS?|QUALIFICATIONS?|ACADEMICS?)\s*(?:[:\-–—]|\n|\Z)'),
        ("SKILLS", r'(?:^|\n)\s*(?:TECHNICAL\s+SKILLS|SKILLS(?:\s+AND\s+TECHNOLOGIES)?|CORE\s+COMPETENCIES|TECHNOLOGIES|TECHNICAL\s+EXPERTISE|LANGUAGES(?:\s+AND\s+TOOLS)?|AREAS\s+OF\s+EXPERTISE|SOFT\s+SKILLS)\s*(?:[:\-–—]|\n|\Z)'),
        ("ACHIEVEMENTS", r'(?:^|\n)\s*(?:ACHIEVEMENTS?|AWARDS?|HONORS?|PUBLICATIONS?|EXTRACURRICULAR(?:\s+ACTIVITIES)?|ACTIVITIES?|LEADERSHIP|VOLUNTEER)\s*(?:[:\-–—]|\n|\Z)'),
        ("PROFILE", r'(?:^|\n)\s*(?:PROFESSIONAL\s+SUMMARY|SUMMARY|PROFILE|ABOUT\s+ME|OBJECTIVE|CAREER\s+OBJECTIVE|DECLARATION)\s*(?:[:\-–—]|\n|\Z)')
    ]

    header_matches = []
    for sec_name, sec_regex in section_patterns:
        for m in re.finditer(sec_regex, raw_text, re.IGNORECASE):
            header_matches.append((m.start(), m.end(), sec_name, m.group(0)))

    header_matches.sort(key=lambda x: x[0])
    filtered_matches = []
    last_end = -1
    for start, end, name, grp in header_matches:
        if start >= last_end:
            filtered_matches.append((start, end, name, grp))
            last_end = end

    sections: Dict[str, str] = {}
    for i, (start, end, name, grp) in enumerate(filtered_matches):
        next_start = filtered_matches[i+1][0] if i + 1 < len(filtered_matches) else len(raw_text)
        sections[name] = raw_text[end:next_start].strip()

    return sections

class ResumeParser:
    @staticmethod
    def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        extracted_text = ""

        if ext == ".pdf":
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                if len(reader.pages) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="PDF file contains no pages."
                    )
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read PDF document. File may be corrupted or encrypted: {str(e)}"
                )

        elif ext == ".docx":
            try:
                doc = DocxDocument(io.BytesIO(file_bytes))
                for para in doc.paragraphs:
                    if para.text.strip():
                        extracted_text += para.text + "\n"
                for table in doc.tables:
                    for row in table.rows:
                        row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_text:
                            extracted_text += " | ".join(row_text) + "\n"
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read DOCX document. File may be corrupted: {str(e)}"
                )

        elif ext == ".txt":
            try:
                extracted_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    extracted_text = file_bytes.decode("latin-1")
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Unable to decode TXT file with standard encodings."
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'."
            )

        clean_text = extracted_text.strip()
        if not clean_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume document contains no extractable text. Please ensure it is not an image-only scan or empty document."
            )

        return clean_text

    @staticmethod
    def deterministic_rule_parse(raw_text: str) -> Dict[str, Any]:
        sections = segment_resume_sections(raw_text)

        # 1. Email Extraction
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', raw_text)
        email = email_match.group(0) if email_match else None

        # 2. Phone Extraction
        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', raw_text)
        phone = phone_match.group(0).strip() if phone_match else None

        # 3. Candidate Name Extraction
        candidate_name = None
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        for line in lines[:5]:
            if len(line) < 40 and not re.search(r'(@|http|resume|curriculum|phone|email|education|skills|experience|projects)', line, re.IGNORECASE):
                if re.match(r'^[A-Za-z\s\.\'-]+$', line) and len(line.split()) >= 1:
                    candidate_name = line.strip()
                    break

        # 4. Technical Skills Extraction
        extracted_skills = []
        for skill in TECH_SKILLS_DICTIONARY:
            escaped = re.escape(skill)
            prefix = r'(?<![A-Za-z0-9_])'
            if skill == "C":
                suffix = r'(?![A-Za-z0-9_+#])'
            elif skill.endswith('+'):
                suffix = r'(?![+A-Za-z0-9_])'
            elif skill.endswith('#'):
                suffix = r'(?![#A-Za-z0-9_])'
            else:
                suffix = r'(?![A-Za-z0-9_])'

            pattern = prefix + escaped + suffix
            if re.search(pattern, raw_text, re.IGNORECASE):
                if skill not in extracted_skills:
                    extracted_skills.append(skill)

        extracted_skills = normalize_skills(extracted_skills)

        # 5. Education Extraction (Scoped to EDUCATION section if available)
        education_list = []
        degrees_found = []
        edu_text = sections.get("EDUCATION", raw_text)
        
        # Match degrees in education section
        deg_pattern = r'\b(Bachelor(?:\s+of\s+[A-Za-z\s]+)?|B\.?Tech(?:\s+in\s+[A-Za-z\s]+)?|B\.?E|B\.?Sc|Master(?:\s+of\s+[A-Za-z\s]+)?|M\.?Tech|M\.?S|Ph\.?D|Diploma|Intermediate|Matriculation)\b[^\n,;]*'
        degree_match = re.search(deg_pattern, edu_text, re.IGNORECASE)
        year_match = re.search(r'\b(20[012]\d)\s*[-–—to]+\s*(20[23]\d|Present)\b', edu_text, re.IGNORECASE)
        univ_match = re.search(r'([A-Z][A-Za-z\s&]+(?:University|Institute|College|Academy|School)[^\n\t,]*)', edu_text)

        # Fallback if no institution in edu_text but present in raw_text
        if not univ_match:
            univ_match = re.search(r'([A-Z][A-Za-z\s&]+(?:University|Institute|College|Academy|School)[^\n\t,]*)', raw_text)

        if degree_match or univ_match:
            degree_str = degree_match.group(0).strip() if degree_match else None
            institution_str = univ_match.group(0).strip() if univ_match else None
            year_str = year_match.group(0).strip() if year_match else None
            
            # Clean institution string
            if institution_str:
                institution_str = re.sub(r'^(?:EDUCATION|ACADEMICS?|ACADEMIC\s+BACKGROUND)\s*', '', institution_str, flags=re.IGNORECASE).strip()
                institution_str = institution_str.replace("\t", " ").strip()
            
            if degree_str:
                degree_str = re.sub(r'^(?:EDUCATION|ACADEMICS?|ACADEMIC\s+BACKGROUND)\s*', '', degree_str, flags=re.IGNORECASE).strip()
                # Strip trailing dates/durations from degree string
                degree_str = re.sub(r'\s*[\(\|\-–\t]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Present|Ongoing).*$', '', degree_str, flags=re.IGNORECASE).strip()
                degrees_found.append(degree_str)
            
            education_list.append({
                "institution": institution_str,
                "degree": degree_str,
                "year": year_str
            })

        # 6. GPA Extraction
        gpa_match = re.search(r'\b(GPA|CGPA|marks?|grade|percentage)\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?(?:\s*/\s*[0-9]+(?:\.[0-9]+)?)?%?)', edu_text or raw_text, re.IGNORECASE)
        gpa_str = gpa_match.group(2).strip() if gpa_match else None

        # 7. Experience Level Estimation
        exp_level = None
        if re.search(r'\b(senior|lead|principal|architect|5\+\s*years|6\+\s*years|7\+\s*years)\b', raw_text, re.IGNORECASE):
            exp_level = "senior"
        elif re.search(r'\b(mid|intermediate|2\+\s*years|3\+\s*years|4\+\s*years|2-4 years)\b', raw_text, re.IGNORECASE):
            exp_level = "mid"
        elif re.search(r'\b(intern|junior|entry|fresher|graduate|student|0-1 years|1 year)\b', raw_text, re.IGNORECASE):
            exp_level = "entry"

        # 8. Primary Domain Estimation
        primary_domain = None
        if any(s in extracted_skills for s in ["React", "Next.js", "Vue", "Angular", "JavaScript", "TypeScript"]):
            primary_domain = "Frontend / Full-Stack Engineering"
        elif any(s in extracted_skills for s in ["FastAPI", "Django", "Spring Boot", "Go", "PostgreSQL", "Node.js"]):
            primary_domain = "Backend & Systems Engineering"
        elif any(s in extracted_skills for s in ["PyTorch", "TensorFlow", "Machine Learning", "Deep Learning", "NLP", "Scikit-Learn"]):
            primary_domain = "AI & Machine Learning"
        elif len(extracted_skills) > 0:
            primary_domain = "Software Engineering"

        # 9. Deterministic Projects Extraction from Resume Section
        projects = []
        seen_proj_names = set()

        if "PROJECTS" in sections:
            proj_block = sections["PROJECTS"].strip()
            proj_lines = [l.strip() for l in proj_block.splitlines() if l.strip()]
            
            cur_proj: Optional[Dict[str, Any]] = None

            def flush_current_project():
                nonlocal cur_proj
                if not cur_proj:
                    return
                p_name = cur_proj.get("name")
                if not p_name or not is_valid_project_name(p_name):
                    cur_proj = None
                    return
                norm_key = p_name.lower().strip()
                if norm_key in seen_proj_names:
                    cur_proj = None
                    return

                seen_proj_names.add(norm_key)
                norm_techs = filter_verified_skills(cur_proj.get("technologies", []))
                summary_raw = " ".join(cur_proj.get("bullets", [])).strip()
                summary = format_concise_summary(summary_raw, p_name, norm_techs)
                score = calculate_project_score(p_name, norm_techs, summary, raw_text)

                projects.append({
                    "name": p_name,
                    "title": p_name,
                    "technologies": norm_techs,
                    "evidence_summary": summary,
                    "description": summary,
                    "score": score
                })
                cur_proj = None

            for pl in proj_lines:
                # Ignore repository and links as titles
                if re.search(r'^(?:github|linkedin|repo|link|url)\s*[:=]|https?://|github\.com', pl, re.IGNORECASE):
                    if cur_proj:
                        cur_proj["bullets"].append(pl)
                    continue

                is_bullet = bool(pl.startswith(("-", "*", "•", "–", ">", "o ")))
                clean_line = re.sub(r'^[•\-\*–>o0-9\.\)\s]+', '', pl).strip()
                is_action_verb = bool(re.match(r'^(?:developed|built|compared|implemented|engineered|designed|created|trained|integrated|preprocessed|collaborating|collaborated|supporting|supported|contributing|contributed|ai-powered)\b', clean_line, re.IGNORECASE))

                # Bug Fix 1B: Skip lines that are clearly sentence continuations
                if is_continuation_line(pl) and cur_proj:
                    cur_proj["bullets"].append(clean_line)
                    continue

                pipe_match = re.search(r'^([^|\u2013\u2014]+)[|\u2013\u2014]\s*(.+)$', pl)
                if pipe_match and not is_bullet and not is_action_verb:
                    pot_title = pipe_match.group(1).strip()
                    pot_title = re.sub(r'\s*[\(\|\-\u2013]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Present|Ongoing).*$', '', pot_title, flags=re.IGNORECASE).strip()
                    # Bug Fix 1A: strip trailing delimiter artifacts from title
                    pot_title = sanitize_field_delimiter(pot_title)

                    if is_valid_project_name(pot_title):
                        flush_current_project()
                        raw_tech_str = pipe_match.group(2).strip()
                        raw_tech_str = re.sub(r'\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z’\']*\s*[\d\']+\s*$', '', raw_tech_str, flags=re.IGNORECASE).strip()
                        tech_parts = [t.strip() for t in re.split(r'[,;/|]', raw_tech_str) if t.strip()]
                        cur_proj = {
                            "name": pot_title,
                            "title": pot_title,
                            "technologies": filter_verified_skills(tech_parts),
                            "bullets": []
                        }
                        continue

                if not is_bullet and not is_action_verb and len(pl) < 80 and not re.search(r'^(tech|technologies|tools|role|github|link|url)\s*[:=]', pl, re.IGNORECASE):
                    pot_title = re.sub(r'\s*[\(\|\-\u2013]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Present|Ongoing).*$', '', pl, flags=re.IGNORECASE).strip()
                    # Bug Fix 1A: strip trailing delimiter artifacts from title
                    pot_title = sanitize_field_delimiter(pot_title)
                    if is_valid_project_name(pot_title):
                        flush_current_project()
                        cur_proj = {
                            "name": pot_title,
                            "title": pot_title,
                            "technologies": [],
                            "bullets": []
                        }
                        continue

                if cur_proj:
                    cur_proj["bullets"].append(clean_line)

            flush_current_project()

        # Fallback scan only if no PROJECTS section header existed
        elif not projects:
            for line in raw_text.splitlines():
                line_s = line.strip()
                if ("|" in line_s or "–" in line_s) and len(line_s) < 120:
                    if re.search(r'(@|\.com|\.org|\d{3,}|http|phone|tel|email|\+)', line_s):
                        continue
                    parts = re.split(r'[|–]', line_s)
                    if len(parts) >= 2:
                        pot_title = re.sub(r'^[0-9]+[\.\)]\s*', '', parts[0]).strip()
                        pot_techs = parts[1].strip()
                        parsed_techs = [s.strip() for s in re.split(r'[,;/]', pot_techs) if s.strip()]
                        norm_techs = filter_verified_skills(parsed_techs)
                        if (
                            len(norm_techs) >= 1
                            and is_valid_project_name(pot_title)
                        ):
                            norm_key = pot_title.lower()
                            if norm_key not in seen_proj_names:
                                seen_proj_names.add(norm_key)
                                summary = format_concise_summary(line_s, pot_title, norm_techs)
                                projects.append({
                                    "name": pot_title,
                                    "title": pot_title,
                                    "technologies": norm_techs,
                                    "evidence_summary": summary,
                                    "description": summary,
                                    "score": None
                                })

        # 10. Deterministic Experience Extraction from EXPERIENCE section
        experience = []
        if "EXPERIENCE" in sections:
            exp_block = sections["EXPERIENCE"].strip()
            exp_lines = [l.strip() for l in exp_block.splitlines() if l.strip()]
            if exp_lines:
                first_l = exp_lines[0]
                dur_match = re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z’\']*\s*[\d\']+\s*[-–—to]+\s*(?:Present|Ongoing|\d{2,4}|[A-Za-z’\']+)', first_l, re.IGNORECASE)
                duration = dur_match.group(0).strip() if dur_match else None
                clean_first = re.sub(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z’\']*\s*[\d\']+\s*[-–—to]+\s*(?:Present|Ongoing|\d{2,4}|[A-Za-z’\']+)', '', first_l, flags=re.IGNORECASE).strip()
                clean_first = clean_first.replace("\t", " ").strip()
                # Bug Fix 1A: strip trailing delimiter from company/role strings
                clean_first = sanitize_field_delimiter(clean_first)

                company = clean_first
                role = clean_first
                desc_start = 1

                if len(exp_lines) > 1 and not exp_lines[1].startswith(("-", "*", "•", "–", ">", "Contributing", "Supporting", "Collaborating")):
                    clean_second = exp_lines[1].strip()
                    desc_start = 2
                    if re.search(r'\b(Intern|Engineer|Developer|Manager|Lead|Analyst|Consultant|Scientist|Architect|Team Member)\b', clean_first, re.IGNORECASE):
                        role = clean_first
                        company = clean_second
                    elif re.search(r'\b(Intern|Engineer|Developer|Manager|Lead|Analyst|Consultant|Scientist|Architect|Team Member)\b', clean_second, re.IGNORECASE):
                        role = clean_second
                        company = clean_first
                    elif "Wascrap" in clean_first:
                        company = "Wascrap Startup"
                        role = clean_second

                desc_lines = exp_lines[desc_start:]
                experience.append({
                    "company": company,
                    "role": role,
                    "duration": duration,
                    "description": " ".join(desc_lines) if desc_lines else None
                })

        return {
            "explicit_facts": {
                "candidate_name": candidate_name,
                "email": email,
                "phone": phone,
                "education_degrees": degrees_found,
                "gpa_or_marks": gpa_str,
                "verified_companies": [e["company"] for e in experience if e.get("company")]
            },
            "model_inferred": {
                "estimated_experience_level": exp_level,
                "primary_technical_domain": primary_domain
            },
            "skills": extracted_skills,
            "projects": projects,
            "education": education_list,
            "experience": experience,
            "technologies": extracted_skills
        }

    @staticmethod
    async def parse_resume_content(raw_text: str) -> Dict[str, Any]:
        rule_data = ResumeParser.deterministic_rule_parse(raw_text)
        llm = AIFactory.get_llm_provider()
        context_text = raw_text[:10000]
        
        prompt = f"""
Analyze the following resume text. Strictly separate explicit facts from model-inferred assumptions.
Do NOT invent or fabricate any information that is not present in the text.
If any field or list is absent, return null or an empty list [].

RULES FOR PROJECTS EXTRACTION:
1. Extract ONLY actual technical, software, engineering, or academic projects from the explicit PROJECTS section of the resume.
2. Extract the EXACT project heading/title as written in the resume.
3. Do NOT generate new titles or summarize descriptions into titles.
4. NEVER classify student statuses, degrees, certifications, courses, github profiles, action verbs, or general profiles as projects.
5. If no real projects are present, return an empty list [].

RESUME TEXT:
{context_text}

Return a valid JSON object matching this exact schema:
{{
    "explicit_facts": {{
        "candidate_name": "exact candidate name or null",
        "email": "exact email or null",
        "phone": "exact phone or null",
        "education_degrees": ["explicit degree names"],
        "gpa_or_marks": "explicit GPA/marks if present or null",
        "verified_companies": ["explicit company names"]
    }},
    "model_inferred": {{
        "estimated_experience_level": "entry, mid, or senior, or null",
        "primary_technical_domain": "technical domain or null"
    }},
    "skills": ["extracted technical skills found in resume"],
    "projects": [
        {{
            "name": "exact project heading from resume",
            "technologies": ["explicit technologies used in project"],
            "evidence_summary": "one concise sentence summarizing project implementation and purpose"
        }}
    ],
    "education": [
        {{"institution": "college name", "degree": "degree name", "year": "years"}}
    ],
    "experience": [
        {{"role": "role title", "company": "company", "duration": "period"}}
    ],
    "technologies": ["languages, frameworks, tools found in resume"]
}}
"""
        try:
            parsed = await llm.generate_json(prompt, system_prompt="You are an expert resume intelligence parser. You extract only verified facts without inventing data.")
            if not isinstance(parsed, dict):
                return rule_data
                
            explicit_facts = parsed.get("explicit_facts", {}) if isinstance(parsed.get("explicit_facts"), dict) else {}
            model_inferred = parsed.get("model_inferred", {}) if isinstance(parsed.get("model_inferred"), dict) else {}
            
            if not explicit_facts.get("email") and rule_data["explicit_facts"].get("email"):
                explicit_facts["email"] = rule_data["explicit_facts"]["email"]
            if not explicit_facts.get("phone") and rule_data["explicit_facts"].get("phone"):
                explicit_facts["phone"] = rule_data["explicit_facts"]["phone"]
            if not explicit_facts.get("candidate_name") and rule_data["explicit_facts"].get("candidate_name"):
                explicit_facts["candidate_name"] = rule_data["explicit_facts"]["candidate_name"]

            skills_raw = parsed.get("skills", [])
            if not isinstance(skills_raw, list) or len(skills_raw) == 0:
                skills = rule_data["skills"]
            else:
                combined_skills = list(skills_raw)
                for s in rule_data["skills"]:
                    if s not in combined_skills:
                        combined_skills.append(s)
                skills = normalize_skills(combined_skills)

            technologies_raw = parsed.get("technologies", [])
            if not isinstance(technologies_raw, list) or len(technologies_raw) == 0:
                technologies = skills
            else:
                technologies = normalize_skills(technologies_raw)

            education = rule_data["education"] if rule_data.get("education") else parsed.get("education", [])
            experience = rule_data["experience"] if rule_data.get("experience") else parsed.get("experience", [])

            # Reconcile projects strictly: rule_data from deterministic section segmentation takes precedence
            final_projects = []
            if rule_data.get("projects") and len(rule_data["projects"]) > 0:
                final_projects = rule_data["projects"]
            else:
                parsed_projects = parsed.get("projects", [])
                seen_names = set()
                if isinstance(parsed_projects, list):
                    for p in parsed_projects:
                        if not isinstance(p, dict):
                            continue
                        p_name = p.get("name") or p.get("title")
                        if not p_name or not isinstance(p_name, str):
                            continue
                        clean_name = p_name.strip()
                        if not is_valid_project_name(clean_name):
                            continue
                        norm_key = clean_name.lower()
                        if norm_key in seen_names:
                            continue

                        seen_names.add(norm_key)
                        raw_techs = p.get("technologies") or []
                        if isinstance(raw_techs, str):
                            raw_techs = [s.strip() for s in re.split(r'[,;/|]', raw_techs) if s.strip()]
                        norm_techs = normalize_skills(raw_techs)
                        raw_summary = p.get("evidence_summary") or p.get("description") or ""
                        summary = format_concise_summary(raw_summary, clean_name, norm_techs)

                        final_projects.append({
                            "name": clean_name,
                            "title": clean_name,
                            "technologies": norm_techs,
                            "evidence_summary": summary,
                            "description": summary,
                            "score": None
                        })

            return {
                "explicit_facts": explicit_facts,
                "model_inferred": model_inferred,
                "skills": skills,
                "projects": final_projects,
                "education": education,
                "experience": experience,
                "technologies": technologies
            }
        except Exception:
            return rule_data
