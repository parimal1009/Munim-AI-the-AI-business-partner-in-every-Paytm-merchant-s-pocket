"""LangGraph supervisor: route -> specialist agent -> approval gate (interrupt) -> finalize."""
import json
import logging
import queue
import re
import threading
from typing import Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel

from app.agents.prompts import AGENTS, COMMON, LANG_NAMES, ROUTER
from app.agents.tools import AGENT_TOOLS, FALLBACK_TOOLS
from app.core import ConflictError, fmt_inr, log, mask_pii
from app.db import session_scope
from app.models import Action, AgentEvent
from app.services import actions as action_svc
from app.services import sarvam

logger = logging.getLogger("agents")
AgentName = Literal["insights", "khata", "inventory", "growth", "finance", "trust"]
MAX_TOOL_ROUNDS = 3

# Order matters: inventory is checked before khata ("khatam" = finished must not match "khata" = ledger).
KEYWORDS: dict[str, tuple[str, ...]] = {
    "inventory": ("stock", "reorder", "order", "maal", "khatam", "ख़तम", "खत्म", "distributor", "doodh", "milk", "स्टॉक",
                  "expiry", "expire", "expiring", "kharab", "एक्सपायर"),
    "khata": ("udhaar", "udhar", "khata", "reminder", "dues", "उधार", "बकाया", "owe"),
    "growth": ("offer", "cashback", "diwali", "festival", "discount", "ऑफर", "दिवाली", "customers", "win"),
    "finance": ("loan", "gst", "forecast", "cash flow", "cashflow", "लोन", "जीएसटी", "tax"),
    "trust": ("fraud", "suspicious", "unusual", "chargeback", "धोखा", "फ्रॉड"),
}


class RouteDecision(BaseModel):
    agent: Literal["insights", "khata", "inventory", "growth", "finance", "trust", "general"]
    reply_language: Literal["hi", "mr", "ta", "en"] = "hi"


class MunimState(TypedDict, total=False):
    question: str
    language: str
    agent: str
    reply: str
    action_ids: list[int]
    facts: list[dict[str, Any]]
    executed: list[dict[str, Any]]
    cards: list[dict[str, Any]]


# ---------------- tracing ----------------
_audit_q: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize=2000)


def _audit_worker() -> None:
    """Persist agent events off the request path so tracing never slows the merchant down."""
    while True:
        row = _audit_q.get()
        try:
            with session_scope() as s:
                s.add(AgentEvent(**row))
        except Exception:  # noqa: BLE001
            logger.warning("could not persist agent event")


threading.Thread(target=_audit_worker, daemon=True, name="audit-writer").start()


def emit(config: RunnableConfig, agent: str, event: str, **detail: Any) -> None:
    """Stream to the UI trace panel and persist to the audit table."""
    payload = {"type": event, "agent": agent, **detail}
    try:
        get_stream_writer()(payload)
    except Exception:  # noqa: BLE001  (called outside a graph run, e.g. tests)
        pass
    cfg = config["configurable"]
    try:
        _audit_q.put_nowait({"merchant_id": int(cfg["merchant_id"]), "thread_id": str(cfg["thread_id"]), "agent": agent,
                             "event": event, "detail": json.loads(json.dumps(detail, default=str))})
    except queue.Full:
        logger.warning("audit queue full")

# ---------------- nodes ----------------
def _keyword_match(q: str) -> str | None:
    low = q.lower()
    for agent, words in KEYWORDS.items():
        if any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", low) for w in words):
            return agent
    return None


def _keyword_route(q: str) -> str:
    return _keyword_match(q) or "insights"


def router(state: MunimState, config: RunnableConfig) -> dict[str, Any]:
    q = mask_pii(state["question"])
    lang = state.get("language", "hi")
    try:
        llm = sarvam.chat_model().with_structured_output(RouteDecision)
        d = llm.invoke([SystemMessage(ROUTER), HumanMessage(q)])
        assert isinstance(d, RouteDecision)
        agent, lang = d.agent, d.reply_language
        if agent == "general" and (hit := _keyword_match(q)):  # never let a clear domain word fall to small talk
            agent = hit
    except Exception as exc:  # noqa: BLE001
        logger.warning("router fallback: %s", type(exc).__name__)
        agent = _keyword_route(q)
    emit(config, "supervisor", "route", routed_to=agent, language=lang, question=q)
    return {"agent": agent, "language": lang, "action_ids": [], "facts": []}


