"""Command-line safety, pipeline stage list, corpus setup, atomic mining output, manifest
and declared dependencies."""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import git
import pytest

from scripts import run_pipeline, setup_corpus, write_manifest
from src.common.config import ROOT
from src.mining import run
from src.mining.run import mine_repo
from tests.unit.test_mining import BULK_LIMIT, build_history

PY = sys.executable
TABLES = ("commits", "file_changes", "methods_changed", "events", "aux_changes", "parse_failures")

# Runs a module as __main__ with every way of writing a file or starting a process blocked,
# so a script that would do real work under --help fails loudly instead of doing it.
# Only version queries may run (`git version` when GitPython is imported, Windows `ver` from
# platform when torch is imported), and mkdir of a directory that already exists (matplotlib
# config dir). pathlib (Python 3.10) keeps its own references to io.open and
# os.mkdir/rename/..., so they are replaced there too.
GUARD = """
import builtins, io, os, pathlib, runpy, subprocess, sys
real_open = io.open
real_popen = subprocess.Popen.__init__
class GuardedOpen:
    def __call__(self, file, mode="r", *args, **kwargs):
        if any(c in mode for c in "wax+"):
            raise RuntimeError(f"write attempted: {file}")
        return real_open(file, mode, *args, **kwargs)
def refuse(*args, **kwargs):
    raise RuntimeError("blocked: " + repr(args[:2]))
def guarded_mkdir(path, *args, **kwargs):
    if os.path.isdir(path):
        raise FileExistsError(path)
    refuse(path)
def guarded_popen(self, cmd, *args, **kwargs):
    last = cmd[-1] if isinstance(cmd, (list, tuple)) else cmd
    if last in ("version", "--version", "ver"):
        return real_popen(self, cmd, *args, **kwargs)
    raise RuntimeError(f"process blocked: {cmd}")
builtins.open = io.open = GuardedOpen()
for name in ("mkdir", "replace", "rename", "remove", "unlink", "rmdir"):
    blocker = guarded_mkdir if name == "mkdir" else refuse
    setattr(os, name, blocker)
    if hasattr(pathlib, "_NormalAccessor") and hasattr(pathlib._NormalAccessor, name):
        setattr(pathlib._NormalAccessor, name, staticmethod(blocker))
if hasattr(pathlib, "_NormalAccessor"):
    pathlib._NormalAccessor.open = staticmethod(io.open)
subprocess.Popen.__init__ = guarded_popen
module = sys.argv[1]
sys.argv = [module] + sys.argv[2:]
runpy.run_module(module, run_name="__main__", alter_sys=True)
"""


def guarded(module, *args, cwd=ROOT, env_path=None):
    env = dict(os.environ, PYTHONPATH=str(env_path)) if env_path else None
    return subprocess.run([PY, "-B", "-c", GUARD, module, *args], cwd=cwd, capture_output=True,
                          text=True, timeout=300, env=env)


OWN_SCRIPTS = ["scripts.run_pipeline", "scripts.sample_validation", "scripts.setup_corpus",
               "scripts.mine_history", "scripts.write_manifest"]
CLI_SCRIPTS = OWN_SCRIPTS + ["scripts.screen_corpus", "scripts.build_datasets", "scripts.extract_features",
                             "scripts.build_graphs", "scripts.run_experiments", "scripts.evaluate"]


@pytest.mark.parametrize("module", CLI_SCRIPTS)
def test_help_prints_usage_and_touches_nothing(module):
    watched = [ROOT / "data" / "results" / "validation" / "event_sample.csv",
               ROOT / "data" / "results" / "run_manifest.json", ROOT / "requirements-lock.txt"]
    before = {p: p.stat().st_mtime_ns for p in watched if p.exists()}
    res = guarded(module, "--help")
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("usage:")
    assert "Traceback" not in res.stderr
    assert {p: p.stat().st_mtime_ns for p in watched if p.exists()} == before


@pytest.mark.parametrize("module", OWN_SCRIPTS)
def test_unknown_flag_is_an_error(module):
    required = ["--repo", "toy"] if module == "scripts.mine_history" else []
    res = guarded(module, *required, "--no-such-flag")
    assert res.returncode == 2
    assert "unrecognized arguments: --no-such-flag" in res.stderr


