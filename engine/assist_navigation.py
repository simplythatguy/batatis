"""Plans for real app destinations. The browser confirms that a plan actually opened.

This module never returns a URL, changes an application, or treats model prose as
an action. Both typed and completed spoken requests can use the same interface.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

from .access import REVIEWABLE


DestinationId = Literal[
    'applications', 'description', 'questions', 'review', 'application',
    'code-library', 'code-search', 'references', 'downloads', 'officer-view',
    'settings', 'notifications', 'accuracy',
    'question-authority', 'question-owner', 'question-representative',
    'question-mailing-address', 'question-date', 'question-scope', 'question-permit',
    'question-site-address', 'question-legal-description', 'question-alternative',
    'question-rationale', 'question-risk', 'question-mitigation', 'question-assumptions',
    'question-maintenance', 'question-qualifications', 'question-documents',
    'review-queue', 'package-review', 'review-overview', 'review-missing',
    'review-checks', 'review-decide', 'review-application', 'review-messages',
    'review-request', 'review-versions', 'review-close-out',
]


class AssistNavigation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    destination: DestinationId


@dataclass(frozen=True)
class Destination:
    id: DestinationId
    name: str
    aliases: tuple[str, ...] = ()
    role: str | None = None
    case: bool = False
    reviewer_case: bool = False


DESTINATIONS = (
    Destination('applications', 'Applications', ('application list', 'sidebar', 'saved applications'), 'applicant'),
    Destination('description', 'Describe', ('description', 'project description'), 'applicant'),
    Destination('questions', 'Questions', ('questionnaire', 'form questions'), 'applicant'),
    Destination('review', 'Review', ('my review', 'application checklist', 'missing information'), 'applicant'),
    Destination('application', 'Application', ('application form', 'form preview', 'pdf preview'), 'applicant'),
    Destination('code-library', 'Code library', ('building code', 'code text', 'codes')),
    Destination('code-search', 'Look up code', ('code search', 'search codes', 'search the code')),
    Destination('references', 'Rules you chose', ('code references', 'selected rules', 'section c', 'attributions'), 'applicant', True),
    Destination('downloads', 'Download options', ('downloads', 'download', 'export options', 'pdf download'), 'applicant', True),
    Destination('officer-view', 'Officer view', ('officer preview',), 'applicant', True),
    Destination('settings', 'Settings', ('account settings', 'account', 'profile')),
    Destination('notifications', 'Notifications', ('notices', 'alerts')),
    Destination('accuracy', 'Accuracy report', ('accuracy',)),
    Destination('question-authority', 'Reviewing jurisdiction', ('authority', 'jurisdiction', 'reviewing authority'), 'applicant', True),
    Destination('question-owner', 'Owner', ('property owner',), 'applicant', True),
    Destination('question-representative', 'Representative', ('applicant representative',), 'applicant', True),
    Destination('question-mailing-address', 'Mailing address', (), 'applicant', True),
    Destination('question-date', 'Request date', ('application date', 'date'), 'applicant', True),
    Destination('question-scope', 'Application scope', ('site scope', 'one site or every site'), 'applicant', True),
    Destination('question-permit', 'Permit number', ('permit',), 'applicant', True),
    Destination('question-site-address', 'Site address', ('municipal address', 'civic address'), 'applicant', True),
    Destination('question-legal-description', 'Legal description', (), 'applicant', True),
    Destination('question-alternative', 'Proposed alternative', ('alternative', 'alternative description'), 'applicant', True),
    Destination('question-rationale', 'Rationale', ('my rationale',), 'applicant', True),
    Destination('question-risk', 'Risk assessment', ('risk', 'risks'), 'applicant', True),
    Destination('question-mitigation', 'Mitigating measures', ('mitigation', 'mitigations'), 'applicant', True),
    Destination('question-assumptions', 'Assumptions and limits', ('assumptions', 'limits', 'limiting factors'), 'applicant', True),
    Destination('question-maintenance', 'Maintenance', ('operations and maintenance',), 'applicant', True),
    Destination('question-qualifications', 'Qualifications', ('professional qualifications',), 'applicant', True),
    Destination('question-documents', 'Supporting documents', ('documents', 'evidence', 'section d'), 'applicant', True),
    Destination('review-queue', 'Review queue', ('queue', 'applications to review'), 'reviewer'),
    Destination('package-review', 'Review a PDF package', ('package review', 'pdf package', 'uploaded package'), 'reviewer'),
    Destination('review-overview', 'Overview', ('review overview', 'summary'), 'reviewer', True, True),
    Destination('review-missing', 'Missing', ('missing items', 'what is missing'), 'reviewer', True, True),
    Destination('review-checks', 'Checks', ('code checks', 'document checks'), 'reviewer', True, True),
    Destination('review-decide', 'Decide', ('decision', 'decision options'), 'reviewer', True, True),
    Destination('review-application', 'Submitted application', ('application', 'application form'), 'reviewer', True, True),
    Destination('review-messages', 'Officer notices', ('messages', 'correspondence'), 'reviewer', True, True),
    Destination('review-request', 'Information request', ('request for information', 'ask for more'), 'reviewer', True, True),
    Destination('review-versions', 'Review versions', ('versions', 'review history'), 'reviewer', True, True),
    Destination('review-close-out', 'Close-out', ('close out', 'closeout'), 'reviewer', True, True),
)
assert {item.id for item in DESTINATIONS} == set(get_args(DestinationId))


def available_destinations(user, case) -> tuple[Destination, ...]:
    """Server role/access checks restrict the client-provided enabled destination set."""
    reviewer_case = (case is not None and user.role == 'reviewer' and user.authority is not None
                     and user.id != case.owner_id and user.authority == case.authority
                     and case.status in REVIEWABLE)
    return tuple(item for item in DESTINATIONS
                 if (item.role is None or item.role == user.role)
                 and (not item.case or case is not None)
                 and (not item.reviewer_case or reviewer_case))


_PREAMBLE = re.compile(r'^(?:(?:can|could|would|will) you\s+)?(?:please\s+)?', re.I)
_OPEN = re.compile(r'^(?:open|show(?: me)?|take me to|go to|navigate to|switch to|jump to|bring up|let me see)\s+(.+)$', re.I)
_UNSAFE = re.compile(r"\b(?:not|never|don['’]?t|do not|if|unless|would|when|said|says|quoted|quote|delete|submit|send|save|change|write|fill|archive|pin)\b", re.I)
_QUOTED = re.compile(r"""["'“”‘’`]""")


