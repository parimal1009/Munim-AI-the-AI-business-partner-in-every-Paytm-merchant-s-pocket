"""Auth, dashboard, briefing, actions, outcomes."""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import MerchantId, issue_token
from app.cache import cached
from app.core import NotFoundError
from app.db import SessionLocal, get_session
from app.models import Briefing, Merchant
from app.schemas import ActionOut, BriefingOut, LoginRequest, MerchantOut, TokenResponse
from app.services import actions, analytics, briefing, demo, finance, growth, inventory, khata

router = APIRouter(prefix="/api")


@router.get("/merchants", response_model=list[MerchantOut])
def list_merchants(s: Session = Depends(get_session)) -> list[Merchant]:
    return list(s.scalars(select(Merchant).order_by(Merchant.id)))


@router.post("/auth/demo-login", response_model=TokenResponse)
def demo_login(body: LoginRequest, s: Session = Depends(get_session)) -> TokenResponse:
    m = s.get(Merchant, body.merchant_id)
    if not m:
        raise NotFoundError("Merchant not found")
    return TokenResponse(token=issue_token(m.id), merchant=MerchantOut.model_validate(m))


@router.get("/me", response_model=MerchantOut)
def me(mid: int = MerchantId, s: Session = Depends(get_session)) -> Merchant:
    m = s.get(Merchant, mid)
    if not m:
        raise NotFoundError("Merchant not found")
    return m


@router.get("/dashboard")
@cached("dashboard")
def dashboard(mid: int = MerchantId) -> dict[str, Any]:
    # Independent read-only queries run concurrently, each on its own pooled connection,
    # so total latency is ~1 DB round-trip chain instead of the sum of all of them.
    jobs: dict[str, Callable[[Session], Any]] = {
        "yesterday": lambda s: analytics.yesterday(s, mid).__dict__,
        "daily": lambda s: analytics.daily_sales(s, mid, 30),
        "top_products": lambda s: analytics.top_products(s, mid, 30, 5),
        "peak_hours": lambda s: analytics.peak_hours(s, mid),
        "category_mix": lambda s: analytics.category_mix(s, mid),
        "peer": lambda s: analytics.peer_comparison(s, mid),
        "outcomes": lambda s: actions.outcomes_summary(s, mid, 7),
        "khata": lambda s: khata.summary(s, mid),
        "stock_at_risk": lambda s: len(inventory.at_risk(s, mid)),
        "lapsed": lambda s: len(growth.lapsed_customers(s, mid)),
        "loan": lambda s: finance.loan_eligibility(s, mid),
    }

    def run(fn: Callable[[Session], Any]) -> Any:
        with SessionLocal() as sess:
            return fn(sess)

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {k: pool.submit(run, fn) for k, fn in jobs.items()}
        return {k: f.result() for k, f in futures.items()}


def _briefing_out(s: Session, mid: int, b: Briefing) -> BriefingOut:
    pend = [ActionOut.model_validate(a) for a in actions.pending(s, mid)]
    return BriefingOut(id=b.id, language=b.language, text=b.text, facts=b.facts, actions=pend,
                       audio_url=f"/media/{b.audio_file}" if b.audio_file else None)


@router.get("/briefing/today", response_model=BriefingOut)
def briefing_today(lang: str | None = None, mid: int = MerchantId, s: Session = Depends(get_session)) -> BriefingOut:
    b = briefing.generate(s, mid, lang)
    s.commit()
    return _briefing_out(s, mid, b)


@router.post("/briefing/regenerate", response_model=BriefingOut)
def briefing_regen(lang: str | None = None, mid: int = MerchantId, s: Session = Depends(get_session)) -> BriefingOut:
    b = briefing.generate(s, mid, lang, force=True)
    s.commit()
    return _briefing_out(s, mid, b)


@router.get("/actions", response_model=list[ActionOut])
def list_actions(status: str = "pending", mid: int = MerchantId, s: Session = Depends(get_session)) -> list[ActionOut]:
    from app.models import Action

    rows = s.scalars(select(Action).where(Action.merchant_id == mid, Action.status == status).order_by(Action.id.desc()).limit(50))
    return [ActionOut.model_validate(a) for a in rows]


@router.post("/actions/{action_id}/approve", response_model=ActionOut)
def approve_action(action_id: int, mid: int = MerchantId, s: Session = Depends(get_session)) -> ActionOut:
    a = actions.approve(s, mid, action_id)
    s.commit()
    return ActionOut.model_validate(a)


@router.post("/actions/{action_id}/reject", response_model=ActionOut)
def reject_action(action_id: int, mid: int = MerchantId, s: Session = Depends(get_session)) -> ActionOut:
    a = actions.reject(s, mid, action_id)
    s.commit()
    return ActionOut.model_validate(a)


@router.get("/outcomes")
def outcomes(days: int = 7, mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, Any]:
    return actions.outcomes_summary(s, mid, max(1, min(days, 90)))


@router.post("/demo/reset")
def demo_reset(mid: int = MerchantId, s: Session = Depends(get_session)) -> dict[str, str]:
    demo.reset_state(s, mid)
    s.commit()
    return {"status": "reset"}