def test_guard_blocks_writes_and_processes(tmp_path):
    (tmp_path / "writes.py").write_text('open("out.txt", "w").write("x")\n', encoding="utf-8")
    (tmp_path / "spawns.py").write_text('import subprocess\nsubprocess.run(["git", "status"])\n', encoding="utf-8")
    (tmp_path / "pathwrites.py").write_text('from pathlib import Path\nPath("out.txt").write_text("x")\n',
                                            encoding="utf-8")
    (tmp_path / "pathdirs.py").write_text('from pathlib import Path\nPath("newdir").mkdir()\n', encoding="utf-8")
    for name in ("writes", "spawns", "pathwrites", "pathdirs"):
        res = guarded(name, cwd=tmp_path, env_path=tmp_path)
        assert res.returncode == 1 and ("write attempted" in res.stderr or "blocked" in res.stderr), res.stderr
    assert not (tmp_path / "out.txt").exists() and not (tmp_path / "newdir").exists()


def test_sample_validation_keeps_an_annotated_sheet(tmp_path):
    from scripts import sample_validation
    header = "event_id,repo,label_correct,is_logging_statement,level_correct,notes\n"
    sheet = tmp_path / "event_sample.csv"
    sheet.write_text(header + "a:1:0,A,,,,\n", encoding="utf-8")
    assert not sample_validation.is_annotated(sheet)
    sheet.write_text(header + "a:1:0,A,,,,\na:1:1,A,y,y,na,\n", encoding="utf-8")
    assert sample_validation.is_annotated(sheet)
    before = sheet.read_bytes()
    with pytest.raises(SystemExit) as exc:
        sample_validation.main(["--data-dir", str(tmp_path), "--out-dir", str(tmp_path)])
    assert exc.value.code == 2 and sheet.read_bytes() == before


# run_pipeline

PRIMARY = ["add_log", "remove_log", "change_level"]
VIEWS = ["add_log", "add_log_post", "remove_log", "change_level"]
POSTHOC = "lr_log1p,mlp_full_log1p,hybrid_ggnn_log1p"


def commands(stage):
    return run_pipeline.stage_commands(stage, PRIMARY, "0,1,2,3,4", "16")


def opt(cmd, name):
    return cmd[cmd.index(name) + 1] if name in cmd else None


def test_pipeline_stages_in_order():
    assert run_pipeline.STAGES == ["corpus", "screen", "mine", "datasets", "features", "graphs", "classical",
                                   "neural", "posthoc", "sensitivity", "multiclass", "evaluate", "manifest"]
    for stage in run_pipeline.STAGES:
        cmds = commands(stage)
        assert cmds, stage
        for cmd in cmds:
            assert (ROOT / (cmd[0].replace(".", "/") + ".py")).exists(), cmd


def test_pipeline_task_and_model_lists():
    assert [opt(c, "--task") for c in commands("features")] == VIEWS + ["multiclass"]
    assert [opt(c, "--task") for c in commands("graphs")] == VIEWS

    classical = commands("classical")
    assert [opt(c, "--task") for c in classical] == VIEWS
    assert all(opt(c, "--setting") == "R4" and opt(c, "--models") == "naive,classical" and "--importance" in c
               for c in classical)

    neural = commands("neural")
    assert [opt(c, "--task") for c in neural] == VIEWS
    assert all(opt(c, "--setting") == "R4" and opt(c, "--models") == "neural,graph" for c in neural)

    posthoc = commands("posthoc")
    assert [opt(c, "--task") for c in posthoc] == PRIMARY
    assert all(opt(c, "--setting") == "R4" and opt(c, "--models") == POSTHOC for c in posthoc)

    sens = commands("sensitivity")
    assert [(opt(c, "--setting"), opt(c, "--task")) for c in sens] == \
        [(s, t) for s in ("R1", "R10") for t in PRIMARY]
    assert all(opt(c, "--models") == "naive,classical" and "--importance" not in c for c in sens)

    assert [(opt(c, "--setting"), opt(c, "--lang")) for c in commands("evaluate")] == \
        [("R4", "both"), ("R1", "both"), ("R10", "both")]
    assert all(opt(c, "--seeds") == "0,1,2,3,4" for c in classical + neural + posthoc + sens)


