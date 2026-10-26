"""One transactional, partial write for an applicant's changed answers and unfinished editors."""
from __future__ import annotations

import json

from .access import enforce_mutation
from .models import Case, Fact, now


class DraftWritesMixin:
    def patch_draft(self, case_id: str, changes: dict, *, expected_version: int) -> Case | None:
        from .store import InvalidAttachment, VersionConflict, attachment_reference, case_with_stored_files

        conflict = None
        result = None
        with self.account_db() as db:
            column, lock = ('data', ' FOR UPDATE') if db.postgres else ('json', '')
            row = db.execute(f'SELECT {column}, version FROM cases WHERE id=?' + lock, (case_id,)).fetchone()
            if row is None or self._purge_expired(db.con, case_id):
                return None
            data = row[0] if db.postgres else json.loads(row[0])
            version = int(row[1])
            file_ids = {entry[0] for entry in db.execute('SELECT id FROM case_files WHERE case_id=?', (case_id,))}
            case = case_with_stored_files(data, file_ids, version)
            enforce_mutation(case)
            if version != expected_version:
                conflict = VersionConflict(case_id, expected_version, version)
            else:
                patch = {key: value for key, value in changes.items() if key != 'facts'}
                if 'facts' in changes:
                    incoming = [Fact.model_validate(value) for value in changes['facts']]
                    for fact in incoming:
                        reference = attachment_reference(fact)
                        if reference is not None and reference not in file_ids:
                            raise InvalidAttachment('Attach an uploaded file from this application before confirming the document.')
                    # Unchanged answers are no-ops; preserve the ordered revision ledger otherwise.
                    old = {fact.id: fact.model_dump(mode='json') for fact in case.facts}
                    incoming = [fact for fact in incoming if old.get(fact.id) != fact.model_dump(mode='json')]
                    if incoming:
                        ids = {fact.id for fact in incoming}
                        patch['facts'] = [fact.model_dump(mode='json') for fact in case.facts if fact.id not in ids]
                        patch['facts'].extend(fact.model_dump(mode='json') for fact in incoming)
                patch = {key: value for key, value in patch.items() if value != data.get(key)}
                if not patch:
                    return case
                stamp = now()
                patch['updated_at'] = stamp
                # Bind only changed paths. Messages, review history and AI output never cross this write boundary.
                expr = column
                parameters = []
                for key, value in patch.items():
                    if key not in {'facts', 'applicant_draft', 'selected_articles', 'jurisdiction', 'authority', 'updated_at'}:
                        raise ValueError('unsupported draft field')
                    if key == 'facts':
                        ids = [fact.id for fact in incoming]
                        delta = json.dumps([fact.model_dump(mode='json') for fact in incoming], ensure_ascii=False)
                        if db.postgres:
                            expr = (f"jsonb_set({expr}, '{{facts}}', COALESCE((SELECT jsonb_agg(fact ORDER BY ord) "
                                    "FROM jsonb_array_elements(COALESCE(data->'facts','[]'::jsonb)) "
                                    "WITH ORDINALITY AS entries(fact,ord) WHERE NOT (fact->>'id' = ANY(?))), "
                                    "'[]'::jsonb) || ?::jsonb, true)")
                            parameters.extend((ids, delta))
                        else:
                            expr = (f"json_set({expr}, '$.facts', json((SELECT json_group_array(json(value)) FROM "
                                    "(SELECT value, 0 AS source, key AS position FROM json_each(json_extract(cases.json, '$.facts')) "
                                    "WHERE json_extract(value, '$.id') NOT IN (SELECT value FROM json_each(?)) "
                                    "UNION ALL SELECT value, 1 AS source, key AS position FROM json_each(?) ORDER BY source, position))))")
                            parameters.extend((json.dumps(ids), delta))
                    elif db.postgres:
                        expr = f"jsonb_set({expr}, '{{{key}}}', ?::jsonb, true)"
                        parameters.append(json.dumps(value, ensure_ascii=False))
                    else:
                        expr = f"json_set({expr}, '$.{key}', json(?))"
                        parameters.append(json.dumps(value, ensure_ascii=False))
                changed = db.execute(f'UPDATE cases SET {column}={expr}, updated_at=?, version=version+1 '
                                     'WHERE id=? AND version=? RETURNING version',
                                     (*parameters, stamp, case_id, version)).fetchone()
                if changed is None:
                    raise VersionConflict(case_id, version)
                result = case_with_stored_files({**data, **patch}, file_ids, int(changed[0]))
        if conflict:
            raise conflict
        return result
