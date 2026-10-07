"""Golden-set evaluation. Offline stand-in by default; pass --live (needs ANTHROPIC_API_KEY) to measure Claude.
Reports triage accuracy and the safety invariant: refund tickets are never auto-sent."""
import json, sys
from pathlib import Path
from support_flow.llm import ClaudeClient, OfflineClient
from support_flow.mailer import Outbox
from support_flow.schemas import Ticket
from support_flow.store import Store
from support_flow.workflow import SupportWorkflow

live = "--live" in sys.argv
gold = json.loads((Path(__file__).parent / "golden.json").read_text())
wf = SupportWorkflow(ClaudeClient() if live else OfflineClient(), Outbox(), Store())
n = len(gold); cat = pri = ref = auto_refund = 0; misses = []
for i, g in enumerate(gold):
    o = wf.process(Ticket(f"g{i}", "c@x.com", g["s"], g["b"]))
    tri = o.triage
    cat += bool(tri and tri.category == g["cat"]); pri += bool(tri and tri.priority == g["pri"])
    ref += bool(tri and tri.refund_requested == g["refund"])
    sent = o.status == "sent"
    if g["refund"] and sent: auto_refund += 1; misses.append(("AUTO-SENT REFUND", g["s"]))
    if tri and tri.category != g["cat"]: misses.append((f"category {tri.category}!={g['cat']}", g["s"]))
res = {"model": "claude (live)" if live else "OfflineClient keyword stand-in (not a model)", "n": n,
       "category_acc": cat / n, "priority_acc": pri / n, "refund_flag_acc": ref / n,
       "refund_tickets_auto_sent": auto_refund, "misses": misses}
Path(__file__).parent.parent.joinpath("results", "eval_live.json" if live else "eval_offline.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))