def test_pipeline_names_match_the_stage_scripts():
    from scripts import build_graphs, run_experiments
    from src.features.extract import TASKS as FEATURE_TASKS
    from src.models import train

    assert {opt(c, "--task") for c in commands("features")} <= set(FEATURE_TASKS)
    assert {opt(c, "--task") for c in commands("graphs")} <= set(build_graphs.TASKS)
    for stage in ("classical", "neural", "posthoc", "sensitivity", "multiclass"):
        for c in commands(stage):
            assert opt(c, "--task") in run_experiments.BINARY_TASKS + ["multiclass"]
            assert opt(c, "--setting") in run_experiments.SETTINGS
            for m in opt(c, "--models").split(","):
                assert m in train.MODEL_GROUPS or m in train.FEATURE_SET, m
    # the post-hoc stage names its models explicitly; they must stay the post-hoc group
    assert sorted(POSTHOC.split(",")) == sorted(train.MODEL_GROUPS.get("posthoc", POSTHOC.split(",")))


def test_pipeline_dry_run_runs_nothing(monkeypatch, capsys):
    def boom(args):
        raise AssertionError(f"ran {args}")
    monkeypatch.setattr(run_pipeline, "run", boom)
    run_pipeline.main(["--dry-run", "--from", "classical", "--to", "evaluate"])
    lines = capsys.readouterr().out.splitlines()
    expected = sum(len(commands(s)) for s in ("classical", "neural", "posthoc", "sensitivity", "multiclass", "evaluate"))
    assert len(lines) == expected
    assert lines[0].startswith("python -m scripts.run_experiments --setting R4 --task add_log ")
    assert lines[-1] == "python -m scripts.evaluate --setting R10 --lang both"


def test_pipeline_overwrite_is_opt_in_and_reaches_only_run_experiments(monkeypatch, capsys):
    for stage in run_pipeline.STAGES:
        plain = commands(stage)
        forced = run_pipeline.stage_commands(stage, PRIMARY, "0,1,2,3,4", "16", overwrite=True)
        assert all("--overwrite" not in c for c in plain)
        assert forced == [c + ["--overwrite"] if c[0] == "scripts.run_experiments" else c for c in plain]
    from scripts import run_experiments
    assert '"--overwrite"' in Path(run_experiments.__file__).read_text(encoding="utf-8")

    monkeypatch.setattr(run_pipeline, "run", lambda args: pytest.fail("ran"))
    run_pipeline.main(["--dry-run", "--from", "graphs", "--to", "classical", "--overwrite"])
    lines = capsys.readouterr().out.splitlines()
    assert [line.endswith(" --overwrite") for line in lines] == [False] * 4 + [True] * 4
    run_pipeline.main(["--dry-run", "--from", "classical", "--to", "classical"])
    assert not any("--overwrite" in line for line in capsys.readouterr().out.splitlines())


def test_pipeline_rejects_bad_stage_ranges(monkeypatch):
    monkeypatch.setattr(run_pipeline, "run", lambda args: pytest.fail("ran"))
    for argv in (["--from", "neural", "--to", "graphs"], ["--from", "train"]):
        with pytest.raises(SystemExit) as exc:
            run_pipeline.main(argv)
        assert exc.value.code == 2


# setup_corpus

def make_repo(path):
    repo = git.Repo.init(path)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test Dev")
        cw.set_value("user", "email", "dev@example.com")
        cw.set_value("commit", "gpgsign", "false")
    (Path(path) / "A.java").write_text("class A {}\n", encoding="utf-8")
    repo.git.add("-A")
    repo.git.commit("-m", "first")
    return repo.head.commit.hexsha


