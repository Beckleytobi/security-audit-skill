# Audit evaluation starter

These small source fixtures are a smoke test for audit behavior, not evidence of real-world detection rates. Each case has a vulnerable or protected boundary. Audit one fixture directory at a time as a scoped target; never include its paired fixture in the same scope. Do not execute or deploy the fixtures.

| Case | Expected result | Boundary to assess |
|---|---|---|
| `tenant-write-vulnerable` | One reportable cross-tenant write | Caller-controlled document ID reaches a shared update without an ownership decision. |
| `tenant-write-protected` | No reportable finding for that boundary | Ownership is checked before the update. |
| `path-read-vulnerable` | One reportable out-of-directory read, if caller can supply the filename | Caller-controlled path reaches a file read without containment. |
| `path-read-protected` | No reportable finding for that boundary | The caller can select only a simple `.txt` name, not a path. |

Assume the report directory and its entries are trusted and cannot be modified by the caller. If an audit needs additional deployment facts to establish reachability or impact, record `needs_validation` rather than forcing a hit. The benchmark label concerns only the stated boundary.

For each case, record the skill revision, model, host, profile, scope, agent budget, source ref, and run time. Run the same configuration at least three times per case. Have a reviewer inspect each finding's source trace and result before marking `detected`; do not match findings by title or fingerprint alone. Count unrelated confirmed findings separately as false positives only after review. Record incomplete runs separately; do not treat them as clean scans.

Put one row per run in a CSV with columns `case_id,run_id,detected,false_positives,agent_calls,duration_seconds,complete`. Leave `duration_seconds` empty if timing was not recorded; the score will count only timed runs. For protected cases, `detected` must be `false`; a claimed boundary finding belongs in `false_positives` after review. Use `python evaluation/score.py <csv>` for the bundled toy cases. For permissioned real repositories, create a JSON object mapping each scoped case ID to `true` (known vulnerable boundary) or `false` (known protected boundary), then pass `--cases <manifest.json>`. Keep the case labels and adjudication evidence separate from independent audit prompts. Compare profiles on the same cases and budgets. A few focused source reviews do not measure full-audit effectiveness.