def _scan_action_ids(content: str) -> list[int]:
    try:
        data = json.loads(content)
    except ValueError:
        return []
    items = data if isinstance(data, list) else [data]
    return [int(i["action_id"]) for i in items if isinstance(i, dict) and "action_id" in i]


def _summary(content: str, limit: int = 220) -> str:
    return content if len(content) <= limit else content[:limit] + "…"


def _run_tool(tools_by_name: dict[str, Any], name: str, args: dict[str, Any], config: RunnableConfig, agent: str) -> str:
    emit(config, agent, "tool_call", tool=name, args=args)
    try:
        out = str(tools_by_name[name].invoke(args, config))
    except Exception as exc:  # noqa: BLE001
        out = json.dumps({"error": f"tool failed: {type(exc).__name__}"})
    emit(config, agent, "tool_result", tool=name, result=_summary(out))
    return out


def _fallback_template(agent: str, facts: list[dict[str, Any]]) -> str:
    return "Yeh jaankari mili hai: " + " | ".join(_summary(f["result"], 160) for f in facts)[:600]


def run_specialist(agent: AgentName, state: MunimState, config: RunnableConfig) -> dict[str, Any]:
    lang = state.get("language", "hi")
    emit(config, agent, "agent_start", language=lang)
    tools = AGENT_TOOLS[agent]
    by_name = {t.name: t for t in tools}
    system = COMMON.format(lang=LANG_NAMES.get(lang, LANG_NAMES["hi"])) + AGENTS[agent]
    msgs: list[BaseMessage] = [SystemMessage(system), HumanMessage(mask_pii(state["question"]))]
    facts: list[dict[str, Any]] = []
    action_ids: list[int] = []
    reply = ""
    try:
        llm = sarvam.chat_model("low" if agent in ("growth", "finance") else None, 1800).bind_tools(tools)
        for _ in range(MAX_TOOL_ROUNDS):
            resp = llm.invoke(msgs)
            msgs.append(resp)
            calls = getattr(resp, "tool_calls", None) or []
            if not calls:
                reply = str(resp.content).strip()
                break
            for c in calls:
                if c["name"] not in by_name:
                    out = json.dumps({"error": "unknown tool"})
                else:
                    out = _run_tool(by_name, c["name"], c["args"], config, agent)
                    facts.append({"tool": c["name"], "result": out})
                    action_ids += _scan_action_ids(out)
                msgs.append(ToolMessage(content=out, tool_call_id=c["id"]))
        if not reply and facts:  # model kept calling tools; force a final answer
            msgs.append(HumanMessage("Now answer the merchant using the tool results."))
            reply = str(sarvam.chat_model(None, 1200).invoke(msgs).content).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent %s LLM path failed (%s); using deterministic fallback", agent, type(exc).__name__)
        emit(config, agent, "fallback", reason=type(exc).__name__)

    if not facts:  # model answered without tools (or failed): ground it with the default tools
        for t in FALLBACK_TOOLS[agent]:
            out = _run_tool({t.name: t}, t.name, {}, config, agent)
            facts.append({"tool": t.name, "result": out})
            action_ids += _scan_action_ids(out)
        reply = ""
    if not reply:
        try:
            ctx = "\n".join(f"{f['tool']}: {f['result']}" for f in facts)
            reply = sarvam.complete(system, f"Merchant asked: {mask_pii(state['question'])}\nTool results:\n{ctx}\nAnswer now.", None, 1200)
        except Exception:  # noqa: BLE001
            reply = _fallback_template(agent, facts)
    emit(config, agent, "agent_done", reply=reply)
    return {"reply": reply, "facts": facts, "action_ids": sorted(set(action_ids))}


def _make_agent_node(name: AgentName) -> Any:
    def node(state: MunimState, config: RunnableConfig) -> dict[str, Any]:
        return run_specialist(name, state, config)

    node.__name__ = name
    return node


def general(state: MunimState, config: RunnableConfig) -> dict[str, Any]:
    lang = state.get("language", "hi")
    emit(config, "general", "agent_start", language=lang)
    try:
        reply = sarvam.complete(COMMON.format(lang=LANG_NAMES.get(lang, "simple Hindi")) +
                                "Greet and tell the merchant what you can do: sales insights, udhaar reminders, stock alerts, offers, loans/GST, fraud checks.",
                                mask_pii(state["question"]))
    except Exception:  # noqa: BLE001
        reply = "Namaste! Main aapka Munim AI hoon. Sales, udhaar, stock, offers, loan aur GST ke baare mein poochiye."
    return {"reply": reply, "facts": [], "action_ids": []}


