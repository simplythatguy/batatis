# Requirement identification contract

Identification prepares an application for review. It does not establish technical
correctness, equivalence, safety, or approval.

The production result is a source-backed requirement ledger. Retrieval, source
verification, applicability, and the applicant's departure are separate decisions.
Finding an article does not establish that it applies. A design following an article
does not make that article irrelevant to the application.

## Inputs and refresh

Identification consumes the latest fact for each field, including confirmed
answers and explicitly empty replacements. Unconfirmed facts and document text
remain labelled context. It reads the supported selectable text from attached
files, preserving file/page origin; unreadable pages and reader limits are gaps.
Personal fields are excluded from the search context.

`input_sha256` binds the active fact ledger, jurisdiction, attachment inventory,
and exact attachment bytes. Generated results and project titles are excluded.
GET does not call a provider or change storage; it reports a changed input as
stale, including a changed or unverifiable code corpus. An applicant's benchmark
and departure survive an unchanged rerun; changed inputs retain the narrative as
a comparison to reconfirm. POST identification uses current inputs. Intake and answer updates refresh
the deterministic requirement profile within their existing compare-and-swap.
Historical provider profiles remain explicit-only. Raw fact writes and file
inventory changes invalidate the fingerprint and require a fresh identification.

The saving layer continues to own concurrency and durability. Identification
does not introduce a queue, new storage adapter, retrying writes, or job lifecycle.
The input composer and local `refresh` function are reusable by other mutation
paths without changing those mechanisms.

## Application scope and applicant confirmation

- A varied requirement is an applicant-confirmed benchmark and departure. Its
  objective/function attribution still comes from deterministic lookup.
- Supporting requirements stay in the ledger when the design follows them. A
  “No” to departing from a rule withdraws a variance claim, not the supporting
  requirement or its dependency evidence.
- Administrative requirements describe information and documentation to address.
  They do not imply that a professional has approved the proposed solution.
- Conditional and unresolved requirements stay available for review, with their
  missing facts and source limitations. They are not silently discarded by rank.
- Previously confirmed requirements survive retrieval reruns. Changed facts
  require their applicability to be reviewed again; prior confirmation is not
  evidence that the new proposal addresses them.

Applicant confirmation must distinguish applicability from departure and must
identify the fact, condition, or source behind an exclusion. Unknown is a useful
answer. An applicant cannot confirm a missing code source into existence.
The question-flow and visual-language work owns how these decisions are presented.

## Evidence and coverage

Every released code identifier, citation and quoted passage must resolve to the
NBC 2023 Alberta Edition second-printing corpus. A document's reference is a search
lead, not current code authority. Notes are explanatory context. Missing table,
appendix, fire-code, energy-code or referenced-standard text remains an explicit
coverage gap; a reference to that text is not a review of it.

Scanning all indexed text or closing a cross-reference graph cannot establish
that every applicable requirement has been identified. Neither lexical retrieval
nor an AI judgement proves that omitted articles are irrelevant. The result must
keep that limitation visible in its machine-readable coverage state.

Broad reference closure can retrieve most of the corpus even for a short request.
Those records are review candidates, not a finding that the application needs
every one. Direct input matches and confirmed selections lead the ordering;
ordering does not remove the rest. Shared passages are stored once in
`requirement_evidence` and linked by evidence IDs. The current deterministic
profile has no validated precision or completeness result and can impose a large
review burden. It must not be promoted as a proven accuracy improvement.

`scope_assessments` evaluates only the confirmed storey, area and supplied
major-occupancy conditions in the verified Part 9 entry sentence. Two storeys
and eight storeys produce different condition assessments. Missing or conflicting
facts stay unresolved, and meeting these gates does not determine the applicable
Part. A failed gate does not delete a Part 9 detail invoked by another requirement.

## Measurement

The separate requirement-coverage evaluator owns answer keys, eligibility,
denominators and reporting. Production identification does not import it. Cases
used for tuning cannot become a fresh held-out result by changing their label.
Minimum known lists measure preservation of those known requirements; they cannot
establish exhaustive identification accuracy. Expert verification and key
completeness are independent recorded properties.

Record actual provider requests, token/cost availability, errors and elapsed time
beside each captured prediction. A local deterministic run spends zero on model
requests; that is not a claim about the cost of intake, document review, hosting,
or human adjudication. No synthetic regression is a product accuracy result.
