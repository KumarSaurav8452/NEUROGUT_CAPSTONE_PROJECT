# Notes for Claude Code

Spec: `../PRD_SCZ_Data_Retrieval.md`. Phase 0 findings and every deviation from the PRD: `docs/discovery.md`. Read both before changing behaviour.

## Run
```
pip install -e .[test]          # or: PYTHONPATH=src
python -m scz_data phase1       # config -> metadata -> label
python -m scz_data phase2 --dry-run   # filter -> download dry-run (no FASTQs fetched)
python -m scz_data metadata --study Zhu_2020B_SCZ --refresh
python -m pytest -q
```

## Conventions
- All parameters in `config/config.yaml`. Study facts that Table S1 cannot hold (extra accessions, mirrors, platform split, disease-only) go in `study_overrides` there; `config/studies.yaml` is generated, never hand-edited.
- Labels only via `config/label_maps/<StudyID>.yaml`. Never invent labels: if a group is not in archive metadata or a paper supplement in `data/supplements/`, stop and ask.
- `data/raw_metadata/<StudyID>.tsv` is one row per run in the schema of `src/scz_data/fetch/schema.py` (`RUN_COLUMNS` + `attr_*`). Keep raw: no filtering there; filtering is FR-4.
- Every network call goes through `fetch.http.CachedHttp` (cache in `data/cache/http`, retries, rate limit). Reruns must not refetch.
- One failing study must not stop the others; logs go to `logs/<stage>/<StudyID>.log`.
- Never pass `stream --yes` (or answer its prompt) without the user's explicit OK in chat for that exact run. Tool setup (`scripts/setup_wsl_tools.sh`, ~3.6 GB) also needs an OK.
- Transient FASTQs must stay on the Windows side (`data/`): space freed inside the WSL virtual disk is not returned to C:.
- Do not download FASTQs without asking (sizes are in the hundreds of GB per study; this machine had 28 GB free on 25 Oct 2026, see docs/phase2.md).
- Filters never force a count: a removed sample gets exactly one `exclusion_step`; gaps vs Table S1 are reported.