def _name(value: str) -> str:
    value = re.sub(r'[^\w\s-]', '', value.casefold()).replace('-', ' ')
    return ' '.join(value.split())


def plan_navigation(question: str, offered: list[DestinationId], user, case) -> AssistNavigation | None:
    """Only an unambiguous explicit request opens a currently offered destination.

    The whole target must match. Words in a quote, a hypothetical, or a mixed
    request never become a side effect. Unrecognized phrasing stays a question.
    """
    text = question.strip()
    if not offered or _QUOTED.search(text):
        return None
    text = _PREAMBLE.sub('', text, count=1)
    if _UNSAFE.search(text):
        return None
    match = _OPEN.fullmatch(text)
    if not match:
        return None
    target = re.sub(r'\s+(?:please|for me)[.!?]*$', '', match[1].strip(), flags=re.I)
    target = re.sub(r'^(?:the|my)\s+', '', target, count=1, flags=re.I)
    target = re.sub(r'\s+(?:page|screen|tab|panel)[.!?]*$', '', target, count=1, flags=re.I)
    target = _name(target)
    enabled = set(offered)
    matches = [item.id for item in available_destinations(user, case)
               if item.id in enabled and target in {_name(item.name), *(_name(alias) for alias in item.aliases)}]
    return AssistNavigation(destination=matches[0]) if len(matches) == 1 else None
