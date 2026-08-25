import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend")))

from app.core.database import AsyncSessionLocal, init_db
from app.core.security import get_password_hash
from app.db.models import User, CandidateProfile, Company, Role, Question, Source, Document

async def seed_database():
    print("Initializing database tables...")
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # Check if users exist
        from sqlalchemy import select
        res = await db.execute(select(User))
        if res.scalars().first():
            print("Database already seeded.")
            return

        print("Seeding Users...")
        admin = User(
            email="admin@university.edu",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="Dr. Sarah Jenkins (Placement Director)",
            role="admin"
        )
        candidate = User(
            email="student@university.edu",
            hashed_password=get_password_hash("StudentPass123!"),
            full_name="Alex Mercer (Final Year B.Tech)",
            role="candidate"
        )
        db.add_all([admin, candidate])
        await db.commit()
        await db.refresh(candidate)

        profile = CandidateProfile(
            user_id=candidate.id,
            headline="Aspiring Backend Engineer",
            target_role="Software Engineer",
            experience_level="entry",
            bio="Final year B.Tech Computer Science student passionate about distributed systems, APIs, and databases."
        )
        db.add(profile)

        print("Seeding Companies & Roles...")
        c1 = Company(name="Google", slug="google", description="Leading tech giant focused on systems & search", target_roles=["Software Engineer", "Systems Architect"])
        c2 = Company(name="Amazon", slug="amazon", description="E-commerce and cloud computing giant", target_roles=["SDE I", "DevOps Engineer"])
        c3 = Company(name="Microsoft", slug="microsoft", description="Global leader in cloud & enterprise tech", target_roles=["Software Engineer"])
        db.add_all([c1, c2, c3])
        await db.commit()

        r1 = Role(company_id=c1.id, title="Software Engineer (Backend)", level="Entry / L3", description="Distributed backend systems role", required_skills=["Python", "FastAPI", "Data Structures"], key_topics=["Data Structures", "Relational Databases", "Distributed Systems"])
        r2 = Role(company_id=c2.id, title="Software Development Engineer (SDE-1)", level="L4 / Entry", description="Scalable microservices role", required_skills=["Java", "Python", "SQL"], key_topics=["Object-Oriented Design", "Concurrency", "Database Indexing"])
        db.add_all([r1, r2])
        await db.commit()

        print("Seeding Question Bank...")
        q1 = Question(
            company_id=c1.id,
            role_id=r1.id,
            topic="Relational Databases",
            subtopic="Indexing",
            difficulty="medium",
            question_type="technical",
            question_text="Explain how B-Tree indexing speeds up database read queries, and discuss the trade-offs on write performance.",
            expected_concepts=["B-Tree node structure", "O(log N) search complexity", "Disk I/O reduction", "Index update overhead on INSERT/UPDATE"],
            follow_ups=["How do composite indexes differ from single-column indexes in query optimization?"]
        )
        q2 = Question(
            company_id=c1.id,
            role_id=r1.id,
            topic="Data Structures",
            subtopic="Caching",
            difficulty="hard",
            question_type="technical",
            question_text="How would you design a thread-safe Least Recently Used (LRU) Cache with O(1) time complexity for get and put operations?",
            expected_concepts=["Doubly Linked List", "Hash Map for O(1) key lookup", "Mutex/Locking for concurrency safety"],
            follow_ups=["How does cache eviction strategy change if we use Least Frequently Used (LFU)?"]
        )
        q3 = Question(
            company_id=c2.id,
            role_id=r2.id,
            topic="Concurrency",
            subtopic="Deadlocks",
            difficulty="medium",
            question_type="technical",
            question_text="What are the four Coffman conditions required for a deadlock to occur in a concurrent system, and how can one of them be broken?",
            expected_concepts=["Mutual Exclusion", "Hold and Wait", "No Preemption", "Circular Wait"],
            follow_ups=["Explain lock ordering as a strategy to break circular wait."]
        )
        q4 = Question(
            company_id=c1.id,
            role_id=r1.id,
            topic="Introduction & Fit",
            subtopic="Background",
            difficulty="easy",
            question_type="hr",
            question_text="Tell me about yourself, your technical background, and what motivated you to pursue software engineering.",
            expected_concepts=["Clear communication", "Technical passion", "Project accomplishments"],
            follow_ups=["What specific technical area excites you the most?"]
        )
        q5 = Question(
            company_id=c2.id,
            role_id=r2.id,
            topic="Behavioral & Conflict",
            subtopic="Team Collaboration",
            difficulty="medium",
            question_type="behavioral",
            question_text="Describe a challenging technical disagreement you experienced with a team member. How did you advocate for your solution and arrive at a consensus?",
            expected_concepts=["Active listening", "STAR methodology", "Data-driven resolution"],
            follow_ups=["How did this experience shape your collaboration style?"]
        )
        q6 = Question(
            company_id=c3.id,
            role_id=r1.id,
            topic="Distributed Systems",
            subtopic="CAP Theorem",
            difficulty="hard",
            question_type="technical",
            question_text="Explain the CAP theorem trade-offs in distributed systems and describe how modern databases achieve eventual consistency.",
            expected_concepts=["Consistency vs Availability vs Partition Tolerance", "Eventual consistency models", "Quorum consensus"],
            follow_ups=["How does vector clocks or gossip protocol help in partition healing?"]
        )
        db.add_all([q1, q2, q3, q4, q5, q6])
        await db.commit()

        print("Seed completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())
