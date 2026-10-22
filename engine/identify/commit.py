"""Automatic commit policy: Part 9 commits, every other Part is a quoted choice.

An article is committed only when ALL of these hold (gap matrix AC3.3):
  1. the run is not the keyword fallback,
  2. the article is in Part 9,
  3. calibration.json says Part 9 is calibrated, validated on the validation fold, for this exact
     pipeline config (config_hash),
  4. the verifier ran and picked the article with a verified word-for-word quote,
  5. its rerank probability is at least the fitted threshold,
  6. fewer than max_commits articles are already committed.

With calibration.json absent, unreadable, or not calibrated for this config, nothing is committed.
That is the honest default: the 0.75 placeholder in cli_sut.py was never fitted. A commit is what the
identification returns; it never writes provisions. The applicant still decides yes, no or not sure.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALIBRATION_FILE = HERE / 'calibration.json'
COMMIT_PARTS = frozenset({9})        # product rule (AGENTS.md); calibration cannot widen it
MAX_COMMITS = 3


@dataclass(frozen=True)
class CommitPolicy:
    status: str                                   # 'calibrated' | 'uncalibrated'
    reason: str
    thresholds: dict[int, float] = field(default_factory=dict)   # calibrated Parts only
    max_commits: int = MAX_COMMITS
    config_hash: str | None = None
    source: str = 'engine/identify/calibration.json'

    def view(self) -> dict:
        return {'status': self.status, 'reason': self.reason, 'parts': sorted(COMMIT_PARTS),
                'thresholds': {str(k): v for k, v in sorted(self.thresholds.items())},
                'max_commits': self.max_commits, 'config_hash': self.config_hash, 'source': self.source}


def _uncalibrated(reason: str) -> CommitPolicy:
    return CommitPolicy('uncalibrated', reason)


def load_policy(config_hash: str, path: Path | str | None = None) -> CommitPolicy:
    """Read calibration.json. Anything short of a complete, matching, calibrated file commits nothing."""
    path = Path(path) if path else CALIBRATION_FILE
    if not path.is_file():
        return _uncalibrated('calibration.json is absent; automatic commits are off')
    try:
        data = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _uncalibrated('calibration.json is unreadable')
    if not isinstance(data, dict) or data.get('status') != 'calibrated':
        return _uncalibrated('calibration.json does not say status: calibrated')
    if data.get('validated_on') != 'validation':
        return _uncalibrated('calibration.json was not validated on the validation fold')
    if data.get('config_hash') != config_hash:
        return _uncalibrated('calibration.json was fitted for a different pipeline config')
    parts = data.get('parts') if isinstance(data.get('parts'), dict) else {}
    thresholds: dict[int, float] = {}
    for key, rule in parts.items():
        try:
            part = int(key)
            threshold = float(rule['threshold'])
        except (TypeError, ValueError, KeyError):
            continue
        if part in COMMIT_PARTS and isinstance(rule, dict) and rule.get('status') == 'calibrated' \
                and 0 < threshold <= 1:
            thresholds[part] = threshold
    if not thresholds:
        return _uncalibrated('no Part 9 threshold is calibrated')
    try:
        cap = int(data.get('max_commits', MAX_COMMITS))
    except (TypeError, ValueError):
        cap = MAX_COMMITS
    return CommitPolicy('calibrated', 'fitted on the calibration fold, validated on the validation fold',
                        thresholds, max(0, min(cap, MAX_COMMITS)), config_hash)


def decide(*, part: int, probability: float | None, fallback: bool, verifier_ran: bool, verifier_picked: bool,
           committed_so_far: int, policy: CommitPolicy) -> tuple[bool, str]:
    """(commit?, reason). The reason is shown on the card and in the trace."""
    if fallback:
        return False, 'keyword fallback: nothing is committed'
    if part not in COMMIT_PARTS:
        return False, 'outside Part 9: offered as a quoted choice'
    threshold = policy.thresholds.get(part)
    if policy.status != 'calibrated' or threshold is None:
        return False, f'not committed: {policy.reason}'
    if not verifier_ran:
        return False, 'not committed: the verifier did not run'
    if not verifier_picked:
        return False, 'not committed: the verifier did not pick it'
    if probability is None or probability < threshold:
        return False, f'not committed: rerank probability below the fitted threshold {threshold:g}'
    if committed_so_far >= policy.max_commits:
        return False, f'not committed: at most {policy.max_commits} commits'
    return True, f'committed: Part 9, verifier quote checked, probability at least {threshold:g}'
