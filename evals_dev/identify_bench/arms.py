"""The arms of the benchmark matrix, with stable names and config hashes.

Names say what the arm is. A pipeline is the chain that ends at an arm: ``V15f-R5`` is the Jev screen, the rerank of its
top 60, then a verifier that reads the top 15 in full text. The IDs R0, R1, R2, R4, R5, R6 and A9 are the plan's
(``benchmark-plan.md`` section 2); ``rec`` suffixed arms are the 2026-10-20 recorded run, used for Stage 0 only.
"""
from __future__ import annotations

import re

from .methods.base import Arm
from .methods.fusion import FuseArm
from .methods.jev import JevRerankArm, JevScreenArm
from .methods.lexical import Bm25Arm, SearchRankArm
from .methods.precedent import PrecedentArm
from .methods.verifier import LunaRerankArm, LunaVerifierArm
from .rows import config_hash


def standard_arms(*, jev_repeats: int = 2, verifier_repeats: int = 5, upstream_cycle: int | None = 2,
                  search_rank: SearchRankArm | None = None) -> dict[str, Arm]:
    """``jev_repeats`` independent Jev draws per case; verifier repeat r reads draw ``r % upstream_cycle`` (None: the same r).

    The Jev account ran out of credits after two complete draws of every case (6,300 requests), so the default is two.
    """
    r1 = search_rank or SearchRankArm('R1-searchrank-v3')
    arms: list[Arm] = [
        Bm25Arm('R0-bm25'),
        r1,
        PrecedentArm('R2-precedent-lofo'),
        JevScreenArm('R4-jev-screen', repeats=jev_repeats),
        JevRerankArm('R5-jev-screen-rerank60', 'R4-jev-screen', repeats=jev_repeats),
        JevRerankArm('R6-bm25-jev-rerank60', 'R0-bm25', repeats=jev_repeats),
        FuseArm('F1-rrf-R5-R1-R2', ('R5-jev-screen-rerank60', 'R1-searchrank-v3', 'R2-precedent-lofo'), repeats=jev_repeats),
        LunaRerankArm('A9-bm25-luna-rerank60', 'R0-bm25', repeats=3),
        LunaVerifierArm('V15f-R5', 'R5-jev-screen-rerank60', repeats=verifier_repeats, upstream_cycle=upstream_cycle),
        LunaVerifierArm('V40f-R5', 'R5-jev-screen-rerank60', shortlist_n=40, repeats=verifier_repeats, upstream_cycle=upstream_cycle),
        LunaVerifierArm('V15c-R5', 'R5-jev-screen-rerank60', chars=700, repeats=verifier_repeats, upstream_cycle=upstream_cycle),
        LunaVerifierArm('V15f-R6', 'R6-bm25-jev-rerank60', repeats=verifier_repeats, upstream_cycle=upstream_cycle),
        LunaVerifierArm('V15f-F1', 'F1-rrf-R5-R1-R2', repeats=verifier_repeats, upstream_cycle=upstream_cycle),
        LunaVerifierArm('V15f-R5-ool', 'R5-jev-screen-rerank60', out_of_list=True, repeats=verifier_repeats, upstream_cycle=upstream_cycle),
    ]
    by_name = {a.name: a for a in arms}
    if not by_name['R1-searchrank-v3'].available:
        pass                                           # kept in the registry; running it reports "unavailable"
    return by_name


def topo_order(arms: dict[str, Arm], wanted: list[str]) -> list[str]:
    """The wanted arms and everything they depend on, upstream first."""
    out: list[str] = []

    def visit(name: str) -> None:
        if name in out:
            return
        for up in arms[name].upstream_names:
            visit(up)
        out.append(name)

    for w in wanted:
        visit(w)
    return out


def arm_hashes(arms: dict[str, Arm]) -> dict[str, str]:
    """Config hash of every arm; a downstream hash covers its upstream hashes."""
    hashes: dict[str, str] = {}
    for name in topo_order(arms, list(arms)):
        a = arms[name]
        hashes[name] = config_hash({'name': name, 'kind': a.kind, 'config': a.config(),
                                    'upstream': {u: hashes[u] for u in a.upstream_names}})
    return hashes


def public_model_id(model_id: str) -> str:
    """A model id that may be shown to a user: the screening vendor is never named (``jev-1.13.0`` -> ``screen-1.13.0``).

    Internal eval files may name it; the accuracy page and anything else a user sees must go through this.
    """
    return re.sub(r'(?i)jev', 'screen', model_id)
