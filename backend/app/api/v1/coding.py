from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/coding", tags=["Coding Sandbox & Evaluation"])


class CodeExecutionRequest(BaseModel):
    language: str  # python, javascript
    code: str
    test_cases: Optional[list[dict]] = []


# This route used to answer every request with "All test cases passed
# successfully!", 3/3 test cases and a 42ms runtime, without running a single
# line of the submitted code and without asking who was calling. Nothing in the
# platform executes candidate code: the coding workspace stores the submission
# as an ordinary interview answer and it is judged in the final evaluation.
# Reporting a pass that was never earned is worse than reporting nothing, so
# the route stays mounted -- an old client gets a clear answer instead of a
# confusing 404 -- and refuses.
@router.post("/execute", include_in_schema=False)
async def execute_code_sandbox(req: CodeExecutionRequest):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Code execution is not available. Submitted code is stored as an "
            "interview answer and assessed in the final evaluation; it is never run."
        ),
    )
