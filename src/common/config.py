from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CONFIGS = ROOT / "configs"

_cache = {}


def load_config(name):
    if name not in _cache:
        with open(CONFIGS / f"{name}.yaml", encoding="utf-8") as f:
            _cache[name] = yaml.safe_load(f)
    return _cache[name]


def corpus_repos(modeling_only=False):
    repos = load_config("corpus")["repos"]
    if modeling_only:
        repos = [r for r in repos if r.get("modeling")]
    return repos


def repo_info(name):
    for r in load_config("corpus")["repos"]:
        if r["name"] == name:
            return r
    raise KeyError(name)


def repo_path(name):
    return ROOT / load_config("corpus")["repo_dir"] / name
