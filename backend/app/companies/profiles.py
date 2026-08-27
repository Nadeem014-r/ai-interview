"""Phase 9: Strongly Typed Company Profiles and Competency Weights.

Defines public, defensible company profiles grounded in reputable public interview
preparation literature, official engineering career portals, and industry-standard
competency frameworks.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class CompanyProfile:
    """Strongly typed company interview profile and weighted competency preferences."""
    company_id: str
    display_name: str
    aliases: List[str] = field(default_factory=list)
    supported_roles: List[str] = field(default_factory=list)
    competency_weights: Dict[str, float] = field(default_factory=dict)
    
    # Quantitative emphasis scores (1.0 to 10.0 scale)
    technical_depth: float = 8.0
    coding_emphasis: float = 8.0
    data_structures_emphasis: float = 8.0
    algorithms_emphasis: float = 8.0
    system_design_emphasis: float = 7.5
    distributed_systems_emphasis: float = 7.0
    database_emphasis: float = 7.5
    security_emphasis: float = 6.5
    behavioral_emphasis: float = 6.0
    project_depth: float = 8.0
    problem_solving_emphasis: float = 8.5
    communication_emphasis: float = 7.5
    
    # Qualitative style guides
    difficulty_profile: str = "balanced_technical"
    follow_up_style: str = "progressive_optimization_and_tradeoffs"
    question_style: str = "algorithmic_reasoning_and_scale"
    evidence_level: str = "HIGH"  # HIGH, MEDIUM, LOW
    public_pattern_notes: str = ""


COMPANY_PROFILES: Dict[str, CompanyProfile] = {
    "google": CompanyProfile(
        company_id="google",
        display_name="Google",
        aliases=["alphabet", "goog"],
        supported_roles=["Software Engineer", "Backend Engineer", "ML Engineer", "Systems Architect", "Frontend Engineer", "Data Engineer"],
        competency_weights={
            "algorithms": 0.30,
            "data_structures": 0.25,
            "system_design": 0.20,
            "computational_complexity": 0.15,
            "googleyness_leadership": 0.10
        },
        technical_depth=9.5,
        coding_emphasis=9.0,
        data_structures_emphasis=9.5,
        algorithms_emphasis=9.5,
        system_design_emphasis=9.0,
        distributed_systems_emphasis=9.0,
        database_emphasis=8.0,
        security_emphasis=7.5,
        behavioral_emphasis=6.0,
        project_depth=8.0,
        problem_solving_emphasis=9.5,
        communication_emphasis=8.5,
        difficulty_profile="high_algorithmic_and_distributed_systems",
        follow_up_style="complexity_optimization_and_edge_cases",
        question_style="algorithmic_reasoning",
        evidence_level="HIGH",
        public_pattern_notes="Public engineering documentation and hiring guides consistently emphasize data structures, algorithmic time/space complexity analysis, and scalable distributed systems design."
    ),
    "amazon": CompanyProfile(
        company_id="amazon",
        display_name="Amazon",
        aliases=["aws", "amzn"],
        supported_roles=["Software Development Engineer", "Backend Engineer", "DevOps Engineer", "Cloud Architect", "Frontend Engineer", "Data Engineer"],
        competency_weights={
            "leadership_principles": 0.30,
            "system_design": 0.25,
            "object_oriented_design": 0.20,
            "scalable_microservices": 0.15,
            "data_structures_algorithms": 0.10
        },
        technical_depth=9.0,
        coding_emphasis=8.0,
        data_structures_emphasis=8.0,
        algorithms_emphasis=8.0,
        system_design_emphasis=9.5,
        distributed_systems_emphasis=9.5,
        database_emphasis=9.0,
        security_emphasis=8.0,
        behavioral_emphasis=9.5,
        project_depth=9.0,
        problem_solving_emphasis=9.0,
        communication_emphasis=8.5,
        difficulty_profile="high_system_design_and_leadership_principles",
        follow_up_style="failure_modes_operational_excellence_and_customer_impact",
        question_style="practical_distributed_systems_and_behavioral",
        evidence_level="HIGH",
        public_pattern_notes="Amazon's public leadership principles (Customer Obsession, Ownership, Deep Dive) are deeply integrated with practical distributed system design, microservices, and failure resilience."
    ),
    "microsoft": CompanyProfile(
        company_id="microsoft",
        display_name="Microsoft",
        aliases=["msft", "azure"],
        supported_roles=["Software Engineer", "Cloud Backend Engineer", "AI Engineer", "Frontend Engineer", "DevOps Engineer"],
        competency_weights={
            "system_architecture": 0.25,
            "clean_code_design": 0.25,
            "data_structures_algorithms": 0.20,
            "cloud_reliability": 0.15,
            "growth_mindset": 0.15
        },
        technical_depth=8.8,
        coding_emphasis=8.5,
        data_structures_emphasis=8.5,
        algorithms_emphasis=8.5,
        system_design_emphasis=8.8,
        distributed_systems_emphasis=8.8,
        database_emphasis=8.5,
        security_emphasis=8.5,
        behavioral_emphasis=7.5,
        project_depth=8.5,
        problem_solving_emphasis=8.8,
        communication_emphasis=8.5,
        difficulty_profile="enterprise_cloud_and_clean_architecture",
        follow_up_style="tradeoff_analysis_and_maintainability",
        question_style="clean_code_and_enterprise_reliability",
        evidence_level="HIGH",
        public_pattern_notes="Public interview literature highlights clean OOP design, enterprise cloud scalability on Azure, growth mindset collaboration, and maintainable software architecture."
    ),
    "meta": CompanyProfile(
        company_id="meta",
        display_name="Meta",
        aliases=["facebook", "fb"],
        supported_roles=["Software Engineer", "Frontend Engineer", "Production Engineer", "AI Research Engineer", "Data Engineer"],
        competency_weights={
            "fast_paced_coding": 0.35,
            "high_scale_system_design": 0.30,
            "data_structures": 0.20,
            "behavioral_impact": 0.15
        },
        technical_depth=9.4,
        coding_emphasis=9.5,
        data_structures_emphasis=9.5,
        algorithms_emphasis=9.0,
        system_design_emphasis=9.5,
        distributed_systems_emphasis=9.5,
        database_emphasis=9.0,
        security_emphasis=7.5,
        behavioral_emphasis=7.0,
        project_depth=8.5,
        problem_solving_emphasis=9.5,
        communication_emphasis=8.0,
        difficulty_profile="rapid_coding_and_ultra_scale_systems",
        follow_up_style="concurrency_throughput_and_bottleneck_resolution",
        question_style="rapid_execution_and_massive_concurrency",
        evidence_level="HIGH",
        public_pattern_notes="Known for rapid clean coding implementation with immediate execution correctness and deep architecture interrogations for billion-user distributed infrastructure."
    ),
    "apple": CompanyProfile(
        company_id="apple",
        display_name="Apple",
        aliases=["aapl"],
        supported_roles=["Software Engineer", "iOS / Client Engineer", "Backend Systems Engineer", "Machine Learning Engineer"],
        competency_weights={
            "domain_specialization": 0.35,
            "low_level_performance": 0.25,
            "system_design_privacy": 0.20,
            "user_experience_polish": 0.20
        },
        technical_depth=9.0,
        coding_emphasis=8.5,
        data_structures_emphasis=8.5,
        algorithms_emphasis=8.0,
        system_design_emphasis=8.5,
        distributed_systems_emphasis=8.0,
        database_emphasis=8.0,
        security_emphasis=9.5,
        behavioral_emphasis=7.0,
        project_depth=9.5,
        problem_solving_emphasis=9.0,
        communication_emphasis=8.5,
        difficulty_profile="domain_depth_and_performance_optimization",
        follow_up_style="memory_management_privacy_and_latency_polish",
        question_style="hardware_software_integration_and_performance",
        evidence_level="HIGH",
        public_pattern_notes="Public sources indicate strong emphasis on candidate project ownership, memory/resource efficiency, user privacy, and domain-specific excellence."
    ),
    "netflix": CompanyProfile(
        company_id="netflix",
        display_name="Netflix",
        aliases=["nflx"],
        supported_roles=["Senior Software Engineer", "Distributed Systems Engineer", "Data Platform Engineer"],
        competency_weights={
            "senior_architecture": 0.35,
            "distributed_resiliency": 0.30,
            "culture_memo_autonomy": 0.20,
            "observability_tooling": 0.15
        },
        technical_depth=9.6,
        coding_emphasis=8.0,
        data_structures_emphasis=8.0,
        algorithms_emphasis=8.0,
        system_design_emphasis=9.8,
        distributed_systems_emphasis=10.0,
        database_emphasis=9.5,
        security_emphasis=8.5,
        behavioral_emphasis=9.0,
        project_depth=9.5,
        problem_solving_emphasis=9.5,
        communication_emphasis=9.0,
        difficulty_profile="senior_distributed_systems_and_chaos_engineering",
        follow_up_style="chaos_failure_injection_and_stateless_scalability",
        question_style="high_throughput_streaming_and_fault_tolerance",
        evidence_level="HIGH",
        public_pattern_notes="Focuses predominantly on senior-level engineers with mastery over distributed microservices, chaos engineering, high concurrency, and high autonomy."
    ),
    "adobe": CompanyProfile(
        company_id="adobe",
        display_name="Adobe",
        aliases=["adbe"],
        supported_roles=["Software Engineer", "Full Stack Engineer", "Computer Vision Engineer"],
        competency_weights={
            "data_structures_algorithms": 0.30,
            "object_oriented_design": 0.25,
            "system_design": 0.25,
            "project_contribution": 0.20
        },
        technical_depth=8.5,
        coding_emphasis=8.5,
        data_structures_emphasis=8.5,
        algorithms_emphasis=8.5,
        system_design_emphasis=8.0,
        distributed_systems_emphasis=7.5,
        database_emphasis=8.0,
        security_emphasis=7.0,
        behavioral_emphasis=6.5,
        project_depth=8.0,
        problem_solving_emphasis=8.5,
        communication_emphasis=7.5,
        difficulty_profile="solid_algorithms_and_creative_cloud_scale",
        follow_up_style="algorithmic_efficiency_and_clean_code",
        question_style="data_structures_and_multimedia_services",
        evidence_level="HIGH",
        public_pattern_notes="Balances classical algorithms/data structures with practical full-stack and cloud service engineering."
    ),
    "oracle": CompanyProfile(
        company_id="oracle",
        display_name="Oracle",
        aliases=["orcl"],
        supported_roles=["Software Developer", "Database Kernel Engineer", "Cloud Infrastructure Engineer"],
        competency_weights={
            "database_internals": 0.35,
            "concurrency_os": 0.25,
            "data_structures_algorithms": 0.25,
            "cloud_networking": 0.15
        },
        technical_depth=8.8,
        coding_emphasis=8.5,
        data_structures_emphasis=8.5,
        algorithms_emphasis=8.5,
        system_design_emphasis=8.5,
        distributed_systems_emphasis=8.5,
        database_emphasis=10.0,
        security_emphasis=8.0,
        behavioral_emphasis=6.0,
        project_depth=8.0,
        problem_solving_emphasis=8.5,
        communication_emphasis=7.5,
        difficulty_profile="database_internals_and_systems_concurrency",
        follow_up_style="acid_transactions_b_trees_and_lock_contention",
        question_style="database_architecture_and_low_level_concurrency",
        evidence_level="HIGH",
        public_pattern_notes="Renowned for deep inquiries into database indexing, ACID guarantees, transaction isolation, storage engines, and operating system concurrency."
    ),
    "ibm": CompanyProfile(
        company_id="ibm",
        display_name="IBM",
        aliases=["international business machines"],
        supported_roles=["Software Developer", "Cloud Solutions Architect", "AI Research Associate"],
        competency_weights={
            "applied_engineering": 0.30,
            "enterprise_cloud_security": 0.25,
            "data_structures": 0.20,
            "collaboration_communication": 0.25
        },
        technical_depth=7.8,
        coding_emphasis=7.5,
        data_structures_emphasis=7.5,
        algorithms_emphasis=7.0,
        system_design_emphasis=7.8,
        distributed_systems_emphasis=7.5,
        database_emphasis=8.0,
        security_emphasis=8.5,
        behavioral_emphasis=8.0,
        project_depth=8.0,
        problem_solving_emphasis=7.8,
        communication_emphasis=8.5,
        difficulty_profile="enterprise_hybrid_cloud_and_applied_ai",
        follow_up_style="enterprise_integration_and_security_compliance",
        question_style="applied_enterprise_systems_and_collaboration",
        evidence_level="HIGH",
        public_pattern_notes="Emphasizes enterprise architecture, hybrid cloud integration (Red Hat / OpenShift), data security compliance, and practical problem solving."
    ),
    "infosys": CompanyProfile(
        company_id="infosys",
        display_name="Infosys",
        aliases=["infy"],
        supported_roles=["Systems Engineer", "Specialist Programmer", "Digital Specialist Engineer"],
        competency_weights={
            "programming_fundamentals": 0.35,
            "database_sql": 0.25,
            "project_discussion": 0.20,
            "communication_clarity": 0.20
        },
        technical_depth=7.5,
        coding_emphasis=8.0,
        data_structures_emphasis=7.5,
        algorithms_emphasis=7.5,
        system_design_emphasis=6.5,
        distributed_systems_emphasis=6.0,
        database_emphasis=8.0,
        security_emphasis=6.5,
        behavioral_emphasis=7.5,
        project_depth=7.5,
        problem_solving_emphasis=7.5,
        communication_emphasis=8.0,
        difficulty_profile="practical_programming_and_database_fundamentals",
        follow_up_style="syntax_mechanics_and_project_contribution",
        question_style="foundational_programming_and_sql_queries",
        evidence_level="HIGH",
        public_pattern_notes="Frequently assesses core programming logic, SQL queries, OOP principles, and clarity of communication during academic and project walkthroughs."
    ),
    "accenture": CompanyProfile(
        company_id="accenture",
        display_name="Accenture",
        aliases=["acn"],
        supported_roles=["Associate Software Engineer", "Advanced App Engineering Analyst", "Cloud Architect"],
        competency_weights={
            "applied_programming": 0.30,
            "scenario_problem_solving": 0.25,
            "project_walkthrough": 0.25,
            "consulting_communication": 0.20
        },
        technical_depth=7.5,
        coding_emphasis=7.5,
        data_structures_emphasis=7.0,
        algorithms_emphasis=7.0,
        system_design_emphasis=7.0,
        distributed_systems_emphasis=6.5,
        database_emphasis=7.5,
        security_emphasis=7.0,
        behavioral_emphasis=8.0,
        project_depth=8.0,
        problem_solving_emphasis=7.8,
        communication_emphasis=8.5,
        difficulty_profile="applied_problem_solving_and_consulting_clarity",
        follow_up_style="scenario_handling_and_client_deliverables",
        question_style="applied_technology_and_scenario_analysis",
        evidence_level="HIGH",
        public_pattern_notes="Places high emphasis on applied programming, candidate project explanations, situational problem-solving, and professional client-facing communication."
    ),
    "tcs": CompanyProfile(
        company_id="tcs",
        display_name="Tata Consultancy Services",
        aliases=["tcs digital", "tcs ninja"],
        supported_roles=["Assistant System Engineer", "Digital Innovator", "Full Stack Developer"],
        competency_weights={
            "core_computer_science": 0.35,
            "sql_and_dbms": 0.25,
            "project_implementation": 0.20,
            "behavioral_aptitude": 0.20
        },
        technical_depth=7.4,
        coding_emphasis=7.5,
        data_structures_emphasis=7.5,
        algorithms_emphasis=7.0,
        system_design_emphasis=6.5,
        distributed_systems_emphasis=6.0,
        database_emphasis=8.0,
        security_emphasis=6.5,
        behavioral_emphasis=7.5,
        project_depth=7.5,
        problem_solving_emphasis=7.5,
        communication_emphasis=8.0,
        difficulty_profile="computer_science_fundamentals_and_sql",
        follow_up_style="concept_clarification_and_fundamental_mechanics",
        question_style="core_cs_principles_and_practical_queries",
        evidence_level="HIGH",
        public_pattern_notes="Focuses on DBMS fundamentals, SQL joins/indexing, OOP concepts, data structures, and candidate project responsibilities."
    ),
    "deloitte": CompanyProfile(
        company_id="deloitte",
        display_name="Deloitte",
        aliases=["deloitte tech"],
        supported_roles=["Solutions Analyst", "Software Development Engineer", "Cloud Consultant"],
        competency_weights={
            "applied_engineering": 0.30,
            "business_technical_alignment": 0.25,
            "database_api_design": 0.25,
            "communication_leadership": 0.20
        },
        technical_depth=7.6,
        coding_emphasis=7.0,
        data_structures_emphasis=7.0,
        algorithms_emphasis=7.0,
        system_design_emphasis=7.5,
        distributed_systems_emphasis=7.0,
        database_emphasis=8.0,
        security_emphasis=7.5,
        behavioral_emphasis=8.5,
        project_depth=8.0,
        problem_solving_emphasis=8.0,
        communication_emphasis=8.8,
        difficulty_profile="technical_business_solutions_and_api_design",
        follow_up_style="business_tradeoffs_and_architecture_clarity",
        question_style="solution_architecture_and_stakeholder_communication",
        evidence_level="HIGH",
        public_pattern_notes="Combines software engineering fundamentals with solution architecture, business impact, security, and structured communication."
    )
}

# Generic fallback profile for unsupported or custom companies
GENERIC_COMPANY_PROFILE = CompanyProfile(
    company_id="generic",
    display_name="Technology Company",
    aliases=["tech", "startup"],
    supported_roles=["Software Engineer", "Backend Engineer", "Frontend Engineer", "Full Stack Engineer"],
    competency_weights={
        "technical_problem_solving": 0.30,
        "clean_coding": 0.25,
        "system_architecture": 0.25,
        "communication": 0.20
    },
    technical_depth=8.0,
    coding_emphasis=8.0,
    data_structures_emphasis=8.0,
    algorithms_emphasis=7.5,
    system_design_emphasis=7.5,
    distributed_systems_emphasis=7.0,
    database_emphasis=7.5,
    security_emphasis=7.0,
    behavioral_emphasis=7.0,
    project_depth=8.0,
    problem_solving_emphasis=8.0,
    communication_emphasis=8.0,
    difficulty_profile="balanced_technical_engineering",
    follow_up_style="progressive_clarification_and_tradeoffs",
    question_style="balanced_technical_and_project_discussion",
    evidence_level="MEDIUM",
    public_pattern_notes="Standard balanced industry software engineering interview rubric."
)
