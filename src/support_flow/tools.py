"""Tools the drafting step may call (the 'augmented LLM': retrieval + lookups). Read-only by design:
nothing here can refund, send mail or change data; side effects happen only in code after the policy gate."""
from __future__ import annotations
import json, re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent.parent / "data"


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


class Tools:
    def __init__(self, kb: list[dict] | None = None, orders: dict | None = None):
        self.kb = kb if kb is not None else json.loads((DATA / "kb.json").read_text())
        self.orders = orders if orders is not None else json.loads((DATA / "orders.json").read_text())

    def lookup_order(self, order_id: str) -> dict:
        return self.orders.get(order_id) or {"error": f"order {order_id!r} not found"}

    def search_kb(self, query: str) -> list[dict]:
        q = _words(query)
        scored = sorted(((len(q & _words(a["title"] + " " + a["text"])), a) for a in self.kb), key=lambda x: -x[0])
        return [{"title": a["title"], "text": a["text"]} for s, a in scored[:3] if s > 0]

    def call(self, name: str, args: dict):
        if name == "lookup_order":
            return self.lookup_order(str(args.get("order_id", "")))
        if name == "search_kb":
            return self.search_kb(str(args.get("query", "")))
        raise ValueError(f"unknown tool {name!r}")
