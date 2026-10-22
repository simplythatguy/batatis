"""'Before you submit': meet the authority having jurisdiction and emergency services early.

The SCC presentation's process step 2 ("Pre-apply: meet the AHJ and emergency services early"). The
local wording and contact come from the jurisdiction pack (engine/jurisdictions); without a pack the
steps stay generic. Engine code names no jurisdiction.
"""
from __future__ import annotations

from ..jurisdictions import registry
from ..models import Case, Jurisdiction
from ..models_intake import PlanSource, PreApplication, PreApplicationStep

DECK = PlanSource(title="Safety Codes Council, Alternative Solutions Under Alberta's Objective-Based Codes "
                        "(presentation to the Building Codes Challenge), process step 2: Pre-apply")
MEET = ('Before you submit, meet a safety codes officer at the authority having jurisdiction to talk through the '
        'code conflict, the alternative you have in mind and what the file must contain.')
EMERGENCY = ('If the alternative could affect firefighting, rescue or evacuation, involve the fire department '
             '(emergency services) early, before the design is fixed.')


def _source(item) -> PlanSource:
    return PlanSource(title=item.title, url=getattr(item, 'url', None))


def pre_application(case: Case, municipality: str | None = None) -> PreApplication:
    """From the case's jurisdiction pack; else from a municipality read from the description (unconfirmed)."""
    reg = registry()
    found, resolved_by = reg.resolve_case(case), 'case'
    if found is None and municipality:
        found = reg.resolve(Jurisdiction(id=municipality.strip().lower().replace(' ', '-'), name=municipality))
        resolved_by = 'description'
    if found is None:
        return PreApplication(steps=[
            PreApplicationStep(id='meet_authority', title='Meet the authority having jurisdiction early', text=MEET,
                               origin='generic', sources=[DECK]),
            PreApplicationStep(id='emergency_services', title='Involve emergency services early', text=EMERGENCY,
                               origin='generic', sources=[DECK])])
    detail = reg.detail(found.pack)
    entry = [note for note in detail.process_notes if note.topic == 'entry_point']
    local = [note for note in entry if note.scope == 'local'] or entry
    meet_text = ' '.join([MEET, f'For this site that is {detail.authority.name}.',
                          *(note.text for note in local), detail.authority.contact or '']).strip()
    meet_sources = [DECK, *(_source(s) for note in local for s in note.sources),
                    *(_source(s) for s in detail.authority.sources)]
    guides = [guide for guide in detail.guides if guide.topic == 'emergency_services']
    emergency_text = ' '.join([EMERGENCY, *(f'{g.title}: {g.summary}' for g in guides)])
    return PreApplication(
        jurisdiction_id=detail.id, jurisdiction_name=detail.name, resolved_by=resolved_by,
        steps=[PreApplicationStep(id='meet_authority', title='Meet the authority having jurisdiction early',
                                  text=meet_text, origin='pack', sources=list({s.title: s for s in meet_sources}.values())),
               PreApplicationStep(id='emergency_services', title='Involve emergency services early', text=emergency_text,
                                  origin='pack' if guides else 'generic',
                                  sources=[DECK, *(_source(g.source) for g in guides)])])