def test_clone_source_decision(tmp_path):
    dest = tmp_path / "raw" / "toy"
    other = tmp_path / "copy" / "toy"
    other.mkdir(parents=True)
    remote = "https://example.invalid/toy.git"
    pick = setup_corpus.clone_source
    assert pick({"remote": remote, "source": str(other)}, dest) == (str(other.resolve()), True)
    assert pick({"remote": remote}, dest) == (remote, False)                                    # no source
    assert pick({"remote": remote, "source": None}, dest) == (remote, False)
    assert pick({"remote": remote, "source": str(tmp_path / "missing")}, dest) == (remote, False)
    dest.mkdir(parents=True)
    assert pick({"remote": remote, "source": str(dest)}, dest) == (remote, False)               # source is dest
    assert pick({"remote": remote, "source": str(dest / ".." / "toy")}, dest) == (remote, False)
    assert pick({"source": str(dest)}, dest) == (None, False)


def test_corpus_entries_in_place_fall_back_to_remote():
    from src.common.config import corpus_repos, repo_path
    for r in corpus_repos():
        if r.get("source") and setup_corpus.same_path(ROOT / r["source"], repo_path(r["name"])):
            assert setup_corpus.clone_source(r, repo_path(r["name"])) == (r["remote"], False)


def test_setup_corpus_clones_and_verifies_head(tmp_path, monkeypatch):
    src = tmp_path / "games" / "toy"
    head = make_repo(src)
    dests = {"local": tmp_path / "raw" / "local", "remote": tmp_path / "raw" / "remote"}
    entries = [{"name": "local", "remote": "https://example.invalid/local.git", "source": str(src), "head": head},
               {"name": "remote", "remote": "https://example.invalid/remote.git",
                "source": str(dests["remote"]), "head": head}]
    monkeypatch.setattr(setup_corpus, "corpus_repos", lambda modeling_only=False: entries)
    monkeypatch.setattr(setup_corpus, "repo_path", lambda name: dests[name])

    clones = []
    real_git = setup_corpus.git

    def fake_git(args, cwd=None):
        if args[0] == "clone":
            clones.append(args)
            if args[1] == "--no-hardlinks":      # local clone: really done, no network
                return real_git(args, cwd)
            return real_git(["clone", str(src), args[-1]])   # stands in for the network clone
        return real_git(args, cwd)

    monkeypatch.setattr(setup_corpus, "git", fake_git)
    with pytest.raises(SystemExit) as exc:
        setup_corpus.main([])
    assert exc.value.code == 0
    assert clones[0] == ["clone", "--no-hardlinks", str(src.resolve()), str(dests["local"])]
    assert clones[1] == ["clone", "https://example.invalid/remote.git", str(dests["remote"])]

    # existing clones are not cloned again; a missing pinned head fails
    clones.clear()
    entries[0]["head"] = "0" * 40
    with pytest.raises(SystemExit) as exc:
        setup_corpus.main([])
    assert exc.value.code == 1 and clones == []


# atomic mining output

class Interrupted(BaseException):
    pass


@pytest.fixture(scope="module")
def toy(tmp_path_factory):
    base = tmp_path_factory.mktemp("atomic")
    repo, shas = build_history(base / "toy")
    return repo.working_tree_dir, shas["delete"], base


def mine(toy, out, log=lambda *a: None, **kw):
    repo_dir, head, _ = toy
    return mine_repo("toy", repo_dir, head, out, workers=1, config={"bulk_commit_java_files": BULK_LIMIT},
                     log=log, **kw)


def tables(out):
    return {name: (out / f"{name}.jsonl").read_bytes() for name in TABLES}


def contents(d):
    return {f.name: f.read_bytes() for f in d.iterdir()}


def test_mining_replaces_the_output_directory(toy):
    out = toy[2] / "replace" / "toy"
    first = mine(toy, out)
    reference = tables(out)
    assert first["commit_errors"] == 0 and first["events"] > 0
    assert sorted(p.name for p in out.parent.iterdir()) == ["toy"]
    assert set(run.TABLES) == set(TABLES)

    (out / "events.jsonl").write_text("old\n", encoding="utf-8")
    (out / "aux_changes.jsonl").unlink()
    mine(toy, out)
    assert sorted(p.name for p in out.parent.iterdir()) == ["toy"]
    assert tables(out) == reference
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["events"] == first["events"] and summary["methods_changed"] == first["methods_changed"]


