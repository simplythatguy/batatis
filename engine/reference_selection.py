"""Withdraw reference decisions and derived scope while preserving applicant material.

The caller validates replacement rows, then saves the entire mutation with the
snapshot's expected version. This helper never reads a store, upserts, or retries.
"""
from __future__ import annotations

from .models import Case, Fact, SectionCRow, Source
from .section_d import plan_item_id


def _canonical(provision: str) -> str:
    return ''.join(provision.split()).rstrip('.')


def _within(child: str, parent: str) -> bool:
    child, parent = _canonical(child), _canonical(parent)
    return child == parent or child.startswith(parent + '.(') or child.startswith(parent + '(')


def replace_references(case: Case, provisions: list[str], rows: list[SectionCRow]) -> None:
    """Apply an explicit selection; an empty list also removes orphaned old decisions."""
    selected = {_canonical(pid) for pid in provisions}
    removed = [pid for pid in case.provisions if _canonical(pid) not in selected]
    removed += [row.provision_id for row in case.section_c
                if not any(_within(row.provision_id, pid) for pid in provisions)]
    current_ids = {plan_item_id(row, pair) for row in rows for pair in row.pairs or [None]}
    old_ids = {plan_item_id(row, pair) for row in case.section_c for pair in row.pairs or [None]}
    if removed or old_ids - current_ids or not selected:
        # Nested legacy slot ids remain intact; the exact suffix determines its metadata field.
        slots = {item.id for item in case.evidence}
        detached = slots & (old_ids - current_ids)
        retained = slots & current_ids
        paired = {item.id for item in case.evidence if item.objective or item.function}
        kept = []
        for fact in case.facts:
            decision = next((fact.field[len(prefix):] for prefix in ('citation.', 'open_question.')
                             if fact.field.startswith(prefix)), None)
            if decision is not None and (not selected or (
                    _canonical(decision) not in selected and any(
                        _within(decision, pid) or _within(pid, decision) for pid in removed))):
                continue
            if fact.field.startswith('evidence.'):
                name = fact.field[len('evidence.'):]
                if '.covers.' in name:
                    slot, target = name.split('.covers.', 1)
                    slots.add(slot)
                    if target not in current_ids:
                        detached.add(slot)
                        continue
                    retained.add(slot)
                elif '.' in name:
                    slot, field = name.rsplit('.', 1)
                    slots.add(slot)
                    if field in {'objective', 'function'}:
                        paired.add(slot)
                    if (field == 'item_id' and fact.value not in current_ids
                            or field == 'provision_id' and (not selected or not isinstance(fact.value, str)
                                or not any(_within(fact.value, pid) for pid in provisions))):
                        detached.add(slot)
                        continue
                    if field in {'item_id', 'provision_id'}:
                        retained.add(slot)
            kept.append(fact)
        detached.update(slots & (old_ids - current_ids))
        detached.update(paired - retained)
        if not selected:
            detached.update(slots)
        detached_fields = {f'evidence.{slot}.{field}' for slot in detached for field in ('objective', 'function')}
        kept = [fact for fact in kept if fact.field not in detached_fields]
        for item in case.evidence:
            if item.id in detached:
                item.objective = item.function = None
        for slot in sorted(detached):
            # Keeping a document id stable must not restore an earlier automatic attachment
            # when the same provision/pair is selected again. Explicit links remain usable.
            field = f'evidence.{slot}.auto_link'
            kept = [fact for fact in kept if fact.field != field]
            kept.append(Fact(field=field, value=False, kind='computed', status='confirmed',
                             source=Source(type='user_click', ref='reference-selection',
                                           quote='Reference scope withdrawn by applicant'),
                             formula='Reference selection changed; automatic document scope withdrawn'))
        case.facts = kept
    case.provisions = list(dict.fromkeys(provisions))
    case.section_c = rows
    case.gaps = []
