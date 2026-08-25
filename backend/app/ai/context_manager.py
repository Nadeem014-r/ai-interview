"""Phase 8: Context & Token Budget Management.

Enforces context window boundaries, reserves output token budgets,
and provides deterministic, prioritized truncation so critical system/security instructions
are never dropped.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from app.core.config import settings
from app.ai.token_counter import estimate_tokens
from app.ai.exceptions import AIContextLimitError


@dataclass
class PromptSection:
    name: str
    content: str
    priority: int  # 1 (highest - system/security) to 5 (lowest - optional background)
    allow_truncation: bool = False


class ContextManager:
    """Manages prompt budgeting and prioritized context truncation."""

    def __init__(
        self,
        max_input_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        context_window_limit: Optional[int] = None,
    ):
        self.max_input_tokens = max_input_tokens or settings.LLM_MAX_INPUT_TOKENS
        self.max_output_tokens = max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS
        self.context_window_limit = context_window_limit or settings.LLM_CONTEXT_WINDOW_LIMIT

    def calculate_available_input_budget(self, reserved_output_tokens: Optional[int] = None) -> int:
        """Calculate maximum allowable tokens for prompt given the output reserve."""
        output_reserve = reserved_output_tokens or self.max_output_tokens
        budget_by_window = self.context_window_limit - output_reserve
        return max(100, min(self.max_input_tokens, budget_by_window))

    def validate_and_fit_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        reserved_output_tokens: Optional[int] = None,
        raise_on_overflow: bool = False
    ) -> str:
        """
        Validate prompt token count against input budget.
        If prompt exceeds budget and raise_on_overflow is True, raises AIContextLimitError.
        Otherwise, safely truncates low-priority portions while preserving instructions.
        """
        budget = self.calculate_available_input_budget(reserved_output_tokens)
        sys_tokens = estimate_tokens(system_prompt) if system_prompt else 0
        prompt_tokens = estimate_tokens(prompt)
        total_tokens = sys_tokens + prompt_tokens

        if total_tokens <= budget:
            return prompt

        if raise_on_overflow:
            raise AIContextLimitError(
                f"Prompt total tokens ({total_tokens}) exceeds maximum input budget ({budget})."
            )

        # Truncate prompt text to fit available budget for prompt
        available_for_prompt = max(50, budget - sys_tokens)
        # Approximate characters: available_for_prompt * 4
        char_limit = available_for_prompt * 4
        if len(prompt) > char_limit:
            return prompt[:char_limit] + "\n...[Context truncated to fit token budget]"
        return prompt

    @staticmethod
    def assemble_prioritized_context(
        sections: List[PromptSection],
        max_total_tokens: int
    ) -> str:
        """
        Assemble prompt sections ordered by priority.
        Sections with allow_truncation=True are truncated first if total budget is exceeded.
        """
        # Sort sections by priority (1 = highest priority)
        sorted_sections = sorted(sections, key=lambda s: s.priority)
        
        # Calculate tokens for non-truncatable sections first
        fixed_tokens = sum(
            estimate_tokens(s.content) for s in sorted_sections if not s.allow_truncation
        )
        
        if fixed_tokens > max_total_tokens:
            raise AIContextLimitError(
                f"Non-truncatable core instructions ({fixed_tokens} tokens) exceed total budget ({max_total_tokens})."
            )

        remaining_budget = max_total_tokens - fixed_tokens
        assembled_parts: List[str] = []

        for section in sorted_sections:
            if not section.content.strip():
                continue

            sec_tokens = estimate_tokens(section.content)
            if not section.allow_truncation:
                assembled_parts.append(section.content)
            else:
                if sec_tokens <= remaining_budget:
                    assembled_parts.append(section.content)
                    remaining_budget -= sec_tokens
                elif remaining_budget > 20:
                    # Truncate this section to fit remaining budget
                    char_limit = remaining_budget * 4
                    truncated = section.content[:char_limit] + "\n...[Remaining context truncated]"
                    assembled_parts.append(truncated)
                    remaining_budget = 0
                else:
                    # No budget left for this low priority section
                    continue

        return "\n\n".join(assembled_parts)
