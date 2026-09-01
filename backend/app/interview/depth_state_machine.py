"""Module 4A: Depth-Aware (1-5) Interview State Machine.

Tracks:
  - current_depth: int (1=surface → 5=expert)
  - time_budget_phase: str (opening/core/design_behavioral/wrapup)
  - depth_history: List[int] — prevents erratic oscillation

Depth Branching Rules:
  - Score >= 8.0 → depth += 1 (cap at 5) → probe trade-offs, edge cases, failure modes
  - Score 5.0-7.9 → depth unchanged → standard contextual follow-up
  - Score < 5.0  → depth -= 1 (floor at 1) → hint or foundational transition

Time Phase Boundaries (% of total_duration_seconds):
  - opening:          0% - 15%   → background & resume deep-dive
  - core:            15% - 75%   → core technical probing & adaptive branching
  - design_behavioral: 75% - 90% → system design / behavioral / gap verification
  - wrapup:          90% - 100%  → wrap-up & candidate questions

Composable with existing AdaptiveStateMachine — call alongside, not instead of.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

logger = logging.getLogger("ai_interviewer.depth_state_machine")


class TimeBudgetPhase(str, Enum):
    OPENING = "opening"               # 0–15%: background & resume
    CORE = "core"                     # 15–75%: technical probing
    DESIGN_BEHAVIORAL = "design_behavioral"   # 75–90%: system design / behavioral
    WRAPUP = "wrapup"                 # 90–100%: wrap-up & candidate questions


# Phase boundaries as (min_pct_elapsed, max_pct_elapsed)
PHASE_BOUNDARIES: Dict[TimeBudgetPhase, Tuple[float, float]] = {
    TimeBudgetPhase.OPENING: (0.0, 0.15),
    TimeBudgetPhase.CORE: (0.15, 0.75),
    TimeBudgetPhase.DESIGN_BEHAVIORAL: (0.75, 0.90),
    TimeBudgetPhase.WRAPUP: (0.90, 1.0),
}

# Depth-to-probe-type mapping
DEPTH_PROBE_TYPES: Dict[int, str] = {
    1: "foundational_concept",
    2: "practical_implementation",
    3: "architectural_design",
    4: "trade_offs_and_failure_modes",
    5: "expert_scale_and_optimization",
}

DEPTH_LABELS: Dict[int, str] = {
    1: "Surface (Conceptual)",
    2: "Practical",
    3: "Architectural",
    4: "Expert Trade-offs",
    5: "Research/Optimization",
}


@dataclass
class QuestionDirective:
    """
    Structured instruction emitted by DepthStateMachine for the next question turn.
    Consumed by PersonaController to build the LLM prompt.
    """
    probe_type: str
    depth: int
    depth_label: str
    time_phase: str
    topic: str
    follow_up_hint: Optional[str] = None
    persona_note: Optional[str] = None
    should_transition_topic: bool = False
    transition_reason: Optional[str] = None


@dataclass
class DepthStateSnapshot:
    """Serializable snapshot of DepthStateMachine state for DB persistence."""
    current_depth: int = 1
    time_budget_phase: str = TimeBudgetPhase.OPENING.value
    depth_history: List[int] = field(default_factory=list)
    score_history: List[float] = field(default_factory=list)
    topic_turn_count: int = 0
    total_turns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_depth": self.current_depth,
            "time_budget_phase": self.time_budget_phase,
            "depth_history": self.depth_history,
            "score_history": self.score_history,
            "topic_turn_count": self.topic_turn_count,
            "total_turns": self.total_turns,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DepthStateSnapshot":
        return cls(
            current_depth=d.get("current_depth", 1),
            time_budget_phase=d.get("time_budget_phase", TimeBudgetPhase.OPENING.value),
            depth_history=d.get("depth_history", []),
            score_history=d.get("score_history", []),
            topic_turn_count=d.get("topic_turn_count", 0),
            total_turns=d.get("total_turns", 0),
        )


class DepthStateMachine:
    """
    Depth-aware (1–5) interview state machine with time-budget phase tracking.

    Designed for composition with the existing AdaptiveStateMachine:
        existing_result = AdaptiveStateMachine.determine_next_stage(...)
        depth_directive = depth_sm.update_and_get_directive(score, topic)
    """

    def __init__(self, snapshot: Optional[DepthStateSnapshot] = None):
        snap = snapshot or DepthStateSnapshot()
        self._depth: int = max(1, min(5, snap.current_depth))
        self._phase: TimeBudgetPhase = TimeBudgetPhase(
            snap.time_budget_phase
        ) if snap.time_budget_phase in [p.value for p in TimeBudgetPhase] else TimeBudgetPhase.OPENING
        self._depth_history: List[int] = list(snap.depth_history)
        self._score_history: List[float] = list(snap.score_history)
        self._topic_turn_count: int = snap.topic_turn_count
        self._total_turns: int = snap.total_turns

    # ── Public API ──────────────────────────────────────────────────────────

    def update_time_phase(
        self,
        elapsed_seconds: float,
        total_duration_seconds: float,
    ) -> TimeBudgetPhase:
        """
        Update the time budget phase based on elapsed proportion.
        Returns the new (or unchanged) phase.
        """
        if total_duration_seconds <= 0:
            return self._phase

        pct_elapsed = min(1.0, elapsed_seconds / total_duration_seconds)

        for phase, (lo, hi) in PHASE_BOUNDARIES.items():
            if lo <= pct_elapsed < hi:
                if self._phase != phase:
                    logger.info(
                        f"DepthSM: phase transition {self._phase.value} → {phase.value} "
                        f"at {pct_elapsed*100:.1f}% elapsed"
                    )
                    self._phase = phase
                return self._phase

        # > 90% elapsed
        self._phase = TimeBudgetPhase.WRAPUP
        return self._phase

    def update_depth(self, answer_score: float) -> int:
        """
        Apply depth branching rules based on the evaluated answer score.
        Anti-oscillation: depth changes by at most 1 per turn.

        Returns the new current_depth.
        """
        clamped = max(0.0, min(10.0, float(answer_score)))
        self._score_history.append(clamped)
        self._depth_history.append(self._depth)
        self._total_turns += 1
        self._topic_turn_count += 1

        if clamped >= 8.0:
            new_depth = min(5, self._depth + 1)
        elif clamped < 5.0:
            new_depth = max(1, self._depth - 1)
        else:
            new_depth = self._depth  # maintain

        if new_depth != self._depth:
            direction = "↑" if new_depth > self._depth else "↓"
            logger.debug(
                f"DepthSM: depth {direction} {self._depth} → {new_depth} "
                f"(score={clamped:.1f})"
            )
        self._depth = new_depth
        return self._depth

    def get_directive(
        self,
        topic: str,
        last_answer_text: Optional[str] = None,
        last_eval_dict: Optional[Dict[str, Any]] = None,
    ) -> QuestionDirective:
        """
        Get the next question directive based on current depth and phase.
        """
        probe_type = DEPTH_PROBE_TYPES.get(self._depth, "practical_implementation")
        depth_label = DEPTH_LABELS.get(self._depth, "Practical")

        follow_up_hint: Optional[str] = None
        persona_note: Optional[str] = None
        should_transition = False
        transition_reason: Optional[str] = None

        # Phase-specific overrides
        if self._phase == TimeBudgetPhase.OPENING:
            probe_type = "background_and_motivation"
            persona_note = "Keep it warm and welcoming. Focus on candidate background."
        elif self._phase == TimeBudgetPhase.DESIGN_BEHAVIORAL:
            if self._depth >= 3:
                probe_type = "system_design_or_behavioral"
                persona_note = "Ask a system design or behavioral question bridging their experience."
        elif self._phase == TimeBudgetPhase.WRAPUP:
            probe_type = "wrap_up"
            persona_note = "Wrap up gracefully. Invite candidate questions."
            should_transition = True
            transition_reason = "time_budget_wrapup"

        # Score-driven follow-up hints
        if last_eval_dict:
            missing = last_eval_dict.get("missing_concepts", [])
            misconceptions = last_eval_dict.get("misconceptions", [])
            if misconceptions:
                follow_up_hint = (
                    f"Candidate had a misconception about: {misconceptions[0]}. "
                    "Gently clarify without breaking character."
                )
            elif missing and self._depth >= 3:
                follow_up_hint = (
                    f"Candidate missed: {missing[0]}. Probe this missing concept "
                    "without giving away the answer."
                )

        # Depth-specific persona notes (if not already set by phase)
        if not persona_note:
            if self._depth <= 2:
                persona_note = "Be encouraging and clear. Foundational conceptual check."
            elif self._depth == 3:
                persona_note = "Neutral, technical tone. Ask about implementation choices."
            else:
                persona_note = (
                    "Challenging, peer-level tone. Expect deep reasoning about "
                    "trade-offs, failure modes, or optimization strategies."
                )

        return QuestionDirective(
            probe_type=probe_type,
            depth=self._depth,
            depth_label=depth_label,
            time_phase=self._phase.value,
            topic=topic,
            follow_up_hint=follow_up_hint,
            persona_note=persona_note,
            should_transition_topic=should_transition,
            transition_reason=transition_reason,
        )

    def reset_topic_turn_count(self) -> None:
        """Call when advancing to a new topic."""
        self._topic_turn_count = 0

    def get_snapshot(self) -> DepthStateSnapshot:
        """Get serializable state for DB persistence."""
        return DepthStateSnapshot(
            current_depth=self._depth,
            time_budget_phase=self._phase.value,
            depth_history=list(self._depth_history[-20:]),  # keep last 20 for memory efficiency
            score_history=list(self._score_history[-20:]),
            topic_turn_count=self._topic_turn_count,
            total_turns=self._total_turns,
        )

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def current_depth(self) -> int:
        return self._depth

    @property
    def current_phase(self) -> TimeBudgetPhase:
        return self._phase

    @property
    def average_score(self) -> float:
        if not self._score_history:
            return 5.0
        return round(sum(self._score_history) / len(self._score_history), 2)

    @property
    def total_turns(self) -> int:
        return self._total_turns
