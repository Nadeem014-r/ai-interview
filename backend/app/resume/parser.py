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

class ResumeParser:
    @staticmethod
    def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
        """
        Extracts clean text from PDF, DOCX, or TXT without silently treating binary bytes as text.
        Raises HTTPException(400) if extraction yields no readable content or is corrupt.
        """
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
        """
        Pure deterministic extraction with ZERO fabricated defaults.
        If information is missing, fields remain None or empty lists.
        """
        # 1. Email Extraction
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', raw_text)
        email = email_match.group(0) if email_match else None

        # 2. Phone Extraction
        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', raw_text)
        phone = phone_match.group(0).strip() if phone_match else None

        # 3. Candidate Name Extraction (Heuristic: First clean non-header line)
        candidate_name = None
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        for line in lines[:5]:
            if len(line) < 40 and not re.search(r'(@|http|resume|curriculum|phone|email|education|skills)', line, re.IGNORECASE):
                # Ensure it looks like a person's name
                if re.match(r'^[A-Za-z\s\.\'-]+$', line) and len(line.split()) >= 1:
                    candidate_name = line.strip()
                    break

        # 4. Technical Skills Extraction (Case-insensitive whole-word and symbol-aware matching)
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

        # 5. Education Extraction
        education_list = []
        degrees_found = []
        degree_match = re.search(r'\b(B\.?Tech|B\.?E|B\.?S|M\.?Tech|M\.?S|Bachelor(?:\s+of\s+[A-Za-z\s]+)?|Master(?:\s+of\s+[A-Za-z\s]+)?|Ph\.?D|Diploma)[^\n,\.]*', raw_text, re.IGNORECASE)
        year_match = re.search(r'\b(20[012]\d)\s*[-–—to]+\s*(20[23]\d|Present)\b', raw_text, re.IGNORECASE)
        univ_match = re.search(r'([A-Z][A-Za-z\s&]+(University|Institute|College|Academy|School)[A-Za-z\s]*)', raw_text)

        if degree_match or univ_match:
            degree_str = degree_match.group(0).strip() if degree_match else None
            institution_str = univ_match.group(0).strip() if univ_match else None
            year_str = year_match.group(0).strip() if year_match else None
            
            if degree_str:
                degrees_found.append(degree_str)
            
            education_list.append({
                "institution": institution_str,
                "degree": degree_str,
                "year": year_str
            })

        # 6. GPA Extraction
        gpa_match = re.search(r'\b(GPA|CGPA|marks?|grade)\s*[:=-]?\s*([0-9]+(?:\.[0-9]+)?(?:\s*/\s*[0-9]+(?:\.[0-9]+)?)?%?)', raw_text, re.IGNORECASE)
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
        elif any(s in extracted_skills for s in ["PyTorch", "TensorFlow", "Machine Learning", "Deep Learning", "NLP"]):
            primary_domain = "AI & Machine Learning"
        elif len(extracted_skills) > 0:
            primary_domain = "Software Engineering"

        # 9. Projects and Experience detection (NO fake default projects!)
        projects = []
        experience = []

        return {
            "explicit_facts": {
                "candidate_name": candidate_name,
                "email": email,
                "phone": phone,
                "education_degrees": degrees_found,
                "gpa_or_marks": gpa_str,
                "verified_companies": []
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
        """
        Parses resume content using LLM with fallback to reliable deterministic extraction.
        Never invents missing candidate details.
        """
        rule_data = ResumeParser.deterministic_rule_parse(raw_text)
        llm = AIFactory.get_llm_provider()
        
        # Handle long resumes by preserving structured sections and taking up to 10,000 characters
        context_text = raw_text[:10000]
        
        prompt = f"""
Analyze the following resume text. Strictly separate explicit facts from model-inferred assumptions.
Do NOT invent or fabricate any information that is not present in the text.
If any field or list is absent, return null or an empty list [].

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
        {{"title": "project name", "description": "brief summary", "technologies": ["tech used"]}}
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
                
            # Sanitize and validate LLM output structure
            explicit_facts = parsed.get("explicit_facts", {}) if isinstance(parsed.get("explicit_facts"), dict) else {}
            model_inferred = parsed.get("model_inferred", {}) if isinstance(parsed.get("model_inferred"), dict) else {}
            
            # Merge deterministic email/phone if LLM missed them
            if not explicit_facts.get("email") and rule_data["explicit_facts"].get("email"):
                explicit_facts["email"] = rule_data["explicit_facts"]["email"]
            if not explicit_facts.get("phone") and rule_data["explicit_facts"].get("phone"):
                explicit_facts["phone"] = rule_data["explicit_facts"]["phone"]
            if not explicit_facts.get("candidate_name") and rule_data["explicit_facts"].get("candidate_name"):
                explicit_facts["candidate_name"] = rule_data["explicit_facts"]["candidate_name"]

            # Merge skills
            skills = parsed.get("skills", [])
            if not isinstance(skills, list) or len(skills) == 0:
                skills = rule_data["skills"]
            else:
                # Combine with deterministic skills to ensure full coverage
                for s in rule_data["skills"]:
                    if s not in skills:
                        skills.append(s)

            technologies = parsed.get("technologies", [])
            if not isinstance(technologies, list) or len(technologies) == 0:
                technologies = skills

            education = parsed.get("education", [])
            if not isinstance(education, list):
                education = rule_data["education"]
            elif len(education) == 0 and len(rule_data["education"]) > 0:
                education = rule_data["education"]

            projects = parsed.get("projects", [])
            if not isinstance(projects, list):
                projects = []

            experience = parsed.get("experience", [])
            if not isinstance(experience, list):
                experience = []

            return {
                "explicit_facts": explicit_facts,
                "model_inferred": model_inferred,
                "skills": skills,
                "projects": projects,
                "education": education,
                "experience": experience,
                "technologies": technologies
            }
        except Exception:
            return rule_data
