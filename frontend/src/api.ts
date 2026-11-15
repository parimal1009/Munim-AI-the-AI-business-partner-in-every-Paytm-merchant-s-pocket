// Typed API client. Base URL is relative (Vite proxy in dev); no secrets live in the bundle.
export type Lang = "hi" | "mr" | "ta" | "en";

export interface Merchant { id: number; name: string; owner_name: string; city: string; language: string }
export interface ActionItem {
  id: number; kind: string; title: string; reason: string; status: string;
  payload: Record<string, unknown>; result: Record<string, unknown> | null; created_at: string;
}
export interface Briefing {
  id: number; language: string; text: string; audio_url: string | null;
  facts: Record<string, unknown>; actions: ActionItem[];
}
export interface DaySummary { date: string; total_paise: number; txns: number; last_week_paise: number; pct_vs_last_week: number | null }
export interface Outcomes {
  days: number; recovered_paise: number; recovered_count: number; stockouts_prevented: number;
  customers_won_back: number; won_back_revenue_paise: number;
}
export interface Dashboard {
  yesterday: DaySummary;
  daily: { date: string; sales_paise: number; txns: number }[];
  top_products: { product: string; category: string; units: number; revenue_paise: number; profit_paise: number }[];
  peak_hours: { hour: number; txns: number; sales_paise: number }[];
  category_mix: { category: string; revenue_paise: number }[];
  peer: { own_daily_avg_paise: number; peer_median_daily_paise: number; pct_vs_peers: number; note: string };
  outcomes: Outcomes;
  khata: KhataSummary;
  stock_at_risk: number;
  lapsed: number;
  loan: Loan;
}
export interface KhataSummary { open_total_paise: number; overdue_total_paise: number; overdue_count: number; open_count: number; recovered_total_paise: number }
export interface KhataRow { khata_id: number; customer_id: number; name: string; amount_paise: number; note: string; days_pending: number; overdue: boolean; status: string }
export interface Loan {
  eligible: boolean; reason?: string; indicative_limit_paise?: number; avg_monthly_revenue_paise?: number;
  stability_score?: number; indicative_tenure_months?: number; note?: string;
}
export interface StockRow {
  product_id: number; name: string; category: string; stock_qty: number; avg_daily_units: number; days_of_cover: number | null; unit: string;
  price_paise: number; expiry_date: string | null; days_to_expiry: number | null; clearance_pct: number | null; selling_price_paise: number;
}
export interface ExpiringRow {
  product_id: number; name: string; unit: string; stock_qty: number; avg_daily_units: number; expiry_date: string; days_left: number;
  severity: "expired" | "critical" | "soon" | "watch"; units_at_risk: number; value_at_risk_paise: number;
  price_paise: number; suggested_discount_pct: number; clearance_pct: number | null; selling_price_paise: number;
}
export interface ReorderDraft { distributor_id: number; distributor_name: string; items: { product_id: number; name: string; qty: number; days_of_cover: number }[] }
export interface Campaign { id: number; name: string; offer_text: string; cashback_paise: number; targets: number; redeemed: number }
export interface Lapsed { customer_id: number; name: string; visits: number; days_absent: number; lifetime_paise: number }
export interface TrustAlert { type: string; severity: string; sale_id: number; amount_paise: number; at: string; reason: string }
export interface PhoneThread {
  phone: string; name: string;
  messages: { id: number; body: string; to_name: string; payment_link_id: string | null; link_status: string | null; created_at: string }[];
}
export interface PayInfo { id: string; merchant_name: string; customer_name: string; amount_paise: number; status: string; note: string }

export type StreamEvent =
  | { type: "start"; thread_id: string }
  | { type: "route"; agent: string; routed_to: string; language: string }
  | { type: "agent_start" | "agent_done" | "fallback" | "reply_ready"; agent: string; [k: string]: unknown }
  | { type: "tool_call"; agent: string; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; agent: string; tool: string; result: string }
  | { type: "approval_required"; agent: string; actions: ApprovalCard[] }
  | { type: "interrupt"; thread_id: string; actions: ApprovalCard[] }
  | { type: "approved" | "rejected"; agent: string; action_id: number; title: string }
  | { type: "final"; thread_id: string; reply: string; agent?: string; language: Lang }
  | { type: "clarify"; message: string }
  | { type: "error"; message: string }
  | { type: "done" };
