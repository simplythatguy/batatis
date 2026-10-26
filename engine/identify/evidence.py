"""Keep exact source passages once, referenced by stable evidence ids."""


def compact(result):
    from engine.models_identify import RequirementLink
    index = {e.id: e for e in result.requirement_evidence}
    links = {(link.source_requirement, link.target_requirement): link for link in result.requirement_links}
    for item in result.requirements:
        if item.source_status != 'verified':
            item.evidence_ids = []
            item.evidence = []
            continue
        for evidence in item.evidence:
            index[evidence.id] = evidence
            if evidence.id not in item.evidence_ids:
                item.evidence_ids.append(evidence.id)
        item.evidence = []
        for discovery in item.discoveries:
            if discovery.evidence is not None:
                evidence = discovery.evidence
                index[evidence.id] = evidence
                discovery.evidence_id = evidence.id
                discovery.evidence = None
            if discovery.kind in ('reference', 'reverse_reference') and discovery.from_requirement:
                source, target = ((discovery.from_requirement, item.id) if discovery.kind == 'reference'
                                  else (item.id, discovery.from_requirement))
                link = links.setdefault((source, target), RequirementLink(
                    source_requirement=source, target_requirement=target))
                for eid in discovery.evidence_ids:
                    if eid not in link.evidence_ids:
                        link.evidence_ids.append(eid)
        # Keep one example path per discovery kind. Every directed source edge
        # and its exact passages remain in the shared requirement_links ledger.
        grouped = {}
        for discovery in item.discoveries:
            first = grouped.setdefault(discovery.kind, discovery)
            if first is not discovery:
                for eid in discovery.evidence_ids:
                    if eid not in first.evidence_ids:
                        first.evidence_ids.append(eid)
        item.discoveries = list(grouped.values())
    for gap in result.requirement_coverage.gaps:
        if gap.evidence is not None:
            index[gap.evidence.id] = gap.evidence
            gap.evidence_id, gap.evidence = gap.evidence.id, None
    result.requirement_evidence = list(index.values())
    result.requirement_links = list(links.values())
    return result
