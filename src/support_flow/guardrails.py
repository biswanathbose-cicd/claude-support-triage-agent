"""Checks on a drafted reply before anything is sent. Cheap, deterministic, testable."""
from __future__ import annotations
import re

PROMISE = re.compile(r"\b(we (have|'ve) (issued|processed|approved)|your refund (has been|is) (issued|processed|approved)|"
                     r"i (have|'ve) (refunded|credited)|guarantee(d)? (a )?refund)\b", re.I)
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
SECRET = re.compile(r"(api[_-]?key|password\s*[:=]|sk-[A-Za-z0-9]{10,})", re.I)
MAX_LEN = 2000


def check_reply(subject: str, body: str, *, refund_approved: bool = False) -> list[str]:
    problems = []
    if not subject.strip() or not body.strip():
        problems.append("empty_reply")
    if len(body) > MAX_LEN:
        problems.append("too_long")
    if CARD.search(body):
        problems.append("card_number_in_reply")
    if SECRET.search(body):
        problems.append("secret_in_reply")
    if not refund_approved and PROMISE.search(body):
        problems.append("unapproved_refund_promise")
    return problems