export interface ApprovalCard { id: number; kind: string; title: string; reason: string }

export class ApiError extends Error {
  constructor(message: string, public status: number, public requestId?: string) {
    super(message);
  }
}

let token: string | null = localStorage.getItem("munim_token");
export const setToken = (t: string | null): void => {
  token = t;
  if (t) localStorage.setItem("munim_token", t);
  else localStorage.removeItem("munim_token");
};

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    return new ApiError(body?.error?.message ?? res.statusText, res.status, body?.error?.request_id);
  } catch {
    return new ApiError(res.statusText || "Request failed", res.status);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("content-type", "application/json");
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("munim-logout"));
  }
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

const post = <T,>(path: string, body?: unknown): Promise<T> =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  merchants: () => request<Merchant[]>("/api/merchants"),
  login: (merchant_id: number) => post<{ token: string; merchant: Merchant }>("/api/auth/demo-login", { merchant_id }),
  me: () => request<Merchant>("/api/me"),
  dashboard: () => request<Dashboard>("/api/dashboard"),
  briefing: (lang?: Lang) => request<Briefing>(`/api/briefing/today${lang ? `?lang=${lang}` : ""}`),
  regenBriefing: (lang?: Lang) => post<Briefing>(`/api/briefing/regenerate${lang ? `?lang=${lang}` : ""}`),
  actions: () => request<ActionItem[]>("/api/actions"),
  approve: (id: number) => post<ActionItem>(`/api/actions/${id}/approve`),
  reject: (id: number) => post<ActionItem>(`/api/actions/${id}/reject`),
  outcomes: (days = 7) => request<Outcomes>(`/api/outcomes?days=${days}`),
  khata: () => request<{ summary: KhataSummary; open: KhataRow[]; recovered: KhataRow[] }>("/api/khata"),
  addKhata: (b: { customer_name: string; phone: string; amount_rupees: number; note: string }) => post<{ khata_id: number }>("/api/khata/entries", b),
  inventory: () => request<{ products: StockRow[]; drafts: ReorderDraft[]; expiring: ExpiringRow[] }>("/api/inventory"),
  growth: () => request<{ stats: { active_30d: number; known_customers: number; lapsed: number }; lapsed: Lapsed[]; campaigns: Campaign[] }>("/api/growth"),
  simulate: (id: number) => post<{ redeemed: number; remaining: number }>(`/api/growth/campaigns/${id}/simulate-redemptions`),
  finance: () => request<{ forecast: { date: string; expected_paise: number }[]; loan: Loan; gst: { slabs: { rate: number; gross_paise: number; taxable_paise: number; tax_paise: number }[]; total_gst_paise: number; total_taxable_paise: number; days: number } }>("/api/finance"),
  trust: () => request<{ alerts: TrustAlert[] }>("/api/trust"),
  messages: () => request<PhoneThread[]>("/api/messages"),
  payInfo: (id: string) => request<PayInfo>(`/api/pay/${id}`),
  pay: (id: string) => post<PayInfo>(`/api/pay/${id}`),
  reset: () => post<{ status: string }>("/api/demo/reset"),
  speak: (text: string, language: Lang) => post<{ audio_url: string }>("/api/voice/speak", { text, language }),
  transcribe: async (blob: Blob, language: string): Promise<{ text: string; language: string }> => {
    const fd = new FormData();
    fd.append("audio", blob, "voice.webm");
    fd.append("language", language);
    return request("/api/voice/transcribe", { method: "POST", body: fd });
  },
};

/** POST that returns Server-Sent Events; calls onEvent for each parsed event. */
export async function streamPost(path: string, body: unknown, onEvent: (e: StreamEvent) => void): Promise<void> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { method: "POST", headers, body: JSON.stringify(body) });
  if (!res.ok || !res.body) throw await parseError(res);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (chunk.startsWith("data:")) onEvent(JSON.parse(chunk.slice(5).trim()) as StreamEvent);
    }
  }
}