def request_approval(state: MunimState, config: RunnableConfig) -> dict[str, Any]:
    """Collect the pending actions the agent proposed and tell the UI an approval is needed."""
    ids = state.get("action_ids") or []
    mid = int(config["configurable"]["merchant_id"])
    cards: list[dict[str, Any]] = []
    if ids:
        with session_scope() as s:
            cards = [{"id": a.id, "kind": a.kind, "title": a.title, "reason": a.reason}
                     for a in s.query(Action).filter(Action.id.in_(ids), Action.merchant_id == mid, Action.status == "pending")]
    if cards:
        emit(config, "approval", "approval_required", actions=cards)
    return {"cards": cards}


def await_decision(state: MunimState, config: RunnableConfig) -> dict[str, Any]:
    """Human-in-the-loop gate. The graph pauses at interrupt() until the merchant approves/rejects."""
    cards = state.get("cards") or []
    if not cards:
        return {"executed": []}
    mid = int(config["configurable"]["merchant_id"])
    decision: dict[str, Any] = interrupt({"actions": cards})  # <- graph pauses here
    decisions: dict[str, bool] = {str(k): bool(v) for k, v in (decision.get("decisions") or {}).items()}
    executed: list[dict[str, Any]] = []
    for card in cards:
        ok = decisions.get(str(card["id"]), False)
        try:
            with session_scope() as s:
                a = action_svc.approve(s, mid, card["id"]) if ok else action_svc.reject(s, mid, card["id"])
                executed.append({"id": a.id, "title": a.title, "status": a.status, "result": a.result})
        except ConflictError:  # already decided elsewhere (e.g. on the Home screen)
            with session_scope() as s:
                a = action_svc.get_action(s, mid, card["id"])
                executed.append({"id": a.id, "title": a.title, "status": a.status, "result": a.result})
        emit(config, "approval", "approved" if ok else "rejected", action_id=card["id"], title=card["title"])
    return {"executed": executed}


_DONE = {
    "hi": {
        "rejected": "ठीक है, '{title}' रद्द कर दिया।",
        "khata_reminders": "{count} रिमाइंडर पेमेंट लिंक के साथ भेज दिए ({amount} का उधार)।",
        "reorder": "{distributor} को ऑर्डर भेज दिया।",
        "campaign": "कैम्पेन चालू हो गया, {targets} ग्राहकों को ऑफर भेजा।",
        "other": "हो गया।",
    },
    "en": {
        "rejected": "Okay, cancelled: {title}.",
        "khata_reminders": "Sent {count} reminders with Paytm payment links ({amount} outstanding).",
        "reorder": "Order sent to {distributor}.",
        "campaign": "Campaign is live, offer sent to {targets} customers.",
        "other": "Done.",
    },
}


def _result_line(e: dict[str, Any], lang: str) -> str:
    tpl = _DONE["hi" if lang in ("hi", "mr") else "en"]
    if e["status"] == "rejected":
        return tpl["rejected"].format(title=e["title"])
    r = e.get("result") or {}
    kind = r.get("kind", "other")
    amount = fmt_inr(sum(x["amount_paise"] for x in r.get("sent", [])))
    return tpl.get(kind, tpl["other"]).format(count=r.get("count", 0), amount=amount,
                                              distributor=r.get("distributor", ""), targets=r.get("targets", 0))


def finalize(state: MunimState, config: RunnableConfig) -> dict[str, Any]:
    ex = state.get("executed") or []
    lang = state.get("language", "hi")
    # once actions were decided, the proposal text is obsolete: reply with what actually happened
    reply = " ".join(_result_line(e, lang) for e in ex) if ex else state.get("reply", "")
    emit(config, "supervisor", "reply_ready", reply=reply)
    return {"reply": reply}


def _route_edge(state: MunimState) -> str:
    return state.get("agent", "insights")


def build_graph(checkpointer: BaseCheckpointSaver[Any] | None = None) -> Any:
    g = StateGraph(MunimState)
    g.add_node("router", router)
    names: list[AgentName] = ["insights", "khata", "inventory", "growth", "finance", "trust"]
    for n in names:
        g.add_node(n, _make_agent_node(n))
    g.add_node("general", general)
    g.add_node("request_approval", request_approval)
    g.add_node("await_decision", await_decision)
    g.add_node("finalize", finalize)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", _route_edge, {**{n: n for n in names}, "general": "general"})
    for n in [*names, "general"]:
        g.add_edge(n, "request_approval")
    g.add_edge("request_approval", "await_decision")
    g.add_edge("await_decision", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


__all__ = ["build_graph", "MunimState", "log", "AIMessage"]

