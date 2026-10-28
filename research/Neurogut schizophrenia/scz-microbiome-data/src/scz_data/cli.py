"""Command line: python -m scz_data <stage> [--study ID ...] [--refresh] [--dry-run] [--subset N]."""

from __future__ import annotations

import argparse

from scz_data import download, fetch, filter as filtering, harmonize, label, parse_table, profile, qc, report, stream
from scz_data.settings import load_settings, load_studies

STAGES = ["config", "metadata", "label", "filter", "download", "check-tools", "stream", "profile", "profile-status",
          "harmonize", "report"]
ALIASES = {
    "phase1": ["config", "metadata", "label"],
    "phase2": ["filter", "download"],  # download stage is --dry-run only; real transfer is `stream`
    "run": ["config", "metadata", "label", "filter", "download"],
    "phase5": ["filter", "harmonize", "report"],  # after profiling: final filter, FR-8 table, FR-9 report
}


def confirm(summary: str, assume_yes: bool) -> bool:
    """PRD FR-5: print the size and ask before downloading. No TTY / EOF counts as 'no'."""
    print(summary)
    if assume_yes:
        print("--yes given: proceeding.")
        return True
    try:
        return input("\nDownload and process these samples now? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def _select(studies: list[dict], wanted: list[str] | None) -> list[dict]:
    if not wanted:
        return studies
    unknown = set(wanted) - {s["study_id"] for s in studies}
    if unknown:
        raise SystemExit(f"unknown study id(s): {sorted(unknown)}")
    return [s for s in studies if s["study_id"] in wanted]


def _report(stage: str, status: dict[str, str]) -> bool:
    print(f"\n== {stage} summary ==")
    for sid, st in status.items():
        print(f"  {sid:<20} {st}")
    return not any(st.startswith("FAILED") for st in status.values())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="scz_data", description=__doc__)
    p.add_argument("stage", choices=STAGES + list(ALIASES), help="a stage, or phase1 / phase2 / phase5 / run")
    p.add_argument("--study", action="append", help="limit to this StudyID (repeatable)")
    p.add_argument("--refresh", action="store_true", help="ignore the HTTP cache and refetch")
    p.add_argument("--dry-run", action="store_true", help="download: list files and total size, download nothing")
    p.add_argument("--subset", type=int, metavar="N", help="download/stream: only N samples per group per study")
    p.add_argument("--yes", action="store_true", help="stream: skip the confirmation prompt")
    p.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = p.parse_args(argv)

    settings = load_settings(args.root)
    stages = ALIASES.get(args.stage, [args.stage])
    if "download" in stages and not args.dry_run:
        raise SystemExit("download: only --dry-run here; real transfer is `python -m scz_data stream`.")
    ok = True
    for stage in stages:
        if stage == "config":
            parse_table.run(settings)
            continue
        studies = _select(load_studies(settings), args.study)
        if stage == "metadata":
            ok &= _report(stage, fetch.run(settings, studies, refresh=args.refresh))
        elif stage == "label":
            ok &= _report(stage, label.run(settings, studies))
        elif stage == "filter":
            ok &= _report(stage, filtering.run(settings, studies))
        elif stage == "download":
            ok &= _report(stage, download.run(settings, studies, dry_run=args.dry_run, subset=args.subset))
        elif stage == "check-tools":
            tcfg = settings.cfg["tools"]
            try:
                found = qc.check_tools(qc.Runner(tcfg), tcfg, settings.resolve(settings.cfg["stream"]["qc_dir"]))
            except qc.ToolError as e:
                print(f"tools NOT ready: {e}")
                return 1
            print("tools ready: " + ", ".join(f"{k}={v}" for k, v in found.items()))
        elif stage == "stream":
            todo, manifest, status, summary = stream.plan(settings, studies, args.subset)
            if todo is None or not len(todo):
                print(summary or "nothing to process")
                ok &= _report(stage, status)
                continue
            if args.dry_run:
                print(summary + "\n--dry-run: nothing downloaded.")
                continue
            if not confirm(summary, args.yes):
                print("Not confirmed: nothing downloaded.")
                return 1
            ok &= _report(stage, stream.run(settings, studies, args.subset, todo, manifest))
        elif stage == "harmonize":
            ok &= _report(stage, harmonize.run(settings, studies))
        elif stage == "report":
            ok &= _report(stage, report.run(settings, studies))
        elif stage == "profile-status":
            profile.write_outputs(settings)  # refresh merged tables + QC from finished samples
            print(profile.status(settings, studies))
        elif stage == "profile":
            todo, runs, status, summary = profile.plan(settings, studies, args.subset)
            if todo is None or not len(todo):
                profile.write_outputs(settings)
                print(summary or "nothing to profile")
                ok &= _report(stage, status)
                continue
            if args.dry_run:
                print(summary + "\n--dry-run: nothing downloaded.")
                continue
            if not confirm(summary, args.yes):
                print("Not confirmed: nothing downloaded.")
                return 1
            ok &= _report(stage, profile.run(settings, todo, runs))
    return 0 if ok else 1
