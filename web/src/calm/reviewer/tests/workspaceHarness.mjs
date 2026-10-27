import { componentHarness, nodes } from '../../../../scripts/component-harness.mjs';
import * as packageView from '../packageView.ts';
import * as queue from '../queue.ts';
import * as threadMessages from '../threadMessages.ts';
import * as workspaceView from '../workspaceView.ts';
import * as sheet from '../sheet.ts';

export class EngineError extends Error {
  constructor(status, detail = 'Synthetic failure') { super(detail); this.status = status; this.detail = detail; }
}
export class AccountsError extends EngineError {
  constructor(status, detail, body = null) { super(status, detail); this.body = body; }
}
export const officer = { id: 'officer', name: 'Morgan', role: 'reviewer', authority: 'edmonton' };
export const mine = { reviewer_id: officer.id, reviewer_name: officer.name, claimed_at: '2026-10-22T12:00:00Z' };
export const reviewSession = (version, caseVersion = 1) => ({
  package_id: 'c1', version, case_version: caseVersion, dispositions: [], findings: [], fields: [], files: [], documents: [], citations: [], section_c: [], diff: null,
  created_at: '2026-10-26T10:00:00Z', created_by_name: 'Morgan', input_kind: 'case', lookup_skipped: false,
  information_request: { intro: 'Opening', items: [], text: 'Exact server preview', sent_at: null, message_id: null, edited: false, sent_by_name: null },
});
export const workspaceFor = (version, caseVersion = 1, over = {}) => ({
  version, case_version: caseVersion, current: true, states: [], rulebook: [], limits: { intro: 2000, item_text: 600, items: 50, text: 6000 },
  tally: { required: 0, to_check: 0, verify: 0, dismissed: 0, rulebook: 0, asked: 1 }, gate: { can_accept: true, reason: '' }, ...over,
});
export const indexFor = (session, over = {}) => ({ latest: session, sessions: session ? [{ ...session, required: 0 }] : [], close_out: null, workspace: session ? workspaceFor(session.version, session.case_version) : null, ...over });
export const workspaceNode = tree => nodes(tree, n => n.props?.onDraft && n.props?.session)[0];
export const menuItem = (tree, label) => {
  const head = nodes(tree, n => n.props?.right)[0];
  return nodes(head.props.right, n => n.type === 'MoreMenu')[0]?.props.items.find(item => item.label === label);
};

export async function workspaceHarness(start = {}, opts = {}) {
  const current = { id: 'c1', title: 'Synthetic workspace', status: 'submitted', version: 1, claim: null, facts: [], section_c: [], submissions: [], professional_resolutions: [], evidence: [], expires_at: null, decision: null, ...start };
  let latest = opts.latest ?? null;
  const calls = { claim: 0, release: 0, run: 0, decisions: [], returns: [] };
  const location = { hash: '#/review/c1' };
  const defaultClaim = async () => { current.status = 'in_review'; current.claim = mine; return mine; };
  const h = await componentHarness(new URL('../ReviewWorkspace.tsx', import.meta.url), 'ReviewWorkspace', {
    '../../api/client': { EngineError },
    '../../api/accounts': { AccountsError, claimConflict: e => e instanceof AccountsError && e.status === 409 ? e.body?.claim ?? null : null,
      review: {
        claim: async () => { calls.claim++; return (opts.claim ?? defaultClaim)(); },
        release: async () => { calls.release++; current.status = 'submitted'; current.claim = null; },
        decide: async (_id, body) => { calls.decisions.push(JSON.parse(JSON.stringify(body))); if (opts.decide) return opts.decide(body); current.status = body.outcome === 'accept' ? 'accepted' : body.outcome === 'refuse' ? 'refused' : 'returned'; return { ...current }; },
      },
    },
    '../../api/packageReview': { packageReview: {
      index: opts.index ?? (async () => indexFor(latest)),
      run: async () => { calls.run++; latest = opts.run ? await opts.run() : reviewSession(calls.run, current.version); return latest; },
      version: opts.version ?? (async (_target, version) => reviewSession(version, current.version)),
      returnWithRequest: async (caseId, version, body) => { calls.returns.push({ caseId, version, body: JSON.parse(JSON.stringify(body)) }); if (opts.returnWithRequest) return opts.returnWithRequest(body); current.status = 'returned'; return { ...current }; },
    } },
    '../account': { useAccount: () => ({ user: officer }), accountSession: () => 1 },
    './reviewSnapshot': { readReviewSnapshot: async () => ({ c: await (opts.getCase ?? (async () => ({ ...current })))(), gaps: opts.gaps ?? [], information: null, messages: [], gapError: '', questionError: '' }) },
    './threadMessages': threadMessages, './sheet': sheet, './workspaceView': workspaceView,
    './reviewData': { useQueue: () => ({ rows: [{ ...current, applicant: { name: 'Mira', applicant_type: 'homebuilder' } }] }), patchRow() {}, setBlocking() {}, loadQueue: async () => {} },
    './queue': queue, './packageView': packageView,
    '../shell/MoreMenu': { MoreMenu: 'MoreMenu' },
    '../notifications/notifications': { getNotificationsState: () => ({ items: [], phase: 'ready' }), subscribeNotifications: () => () => {} },
    './RequestRail': { RequestRail: 'RequestRail' },
  }, { window: { location }, document: { addEventListener() {}, removeEventListener() {} } });
  return { ...h, calls, current, location };
}
