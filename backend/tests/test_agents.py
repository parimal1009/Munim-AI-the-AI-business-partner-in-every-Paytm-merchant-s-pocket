"""Agent graph tests with the LLM unavailable: proves routing + tools + approval gate + execution
work through deterministic fallbacks, and that nothing executes without approval."""
import uuid
from typing import Any

import pytest
from langgraph.types import Command

from app.agents import graph as graph_mod
from app.agents.graph import build_graph
from app.db import session_scope
from app.models import Action, Message
from app.services import sarvam

pytestmark = pytest.mark.integration


@pytest.fixture()
def offline_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: Any, **__: Any) -> Any:
        raise RuntimeError("LLM offline")

    monkeypatch.setattr(sarvam, "chat_model", boom)
    monkeypatch.setattr(sarvam, "complete", boom)


def _run(g: Any, inp: Any, cfg: dict[str, Any]) -> list[Any]:
    return list(g.stream(inp, cfg, stream_mode="updates"))


def _cfg() -> dict[str, Any]:
    return {"configurable": {"merchant_id": 1, "thread_id": uuid.uuid4().hex[:12]}}


def test_khata_flow_pauses_then_executes_only_after_approval(offline_llm: None, clean_state: None) -> None:
    g = build_graph()
    cfg = _cfg()
    chunks = _run(g, {"question": "udhaar reminder bhejo", "language": "en"}, cfg)
    assert any("__interrupt__" in c for c in chunks), "graph must pause for approval"
    state = g.get_state(cfg)
    assert state.next, "graph is waiting"
    with session_scope() as s:
        assert s.query(Message).filter(Message.merchant_id == 1).count() == 0  # nothing sent yet
        pending = s.query(Action).filter(Action.merchant_id == 1, Action.status == "pending").all()
        assert pending and all(a.result is None for a in pending)
        aid = pending[0].id

    _run(g, Command(resume={"decisions": {aid: True}}), cfg)
    final = g.get_state(cfg)
    assert not final.next
    assert "Sent 3 reminders" in final.values["reply"]
    with session_scope() as s:
        assert s.query(Message).filter(Message.merchant_id == 1).count() == 3


def test_rejection_executes_nothing(offline_llm: None, clean_state: None) -> None:
    g = build_graph()
    cfg = _cfg()
    _run(g, {"question": "stock reorder doodh", "language": "en"}, cfg)
    with session_scope() as s:
        pend = [a.id for a in s.query(Action).filter(Action.merchant_id == 1, Action.status == "pending", Action.kind == "reorder")]
    assert pend
    _run(g, Command(resume={"decisions": {i: False for i in pend}}), cfg)
    with session_scope() as s:
        assert s.query(Action).filter(Action.id.in_(pend), Action.status == "rejected").count() == len(pend)
        assert s.query(Message).filter(Message.merchant_id == 1).count() == 0
    assert "cancelled" in g.get_state(cfg).values["reply"]


def test_read_only_question_never_interrupts(offline_llm: None, clean_state: None) -> None:
    g = build_graph()
    cfg = _cfg()
    chunks = _run(g, {"question": "kal ki sale", "language": "en"}, cfg)
    assert not any("__interrupt__" in c for c in chunks)
    assert not g.get_state(cfg).next
    assert g.get_state(cfg).values["agent"] == "insights"


def test_module_exposes_graph_builder() -> None:
    assert callable(graph_mod.build_graph)


def test_completed_work_is_not_reproposed(clean_state: None) -> None:
    from app.services import actions

    with session_scope() as s:
        a = actions.propose_khata_reminders(s, 1)
        r = actions.propose_reorders(s, 1)
        c = actions.propose_winback(s, 1)
        assert a and r and c
        for x in (a, *r, c):
            actions.approve(s, 1, x.id)
    with session_scope() as s:
        assert actions.propose_khata_reminders(s, 1) is None
        assert actions.propose_reorders(s, 1) == []
        assert actions.propose_winback(s, 1) is None


def test_clearance_proposal_is_pending_deduped_and_applied_once(clean_state: None) -> None:
    from app.models import Product
    from app.services import actions

    with session_scope() as s:
        a = actions.propose_clearance(s, 1)
        assert a and a.status == "pending" and a.kind == "clearance"
        assert actions.propose_clearance(s, 1).id == a.id  # type: ignore[union-attr]  # de-duplicated
        pids = [i["product_id"] for i in a.payload["items"]]
        assert all(s.get(Product, p).clearance_pct is None for p in pids)  # nothing applied before approval
        aid = a.id
    with session_scope() as s:
        done = actions.approve(s, 1, aid)
        again = actions.approve(s, 1, aid)  # idempotent
        assert done.result == again.result and done.result["items"]
        for i in done.result["items"]:
            p = s.get(Product, i["product_id"])
            assert p.clearance_pct == i["pct"]
            assert p.price_paise * (100 - p.clearance_pct) // 100 >= p.cost_paise  # never below cost
    with session_scope() as s:
        assert actions.propose_clearance(s, 1) is None or all(
            i["product_id"] not in pids for i in actions.propose_clearance(s, 1).payload["items"])  # type: ignore[union-attr]


def test_clearance_is_scoped_to_the_merchant(clean_state: None) -> None:
    import pytest as _pt

    from app.core import NotFoundError
    from app.services import actions

    with session_scope() as s:
        a = actions.propose_clearance(s, 1)
        assert a
        aid = a.id
    with session_scope() as s, _pt.raises(NotFoundError):
        actions.approve(s, 2, aid)