def test_interrupted_mining_keeps_the_previous_output(toy, monkeypatch):
    out = toy[2] / "interrupted" / "toy"
    mine(toy, out)
    before = tables(out)
    summary_before = (out / "summary.json").read_bytes()

    real = run.mine_commit
    calls = []

    def flaky(*args):
        calls.append(1)
        if len(calls) == 4:
            raise Interrupted()
        return real(*args)

    monkeypatch.setattr(run, "mine_commit", flaky)
    with pytest.raises(Interrupted):
        mine(toy, out)
    assert tables(out) == before and (out / "summary.json").read_bytes() == summary_before
    tmp = out.with_name("toy.tmp")
    assert tmp.is_dir() and not (tmp / "summary.json").exists()

    monkeypatch.setattr(run, "mine_commit", real)
    mine(toy, out)
    assert not tmp.exists()
    assert tables(out) == before


def test_mining_never_replaces_a_folder_with_other_content(toy):
    # e.g. --out data/interim/mining with one repository: the other repositories must survive
    shared = toy[2] / "shared"
    (shared / "OtherRepo").mkdir(parents=True)
    (shared / "OtherRepo" / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (shared / "notes.txt").write_text("keep\n", encoding="utf-8")
    for target in (shared, shared / "OtherRepo" / ".."):
        with pytest.raises(ValueError, match="not replaced"):
            mine(toy, target)
    assert (shared / "OtherRepo" / "events.jsonl").exists() and (shared / "notes.txt").exists()
    assert not shared.with_name("shared.tmp").exists()

    lone = toy[2] / "lone" / "toy"
    lone.mkdir(parents=True)
    (lone / "README.md").write_text("mine\n", encoding="utf-8")
    with pytest.raises(ValueError):
        mine(toy, lone)
    assert (lone / "README.md").exists()


def test_mining_never_replaces_json_folders_that_are_not_its_output(toy):
    # e.g. a mistaken --out data/processed/instances, or the mining folder of another repository
    instances = toy[2] / "processed" / "instances"
    instances.mkdir(parents=True)
    for name in ("add_log.jsonl", "folds.json", "summary.json"):
        (instances / name).write_text("{}\n", encoding="utf-8")
    other = toy[2] / "other_repo" / "toy"
    other.mkdir(parents=True)
    (other / "events.jsonl").write_text("{}\n", encoding="utf-8")
    (other / "summary.json").write_text(json.dumps({"repo": "OtherRepo"}), encoding="utf-8")
    broken = toy[2] / "broken_summary" / "toy"
    broken.mkdir(parents=True)
    (broken / "summary.json").write_text('{"repo": "to', encoding="utf-8")
    for target in (instances, other, broken):
        before = contents(target)
        with pytest.raises(ValueError, match="not replaced"):
            mine(toy, target)
        assert contents(target) == before
        assert sorted(p.name for p in target.parent.iterdir()) == [target.name]

    leftover = toy[2] / "leftover" / "toy.tmp"
    leftover.mkdir(parents=True)
    (leftover / "notes.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not replaced"):
        mine(toy, leftover.with_name("toy"))
    assert (leftover / "notes.json").exists()


def test_official_mining_outputs_are_replaceable_and_instances_are_not():
    from src.common.config import DATA, corpus_repos
    mining = DATA / "interim" / "mining"
    repos = [mining / r["name"] for r in corpus_repos() if (mining / r["name"]).is_dir()]
    for d in repos:
        assert run._replaceable(d, d.name), d
        assert not run._replaceable(d, "SomeOtherRepo"), d
    instances = DATA / "processed" / "instances"
    if instances.exists():
        assert not run._replaceable(instances, "Mindustry")
    if not repos:
        pytest.skip("no mining output in data/interim/mining")


def test_failed_swap_restores_the_previous_output(toy, monkeypatch):
    out = toy[2] / "swap" / "toy"
    mine(toy, out)
    before = contents(out)

    real = run._rename
    calls = []

    def locked(src, dst, attempts=5):
        calls.append((Path(src).name, Path(dst).name))
        if len(calls) == 2:
            raise PermissionError("held by another program")
        return real(src, dst, attempts)

    monkeypatch.setattr(run, "_rename", locked)
    with pytest.raises(PermissionError):
        mine(toy, out)
    assert calls == [("toy", "toy.old"), ("toy.tmp", "toy"), ("toy.old", "toy")]
    assert contents(out) == before
    assert sorted(p.name for p in out.parent.iterdir()) == ["toy", "toy.tmp"]

    # the next run deletes the leftover .tmp and swaps normally
    monkeypatch.setattr(run, "_rename", real)
    mine(toy, out)
    assert sorted(p.name for p in out.parent.iterdir()) == ["toy"]
    assert tables(out) == {name: before[f"{name}.jsonl"] for name in TABLES}


def test_undeletable_previous_output_only_warns(toy, monkeypatch):
    out = toy[2] / "undeletable" / "toy"
    mine(toy, out)
    reference = tables(out)
    (out / "events.jsonl").write_text("old\n", encoding="utf-8")

    real_rmtree = run.shutil.rmtree

    def locked(path, *args, **kwargs):
        if Path(path).name == "toy.old":
            raise PermissionError("held by another program")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(run.shutil, "rmtree", locked)
    monkeypatch.setattr(run.time, "sleep", lambda s: None)
    logs = []
    summary = mine(toy, out, log=logs.append)
    assert summary["commit_errors"] == 0
    assert tables(out) == reference
    assert (out.with_name("toy.old") / "events.jsonl").read_text(encoding="utf-8") == "old\n"
    assert any(line.startswith("warning: could not delete") for line in logs)

    monkeypatch.setattr(run.shutil, "rmtree", real_rmtree)
    mine(toy, out)
    assert sorted(p.name for p in out.parent.iterdir()) == ["toy"]
    assert tables(out) == reference


def test_max_commits_needs_an_out_outside_the_mining_folder(tmp_path, monkeypatch):
    from scripts import mine_history
    from src.common.config import DATA
    summary = {"n_commits": 0, "n_non_merge": 0, "n_bulk": 0, "java_file_changes": 0, "java_files_mined": 0,
               "blob_parses": 0, "parse_failures": 0, "commit_errors": 0, "file_change_mismatch_commits": 0,
               "events_by_label_validity": {}, "commit_error_examples": []}
    calls = []
    monkeypatch.setattr(mine_history, "mine_repo", lambda *a, **k: calls.append((a, k)) or summary)
    mining = DATA / "interim" / "mining"
    for extra in ([], ["--out", str(mining / "jme3rpg")], ["--out", str(mining)], ["--out", str(mining / "x" / "..")]):
        with pytest.raises(SystemExit) as exc:
            mine_history.main(["--repo", "jme3rpg", "--max-commits", "5"] + extra)
        assert exc.value.code == 2
    assert calls == []

    mine_history.main(["--repo", "jme3rpg", "--max-commits", "5", "--out", str(tmp_path / "smoke")])
    assert calls[-1][0][3] == tmp_path / "smoke" and calls[-1][1]["max_commits"] == 5
    mine_history.main(["--repo", "jme3rpg"])   # the full history may go to the official folder
    assert calls[-1][0][3] == mining / "jme3rpg" and calls[-1][1]["max_commits"] is None


def test_interrupted_numstat_log_writes_no_summary(toy, monkeypatch):
    out = toy[2] / "fresh" / "toy"

    def broken(*args):
        raise Interrupted()

    monkeypatch.setattr(run, "file_changes", broken)
    with pytest.raises(Interrupted):
        mine(toy, out)
    assert not out.exists()
    assert not (out.with_name("toy.tmp") / "summary.json").exists()


# run manifest

def test_manifest_hashes_results_and_skips_incomplete_mining(tmp_path):
    d = tmp_path / "data"
    files = ["interim/mining/toy/summary.json", "interim/mining/toy/events.jsonl",
             "interim/mining/toy.tmp/events.jsonl", "interim/mining/toy.old/events.jsonl",
             "results/predictions/R4/add_log/hgb/seed0.csv", "results/predictions/R4/add_log/hgb/seed0.json",
             "results/tables/rq3_overall_pooled.csv", "results/report/experiment_report.md",
             "results/rq1/corpus_snapshot.csv", "results/validation/event_sample.csv",
             "processed/events_master.jsonl", "processed/events_master.csv",
             "results/importance/R4/add_log/hgb_seed0.json", "results/importance/R4/add_log/hgb_seed0_features.csv",
             "results/importance/R4/add_log_post/hgb_seed0_groups.csv",
             "results/figures/pr_curves_add_log_R4_en.png", "results/error_analysis/confusion.csv"]
    for f in files:
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        (d / f).write_text(f, encoding="utf-8")
    (d / "results" / "tables" / "subdir").mkdir()

    hashes = write_manifest.data_hashes(d)
    assert set(hashes) == {f for f in files if ".tmp/" not in f and ".old/" not in f}
    assert hashes["results/tables/rq3_overall_pooled.csv"] == write_manifest.sha256_file(
        d / "results/tables/rq3_overall_pooled.csv")
    assert write_manifest.incomplete_mining(d) == ["toy.old", "toy.tmp"]


def test_manifest_hardware_and_evaluation_parameters():
    from src.common.config import load_config
    hw = write_manifest.hardware()
    assert hw["logical_cores"] and hw["logical_cores"] >= 1
    assert hw["ram_gb"] is None or hw["ram_gb"] > 0
    exp = load_config("experiment")
    ev = write_manifest.evaluation_params(exp)
    assert ev["bootstrap_samples"] == exp["evaluation"]["bootstrap_samples"]
    assert isinstance(ev["bootstrap_seed"], int)
    custom = write_manifest.evaluation_params({"evaluation": {"bootstrap_samples": 7, "bootstrap_seed": 3}})
    assert custom["bootstrap_samples"] == 7 and custom["bootstrap_seed"] == 3
    source = Path(write_manifest.__file__).read_text(encoding="utf-8")
    assert '"bootstrap": 42' not in source


def test_manifest_bootstrap_parameters_follow_evaluate(monkeypatch):
    # scripts/evaluate.py takes B, B_tests and the seed from analysis.bootstrap_sizes(cfg)
    from src.common.config import load_config
    from src.evaluation import analysis
    assert "bootstrap_sizes(cfg)" in (ROOT / "scripts" / "evaluate.py").read_text(encoding="utf-8")
    exp = load_config("experiment")
    ev = write_manifest.evaluation_params(exp)
    assert (ev["bootstrap_samples"], ev["bootstrap_samples_tests"], ev["bootstrap_seed"]) == \
        analysis.bootstrap_sizes(exp)
    configured = "bootstrap_seed" in exp["evaluation"]
    assert ev["bootstrap_seed_source"] == ("configs/experiment.yaml" if configured
                                           else "default of src/evaluation/analysis.py bootstrap_sizes")

    monkeypatch.setattr(analysis, "bootstrap_sizes", lambda cfg=None: (11, 22, 99))
    ev = write_manifest.evaluation_params({"evaluation": {"bootstrap_samples": 11}})
    assert (ev["bootstrap_samples"], ev["bootstrap_samples_tests"], ev["bootstrap_seed"]) == (11, 22, 99)
    assert ev["bootstrap_seed_source"] == "default of src/evaluation/analysis.py bootstrap_sizes"


# validation sheet

# declared dependencies

# import name -> distribution name, where they differ
IMPORT_DIST = {"git": "gitpython", "yaml": "pyyaml", "sklearn": "scikit-learn",
               "Levenshtein": "python-levenshtein", "torch_geometric": "torch-geometric"}


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def declared():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    out = set()
    for block in re.findall(r"^(?:dependencies|dev)\s*=\s*\[(.*?)\]", text, flags=re.S | re.M):
        for req in re.findall(r'"([^"]+)"', block):
            out.add(norm(re.split(r"[<>=!~\[ ;]", req)[0]))
    return out


def third_party_imports():
    names = set()
    files = list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")) + \
        list((ROOT / "tests").rglob("*.py"))
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue   # fails its own tests; this one is only about dependencies
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return {n for n in names if n not in sys.stdlib_module_names and n not in {"src", "scripts", "tests", "__future__"}}


def test_every_imported_package_is_declared():
    deps = declared()
    assert "threadpoolctl" in deps and "pytest" in deps
    missing = sorted(n for n in third_party_imports() if norm(IMPORT_DIST.get(n, n)) not in deps)
    assert missing == []
