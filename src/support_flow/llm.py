"""LLM access behind one tiny interface (Anthropic Messages API shape).

ClaudeClient    real calls via HTTPS (stdlib only, no SDK). NOT executed in the sandbox this repo was written in
                (no API key); its request building and error handling are unit-tested with a fake transport.
OfflineClient   deterministic keyword stand-in so the workflow, policy and tests run without network. It is NOT
                a model and its accuracy says nothing about Claude's.
"""
from __future__ import annotations

import json, os, re, time, urllib.error, urllib.request
from dataclasses import dataclass
from typing import Callable, Protocol

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.environ.get("SUPPORT_FLOW_MODEL", "claude-sonnet-5-5")


class LLMError(RuntimeError):
    pass


@dataclass
class Response:
    content: list[dict]      # Anthropic-style blocks: {"type": "text"|"tool_use", ...}
    stop_reason: str = "end_turn"

    def tool_uses(self) -> list[dict]:
        return [b for b in self.content if b.get("type") == "tool_use"]


class LLM(Protocol):
    def complete(self, system: str, messages: list[dict], tools: list[dict], tool_choice: dict | None = None) -> Response: ...


class ClaudeClient:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL, max_tokens: int = 1024,
                 timeout: float = 30.0, retries: int = 3, transport: Callable[[urllib.request.Request, float], bytes] | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key and transport is None:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.model, self.max_tokens, self.timeout, self.retries = model, max_tokens, timeout, retries
        self._transport = transport or self._http
        self._sleep = sleep

    @staticmethod
    def _http(req: urllib.request.Request, timeout: float) -> bytes:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()

    def build_payload(self, system, messages, tools, tool_choice) -> dict:
        p = {"model": self.model, "max_tokens": self.max_tokens, "system": system, "messages": messages}
        if tools:
            p["tools"] = tools
        if tool_choice:
            p["tool_choice"] = tool_choice
        return p

    def complete(self, system, messages, tools=(), tool_choice=None) -> Response:
        payload = json.dumps(self.build_payload(system, messages, list(tools), tool_choice)).encode()
        headers = {"content-type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": self.api_key or ""}
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                raw = self._transport(urllib.request.Request(API_URL, data=payload, headers=headers, method="POST"), self.timeout)
                data = json.loads(raw)
                return Response(data["content"], data.get("stop_reason", "end_turn"))
            except urllib.error.HTTPError as e:
                if e.code not in (408, 429, 500, 502, 503, 529):   # retry only transient errors
                    raise LLMError(f"HTTP {e.code}") from e
                last = e
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as e:
                last = e
            self._sleep(min(2 ** attempt, 8))
        raise LLMError(f"LLM call failed after {self.retries} attempts: {last!r}")


class OfflineClient:
    """Keyword heuristics speaking the same protocol. Deterministic; used for demos and tests."""
    _REFUND = re.compile(r"\b(refund|money back|chargeback|reimburse|credit back)\b", re.I)
    _CATS = [("security", r"hacked|unauthori[sz]ed|breach|phish|compromised|stolen"),
             ("account_access", r"password|log ?in|locked out|2fa|can'?t sign"),
             ("shipping", r"deliver|shipping|package|tracking|arrived|late"),
             ("billing", r"charged|invoice|billing|double|payment"),
             ("technical", r"error|crash|bug|not working|broken|fails?|down"),
             ("product_question", r"how (do|can)|does it|can i|\?")]

    def complete(self, system, messages, tools=(), tool_choice=None) -> Response:
        name = (tool_choice or {}).get("name")
        text = messages[0]["content"] if isinstance(messages[0]["content"], str) else ""
        if name == "record_triage":
            return Response([{"type": "tool_use", "id": "t1", "name": name, "input": self._triage(text)}], "tool_use")
        return self._draft(messages)

    def _triage(self, text: str) -> dict:
        t = text.lower()
        refund = bool(self._REFUND.search(t))
        cat = "refund" if refund else next((c for c, p in self._CATS if re.search(p, t)), "other")
        pri = "P1" if cat == "security" or re.search(r"\b(outage|urgent|production|cannot work)\b", t) else \
              "P2" if re.search(r"\b(asap|angry|unacceptable|third time)\b", t) else "P4" if cat == "product_question" else "P3"
        amt = re.search(r"\$\s?(\d+(?:\.\d{1,2})?)", t)
        angry = bool(re.search(r"unacceptable|furious|angry|terrible|worst", t))
        return {"category": cat, "priority": pri, "sentiment": "angry" if angry else "neutral", "refund_requested": refund,
                "refund_amount": float(amt.group(1)) if (amt and refund) else None, "confidence": 0.9 if cat != "other" else 0.5,
                "summary": text.strip().splitlines()[-1][:200] if text.strip() else "empty",
                "injection_suspected": bool(re.search(r"ignore (all|previous)|system prompt|you are now", t))}

    def _draft(self, messages) -> Response:
        last = messages[-1]
        if last["role"] == "user" and isinstance(last["content"], list):   # got tool results -> write the reply
            results = " ".join(str(b.get("content", "")) for b in last["content"])
            body = "Thanks for contacting us. " + (f"Here is what I found: {results[:300]} " if results.strip() else "") + \
                   "Let us know if there is anything else we can help with."
            return Response([{"type": "tool_use", "id": "r1", "name": "submit_reply",
                              "input": {"subject": "Re: your support request", "body": body}}], "tool_use")
        return Response([{"type": "tool_use", "id": "k1", "name": "search_kb", "input": {"query": str(messages[0]["content"])[:200]}}], "tool_use")
