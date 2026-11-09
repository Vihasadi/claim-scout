"""The shape of a playbook. The model's JSON is validated against these models."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field


def _cap(n: int):
    return AfterValidator(lambda items: items[:n])


class ObjectionPlay(BaseModel):
    objection: str = Field(description="A pushback buyers in this segment raise, in one sentence.")
    best_response: str = Field(description="The response that worked, concretely enough to reuse.")


class Playbook(BaseModel):
    headline: str = Field(description="One sentence a rep could remember: how we win this segment.")
    buyer_tendencies: Annotated[list[str], _cap(5)] = Field(
        description="How buyers in this segment behave: what they test, demand, fear or stall on.")
    winning_moves: Annotated[list[str], _cap(5)] = Field(
        description="Seller actions that repeatedly moved deals forward, most reliable first.")
    objections: Annotated[list[ObjectionPlay], _cap(5)] = Field(default_factory=list)
    watch_outs: Annotated[list[str], _cap(4)] = Field(
        default_factory=list, description="Mistakes or risks visible in these deals.")
    exemplar_deal_id: int | None = Field(
        default=None, description="The one deal that shows this playbook best (must be a DEAL id shown).")
    exemplar_reason: str | None = None
