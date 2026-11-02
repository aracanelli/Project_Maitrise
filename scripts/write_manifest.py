"""
Write the run manifest to <data-dir>/results/run_manifest.json.

The manifest records package, srcML and git versions, the CUDA device and hardware, the
pinned corpus heads, the evaluation parameters (bootstrap sizes and seed, resolved the way
scripts/evaluate.py resolves them), the sha256 of every config and source file and of the
data artefacts, and the current time. The script also writes requirements-lock.txt (pip
freeze of the running interpreter) at the project root.

Mining directories ending in .tmp or .old, left by an interrupted mining run, are not
hashed and are listed under incomplete_mining_outputs. Repositories are only read.

Usage:
    python -m scripts.write_manifest [--data-dir DIR] [--no-lock]
"""

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from src.common.config import ROOT, DATA, CONFIGS, load_config, repo_path

PACKAGES = {
    "torch": ["torch"],
    "torch_geometric": ["torch_geometric", "torch-geometric"],
    "scikit-learn": ["scikit-learn"],
    "numpy": ["numpy"],
    "scipy": ["scipy"],
    "pandas": ["pandas"],
    "lxml": ["lxml"],
    "GitPython": ["GitPython"],
    "matplotlib": ["matplotlib"],
    "PyYAML": ["PyYAML"],
    "Levenshtein": ["Levenshtein", "python-Levenshtein"],
    "threadpoolctl": ["threadpoolctl"],
}
DATA_PATTERNS = [
    "interim/mining/*/summary.json", "interim/mining/*/*.jsonl",
    "processed/events_master.jsonl", "processed/events_master.csv",
    "processed/instances/*.jsonl", "processed/instances/*.json",
    "processed/features/*.csv", "processed/features/*.json", "processed/features/*.jsonl",
    "processed/graphs/*_index.csv", "processed/graphs/*_meta.json", "processed/graphs/*.npz",
    "results/predictions/**/*.csv", "results/predictions/**/*.json",
    "results/importance/**/*.csv", "results/importance/**/*.json",
    "results/tables/*", "results/figures/*", "results/report/*", "results/error_analysis/*",
    "results/rq1/*", "results/validation/*",
]


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def package_versions():
    out = {}
    for name, dists in PACKAGES.items():
        out[name] = None
        for d in dists:
            try:
                out[name] = metadata.version(d)
                break
            except metadata.PackageNotFoundError:
                continue
    return out


def run(cmd, cwd=None):
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    return res.returncode, (res.stdout or res.stderr).strip()


def srcml_version():
    try:
        from src.parsing.srcml_parser import _find_srcml
        code, text = run([_find_srcml(), "--version"])
        return text if code == 0 else None
    except Exception as e:
        return f"unavailable ({e})"


def cuda_info():
    try:
        import torch
    except Exception as e:
        return {"available": False, "error": str(e)}
    info = {"available": bool(torch.cuda.is_available()), "torch_cuda": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None}
    if info["available"]:
        info["device_name"] = torch.cuda.get_device_name(0)
        info["device_count"] = torch.cuda.device_count()
    return info


def cpu_model():
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        if sys.platform == "darwin":
            return run(["sysctl", "-n", "machdep.cpu.brand_string"])[1]
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or None


def ram_gb():
    try:
        if sys.platform == "win32":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                           [(n, ctypes.c_ulonglong) for n in ("total_phys", "avail_phys", "total_page", "avail_page",
                                                              "total_virtual", "avail_virtual", "avail_ext")]
            m = MemoryStatus()
            m.dwLength = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            total = m.total_phys
        else:
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return round(total / 2 ** 30, 1)
    except Exception:
        return None


def hardware():
    return {"cpu": cpu_model(), "logical_cores": os.cpu_count(), "ram_gb": ram_gb()}


def evaluation_params(exp):
    """The evaluation block of configs/experiment.yaml, with the bootstrap sizes and seed
    from src.evaluation.analysis.bootstrap_sizes, which scripts/evaluate.py also calls."""
    ev = dict(exp.get("evaluation") or {})
    configured = "bootstrap_seed" in ev
    try:
        from src.evaluation.analysis import bootstrap_sizes
        b, b_tests, seed = bootstrap_sizes(exp)
    except Exception as e:
        ev.setdefault("bootstrap_seed", None)
        ev["bootstrap_seed_source"] = f"unavailable ({e})"
        return ev
    ev.update({"bootstrap_samples": b, "bootstrap_samples_tests": b_tests, "bootstrap_seed": seed,
               "bootstrap_seed_source": "configs/experiment.yaml" if configured
               else "default of src/evaluation/analysis.py bootstrap_sizes"})
    return ev


