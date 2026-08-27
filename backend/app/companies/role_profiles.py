"""Phase 9: Strongly Typed Job Role Profiles.

Defines role-specific competency focus, key technologies, trade-off areas,
and failure/scalability requirements across standard engineering families.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class RoleProfile:
    """Strongly typed job role profile."""
    role_family: str
    display_name: str
    core_competencies: List[str]
    key_technologies: List[str]
    architecture_focus: str
    tradeoff_areas: List[str]
    security_focus: List[str]
    scalability_focus: List[str]
    difficulty_baseline: float = 8.0


ROLE_PROFILES: Dict[str, RoleProfile] = {
    "backend": RoleProfile(
        role_family="backend",
        display_name="Backend Engineer",
        core_competencies=["API Design", "Database Transactions", "Distributed Caching", "Concurrency", "System Scalability"],
        key_technologies=["FastAPI", "PostgreSQL", "Redis", "SQLAlchemy", "Docker", "Kafka", "REST APIs", "gRPC"],
        architecture_focus="Microservices, async event loops, transaction boundaries, and cache-aside layers",
        tradeoff_areas=["ACID vs BASE", "Read latency vs Cache invalidation", "Normalized vs Denormalized schema"],
        security_focus=["JWT signature validation", "SQL injection prevention", "Rate limiting", "RBAC authorization"],
        scalability_focus=["Connection pool exhaustion", "Database read replicas", "Cache stampede prevention", "Horizontal scaling"],
        difficulty_baseline=8.5
    ),
    "frontend": RoleProfile(
        role_family="frontend",
        display_name="Frontend Engineer",
        core_competencies=["React / UI Architecture", "Browser Rendering & DOM", "State Management", "Web Performance & Core Web Vitals", "Client Security"],
        key_technologies=["React", "TypeScript", "Next.js", "JavaScript", "HTML/CSS", "Redux/Zustand", "WebSockets"],
        architecture_focus="Component hierarchy, state normalization, client routing, and design system integration",
        tradeoff_areas=["Client-side rendering vs SSR vs SSG", "Local state vs Global store", "Bundle size vs Feature richness"],
        security_focus=["Cross-Site Scripting (XSS)", "CSRF protection", "Secure cookie storage", "Content Security Policy (CSP)"],
        scalability_focus=["Virtual DOM re-render minimization", "Code splitting / lazy loading", "Image optimization", "Memory leak prevention"],
        difficulty_baseline=8.0
    ),
    "ml": RoleProfile(
        role_family="ml",
        display_name="AI & Machine Learning Engineer",
        core_competencies=["ML Fundamentals", "Model Evaluation & Loss Functions", "Feature Engineering", "Overfitting Mitigation", "Inference & Deployment"],
        key_technologies=["Python", "PyTorch", "TensorFlow", "Scikit-Learn", "Pandas", "Transformers", "LLMs", "RAG"],
        architecture_focus="Training pipelines, feature stores, model serialization, and low-latency inference services",
        tradeoff_areas=["Model accuracy vs Inference latency", "Precision vs Recall", "Model quantization vs Loss of fidelity"],
        security_focus=["Prompt injection mitigation", "Training data poisoning", "Data privacy & PII sanitization"],
        scalability_focus=["Batch inference optimization", "GPU memory saturation", "Vector database indexing (HNSW)", "Model caching"],
        difficulty_baseline=8.8
    ),
    "data": RoleProfile(
        role_family="data",
        display_name="Data Engineer",
        core_competencies=["Data Modeling", "ETL / ELT Pipelines", "SQL & Query Optimization", "Distributed Processing", "Data Quality & Governance"],
        key_technologies=["SQL", "Python", "PostgreSQL", "Apache Spark", "Kafka", "Airflow", "Snowflake / BigQuery", "Parquet"],
        architecture_focus="Data lakehouse architecture, idempotent ingestion pipelines, and star/snowflake schemas",
        tradeoff_areas=["Row-oriented vs Columnar storage", "Streaming vs Batch processing", "Data freshness vs Ingestion cost"],
        security_focus=["Column-level encryption", "Role-based access control", "Audit logging", "Data anonymization"],
        scalability_focus=["Table partitioning & clustering", "Data skew resolution in distributed joins", "Backpressure in streaming"],
        difficulty_baseline=8.2
    ),
    "devops": RoleProfile(
        role_family="devops",
        display_name="DevOps / Cloud Platform Engineer",
        core_competencies=["Container Orchestration", "CI/CD Pipelines", "Infrastructure as Code", "Observability & Metrics", "High Availability & SRE"],
        key_technologies=["Docker", "Kubernetes", "AWS / GCP / Azure", "Terraform", "Linux", "GitHub Actions", "Prometheus", "Grafana"],
        architecture_focus="Immutable infrastructure, zero-downtime blue/green deployments, and multi-region failover",
        tradeoff_areas=["Infrastructure cost vs Redundancy", "Microservice isolation vs Operational complexity"],
        security_focus=["Least privilege IAM policies", "Secrets management", "Container image vulnerability scanning", "mTLS networking"],
        scalability_focus=["Horizontal pod autoscaling", "Ingress traffic throttling", "Multi-region database replication"],
        difficulty_baseline=8.5
    ),
    "fullstack": RoleProfile(
        role_family="fullstack",
        display_name="Full Stack Software Engineer",
        core_competencies=["Full Lifecycle Feature Development", "Frontend React / UI", "Backend REST / GraphQL APIs", "Database Schema Design", "Authentication"],
        key_technologies=["React", "TypeScript", "Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs", "JWT"],
        architecture_focus="End-to-end data flow from UI component to database persistence",
        tradeoff_areas=["Full stack monorepo vs Multi-repo", "Server-rendered HTML vs SPA client app"],
        security_focus=["End-to-end token authentication", "Input validation across client and server", "CORS policy"],
        scalability_focus=["API response caching", "Frontend asset CDN delivery", "Database connection pooling"],
        difficulty_baseline=8.2
    ),
    "software_engineer": RoleProfile(
        role_family="software_engineer",
        display_name="Software Engineer (General)",
        core_competencies=["Data Structures & Algorithms", "Object-Oriented Design", "Modular Code Architecture", "Debugging & Problem Solving"],
        key_technologies=["Python", "Java", "C++", "JavaScript", "SQL", "Git", "Data Structures", "Algorithms"],
        architecture_focus="Clean code, SOLID principles, design patterns, and testable modular systems",
        tradeoff_areas=["Time complexity vs Space complexity", "Abstraction flexibility vs Code readability"],
        security_focus=["Input sanitization", "Memory safety & buffer overflows", "Exception handling"],
        scalability_focus=["Algorithmic big-O efficiency", "Memory footprint optimization"],
        difficulty_baseline=8.0
    )
}

# Generic fallback profile
GENERIC_ROLE_PROFILE = RoleProfile(
    role_family="software_engineer",
    display_name="Software Engineer",
    core_competencies=["Data Structures", "System Architecture", "Problem Solving", "Clean Code"],
    key_technologies=["Python", "SQL", "REST APIs", "Git"],
    architecture_focus="Modular software design and database interaction",
    tradeoff_areas=["Time vs Space complexity", "Speed of delivery vs Architecture perfection"],
    security_focus=["Input validation and safe error handling"],
    scalability_focus=["Algorithmic efficiency and load scaling"],
    difficulty_baseline=8.0
)
