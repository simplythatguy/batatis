# Re-run Opus 5.5 review (when Task slugs work)

Cloud agents that hit `On-demand usage is required` cannot spawn `claude-opus-5-5-*` Tasks. When enabled:

1. Point a Task at `model: claude-opus-5-5-max` (else `xhigh`).
2. Score all files under the store path `internal/env-experiments/battle-tests/responses/` (or repo copies if mirrored).
3. Require pass-bar: average ≥ 4.0, zero material gaps.
4. Write `reviews/opus-bt01-35.md` with `reviewer_model` recorded.
5. If FAIL, patch `.cursor/skills/batatis-*` / rules and re-answer failed IDs only.