def corpus_heads():
    rows = []
    for r in load_config("corpus")["repos"]:
        path = repo_path(r["name"])
        row = {"name": r["name"], "pinned_head": r["head"], "remote": r.get("remote"),
               "modeling": bool(r.get("modeling")), "clone_present": path.exists()}
        if path.exists():
            code, text = run(["git", "cat-file", "-t", r["head"]], cwd=path)
            row["pinned_head_present"] = code == 0 and text == "commit"
            code, text = run(["git", "rev-parse", "HEAD"], cwd=path)
            row["clone_head"] = text if code == 0 else None
        rows.append(row)
    return rows


def source_hashes():
    files = {}
    for f in sorted(CONFIGS.glob("*.yaml")):
        files[f.relative_to(ROOT).as_posix()] = sha256_file(f)
    for top in ("src", "scripts"):
        for f in sorted((ROOT / top).rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            files[f.relative_to(ROOT).as_posix()] = sha256_file(f)
    return files


def incomplete_mining(data_dir):
    base = Path(data_dir) / "interim" / "mining"
    if not base.exists():
        return []
    return sorted(d.name for d in base.iterdir() if d.is_dir() and d.suffix in (".tmp", ".old"))


def data_hashes(data_dir):
    data_dir = Path(data_dir)
    skip = set(incomplete_mining(data_dir))
    out = {}
    for pat in DATA_PATTERNS:
        for f in sorted(data_dir.glob(pat)):
            rel = f.relative_to(data_dir)
            if not f.is_file() or rel.as_posix() in out:
                continue
            if rel.parts[:2] == ("interim", "mining") and rel.parts[2] in skip:
                continue
            out[rel.as_posix()] = sha256_file(f)
    return out


def prediction_inventory(data_dir):
    base = Path(data_dir) / "results" / "predictions"
    inv = {}
    if not base.exists():
        return inv
    for f in sorted(base.glob("*/*/*/seed*.csv")):
        setting, task, model = f.parts[-4], f.parts[-3], f.parts[-2]
        inv.setdefault(setting, {}).setdefault(task, {}).setdefault(model, []).append(f.stem)
    return inv


def build_manifest(data_dir=DATA):
    exp = load_config("experiment")
    ev = evaluation_params(exp)
    return {
        "generated": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": package_versions(),
        "srcml": srcml_version(),
        "git": run(["git", "--version"])[1],
        "cuda": cuda_info(),
        "hardware": hardware(),
        "seeds": {"sampling": exp["sampling"]["seed"], "training": exp["protocol"]["seeds"],
                  "bootstrap": ev["bootstrap_seed"], "bootstrap_samples": ev.get("bootstrap_samples")},
        "evaluation": ev,
        "corpus": corpus_heads(),
        "source_sha256": source_hashes(),
        "data_sha256": data_hashes(data_dir),
        "incomplete_mining_outputs": incomplete_mining(data_dir),
        "predictions": prediction_inventory(data_dir),
    }


def index_lines(requirements):
    """pip options for local-version CUDA wheels (e.g. torch==2.6.0+cu124), which are not on PyPI."""
    tags = sorted(set(re.findall(r"^\S+==\S+\+(cu\d+)\s*$", requirements, flags=re.M)))
    return [f"--extra-index-url https://download.pytorch.org/whl/{tag}" for tag in tags]


def write_lock(path):
    code, text = run([sys.executable, "-m", "pip", "freeze"])
    if code != 0:
        lines = sorted(f"{d.metadata['Name']}=={d.version}" for d in metadata.distributions())
        text = "\n".join(lines)
    text = text.strip()
    header = (f"# pip freeze of {sys.executable}\n# python {platform.python_version()}, "
              f"written by scripts/write_manifest.py on {datetime.now().date().isoformat()}\n")
    options = index_lines(text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "".join(o + "\n" for o in options) + text + "\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write <data-dir>/results/run_manifest.json and requirements-lock.txt.")
    ap.add_argument("--data-dir", default=str(DATA))
    ap.add_argument("--no-lock", action="store_true", help="do not rewrite requirements-lock.txt")
    args = ap.parse_args(argv)
    data_dir = Path(args.data_dir)
    manifest = build_manifest(data_dir)
    out = data_dir / "results" / "run_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {out} ({len(manifest['source_sha256'])} source files, {len(manifest['data_sha256'])} data files)")
    if manifest["incomplete_mining_outputs"]:
        print(f"warning: incomplete mining outputs not hashed: {manifest['incomplete_mining_outputs']}")
    if not args.no_lock:
        print(f"wrote {write_lock(ROOT / 'requirements-lock.txt')}")


if __name__ == "__main__":
    main()
