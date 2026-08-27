import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.models import Company, Role


COMPANIES = [
    {
        "name": "Google",
        "slug": "google",
        "description": "Technology company known for search, cloud, AI, distributed systems, and large-scale software engineering.",
        "website": "https://careers.google.com",
        "target_roles": [
            "Software Engineer",
            "Backend Software Engineer",
            "Machine Learning Engineer",
        ],
        "culture_keywords": [
            "Algorithmic problem solving",
            "Scalability",
            "System design",
            "Technical depth",
            "Innovation",
        ],
        "roles": [
            {
                "title": "Software Engineer",
                "level": "Entry / L3",
                "description": "Build reliable and scalable software systems.",
                "required_skills": [
                    "C++",
                    "Python",
                    "Java",
                    "Data Structures",
                    "Algorithms",
                ],
                "key_topics": [
                    "Data Structures",
                    "Algorithms",
                    "System Design",
                    "Distributed Systems",
                    "Concurrency",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "Behavioral",
                ],
            },
            {
                "title": "Backend Software Engineer",
                "level": "Entry / L3",
                "description": "Develop scalable backend services and distributed systems.",
                "required_skills": [
                    "Python",
                    "C++",
                    "Java",
                    "SQL",
                    "REST APIs",
                ],
                "key_topics": [
                    "Data Structures",
                    "Algorithms",
                    "Databases",
                    "Distributed Systems",
                    "API Design",
                    "Concurrency",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "System Design",
                    "Behavioral",
                ],
            },
            {
                "title": "Machine Learning Engineer",
                "level": "Entry / L3",
                "description": "Build and deploy machine learning systems.",
                "required_skills": [
                    "Python",
                    "Machine Learning",
                    "Statistics",
                    "PyTorch",
                    "Data Structures",
                ],
                "key_topics": [
                    "Machine Learning",
                    "Model Evaluation",
                    "Feature Engineering",
                    "ML Systems",
                    "Algorithms",
                ],
                "interview_categories": [
                    "Technical",
                    "ML Design",
                    "Coding",
                    "Behavioral",
                ],
            },
        ],
    },
    {
        "name": "Amazon",
        "slug": "amazon",
        "description": "Technology company with strong focus on cloud computing, distributed systems, and customer-focused engineering.",
        "website": "https://amazon.jobs",
        "target_roles": [
            "Software Development Engineer I",
            "Software Development Engineer II",
            "Cloud Engineer",
        ],
        "culture_keywords": [
            "Customer Obsession",
            "Ownership",
            "Bias for Action",
            "Invent and Simplify",
            "Dive Deep",
        ],
        "roles": [
            {
                "title": "Software Development Engineer I",
                "level": "Entry / SDE-1",
                "description": "Build reliable software services for large-scale systems.",
                "required_skills": [
                    "Java",
                    "Python",
                    "C++",
                    "Data Structures",
                    "Algorithms",
                    "SQL",
                ],
                "key_topics": [
                    "Data Structures",
                    "Algorithms",
                    "Object-Oriented Design",
                    "Distributed Systems",
                    "Database Design",
                    "Concurrency",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "Behavioral",
                    "Leadership Principles",
                ],
            },
            {
                "title": "Software Development Engineer II",
                "level": "Mid / SDE-2",
                "description": "Design and implement scalable production services.",
                "required_skills": [
                    "Java",
                    "Python",
                    "AWS",
                    "SQL",
                    "System Design",
                ],
                "key_topics": [
                    "System Design",
                    "Distributed Systems",
                    "Scalability",
                    "Databases",
                    "Reliability",
                ],
                "interview_categories": [
                    "Coding",
                    "System Design",
                    "Technical",
                    "Behavioral",
                ],
            },
        ],
    },
    {
        "name": "Microsoft",
        "slug": "microsoft",
        "description": "Technology company focused on cloud computing, enterprise software, operating systems, and developer platforms.",
        "website": "https://careers.microsoft.com",
        "target_roles": [
            "Software Engineer",
            "Cloud Engineer",
            "Software Engineer II",
        ],
        "culture_keywords": [
            "Growth Mindset",
            "Collaboration",
            "Innovation",
            "Cloud",
            "Reliability",
        ],
        "roles": [
            {
                "title": "Software Engineer",
                "level": "Entry / Graduate",
                "description": "Develop reliable software and cloud-connected applications.",
                "required_skills": [
                    "C#",
                    "C++",
                    "Python",
                    "Data Structures",
                    "Algorithms",
                ],
                "key_topics": [
                    "Data Structures",
                    "Algorithms",
                    "Object-Oriented Programming",
                    "Operating Systems",
                    "Cloud Computing",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "Behavioral",
                ],
            },
            {
                "title": "Cloud Engineer",
                "level": "Entry / Graduate",
                "description": "Build and operate cloud-based services.",
                "required_skills": [
                    "C#",
                    "Python",
                    "Azure",
                    "Docker",
                    "REST APIs",
                ],
                "key_topics": [
                    "Cloud Architecture",
                    "Microservices",
                    "API Design",
                    "Security",
                    "Reliability",
                ],
                "interview_categories": [
                    "Technical",
                    "Cloud Design",
                    "Coding",
                    "Behavioral",
                ],
            },
        ],
    },
    {
        "name": "Meta",
        "slug": "meta",
        "description": "Technology company operating large-scale social, communication, infrastructure, and AI platforms.",
        "website": "https://www.metacareers.com",
        "target_roles": [
            "Software Engineer",
            "Backend Engineer",
        ],
        "culture_keywords": [
            "Move Fast",
            "Scale",
            "Product Thinking",
            "Infrastructure",
            "Impact",
        ],
        "roles": [
            {
                "title": "Software Engineer",
                "level": "Entry",
                "description": "Develop high-scale products and infrastructure.",
                "required_skills": [
                    "Python",
                    "C++",
                    "Java",
                    "Data Structures",
                    "Algorithms",
                ],
                "key_topics": [
                    "Algorithms",
                    "Data Structures",
                    "System Design",
                    "Distributed Systems",
                    "Performance",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "Behavioral",
                ],
            },
            {
                "title": "Backend Engineer",
                "level": "Entry",
                "description": "Build scalable backend services.",
                "required_skills": [
                    "Python",
                    "Java",
                    "C++",
                    "SQL",
                    "APIs",
                ],
                "key_topics": [
                    "Distributed Systems",
                    "Databases",
                    "API Design",
                    "Caching",
                    "Concurrency",
                ],
                "interview_categories": [
                    "Coding",
                    "System Design",
                    "Technical",
                ],
            },
        ],
    },
    {
        "name": "Apple",
        "slug": "apple",
        "description": "Technology company focused on consumer devices, operating systems, software, and services.",
        "website": "https://jobs.apple.com",
        "target_roles": [
            "Software Engineer",
            "iOS Engineer",
        ],
        "culture_keywords": [
            "Product Quality",
            "Performance",
            "Privacy",
            "Attention to Detail",
            "Innovation",
        ],
        "roles": [
            {
                "title": "Software Engineer",
                "level": "Entry",
                "description": "Develop high-quality software and platform components.",
                "required_skills": [
                    "C++",
                    "Swift",
                    "Python",
                    "Data Structures",
                    "Algorithms",
                ],
                "key_topics": [
                    "Algorithms",
                    "Data Structures",
                    "Operating Systems",
                    "Concurrency",
                    "Performance",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "Behavioral",
                ],
            },
            {
                "title": "iOS Engineer",
                "level": "Entry",
                "description": "Build reliable and performant iOS applications.",
                "required_skills": [
                    "Swift",
                    "Objective-C",
                    "UIKit",
                    "Concurrency",
                ],
                "key_topics": [
                    "iOS Architecture",
                    "Memory Management",
                    "Concurrency",
                    "Performance",
                    "UI Architecture",
                ],
                "interview_categories": [
                    "Technical",
                    "Coding",
                    "Behavioral",
                ],
            },
        ],
    },
    {
        "name": "Netflix",
        "slug": "netflix",
        "description": "Streaming technology company operating large-scale distributed services and content platforms.",
        "website": "https://jobs.netflix.com",
        "target_roles": [
            "Software Engineer",
            "Backend Engineer",
        ],
        "culture_keywords": [
            "Freedom and Responsibility",
            "Distributed Systems",
            "Reliability",
            "Performance",
            "Engineering Excellence",
        ],
        "roles": [
            {
                "title": "Software Engineer",
                "level": "Entry",
                "description": "Build reliable software for large-scale streaming systems.",
                "required_skills": [
                    "Java",
                    "Python",
                    "Data Structures",
                    "Algorithms",
                    "Distributed Systems",
                ],
                "key_topics": [
                    "Distributed Systems",
                    "Algorithms",
                    "Microservices",
                    "Caching",
                    "Reliability",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "System Design",
                    "Behavioral",
                ],
            },
            {
                "title": "Backend Engineer",
                "level": "Entry",
                "description": "Develop highly available backend services.",
                "required_skills": [
                    "Java",
                    "Python",
                    "SQL",
                    "REST APIs",
                    "Cloud",
                ],
                "key_topics": [
                    "Microservices",
                    "Databases",
                    "Caching",
                    "Distributed Systems",
                    "API Design",
                ],
                "interview_categories": [
                    "Technical",
                    "System Design",
                    "Coding",
                ],
            },
        ],
    },
    {
        "name": "Adobe",
        "slug": "adobe",
        "description": "Software company building creative, document, digital experience, and cloud products.",
        "website": "https://careers.adobe.com",
        "target_roles": [
            "Software Engineer",
            "Backend Engineer",
        ],
        "culture_keywords": [
            "Creativity",
            "Innovation",
            "Cloud",
            "Product Engineering",
            "User Experience",
        ],
        "roles": [
            {
                "title": "Software Engineer",
                "level": "Entry",
                "description": "Build scalable software products and services.",
                "required_skills": [
                    "Java",
                    "C++",
                    "Python",
                    "Data Structures",
                    "Algorithms",
                ],
                "key_topics": [
                    "Data Structures",
                    "Algorithms",
                    "OOP",
                    "Databases",
                    "API Design",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "Behavioral",
                ],
            },
            {
                "title": "Backend Engineer",
                "level": "Entry",
                "description": "Develop cloud-based backend services.",
                "required_skills": [
                    "Java",
                    "Python",
                    "SQL",
                    "REST APIs",
                    "Cloud",
                ],
                "key_topics": [
                    "Databases",
                    "APIs",
                    "Microservices",
                    "Caching",
                    "Scalability",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "System Design",
                ],
            },
        ],
    },
    {
        "name": "IBM",
        "slug": "ibm",
        "description": "Technology company focused on enterprise software, cloud, AI, and infrastructure.",
        "website": "https://www.ibm.com/careers",
        "target_roles": [
            "Software Engineer",
            "Cloud Developer",
        ],
        "culture_keywords": [
            "Enterprise Technology",
            "Cloud",
            "AI",
            "Security",
            "Reliability",
        ],
        "roles": [
            {
                "title": "Software Engineer",
                "level": "Entry",
                "description": "Develop enterprise software and cloud services.",
                "required_skills": [
                    "Java",
                    "Python",
                    "C++",
                    "SQL",
                    "Data Structures",
                ],
                "key_topics": [
                    "Algorithms",
                    "Databases",
                    "OOP",
                    "Cloud Computing",
                    "Security",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "Behavioral",
                ],
            },
            {
                "title": "Cloud Developer",
                "level": "Entry",
                "description": "Develop and maintain cloud-native enterprise services.",
                "required_skills": [
                    "Python",
                    "Java",
                    "Docker",
                    "Kubernetes",
                    "REST APIs",
                ],
                "key_topics": [
                    "Cloud Architecture",
                    "Containers",
                    "Microservices",
                    "API Security",
                    "Reliability",
                ],
                "interview_categories": [
                    "Technical",
                    "Cloud",
                    "System Design",
                ],
            },
        ],
    },
    {
        "name": "Oracle",
        "slug": "oracle",
        "description": "Enterprise technology company specializing in databases, cloud infrastructure, and business software.",
        "website": "https://www.oracle.com/careers",
        "target_roles": [
            "Software Engineer",
            "Cloud Engineer",
        ],
        "culture_keywords": [
            "Databases",
            "Enterprise Systems",
            "Cloud",
            "Performance",
            "Reliability",
        ],
        "roles": [
            {
                "title": "Software Engineer",
                "level": "Entry",
                "description": "Develop enterprise software and database-driven systems.",
                "required_skills": [
                    "Java",
                    "C++",
                    "Python",
                    "SQL",
                    "Data Structures",
                ],
                "key_topics": [
                    "Algorithms",
                    "Databases",
                    "SQL",
                    "OOP",
                    "Concurrency",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "Database",
                ],
            },
            {
                "title": "Cloud Engineer",
                "level": "Entry",
                "description": "Build cloud infrastructure and services.",
                "required_skills": [
                    "Java",
                    "Python",
                    "OCI",
                    "Docker",
                    "Kubernetes",
                ],
                "key_topics": [
                    "Cloud Architecture",
                    "Distributed Systems",
                    "Networking",
                    "Containers",
                    "Security",
                ],
                "interview_categories": [
                    "Technical",
                    "Cloud",
                    "System Design",
                ],
            },
        ],
    },
    {
        "name": "Infosys",
        "slug": "infosys",
        "description": "Global IT services and consulting company with strong software engineering and enterprise technology roles.",
        "website": "https://www.infosys.com/careers",
        "target_roles": [
            "Systems Engineer",
            "Software Engineer",
            "Technology Analyst",
        ],
        "culture_keywords": [
            "Problem Solving",
            "Enterprise Software",
            "Client Focus",
            "Adaptability",
            "Technical Fundamentals",
        ],
        "roles": [
            {
                "title": "Systems Engineer",
                "level": "Entry",
                "description": "Develop and maintain enterprise software solutions.",
                "required_skills": [
                    "Java",
                    "Python",
                    "SQL",
                    "OOP",
                    "Data Structures",
                ],
                "key_topics": [
                    "Data Structures",
                    "Algorithms",
                    "OOP",
                    "SQL",
                    "Software Engineering",
                ],
                "interview_categories": [
                    "Coding",
                    "Technical",
                    "HR",
                ],
            },
            {
                "title": "Technology Analyst",
                "level": "Entry",
                "description": "Develop technical solutions for enterprise clients.",
                "required_skills": [
                    "Java",
                    "Python",
                    "SQL",
                    "Cloud",
                    "REST APIs",
                ],
                "key_topics": [
                    "APIs",
                    "Databases",
                    "Cloud Computing",
                    "Software Architecture",
                    "Problem Solving",
                ],
                "interview_categories": [
                    "Technical",
                    "Coding",
                    "Behavioral",
                ],
            },
        ],
    },
]


async def seed_database():
    async with AsyncSessionLocal() as db:
        for company_data in COMPANIES:
            result = await db.execute(
                select(Company).where(
                    Company.slug == company_data["slug"]
                )
            )
            company = result.scalars().first()

            if not company:
                company = Company(
                    name=company_data["name"],
                    slug=company_data["slug"],
                    description=company_data["description"],
                    website=company_data["website"],
                    target_roles=company_data["target_roles"],
                    culture_keywords=company_data["culture_keywords"],
                )
                db.add(company)
                await db.flush()

            for role_data in company_data["roles"]:
                result = await db.execute(
                    select(Role).where(
                        Role.company_id == company.id,
                        Role.title == role_data["title"],
                    )
                )
                role = result.scalars().first()

                if not role:
                    db.add(
                        Role(
                            company_id=company.id,
                            title=role_data["title"],
                            level=role_data["level"],
                            description=role_data["description"],
                            required_skills=role_data["required_skills"],
                            key_topics=role_data["key_topics"],
                            interview_categories=role_data["interview_categories"],
                        )
                    )

        await db.commit()


async def main():
    print("Seeding company and role catalog...")
    await seed_database()
    print("DONE: company and role catalog seeded successfully.")


if __name__ == "__main__":
    asyncio.run(main())