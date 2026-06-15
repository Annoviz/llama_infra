## Plan: Update Qwen model aliases and rebuild

Update Ollama model sources so Planner/Coder/Fast-Coder point to the requested tags, persist those base models in sync config, then rebuild aliases via the repository’s standard build path (`make` + `scripts/build_models.sh`) and verify resulting aliases.

**Steps**
1. Baseline check: confirm current model definitions in `workspace/models/Planner.Modelfile`, `workspace/models/Coder.Modelfile`, `workspace/models/FastCoder.Modelfile`, and existing sync entries in `workspace/models/models-config.yaml` to avoid overwriting unrelated user edits.
2. Update Coder model source and context: in `workspace/models/Coder.Modelfile`, set `FROM qwen3-coder:30b` and `PARAMETER num_ctx 65536` (*depends on step 1*).
3. Update Fast-Coder model source: in `workspace/models/FastCoder.Modelfile`, set `FROM qwen2.5-coder:1.5b` (*depends on step 1*).
4. Keep Planner aligned: ensure `workspace/models/Planner.Modelfile` remains on `FROM qwen3.6:35b` with current params unchanged unless drift is detected (*depends on step 1*).
5. Persist base model sync entries: in `workspace/models/models-config.yaml`, add/update entries so `make models-sync` pulls `qwen3-coder:30b` and `qwen2.5-coder:1.5b` for future runs (*depends on steps 2-3; can be prepared in parallel with step 4*).
6. Build prerequisites: start Ollama stack if needed using `make up-ollama`; validate `ollama-server` container is healthy before pull/build (*depends on steps 2-5*).
7. Pull/sync base models: run `make models-sync` so entrypoint sync pulls newly configured base models (*depends on step 6*).
8. Rebuild aliases: run `./scripts/build_models.sh` to recreate `planner`, `coder`, and `fast-coder` aliases from Modelfiles (*depends on step 7*).
9. Verify output: check `ollama list` inside container to confirm aliases exist and map to expected sources; do quick smoke invocations for `planner`, `coder`, `fast-coder` if requested (*depends on step 8*).
10. Document delta: summarize file changes + build verification results for handoff (*depends on step 9*).

**Relevant files**
- `/home/dima/Documents/Projects/Personal/llama_infra/workspace/models/Coder.Modelfile` — set source to `qwen3-coder:30b` and context window to `65536`.
- `/home/dima/Documents/Projects/Personal/llama_infra/workspace/models/FastCoder.Modelfile` — set source to `qwen2.5-coder:1.5b`.
- `/home/dima/Documents/Projects/Personal/llama_infra/workspace/models/Planner.Modelfile` — validate requested Planner source already matches.
- `/home/dima/Documents/Projects/Personal/llama_infra/workspace/models/models-config.yaml` — persist new base pulls for `make models-sync`.
- `/home/dima/Documents/Projects/Personal/llama_infra/scripts/build_models.sh` — execution path for alias rebuild.
- `/home/dima/Documents/Projects/Personal/llama_infra/Makefile` — `models-sync`/stack lifecycle targets.

**Verification**
1. Run `make up-ollama` and confirm container is running.
2. Run `make models-sync` and verify pulls for `qwen3-coder:30b` and `qwen2.5-coder:1.5b` complete without errors.
3. Run `./scripts/build_models.sh` and confirm successful `ollama create` for `planner`, `coder`, `fast-coder`.
4. Run `ollama list` in `ollama-server` and verify aliases are present.
5. Optional smoke test: run one prompt each with `ollama run planner`, `ollama run coder`, `ollama run fast-coder`.

**Decisions**
- Persist the new base models in `models-config.yaml` for future `make models-sync` runs (user-confirmed).
- Keep `workspace/requirements.txt` untouched (frozen snapshot policy).
- Use repository-standard commands (`make` targets + `scripts/build_models.sh`) instead of ad-hoc compose commands.

**Further Considerations**
1. `scripts/build_models.sh` currently references alias naming in a memory note with a typo (`fast-codder`) but script itself builds `fast-coder`; no script change required unless explicit alias rename is desired.
2. If `qwen3-coder:30b` is not available in the upstream registry used by Ollama, substitute with an available tag after listing remote tags, then re-run sync/build.

**Audit Snapshot (2026-06-11)**
- `Planner.Modelfile`: `PARAMETER num_ctx 65536` — aligned.
- `Coder.Modelfile`: `PARAMETER num_ctx 32768` — not aligned with requested `65536` for qwen3-coder profile.
- `FastCoder.Modelfile`: `PARAMETER num_ctx 32768` — aligned with file’s own stated minimum (32k).
- Additional `n_ctx` values exist in JSON llama.cpp configs under `workspace/models/*.json`; these are separate from Ollama Modelfiles and were not part of the requested qwen alias update.
