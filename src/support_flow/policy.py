"""Deterministic routing policy. The LLM *extracts*; this code *decides*. Because the decision is plain code
over validated fields (plus a regex backstop), text inside a ticket cannot talk its way past the refund gate."""
from __future__ import annotations
import re
from dataclasses import dataclass

from .schemas import Ticket, Triage

REFUND_BACKSTOP = re.compile(r"\b(refund|money back|chargeback|reimburse|credit back|dispute (the )?charge|cash (back|returned)|returned to my card|reverse (the|this) charge|reimburs\w*)\b", re.I)
MIN_CONFIDENCE = 0.7


@dataclass(frozen=True)
class Decision:
    route: str           # "auto_reply" | "human_review" | "escalate"
    reasons: tuple[str, ...]


def decide(ticket: Ticket, t: Triage) -> Decision:
    reasons = []
    if t.category == "security" or t.priority == "P1":
        reasons.append("security_or_p1")
    if t.refund_requested or t.category == "refund" or REFUND_BACKSTOP.search(ticket.subject + " " + ticket.body):
        reasons.append("refund_needs_human_approval")
    if t.confidence < MIN_CONFIDENCE:
        reasons.append("low_confidence")
    if t.injection_suspected:
        reasons.append("possible_prompt_injection")
    if t.sentiment == "angry":
        reasons.append("angry_customer")
    if "security_or_p1" in reasons:
        return Decision("escalate", tuple(reasons))
    return Decision("human_review" if reasons else "auto_reply", tuple(reasons))
