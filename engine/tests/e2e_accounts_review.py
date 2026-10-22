"""Local HTTP receipt, synthetic data only. Run against the engine on port 8040.

    python -m engine.tests.e2e_accounts_review

No database injection and no live model calls. The attachment and all process
passages are explicit test data, not real professional evidence or judgments.
"""
from __future__ import annotations

from io import BytesIO
import json
import os

import httpx
from reportlab.pdfgen.canvas import Canvas


def main():
    base = os.environ.get('BATATIS_E2E_ORIGIN', 'http://localhost:8040')
    receipt = []

    def request(client, method, path, *, expected=200, label=None, **kwargs):
        response = client.request(method, path, **kwargs)
        assert response.status_code == expected, (path, response.status_code, response.text[:1600])
        if label:
            receipt.append({'step': label, 'status': response.status_code})
            print(f'{label}: {response.status_code}', flush=True)
        return response.json() if response.content else None

    suffix = __import__('uuid').uuid4().hex[:10]
    with httpx.Client(base_url=base, timeout=30) as owner, httpx.Client(base_url=base, timeout=30) as officer, \
            httpx.Client(base_url=base, timeout=30) as second:
        for client, name, role in [(owner, 'Applicant', 'applicant'), (officer, 'Reviewer One', 'reviewer'),
                                  (second, 'Reviewer Two', 'reviewer')]:
            user = request(client, 'POST', '/auth/signup', expected=201, label=name + ' signs up',
                json={'email': name.replace(' ', '').lower() + suffix + '@example.test',
                      'password': 'synthetic e2e password', 'name': name})['user']
            payload = ({'role': role, 'applicant_type': 'manufacturer'} if role == 'applicant' else
                       {'role': role, 'authority': 'edmonton', 'access_code': 'demo-edmonton-code'})
            request(client, 'POST', '/auth/onboarding', json=payload, label=name + ' onboards')
        case = request(owner, 'POST', '/cases', expected=201, label='Applicant creates owned application',
                       json={'title': 'SYNTHETIC HTTP administrative review fixture', 'authority': 'edmonton',
                             'jurisdiction': {'id': 'edmonton', 'name': 'Edmonton'}})
        cid = case['id']
        request(owner, 'POST', f'/cases/{cid}/submit', expected=409, json={}, label='Empty application blocked by gaps')

        def add(field, value, source=None):
            return request(owner, 'POST', f'/cases/{cid}/facts', json={
                'field': field, 'value': value, 'kind': 'pointed', 'status': 'confirmed',
                'source': source or {'type': 'user_text', 'ref': 'synthetic-http-applicant', 'quote': str(value)}})

        for field, value in {
            'owner_name': 'SYNTHETIC owner', 'application_date': '2026-10-20',
            'civic_address': '000 Synthetic Street', 'legal_description': 'Synthetic lot 1 block 2 plan 3',
            'representative': 'SYNTHETIC applicant', 'mailing_address': '000 Synthetic Street',
            'scope': 'site', 'alternative_description': 'SYNTHETIC departure for an API exercise only.',
            'rationale': 'SYNTHETIC applicant rationale for the fixture.',
            'risk_assessment': 'SYNTHETIC applicant risk passage, no technical assessment.',
            'mitigating_measures': 'SYNTHETIC applicant measures, no adequacy judgment.',
            'assumptions_and_limits': 'SYNTHETIC scope limits, fixture only.',
            'maintenance_operation': 'SYNTHETIC operation and maintenance passage.',
            'qualifications': 'SYNTHETIC document author role, no licence or competence asserted.',
            'professional_status': 'not_engaged', 'occupancy': 'single_family',
        }.items():
            add(field, value)
        selected = request(owner, 'GET', f'/cases/{cid}')
        plan = request(owner, 'POST', f'/cases/{cid}/section-d', json={
            'provisions': ['9.10.9.16.(1)'], 'expected_version': selected['version']},
            label='Applicant confirms benchmark; Section C uses lookup')
        pdf = BytesIO()
        canvas = Canvas(pdf)
        canvas.drawString(50, 780, 'SYNTHETIC API fixture. No test, professional evidence or result is asserted.')
        canvas.save()
        file = request(owner, 'POST', f'/cases/{cid}/files', expected=201,
            content=pdf.getvalue(), headers={'Content-Type': 'application/pdf', 'X-Filename': 'SYNTHETIC-fixture.pdf'},
            label='Applicant uploads synthetic PDF fixture')
        add('evidence.synthetic.file_ref', file['id'], {'type': 'file', 'ref': file['id'],
                                                     'quote': 'SYNTHETIC storage-binding fixture only.'})
        for field, value in [('title', 'SYNTHETIC storage-binding attachment'),
                             ('responsible_party', 'SYNTHETIC fixture author'), ('date', '2026-10-20')]:
            add('evidence.synthetic.' + field, value)
        for item in plan['items']:
            add('evidence.synthetic.covers.' + item['id'], True)
        gaps = request(owner, 'GET', f'/cases/{cid}/gaps')['items']
        blocking = [gap for gap in gaps if gap['severity'] == 'blocking']
        assert not blocking, json.dumps(blocking, indent=2)
        receipt.append({'step': 'Gap check', 'blocking': 0, 'warnings': [g['id'] for g in gaps]})
        request(owner, 'POST', f'/cases/{cid}/submit', json={}, label='Applicant submits complete administrative fixture')
        queue = request(officer, 'GET', '/review/queue', label='Reviewer reads authority queue')['applications']
        assert any(a['id'] == cid for a in queue)
        request(officer, 'POST', f'/review/{cid}/claim', json={}, label='Reviewer One claims')
        conflict = request(second, 'POST', f'/review/{cid}/claim', json={}, expected=409,
                           label='Reviewer Two sees claim conflict')
        assert conflict['detail'] == 'Already being reviewed'
        returned = request(officer, 'POST', f'/review/{cid}/decision', label='Reviewer returns with message',
            json={'outcome': 'return', 'message': 'Please clarify the synthetic attachment revision.',
                  'items': [{'field': 'evidence.synthetic.date', 'note': 'Confirm the revision date.'}]})
        assert returned['status'] == 'returned'
        application = next(a for a in request(owner, 'GET', '/me/applications')['applications'] if a['id'] == cid)
        assert application['status'] == 'returned' and application['unread_messages'] == 1
        receipt.append({'step': 'Applicant sees return', 'status': 'returned', 'unread_messages': 1})
        request(owner, 'POST', f'/cases/{cid}/messages/read', json={}, expected=204,
                label='Applicant marks reviewer message read')
        request(owner, 'POST', f'/cases/{cid}/messages', expected=403,
                json={'body': 'SYNTHETIC reply: the revision date is confirmed.'}, label='Applicant cannot reply (one-way messages)')
        request(owner, 'POST', f'/cases/{cid}/submit', json={}, label='Applicant resubmits')
        request(officer, 'POST', f'/review/{cid}/claim', json={}, label='Reviewer reclaims')
        accepted = request(officer, 'POST', f'/review/{cid}/decision', json={'outcome': 'accept'},
                           label='Reviewer accepts as administratively complete')
        assert accepted['status'] == 'accepted'
        request(owner, 'POST', f'/cases/{cid}/facts', expected=409,
                json={'field': 'scope', 'value': 'changed', 'kind': 'pointed',
                      'source': {'type': 'user_text', 'ref': 'synthetic'}}, label='Accepted application rejects edits')
        request(owner, 'POST', '/assist', json={'case_id': cid, 'screen': 'application',
                'question': 'What does administrative acceptance mean?'}, expected=503,
                label='Assistant unavailable without provider keys')
        receipt.append({'case_id': cid, 'history': [h['to_status'] for h in accepted['status_history']],
                        'decision': accepted['decision']['message']})
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
