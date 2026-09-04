"""Cleanup script for PostgreSQL Database.

Safely deletes all companies except the 10 approved companies:
- Google (google)
- Amazon (amazon)
- Microsoft (microsoft)
- Meta (meta)
- Apple (apple)
- Netflix (netflix)
- Adobe (adobe)
- IBM (ibm)
- Oracle (oracle)
- Infosys (infosys)

Preserves:
- All 10 approved companies and their original IDs
- All roles, interviews, questions, states, reports, answers, evaluations belonging to approved companies
- All users, candidate profiles, resumes, resume profiles
- All unrelated records

Performs all deletions inside a SINGLE TRANSACTION with strict pre- and post-validation checks.
Rolls back immediately if any check fails or any error is encountered.
"""

import asyncio
import logging
import sys
from typing import List, Set, Tuple

from sqlalchemy import text
from app.core.database import AsyncSessionLocal

# Suppress verbose engine logging for cleaner CLI output
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

APPROVED_SLUGS: List[str] = [
    "adobe",
    "amazon",
    "apple",
    "google",
    "ibm",
    "infosys",
    "meta",
    "microsoft",
    "netflix",
    "oracle",
]

EXPECTED_APPROVED_COUNT = 10


async def cleanup_database(dry_run: bool = False) -> bool:
    print("=" * 70)
    print("DATABASE CLEANUP PROCESS INITIALIZATION")
    print("=" * 70)

    async with AsyncSessionLocal() as session:
        # Start a single explicit transaction
        async with session.begin():
            print("\n[STEP 1] Validating Approved Companies Existence...")

            res = await session.execute(
                text("SELECT id, name, slug FROM companies WHERE slug = ANY(:slugs) ORDER BY slug"),
                {"slugs": APPROVED_SLUGS}
            )
            approved_records = res.fetchall()
            found_slugs = {r.slug: (r.id, r.name) for r in approved_records}

            missing_slugs = set(APPROVED_SLUGS) - set(found_slugs.keys())
            if missing_slugs:
                print(f"\n[ERROR] CRITICAL: Missing approved companies: {sorted(list(missing_slugs))}")
                print("[ERROR] Transaction will ROLLBACK. No changes made.")
                await session.rollback()
                return False

            if len(approved_records) != EXPECTED_APPROVED_COUNT:
                print(f"\n[ERROR] Expected {EXPECTED_APPROVED_COUNT} approved companies, but found {len(approved_records)}.")
                await session.rollback()
                return False

            print("[OK] All 10 approved companies verified:")
            for slug in sorted(APPROVED_SLUGS):
                cid, cname = found_slugs[slug]
                print(f"   - {slug:<12} (ID: {cid:<5}, Name: '{cname}')")

            approved_company_ids = [r.id for r in approved_records]

            # ----------------------------------------------------
            # STEP 2: Pre-calculation & Dependency Tracing
            # ----------------------------------------------------
            print("\n[STEP 2] Tracing Dependency Graph & Calculating Records To Delete...")

            # 1. Total companies
            total_companies_before = (await session.execute(text("SELECT COUNT(*) FROM companies"))).scalar()

            # 2. Unwanted companies
            res = await session.execute(
                text("SELECT id, name, slug FROM companies WHERE NOT (slug = ANY(:slugs))"),
                {"slugs": APPROVED_SLUGS}
            )
            unwanted_companies = res.fetchall()
            unwanted_company_ids = [c.id for c in unwanted_companies]
            unwanted_companies_count = len(unwanted_company_ids)

            print(f"   Total companies before:     {total_companies_before}")
            print(f"   Approved companies:         {len(approved_company_ids)}")
            print(f"   Unwanted companies to drop: {unwanted_companies_count}")

            if unwanted_companies_count == 0:
                print("\n[INFO] No unwanted companies found. Database is already clean.")
                return True

            # 3. Unwanted Roles (roles belonging to unwanted companies)
            res = await session.execute(
                text("SELECT id FROM roles WHERE company_id = ANY(:cids)"),
                {"cids": unwanted_company_ids}
            )
            unwanted_role_ids = [r.id for r in res.fetchall()]

            # 4. Unwanted Interviews (interviews belonging to unwanted companies OR unwanted roles)
            res = await session.execute(
                text("SELECT id FROM interviews WHERE company_id = ANY(:cids) OR role_id = ANY(:rids)"),
                {"cids": unwanted_company_ids, "rids": unwanted_role_ids if unwanted_role_ids else [-1]}
            )
            unwanted_interview_ids = [i.id for i in res.fetchall()]

            # 5. Unwanted Interview States
            res = await session.execute(
                text("SELECT id FROM interview_states WHERE interview_id = ANY(:iids)"),
                {"iids": unwanted_interview_ids if unwanted_interview_ids else [-1]}
            )
            unwanted_state_ids = [s.id for s in res.fetchall()]

            # 6. Unwanted Reports
            res = await session.execute(
                text("SELECT id FROM reports WHERE interview_id = ANY(:iids)"),
                {"iids": unwanted_interview_ids if unwanted_interview_ids else [-1]}
            )
            unwanted_report_ids = [r.id for r in res.fetchall()]

            # 7. Unwanted Usage Metrics
            res = await session.execute(
                text("SELECT id FROM usage_metrics WHERE interview_id = ANY(:iids)"),
                {"iids": unwanted_interview_ids if unwanted_interview_ids else [-1]}
            )
            unwanted_usage_metric_ids = [u.id for u in res.fetchall()]

            # 8. Unwanted Answers (answers from unwanted interviews)
            res = await session.execute(
                text("SELECT id FROM answers WHERE interview_id = ANY(:iids)"),
                {"iids": unwanted_interview_ids if unwanted_interview_ids else [-1]}
            )
            unwanted_answer_ids = [a.id for a in res.fetchall()]

            # 9. Unwanted Evaluations (evaluations for unwanted answers)
            res = await session.execute(
                text("SELECT id FROM evaluations WHERE answer_id = ANY(:aids)"),
                {"aids": unwanted_answer_ids if unwanted_answer_ids else [-1]}
            )
            unwanted_evaluation_ids = [e.id for e in res.fetchall()]

            # 10. Unwanted Questions (questions belonging to unwanted companies OR unwanted roles)
            res = await session.execute(
                text("SELECT id FROM questions WHERE company_id = ANY(:cids) OR role_id = ANY(:rids)"),
                {"cids": unwanted_company_ids, "rids": unwanted_role_ids if unwanted_role_ids else [-1]}
            )
            unwanted_question_ids = [q.id for q in res.fetchall()]

            # 11. Safety Check: Verify no answers in APPROVED interviews reference unwanted questions
            res = await session.execute(
                text("""
                    SELECT COUNT(*) FROM answers 
                    WHERE (NOT (interview_id = ANY(:iids))) AND (question_id = ANY(:qids))
                """),
                {
                    "iids": unwanted_interview_ids if unwanted_interview_ids else [-1],
                    "qids": unwanted_question_ids if unwanted_question_ids else [-1]
                }
            )
            cross_q_conflicts = res.scalar()
            if cross_q_conflicts > 0:
                print(f"[ERROR] Found {cross_q_conflicts} answers in approved interviews referencing questions marked for deletion!")
                print("[ERROR] Aborting transaction to prevent foreign key violation or data loss.")
                await session.rollback()
                return False

            # 12. Unwanted Sources (sources belonging to unwanted companies OR unwanted roles)
            res = await session.execute(
                text("SELECT id FROM sources WHERE company_id = ANY(:cids) OR role_id = ANY(:rids)"),
                {"cids": unwanted_company_ids, "rids": unwanted_role_ids if unwanted_role_ids else [-1]}
            )
            unwanted_source_ids = [s.id for s in res.fetchall()]

            # 13. Unwanted Documents
            res = await session.execute(
                text("SELECT id FROM documents WHERE source_id = ANY(:sids)"),
                {"sids": unwanted_source_ids if unwanted_source_ids else [-1]}
            )
            unwanted_doc_ids = [d.id for d in res.fetchall()]

            # 14. Unwanted Document Chunks
            res = await session.execute(
                text("SELECT id FROM document_chunks WHERE document_id = ANY(:dids)"),
                {"dids": unwanted_doc_ids if unwanted_doc_ids else [-1]}
            )
            unwanted_chunk_ids = [c.id for c in res.fetchall()]

            # Display exact deletion plan
            print("\n" + "-" * 50)
            print("DELETION PLAN BREAKDOWN (TARGET RECORD COUNTS):")
            print("-" * 50)
            print(f"  1.  document_chunks:  {len(unwanted_chunk_ids):>6} records")
            print(f"  2.  documents:        {len(unwanted_doc_ids):>6} records")
            print(f"  3.  sources:          {len(unwanted_source_ids):>6} records")
            print(f"  4.  evaluations:      {len(unwanted_evaluation_ids):>6} records")
            print(f"  5.  answers:          {len(unwanted_answer_ids):>6} records")
            print(f"  6.  interview_states: {len(unwanted_state_ids):>6} records")
            print(f"  7.  reports:          {len(unwanted_report_ids):>6} records")
            print(f"  8.  usage_metrics:    {len(unwanted_usage_metric_ids):>6} records")
            print(f"  9.  interviews:       {len(unwanted_interview_ids):>6} records")
            print(f"  10. questions:        {len(unwanted_question_ids):>6} records")
            print(f"  11. roles:            {len(unwanted_role_ids):>6} records")
            print(f"  12. companies:        {len(unwanted_company_ids):>6} records")
            print("-" * 50)

            if dry_run:
                print("\n[DRY RUN] Dry run requested. Rolling back transaction without executing deletions.")
                await session.rollback()
                return True

            # ----------------------------------------------------
            # STEP 3: Dependency-Safe Deletions in Exact Order
            # ----------------------------------------------------
            print("\n[STEP 3] Executing Dependency-Safe Deletions in Exact Order...")

            # 1. document_chunks
            if unwanted_chunk_ids:
                res = await session.execute(
                    text("DELETE FROM document_chunks WHERE id = ANY(:ids)"),
                    {"ids": unwanted_chunk_ids}
                )
                print(f"   [DELETED] document_chunks:  {res.rowcount} rows")

            # 2. documents
            if unwanted_doc_ids:
                res = await session.execute(
                    text("DELETE FROM documents WHERE id = ANY(:ids)"),
                    {"ids": unwanted_doc_ids}
                )
                print(f"   [DELETED] documents:        {res.rowcount} rows")

            # 3. sources
            if unwanted_source_ids:
                res = await session.execute(
                    text("DELETE FROM sources WHERE id = ANY(:ids)"),
                    {"ids": unwanted_source_ids}
                )
                print(f"   [DELETED] sources:          {res.rowcount} rows")

            # 4. evaluations
            if unwanted_evaluation_ids:
                res = await session.execute(
                    text("DELETE FROM evaluations WHERE id = ANY(:ids)"),
                    {"ids": unwanted_evaluation_ids}
                )
                print(f"   [DELETED] evaluations:      {res.rowcount} rows")

            # 5. answers
            if unwanted_answer_ids:
                res = await session.execute(
                    text("DELETE FROM answers WHERE id = ANY(:ids)"),
                    {"ids": unwanted_answer_ids}
                )
                print(f"   [DELETED] answers:          {res.rowcount} rows")

            # 6. interview_states
            if unwanted_state_ids:
                res = await session.execute(
                    text("DELETE FROM interview_states WHERE id = ANY(:ids)"),
                    {"ids": unwanted_state_ids}
                )
                print(f"   [DELETED] interview_states: {res.rowcount} rows")

            # 7. reports
            if unwanted_report_ids:
                res = await session.execute(
                    text("DELETE FROM reports WHERE id = ANY(:ids)"),
                    {"ids": unwanted_report_ids}
                )
                print(f"   [DELETED] reports:          {res.rowcount} rows")

            # 8. usage_metrics
            if unwanted_usage_metric_ids:
                res = await session.execute(
                    text("DELETE FROM usage_metrics WHERE id = ANY(:ids)"),
                    {"ids": unwanted_usage_metric_ids}
                )
                print(f"   [DELETED] usage_metrics:    {res.rowcount} rows")

            # 9. interviews
            if unwanted_interview_ids:
                res = await session.execute(
                    text("DELETE FROM interviews WHERE id = ANY(:ids)"),
                    {"ids": unwanted_interview_ids}
                )
                print(f"   [DELETED] interviews:       {res.rowcount} rows")

            # 10. questions
            if unwanted_question_ids:
                res = await session.execute(
                    text("DELETE FROM questions WHERE id = ANY(:ids)"),
                    {"ids": unwanted_question_ids}
                )
                print(f"   [DELETED] questions:        {res.rowcount} rows")

            # 11. roles
            if unwanted_role_ids:
                res = await session.execute(
                    text("DELETE FROM roles WHERE id = ANY(:ids)"),
                    {"ids": unwanted_role_ids}
                )
                print(f"   [DELETED] roles:            {res.rowcount} rows")

            # 12. companies
            if unwanted_company_ids:
                res = await session.execute(
                    text("DELETE FROM companies WHERE id = ANY(:ids)"),
                    {"ids": unwanted_company_ids}
                )
                print(f"   [DELETED] companies:        {res.rowcount} rows")

            # ----------------------------------------------------
            # STEP 4: Comprehensive In-Transaction Integrity Verification
            # ----------------------------------------------------
            print("\n[STEP 4] Running Post-Deletion Integrity Verifications...")

            # 4.1 Check companies count == 10
            comp_count = (await session.execute(text("SELECT COUNT(*) FROM companies"))).scalar()
            if comp_count != EXPECTED_APPROVED_COUNT:
                print(f"[ERROR] Verification failed: Total companies is {comp_count}, expected {EXPECTED_APPROVED_COUNT}!")
                await session.rollback()
                return False
            print("   [PASS] Total companies count is exactly 10")

            # 4.2 Check exact slugs
            res = await session.execute(text("SELECT slug FROM companies ORDER BY slug"))
            remaining_slugs = [r.slug for r in res.fetchall()]
            if remaining_slugs != sorted(APPROVED_SLUGS):
                print(f"[ERROR] Verification failed: Remaining slugs do not match approved list!")
                print(f"        Got:      {remaining_slugs}")
                print(f"        Expected: {sorted(APPROVED_SLUGS)}")
                await session.rollback()
                return False
            print("   [PASS] Exactly 10 approved slugs match approved list")

            # 4.3 Check ZERO unwanted companies exist
            unwanted_remaining = (await session.execute(
                text("SELECT COUNT(*) FROM companies WHERE NOT (slug = ANY(:slugs))"),
                {"slugs": APPROVED_SLUGS}
            )).scalar()
            if unwanted_remaining != 0:
                print(f"[ERROR] Verification failed: {unwanted_remaining} unwanted companies remain!")
                await session.rollback()
                return False
            print("   [PASS] ZERO unwanted companies remain")

            # 4.4 Verify no orphan foreign keys remain pointing to missing records
            # Check roles -> companies
            orphan_roles = (await session.execute(
                text("SELECT COUNT(*) FROM roles r LEFT JOIN companies c ON c.id = r.company_id WHERE c.id IS NULL")
            )).scalar()
            if orphan_roles > 0:
                print(f"[ERROR] Orphan roles found: {orphan_roles}")
                await session.rollback()
                return False

            # Check interviews -> companies / roles
            orphan_interviews = (await session.execute(
                text("""
                    SELECT COUNT(*) FROM interviews i 
                    LEFT JOIN companies c ON c.id = i.company_id 
                    LEFT JOIN roles r ON r.id = i.role_id 
                    WHERE c.id IS NULL OR r.id IS NULL
                """)
            )).scalar()
            if orphan_interviews > 0:
                print(f"[ERROR] Orphan interviews found: {orphan_interviews}")
                await session.rollback()
                return False

            # Check questions -> companies / roles
            orphan_questions = (await session.execute(
                text("""
                    SELECT COUNT(*) FROM questions q 
                    LEFT JOIN companies c ON c.id = q.company_id 
                    LEFT JOIN roles r ON r.id = q.role_id 
                    WHERE (q.company_id IS NOT NULL AND c.id IS NULL) 
                       OR (q.role_id IS NOT NULL AND r.id IS NULL)
                """)
            )).scalar()
            if orphan_questions > 0:
                print(f"[ERROR] Orphan questions found: {orphan_questions}")
                await session.rollback()
                return False

            # Check sources -> companies / roles
            orphan_sources = (await session.execute(
                text("""
                    SELECT COUNT(*) FROM sources s 
                    LEFT JOIN companies c ON c.id = s.company_id 
                    LEFT JOIN roles r ON r.id = s.role_id 
                    WHERE (s.company_id IS NOT NULL AND c.id IS NULL) 
                       OR (s.role_id IS NOT NULL AND r.id IS NULL)
                """)
            )).scalar()
            if orphan_sources > 0:
                print(f"[ERROR] Orphan sources found: {orphan_sources}")
                await session.rollback()
                return False

            # Check documents -> sources
            orphan_documents = (await session.execute(
                text("SELECT COUNT(*) FROM documents d LEFT JOIN sources s ON s.id = d.source_id WHERE s.id IS NULL")
            )).scalar()
            if orphan_documents > 0:
                print(f"[ERROR] Orphan documents found: {orphan_documents}")
                await session.rollback()
                return False

            # Check document_chunks -> documents
            orphan_chunks = (await session.execute(
                text("SELECT COUNT(*) FROM document_chunks dc LEFT JOIN documents d ON d.id = dc.document_id WHERE d.id IS NULL")
            )).scalar()
            if orphan_chunks > 0:
                print(f"[ERROR] Orphan document chunks found: {orphan_chunks}")
                await session.rollback()
                return False

            # Check answers -> interviews / questions
            orphan_answers = (await session.execute(
                text("""
                    SELECT COUNT(*) FROM answers a 
                    LEFT JOIN interviews i ON i.id = a.interview_id 
                    LEFT JOIN questions q ON q.id = a.question_id 
                    WHERE i.id IS NULL OR q.id IS NULL
                """)
            )).scalar()
            if orphan_answers > 0:
                print(f"[ERROR] Orphan answers found: {orphan_answers}")
                await session.rollback()
                return False

            # Check interview_states -> interviews
            orphan_states = (await session.execute(
                text("SELECT COUNT(*) FROM interview_states ist LEFT JOIN interviews i ON i.id = ist.interview_id WHERE i.id IS NULL")
            )).scalar()
            if orphan_states > 0:
                print(f"[ERROR] Orphan interview states found: {orphan_states}")
                await session.rollback()
                return False

            # Check reports -> interviews
            orphan_reports = (await session.execute(
                text("SELECT COUNT(*) FROM reports rep LEFT JOIN interviews i ON i.id = rep.interview_id WHERE i.id IS NULL")
            )).scalar()
            if orphan_reports > 0:
                print(f"[ERROR] Orphan reports found: {orphan_reports}")
                await session.rollback()
                return False

            # Check evaluations -> answers
            orphan_evaluations = (await session.execute(
                text("SELECT COUNT(*) FROM evaluations ev LEFT JOIN answers a ON a.id = ev.answer_id WHERE a.id IS NULL")
            )).scalar()
            if orphan_evaluations > 0:
                print(f"[ERROR] Orphan evaluations found: {orphan_evaluations}")
                await session.rollback()
                return False

            # Check approved company IDs unchanged
            res = await session.execute(
                text("SELECT id, name, slug FROM companies ORDER BY id")
            )
            final_approved_records = res.fetchall()
            for r in final_approved_records:
                orig_id, orig_name = found_slugs[r.slug]
                if r.id != orig_id or r.name != orig_name:
                    print(f"[ERROR] Approved company record mutated: expected ({orig_id}, {orig_name}), got ({r.id}, {r.name})")
                    await session.rollback()
                    return False

            print("   [PASS] All foreign-key relationships and integrity checks passed with ZERO orphans")
            print("   [PASS] Approved companies preserved with identical IDs and names")

            # ----------------------------------------------------
            # STEP 5: COMMIT
            # ----------------------------------------------------
            print("\n[STEP 5] All verifications passed. Committing transaction...")
            await session.commit()
            print("[OK] Transaction committed successfully.")

            # ----------------------------------------------------
            # STEP 6: Final Summary Display
            # ----------------------------------------------------
            print("\n" + "=" * 70)
            print("CLEANUP SUCCESSFUL")
            print("=" * 70)
            print(f"Companies before:             {total_companies_before}")
            print(f"Approved companies preserved: {len(final_approved_records)}")
            print(f"Unwanted companies deleted:   {unwanted_companies_count}")
            print("\nPreserved 10 Companies (IDs & Slugs):")
            print("-" * 50)
            for r in final_approved_records:
                print(f"  ID: {r.id:<5} | Slug: {r.slug:<12} | Name: {r.name}")
            print("-" * 50)

            print("\nSummary of deleted records by table:")
            print("-" * 50)
            print(f"  - document_chunks:  {len(unwanted_chunk_ids):>6} deleted")
            print(f"  - documents:        {len(unwanted_doc_ids):>6} deleted")
            print(f"  - sources:          {len(unwanted_source_ids):>6} deleted")
            print(f"  - evaluations:      {len(unwanted_evaluation_ids):>6} deleted")
            print(f"  - answers:          {len(unwanted_answer_ids):>6} deleted")
            print(f"  - interview_states: {len(unwanted_state_ids):>6} deleted")
            print(f"  - reports:          {len(unwanted_report_ids):>6} deleted")
            print(f"  - usage_metrics:    {len(unwanted_usage_metric_ids):>6} deleted")
            print(f"  - interviews:       {len(unwanted_interview_ids):>6} deleted")
            print(f"  - questions:        {len(unwanted_question_ids):>6} deleted")
            print(f"  - roles:            {len(unwanted_role_ids):>6} deleted")
            print(f"  - companies:        {len(unwanted_company_ids):>6} deleted")
            print("-" * 50)

            return True


async def main():
    dry_run = "--dry-run" in sys.argv
    try:
        success = await cleanup_database(dry_run=dry_run)
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL ERROR] An unexpected exception occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
