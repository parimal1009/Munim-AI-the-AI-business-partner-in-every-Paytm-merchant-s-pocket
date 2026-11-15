import { Card } from "../components/ui";

const DEMO = [
  ["WhatsApp reminders", "Customer Phone simulator + wa.me deep link", "WhatsApp Business API (Cloud) with approved templates and delivery receipts"],
  ["Paytm payment link", "Working mock pay page; payment marks udhaar recovered and updates ROI live", "Paytm Payment Gateway payment links + webhooks"],
  ["Soundbox briefing", "Soundbox-style audio player using Sarvam Bulbul TTS", "Push audio to Soundbox devices over Paytm's IoT channel"],
  ["Distributor orders", "Purchase order saved and message drafted", "Distributor APIs / marketplace with commission"],
  ["Data source", "Synthetic Paytm UPI data in Postgres (Neon)", "Paytm merchant transaction APIs with consent"],
  ["Peer benchmark", "Synthetic peer median", "Anonymised cohort analytics across Paytm merchants"],
  ["Memory and RAG", "LangGraph PostgresSaver checkpoints", "pgvector merchant memory and festival/seasonality knowledge"],
  ["Observability", "Structured logs, request IDs, persisted agent audit trail", "LangSmith tracing, PII-masked evals, per-merchant cost dashboards"],
];

const PHASES = [
  ["Hackathon MVP (today)", "Web app, 6 agents with approvals, Hindi voice, synthetic data"],
  ["Months 1-3", "WhatsApp Business API, Paytm PG links, 1,000-merchant Pune pilot"],
  ["Months 3-6", "Soundbox voice briefings, more languages, distributor integrations"],
  ["Months 6-12", "Vertical packs (restaurants, pharmacies, salons), peer benchmarking, credit-scoring signals"],
];

export default function Roadmap() {
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-paytm-navy">Roadmap: from demo to production</h1>
      <Card>
        <h2 className="mb-3 font-semibold">What is simulated today, and what replaces it</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-slate-500"><th className="py-1">Capability</th><th>In this demo</th><th>In production</th></tr></thead>
            <tbody>{DEMO.map(([a, b, c]) => <tr key={a} className="border-t align-top"><td className="py-2 pr-3 font-medium">{a}</td><td className="pr-3">{b}</td><td>{c}</td></tr>)}</tbody>
          </table>
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        {PHASES.map(([t, d]) => <Card key={t}><div className="font-semibold text-paytm-navy">{t}</div><p className="text-sm text-slate-600">{d}</p></Card>)}
      </div>
      <Card>
        <h2 className="mb-2 font-semibold">Responsible AI, already built in</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
          <li>The merchant approves every action. The LLM can only propose; a LangGraph interrupt gates execution.</li>
          <li>All numbers come from SQL and Python services, never from the model.</li>
          <li>Merchant ID comes from the signed token, never from model output. Text-to-SQL is read-only, view-scoped and AST-validated.</li>
          <li>Phone numbers are masked before text reaches the LLM. Actions are idempotent, so a double tap never sends or pays twice.</li>
          <li>Every agent step is persisted for audit and shown live in the trace panel.</li>
        </ul>
      </Card>
    </div>
  );
}
