"""FR-6: read QC (fastp) + host-read removal (bowtie2 vs GRCh38), platform-aware (PRD §6.3).

fastp writes trimmed reads to stdout and bowtie2 reads them from stdin, so no trimmed-but-host-containing
intermediate ever touches the disk. Only the host-removed reads are written (if `stream.keep_clean`).
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path, PureWindowsPath

_R1 = re.compile(r"(_1|_R1|\.R1|\.1|_f1)\.f(ast)?q\.gz$", re.IGNORECASE)
_R2 = re.compile(r"(_2|_R2|\.R2|\.2|_r2)\.f(ast)?q\.gz$", re.IGNORECASE)


class ToolError(RuntimeError):
    pass


# --- paths & runner --------------------------------------------------------------------------
def sh_word(value: str) -> str:
    """Shell-quote, but let a leading ~/ expand to $HOME inside the runner."""
    if value.startswith("~/"):
        return '"$HOME/' + value[2:].replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$") + '"'
    return shlex.quote(value)


class Runner:
    """Runs bash scripts natively or inside a WSL distro; converts Windows paths for the latter."""

    def __init__(self, tcfg: dict):
        self.kind = tcfg["runner"]
        self.distro = tcfg.get("wsl_distro", "Ubuntu")
        self.path_prepend = tcfg.get("path_prepend") or ""
        if self.kind not in ("wsl", "native"):
            raise ValueError(f"tools.runner must be wsl or native, not {self.kind!r}")

    def path(self, p: str | Path) -> str:
        if self.kind == "native":
            return str(Path(p).resolve())
        w = PureWindowsPath(Path(p).resolve())
        drive = w.drive.rstrip(":").lower()
        return f"/mnt/{drive}/" + "/".join(w.parts[1:])

    def q(self, p: str | Path) -> str:
        return shlex.quote(self.path(p))

    def header(self) -> str:
        lines = ["set -euo pipefail"]
        if self.path_prepend:
            lines.append(f"export PATH={sh_word(self.path_prepend)}:\"$PATH\"")
        return "\n".join(lines) + "\n"

    def run(self, body: str, script_path: Path, timeout: float | None = None) -> subprocess.CompletedProcess:
        """Write the script next to its logs (kept for reproducibility) and execute it."""
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(self.header() + body, encoding="utf-8", newline="\n")
        cmd = ["bash", self.path(script_path)]
        if self.kind == "wsl":
            cmd = ["wsl.exe", "-d", self.distro, "--"] + cmd
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def check_tools(runner: Runner, tcfg: dict, scratch: Path) -> dict[str, str]:
    """Versions of fastp/bowtie2 and whether the host index exists. Raises ToolError with a fix-it hint."""
    idx = sh_word(tcfg["host_index"])
    body = (
        "if command -v fastp >/dev/null; then echo fastp=$(fastp --version 2>&1 | head -1); else echo fastp=missing; fi\n"
        "if command -v bowtie2 >/dev/null; then echo bowtie2=$(bowtie2 --version 2>&1 | head -1 | awk '{print $NF}');"
        " else echo bowtie2=missing; fi\n"
        f"if ls {idx}.1.bt2 >/dev/null 2>&1 || ls {idx}.1.bt2l >/dev/null 2>&1; then echo index=ok; else echo index=missing; fi\n"
    )
    try:
        res = runner.run(body, scratch / "check_tools.sh", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ToolError(f"cannot start the tool runner ({runner.kind}): {e}")
    found = dict(line.split("=", 1) for line in res.stdout.splitlines() if "=" in line)
    problems = []
    for tool in ("fastp", "bowtie2"):
        if not re.search(r"\d+\.\d+", found.get(tool, "")):
            problems.append(f"{tool} not found")
    if found.get("index") != "ok":
        problems.append(f"host index not found at {tcfg['host_index']}")
    if problems:
        raise ToolError("; ".join(problems) + ". Run scripts/setup_wsl_tools.sh inside WSL (see README).\n"
                        f"runner output: {res.stdout.strip()} {res.stderr.strip()[:300]}")
    return found


# --- commands --------------------------------------------------------------------------------
def pair_files(paths: list[str]) -> tuple[str, str | None]:
    """(R1, R2) for a paired run, (R, None) for single. ENA sometimes adds a third unpaired file: dropped."""
    if len(paths) == 1:
        return paths[0], None
    r1 = [p for p in paths if _R1.search(p)]
    r2 = [p for p in paths if _R2.search(p)]
    if len(r1) == 1 and len(r2) == 1:
        return r1[0], r2[0]
    raise ValueError(f"cannot tell R1/R2 apart in {paths}")


def fastp_options(platform: str, layout: str, tcfg: dict) -> str:
    key = f"{platform}_{layout}"
    if key not in tcfg["fastp"]:
        raise ValueError(f"no fastp settings for {key} (config tools.fastp)")
    return " ".join(x for x in (tcfg["fastp"].get("common", ""), tcfg["fastp"][key]) if x)


def build_run_script(runner: Runner, tcfg: dict, platform: str, layout: str, inputs: list[Path],
                     qc_prefix: Path, out_prefix: Path | None) -> str:
    """fastp | bowtie2 for one run. out_prefix=None -> count only, nothing written but logs."""
    t = int(tcfg["threads"])
    idx = sh_word(tcfg["host_index"])
    q = runner.q
    opts = fastp_options(platform, layout, tcfg)
    logs = (f"-j {q(f'{qc_prefix}.fastp.json')} -h {q(f'{qc_prefix}.fastp.html')}")
    bt2 = f"bowtie2 -p {t} {tcfg.get('bowtie2_args', '')} -x {idx}"
    # The bowtie2 wrapper passes --un*-gz paths to `sh` unquoted, so a space in the path (e.g. "Neurogut
    # schizophrenia") breaks it. Write through a space-free symlink to the output folder instead.
    setup = ""
    if out_prefix:
        setup = (
            'alias_dir=$(mktemp -d)\n'
            'trap \'rm -rf "$alias_dir"\' EXIT\n'  # removes only the link, never the target
            f'ln -s {q(Path(out_prefix).parent)} "$alias_dir/out"\n'
        )
        out = f'"$alias_dir/out/{Path(out_prefix).name}'
    if layout == "PAIRED":
        r1, r2 = pair_files([str(p) for p in inputs])
        un = f'--un-conc-gz {out}.R%.fq.gz"' if out_prefix else ""
        return setup + (
            f"fastp -i {q(r1)} -I {q(r2)} --stdout -w {min(t, 16)} {opts} {logs} 2> {q(f'{qc_prefix}.fastp.log')} \\\n"
            f"  | {bt2} --interleaved - {un} -S /dev/null 2> {q(f'{qc_prefix}.bowtie2.log')}\n"
        )
    if len(inputs) != 1:
        raise ValueError(f"single-end run with {len(inputs)} files")
    un = f'--un-gz {out}.fq.gz"' if out_prefix else ""
    return setup + (
        f"fastp -i {q(inputs[0])} --stdout -w {min(t, 16)} {opts} {logs} 2> {q(f'{qc_prefix}.fastp.log')} \\\n"
        f"  | {bt2} -U - {un} -S /dev/null 2> {q(f'{qc_prefix}.bowtie2.log')}\n"
    )


# --- log parsing -----------------------------------------------------------------------------
def parse_fastp(json_path: Path) -> dict[str, int]:
    s = json.loads(Path(json_path).read_text())["summary"]
    return {"raw_reads": int(s["before_filtering"]["total_reads"]), "clean_reads": int(s["after_filtering"]["total_reads"])}


def parse_bowtie2(log_text: str, paired: bool) -> dict[str, int]:
    """Reads left after host removal, counted as single reads (2 per pair) to match fastp's total_reads."""
    total = re.search(r"^(\d+) reads; of these:", log_text, re.MULTILINE)
    if paired:
        m = re.search(r"^\s*(\d+) \([\d.]+%\) aligned concordantly 0 times$", log_text, re.MULTILINE)
        if not (total and m):
            raise ToolError("unrecognised bowtie2 paired-end summary")
        return {"bowtie2_input_reads": 2 * int(total.group(1)), "host_removed_reads": 2 * int(m.group(1))}
    m = re.search(r"^\s*(\d+) \([\d.]+%\) aligned 0 times$", log_text, re.MULTILINE)
    if not (total and m):
        raise ToolError("unrecognised bowtie2 single-end summary")
    return {"bowtie2_input_reads": int(total.group(1)), "host_removed_reads": int(m.group(1))}
