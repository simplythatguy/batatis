# Export from the app on dev

The Safety Codes Council variance form PDF is not in git. Export checks the file's SHA-256 against `engine/export/field_maps/scc_2026-10.json` (`f44640ca005c957c11a2387d2768fffc35ef93c97125dcca37436fcc0b9afc1d`, the Oct 6, 2026 form). Fetch that file yourself and point the engine at it. Do not commit it.

```sh
export BATATIS_SCC_FORM=/path/to/Variance_Template_final.pdf
# or place the same bytes at reference/guides/SCC-Variance-Form.pdf
uvicorn engine.api:app
curl -X POST "http://127.0.0.1:8000/cases/$CASE_ID/export" \
  -H 'content-type: application/json' \
  -d '{"draft": true}' \
  -o variance.pdf
```

`draft: false` returns 409 while a blocking administrative gap is open. `draft: true` still writes only confirmed facts. A missing form is 503 `SCC variance form not found` once that handler is on the branch; on dev the error names the path in the server log. The response is a filled Part 1 PDF plus the generated appendix. It does not sign the form, fill an officer field, or state that a design complies or is safe.

The code field says `2nd printing` only when the codedb build stats label for `NBC-AE` is `NBC(AE) 2023 p2`. Otherwise the field is `NBC(AE) 2023`.
