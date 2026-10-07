"""Demo CLI (offline stand-in model unless ANTHROPIC_API_KEY is set and --live is passed).
  python -m support_flow.cli process --db demo.db --from alice@x.com --subject "..." --body "..." [--live]
  python -m support_flow.cli queue --db demo.db
  python -m support_flow.cli approve --db demo.db TICKET_ID --reviewer me [--refund-approved]
"""
from __future__ import annotations
import argparse, uuid

from .llm import ClaudeClient, OfflineClient
from .mailer import Outbox
from .schemas import Ticket
from .store import Store
from .workflow import SupportWorkflow


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("process"); p.add_argument("--db", default="support.db"); p.add_argument("--live", action="store_true")
    p.add_argument("--from", dest="sender", required=True); p.add_argument("--subject", required=True); p.add_argument("--body", required=True)
    p.add_argument("--order-id")
    q = sub.add_parser("queue"); q.add_argument("--db", default="support.db")
    a = sub.add_parser("approve"); a.add_argument("--db", default="support.db"); a.add_argument("ticket_id"); a.add_argument("--reviewer", required=True)
    a.add_argument("--refund-approved", action="store_true")
    r = sub.add_parser("reject"); r.add_argument("--db", default="support.db"); r.add_argument("ticket_id"); r.add_argument("--reviewer", required=True); r.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    wf = SupportWorkflow(ClaudeClient() if getattr(args, "live", False) else OfflineClient(), Outbox(), Store(args.db))
    if args.cmd == "process":
        o = wf.process(Ticket(uuid.uuid4().hex[:8], args.sender, args.subject, args.body, args.order_id))
        print(f"{o.ticket_id}: {o.status} (route={o.route}, reasons={list(o.reasons)})")
        if o.triage: print(f"  category={o.triage.category} priority={o.triage.priority} refund={o.triage.refund_requested}")
        if o.draft: print(f"  draft: {o.draft[1]}")
    elif args.cmd == "queue":
        for row in wf.store.pending():
            print(row["id"], row["subject"], row["reasons"])
    elif args.cmd == "approve":
        wf.approve(args.ticket_id, args.reviewer, refund_approved=args.refund_approved); print("approved")
    else:
        wf.reject(args.ticket_id, args.reviewer, args.reason); print("rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
