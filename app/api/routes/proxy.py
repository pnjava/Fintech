"""Proxy voting endpoints."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes.auth import AuthenticatedUser, require_role
from app.models import ProxyBallot, Shareholder
from app.schemas.proxy import ProxyVoteCreate, ProxyVoteRead, ProxyVoteSummary

router = APIRouter(prefix="/proxy")


def _get_shareholder(
    *, session: Session, shareholder_id: str, tenant_id: str
) -> Shareholder:
    shareholder = session.get(Shareholder, shareholder_id)
    if shareholder is None or shareholder.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shareholder not found")
    return shareholder


@router.post("/votes", response_model=ProxyVoteRead, status_code=status.HTTP_201_CREATED)
def submit_proxy_vote(
    payload: ProxyVoteCreate,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "EMPLOYEE", "COMPLIANCE", "OPS")),
) -> ProxyVoteRead:
    _get_shareholder(
        session=session, shareholder_id=payload.shareholder_id, tenant_id=user.tenant_id
    )

    ballot = ProxyBallot(
        tenant_id=user.tenant_id,
        meeting_id=payload.meeting_id,
        shareholder_id=payload.shareholder_id,
        ballot_choices=payload.ballot_choices,
        submitted_by=payload.submitted_by,
    )

    session.add(ballot)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proxy vote already submitted for this meeting",
        ) from exc
    session.refresh(ballot)
    return ProxyVoteRead.model_validate(ballot)


@router.get("/votes/summary", response_model=ProxyVoteSummary)
def proxy_vote_summary(
    meeting_id: str = Query(..., max_length=64),
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "COMPLIANCE")),
) -> ProxyVoteSummary:
    statement = select(ProxyBallot).where(
        ProxyBallot.tenant_id == user.tenant_id, ProxyBallot.meeting_id == meeting_id
    )
    ballots = session.scalars(statement).all()

    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ballot in ballots:
        for resolution, choice in ballot.ballot_choices.items():
            totals[resolution][choice] += 1

    totals_dict: dict[str, dict[str, int]] = {
        resolution: dict(choices) for resolution, choices in totals.items()
    }
    return ProxyVoteSummary(
        meeting_id=meeting_id,
        totals=totals_dict,
        total_ballots=len(ballots),
    )


__all__ = ["proxy_vote_summary", "router", "submit_proxy_vote"]
