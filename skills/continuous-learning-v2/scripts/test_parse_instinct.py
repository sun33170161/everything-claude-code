"""Tests for continuous-learning-v2 instinct-cli.py

Covers:
  - parse_instinct_file() — content preservation, edge cases
  - _validate_file_path() — path traversal blocking
  - detect_project() — project detection with mocked git/env
  - load_all_instincts() — loading from project + global dirs, dedup
  - _load_instincts_from_dir() — directory scanning
  - cmd_projects() — listing projects from registry
  - cmd_status() — status display
  - _promote_specific() — single instinct promotion
  - _promote_auto() — auto-promotion across projects
"""

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

# Load instinct-cli.py (hyphenated filename requires importlib)
_spec = importlib.util.spec_from_file_location(
    "instinct_cli",
    os.path.join(os.path.dirname(__file__), "instinct-cli.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

parse_instinct_file = _mod.parse_instinct_file
_validate_file_path = _mod._validate_file_path
detect_project = _mod.detect_project
load_all_instincts = _mod.load_all_instincts
load_project_only_instincts = _mod.load_project_only_instincts
_load_instincts_from_dir = _mod._load_instincts_from_dir
cmd_status = _mod.cmd_status
cmd_projects = _mod.cmd_projects
_promote_specific = _mod._promote_specific
_promote_auto = _mod._promote_auto
_find_cross_project_instincts = _mod._find_cross_project_instincts
load_registry = _mod.load_registry
_validate_instinct_id = _mod._validate_instinct_id
_update_registry = _mod._update_registry
_calculate_decayed_confidence = _mod._calculate_decayed_confidence
_apply_confidence_decay = _mod._apply_confidence_decay
_get_instincts_eligible_for_deprecation = _mod._get_instincts_eligible_for_deprecation
_move_to_deprecated = _mod._move_to_deprecated
_auto_deprecate = _mod._auto_deprecate
_load_instincts_from_deprecated_dir = _mod._load_instincts_from_deprecated_dir
_load_user_profile_instincts = _mod._load_user_profile_instincts
_load_identity = _mod._load_identity
_validate_identity = _mod._validate_identity
cmd_analyze = _mod.cmd_analyze
_create_default_identity = _mod._create_default_identity
_inject_identity_prompt = _mod._inject_identity_prompt
IDENTITY_FILE = _mod.IDENTITY_FILE
IDENTITY_DEFAULTS = _mod.IDENTITY_DEFAULTS


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

SAMPLE_INSTINCT_YAML = """\
---
id: test-instinct
trigger: "when writing tests"
confidence: 0.8
domain: testing
scope: project
---

## Action
Always write tests first.

## Evidence
TDD leads to better design.
"""

SAMPLE_GLOBAL_INSTINCT_YAML = """\
---
id: global-instinct
trigger: "always"
confidence: 0.9
domain: security
scope: global
---

## Action
Validate all user input.
"""


@pytest.fixture
def project_tree(tmp_path):
    """Create a realistic project directory tree for testing."""
    homunculus = tmp_path / ".opencode" / "homunculus"
    projects_dir = homunculus / "projects"
    global_personal = homunculus / "instincts" / "personal"
    global_inherited = homunculus / "instincts" / "inherited"
    global_deprecated = homunculus / "instincts" / "deprecated"
    global_evolved = homunculus / "evolved"

    for d in [
        global_personal, global_inherited, global_deprecated,
        global_evolved / "skills", global_evolved / "commands", global_evolved / "agents",
        projects_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    return {
        "root": tmp_path,
        "homunculus": homunculus,
        "projects_dir": projects_dir,
        "global_personal": global_personal,
        "global_inherited": global_inherited,
        "global_deprecated": global_deprecated,
        "global_evolved": global_evolved,
        "registry_file": homunculus / "projects.json",
    }


@pytest.fixture
def patch_globals(project_tree, monkeypatch):
    """Patch module-level globals to use tmp_path-based directories."""
    monkeypatch.setattr(_mod, "HOMUNCULUS_DIR", project_tree["homunculus"])
    monkeypatch.setattr(_mod, "PROJECTS_DIR", project_tree["projects_dir"])
    monkeypatch.setattr(_mod, "REGISTRY_FILE", project_tree["registry_file"])
    monkeypatch.setattr(_mod, "GLOBAL_PERSONAL_DIR", project_tree["global_personal"])
    monkeypatch.setattr(_mod, "GLOBAL_INHERITED_DIR", project_tree["global_inherited"])
    monkeypatch.setattr(_mod, "GLOBAL_DEPRECATED_DIR", project_tree["global_deprecated"])
    monkeypatch.setattr(_mod, "GLOBAL_EVOLVED_DIR", project_tree["global_evolved"])
    monkeypatch.setattr(_mod, "GLOBAL_OBSERVATIONS_FILE", project_tree["homunculus"] / "observations.jsonl")
    monkeypatch.setattr(_mod, "IDENTITY_FILE", project_tree["homunculus"] / "identity.json")
    return project_tree


def _make_project(tree, pid="abc123", pname="test-project"):
    """Create project directory structure and return a project dict."""
    project_dir = tree["projects_dir"] / pid
    personal_dir = project_dir / "instincts" / "personal"
    inherited_dir = project_dir / "instincts" / "inherited"
    for d in [personal_dir, inherited_dir,
              project_dir / "evolved" / "skills",
              project_dir / "evolved" / "commands",
              project_dir / "evolved" / "agents",
              project_dir / "observations.archive"]:
        d.mkdir(parents=True, exist_ok=True)

    return {
        "id": pid,
        "name": pname,
        "root": str(tree["root"] / "fake-repo"),
        "remote": "https://github.com/test/test-project.git",
        "project_dir": project_dir,
        "instincts_personal": personal_dir,
        "instincts_inherited": inherited_dir,
        "evolved_dir": project_dir / "evolved",
        "observations_file": project_dir / "observations.jsonl",
    }


# ─────────────────────────────────────────────
# parse_instinct_file tests
# ─────────────────────────────────────────────

MULTI_SECTION = """\
---
id: instinct-a
trigger: "when coding"
confidence: 0.9
domain: general
---

## Action
Do thing A.

## Examples
- Example A1

---
id: instinct-b
trigger: "when testing"
confidence: 0.7
domain: testing
---

## Action
Do thing B.
"""


def test_multiple_instincts_preserve_content():
    result = parse_instinct_file(MULTI_SECTION)
    assert len(result) == 2
    assert "Do thing A." in result[0]["content"]
    assert "Example A1" in result[0]["content"]
    assert "Do thing B." in result[1]["content"]


def test_single_instinct_preserves_content():
    content = """\
---
id: solo
trigger: "when reviewing"
confidence: 0.8
domain: review
---

## Action
Check for security issues.

## Evidence
Prevents vulnerabilities.
"""
    result = parse_instinct_file(content)
    assert len(result) == 1
    assert "Check for security issues." in result[0]["content"]
    assert "Prevents vulnerabilities." in result[0]["content"]


def test_empty_content_no_error():
    content = """\
---
id: empty
trigger: "placeholder"
confidence: 0.5
domain: general
---
"""
    result = parse_instinct_file(content)
    assert len(result) == 1
    assert result[0]["content"] == ""


def test_parse_no_id_skipped():
    """Instincts without an 'id' field should be silently dropped."""
    content = """\
---
trigger: "when doing nothing"
confidence: 0.5
---

No id here.
"""
    result = parse_instinct_file(content)
    assert len(result) == 0


def test_parse_confidence_is_float():
    content = """\
---
id: float-check
trigger: "when parsing"
confidence: 0.42
domain: general
---

Body.
"""
    result = parse_instinct_file(content)
    assert isinstance(result[0]["confidence"], float)
    assert result[0]["confidence"] == pytest.approx(0.42)


def test_parse_trigger_strips_quotes():
    content = """\
---
id: quote-check
trigger: "when quoting"
confidence: 0.5
domain: general
---

Body.
"""
    result = parse_instinct_file(content)
    assert result[0]["trigger"] == "when quoting"


def test_parse_empty_string():
    result = parse_instinct_file("")
    assert result == []


def test_parse_garbage_input():
    result = parse_instinct_file("this is not yaml at all\nno frontmatter here")
    assert result == []


def test_parse_last_observed():
    """Instinct with last_observed should parse the field as a string."""
    content = """\
---
id: test-instinct
trigger: "when testing"
confidence: 0.8
domain: testing
last_observed: 2025-06-01T00:00:00Z
---

## Action
Test.
"""
    result = parse_instinct_file(content)
    assert len(result) == 1
    assert result[0].get('last_observed') == "2025-06-01T00:00:00Z"


def test_parse_no_last_observed():
    """Instinct without last_observed should not have the key."""
    content = """\
---
id: test-instinct
trigger: "when testing"
confidence: 0.8
domain: testing
---

## Action
Test.
"""
    result = parse_instinct_file(content)
    assert len(result) == 1
    assert 'last_observed' not in result[0]


def test_update_last_observed(tmp_path):
    """_update_last_observed should write current timestamp back to file."""
    instinct_file = tmp_path / "test.yaml"
    content = """\
---
id: test-instinct
trigger: "when testing"
confidence: 0.8
domain: testing
last_observed: 2025-01-01T00:00:00Z
---

## Action
Test.
"""
    instinct_file.write_text(content)

    _mod._update_last_observed(instinct_file)

    result = parse_instinct_file(instinct_file.read_text())
    observed = result[0].get('last_observed', '')
    assert observed != "2025-01-01T00:00:00Z"
    assert observed.endswith("Z")
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(observed.replace('Z', '+00:00'))
    assert (datetime.now(timezone.utc) - dt).total_seconds() < 10


# ─────────────────────────────────────────────
# _validate_file_path tests
# ─────────────────────────────────────────────

def test_validate_normal_path(tmp_path):
    test_file = tmp_path / "test.yaml"
    test_file.write_text("hello")
    result = _validate_file_path(str(test_file), must_exist=True)
    assert result == test_file.resolve()


def test_validate_rejects_etc():
    with pytest.raises(ValueError, match="system directory"):
        _validate_file_path("/etc/passwd")


def test_validate_rejects_var_log():
    with pytest.raises(ValueError, match="system directory"):
        _validate_file_path("/var/log/syslog")


def test_validate_rejects_usr():
    with pytest.raises(ValueError, match="system directory"):
        _validate_file_path("/usr/local/bin/foo")


def test_validate_rejects_proc():
    with pytest.raises(ValueError, match="system directory"):
        _validate_file_path("/proc/self/status")


def test_validate_must_exist_fails(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        _validate_file_path(str(tmp_path / "nonexistent.yaml"), must_exist=True)


def test_validate_home_expansion(tmp_path):
    """Tilde expansion should work."""
    result = _validate_file_path("~/test.yaml")
    assert str(result).startswith(str(Path.home()))


def test_validate_relative_path(tmp_path, monkeypatch):
    """Relative paths should be resolved."""
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "rel.yaml"
    test_file.write_text("content")
    result = _validate_file_path("rel.yaml", must_exist=True)
    assert result == test_file.resolve()


# ─────────────────────────────────────────────
# detect_project tests
# ─────────────────────────────────────────────

def test_detect_project_global_fallback(patch_globals, monkeypatch):
    """When no git and no env var, should return global project."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    # Mock subprocess.run to simulate git not available
    def mock_run(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("subprocess.run", mock_run)

    project = detect_project()
    assert project["id"] == "global"
    assert project["name"] == "global"


def test_detect_project_from_env(patch_globals, monkeypatch, tmp_path):
    """CLAUDE_PROJECT_DIR env var should be used as project root."""
    fake_repo = tmp_path / "my-repo"
    fake_repo.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(fake_repo))

    # Mock git remote to return a URL
    def mock_run(cmd, **kwargs):
        if "rev-parse" in cmd:
            return SimpleNamespace(returncode=0, stdout=str(fake_repo) + "\n", stderr="")
        if "get-url" in cmd:
            return SimpleNamespace(returncode=0, stdout="https://github.com/test/my-repo.git\n", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    project = detect_project()
    assert project["id"] != "global"
    assert project["name"] == "my-repo"


def test_detect_project_git_timeout(patch_globals, monkeypatch):
    """Git timeout should fall through to global."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    import subprocess as sp

    def mock_run(cmd, **kwargs):
        raise sp.TimeoutExpired(cmd, 5)

    monkeypatch.setattr("subprocess.run", mock_run)

    project = detect_project()
    assert project["id"] == "global"


def test_detect_project_creates_directories(patch_globals, monkeypatch, tmp_path):
    """detect_project should create the project dir structure."""
    fake_repo = tmp_path / "structured-repo"
    fake_repo.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(fake_repo))

    def mock_run(cmd, **kwargs):
        if "rev-parse" in cmd:
            return SimpleNamespace(returncode=0, stdout=str(fake_repo) + "\n", stderr="")
        if "get-url" in cmd:
            return SimpleNamespace(returncode=1, stdout="", stderr="no remote")
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    project = detect_project()
    assert project["instincts_personal"].exists()
    assert project["instincts_inherited"].exists()
    assert (project["evolved_dir"] / "skills").exists()


# ─────────────────────────────────────────────
# _load_instincts_from_dir tests
# ─────────────────────────────────────────────

def test_load_from_empty_dir(tmp_path):
    result = _load_instincts_from_dir(tmp_path, "personal", "project")
    assert result == []


def test_load_from_nonexistent_dir(tmp_path):
    result = _load_instincts_from_dir(tmp_path / "does-not-exist", "personal", "project")
    assert result == []


def test_load_annotates_metadata(tmp_path):
    """Loaded instincts should have _source_file, _source_type, _scope_label."""
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(SAMPLE_INSTINCT_YAML)

    result = _load_instincts_from_dir(tmp_path, "personal", "project")
    assert len(result) == 1
    assert result[0]["_source_file"] == str(yaml_file)
    assert result[0]["_source_type"] == "personal"
    assert result[0]["_scope_label"] == "project"


def test_load_defaults_scope_from_label(tmp_path):
    """If an instinct has no 'scope' in frontmatter, it should default to scope_label."""
    no_scope_yaml = """\
---
id: no-scope
trigger: "test"
confidence: 0.5
domain: general
---

Body.
"""
    (tmp_path / "no-scope.yaml").write_text(no_scope_yaml)
    result = _load_instincts_from_dir(tmp_path, "inherited", "global")
    assert result[0]["scope"] == "global"


def test_load_preserves_explicit_scope(tmp_path):
    """If frontmatter has explicit scope, it should be preserved."""
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(SAMPLE_INSTINCT_YAML)

    result = _load_instincts_from_dir(tmp_path, "personal", "global")
    # Frontmatter says scope: project, scope_label is global
    # The explicit scope should be preserved (not overwritten)
    assert result[0]["scope"] == "project"


def test_load_handles_corrupt_file(tmp_path, capsys):
    """Corrupt YAML files should be warned about but not crash."""
    # A file that will cause parse_instinct_file to return empty
    (tmp_path / "good.yaml").write_text(SAMPLE_INSTINCT_YAML)
    (tmp_path / "bad.yaml").write_text("not yaml\nno frontmatter")

    result = _load_instincts_from_dir(tmp_path, "personal", "project")
    # bad.yaml has no valid instincts (no id), so only good.yaml contributes
    assert len(result) == 1
    assert result[0]["id"] == "test-instinct"


def test_load_supports_yml_extension(tmp_path):
    yml_file = tmp_path / "test.yml"
    yml_file.write_text(SAMPLE_INSTINCT_YAML)

    result = _load_instincts_from_dir(tmp_path, "personal", "project")
    ids = {i["id"] for i in result}
    assert "test-instinct" in ids


def test_load_supports_md_extension(tmp_path):
    md_file = tmp_path / "legacy-instinct.md"
    md_file.write_text(SAMPLE_INSTINCT_YAML)

    result = _load_instincts_from_dir(tmp_path, "personal", "project")
    ids = {i["id"] for i in result}
    assert "test-instinct" in ids


def test_load_instincts_from_dir_uses_utf8_encoding(tmp_path, monkeypatch):
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("placeholder")
    calls = []

    def fake_read_text(self, *args, **kwargs):
        calls.append(kwargs.get("encoding"))
        return SAMPLE_INSTINCT_YAML

    monkeypatch.setattr(Path, "read_text", fake_read_text)
    result = _load_instincts_from_dir(tmp_path, "personal", "project")
    assert result[0]["id"] == "test-instinct"
    assert calls == ["utf-8"]


# ─────────────────────────────────────────────
# load_all_instincts tests
# ─────────────────────────────────────────────

def test_load_all_project_and_global(patch_globals):
    """Should load from both project and global directories."""
    tree = patch_globals
    project = _make_project(tree)

    # Write a project instinct
    (project["instincts_personal"] / "proj.yaml").write_text(SAMPLE_INSTINCT_YAML)
    # Write a global instinct
    (tree["global_personal"] / "glob.yaml").write_text(SAMPLE_GLOBAL_INSTINCT_YAML)

    result = load_all_instincts(project)
    ids = {i["id"] for i in result}
    assert "test-instinct" in ids
    assert "global-instinct" in ids


def test_load_all_project_overrides_global(patch_globals):
    """When project and global have same ID, project wins."""
    tree = patch_globals
    project = _make_project(tree)

    # Same ID but different confidence
    proj_yaml = SAMPLE_INSTINCT_YAML.replace("id: test-instinct", "id: shared-id")
    proj_yaml = proj_yaml.replace("confidence: 0.8", "confidence: 0.9")
    glob_yaml = SAMPLE_GLOBAL_INSTINCT_YAML.replace("id: global-instinct", "id: shared-id")
    glob_yaml = glob_yaml.replace("confidence: 0.9", "confidence: 0.3")

    (project["instincts_personal"] / "shared.yaml").write_text(proj_yaml)
    (tree["global_personal"] / "shared.yaml").write_text(glob_yaml)

    result = load_all_instincts(project)
    shared = [i for i in result if i["id"] == "shared-id"]
    assert len(shared) == 1
    assert shared[0]["_scope_label"] == "project"
    assert shared[0]["confidence"] == 0.9


def test_load_all_global_only(patch_globals):
    """Global project should only load global instincts."""
    tree = patch_globals
    (tree["global_personal"] / "glob.yaml").write_text(SAMPLE_GLOBAL_INSTINCT_YAML)

    global_project = {
        "id": "global",
        "name": "global",
        "root": "",
        "project_dir": tree["homunculus"],
        "instincts_personal": tree["global_personal"],
        "instincts_inherited": tree["global_inherited"],
        "evolved_dir": tree["global_evolved"],
        "observations_file": tree["homunculus"] / "observations.jsonl",
    }

    result = load_all_instincts(global_project)
    assert len(result) == 1
    assert result[0]["id"] == "global-instinct"


def test_load_project_only_excludes_global(patch_globals):
    """load_project_only_instincts should NOT include global instincts."""
    tree = patch_globals
    project = _make_project(tree)

    (project["instincts_personal"] / "proj.yaml").write_text(SAMPLE_INSTINCT_YAML)
    (tree["global_personal"] / "glob.yaml").write_text(SAMPLE_GLOBAL_INSTINCT_YAML)

    result = load_project_only_instincts(project)
    ids = {i["id"] for i in result}
    assert "test-instinct" in ids
    assert "global-instinct" not in ids


def test_load_project_only_global_fallback_loads_global(patch_globals):
    """Global fallback should return global instincts for project-only queries."""
    tree = patch_globals
    (tree["global_personal"] / "glob.yaml").write_text(SAMPLE_GLOBAL_INSTINCT_YAML)

    global_project = {
        "id": "global",
        "name": "global",
        "root": "",
        "project_dir": tree["homunculus"],
        "instincts_personal": tree["global_personal"],
        "instincts_inherited": tree["global_inherited"],
        "evolved_dir": tree["global_evolved"],
        "observations_file": tree["homunculus"] / "observations.jsonl",
    }

    result = load_project_only_instincts(global_project)
    assert len(result) == 1
    assert result[0]["id"] == "global-instinct"


def test_load_all_empty(patch_globals):
    """No instincts at all should return empty list."""
    tree = patch_globals
    project = _make_project(tree)

    result = load_all_instincts(project)
    assert result == []


# ─────────────────────────────────────────────
# cmd_status tests
# ─────────────────────────────────────────────

def test_cmd_status_no_instincts(patch_globals, monkeypatch, capsys):
    """Status with no instincts should print fallback message."""
    tree = patch_globals
    project = _make_project(tree)
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    args = SimpleNamespace()
    ret = cmd_status(args)
    assert ret == 0
    out = capsys.readouterr().out
    assert "No instincts found." in out


def test_cmd_status_with_instincts(patch_globals, monkeypatch, capsys):
    """Status should show project and global instinct counts."""
    tree = patch_globals
    project = _make_project(tree)
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    (project["instincts_personal"] / "proj.yaml").write_text(SAMPLE_INSTINCT_YAML)
    (tree["global_personal"] / "glob.yaml").write_text(SAMPLE_GLOBAL_INSTINCT_YAML)

    args = SimpleNamespace()
    ret = cmd_status(args)
    assert ret == 0
    out = capsys.readouterr().out
    assert "INSTINCT STATUS" in out
    assert "Project instincts: 1" in out
    assert "Global instincts:  1" in out
    assert "PROJECT-SCOPED" in out
    assert "GLOBAL" in out


def test_cmd_status_returns_int(patch_globals, monkeypatch):
    """cmd_status should always return an int."""
    tree = patch_globals
    project = _make_project(tree)
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    args = SimpleNamespace()
    ret = cmd_status(args)
    assert isinstance(ret, int)


# ─────────────────────────────────────────────
# cmd_projects tests
# ─────────────────────────────────────────────

def test_cmd_projects_empty_registry(patch_globals, capsys):
    """No projects should print helpful message."""
    args = SimpleNamespace()
    ret = cmd_projects(args)
    assert ret == 0
    out = capsys.readouterr().out
    assert "No projects registered yet." in out


def test_cmd_projects_with_registry(patch_globals, capsys):
    """Should list projects from registry."""
    tree = patch_globals

    # Create a project dir with instincts
    pid = "test123abc"
    project = _make_project(tree, pid=pid, pname="my-app")
    (project["instincts_personal"] / "inst.yaml").write_text(SAMPLE_INSTINCT_YAML)

    # Write registry
    registry = {
        pid: {
            "name": "my-app",
            "root": "/home/user/my-app",
            "remote": "https://github.com/user/my-app.git",
            "last_seen": "2025-01-15T12:00:00Z",
        }
    }
    tree["registry_file"].write_text(json.dumps(registry))

    args = SimpleNamespace()
    ret = cmd_projects(args)
    assert ret == 0
    out = capsys.readouterr().out
    assert "my-app" in out
    assert pid in out
    assert "1 personal" in out


# ─────────────────────────────────────────────
# _promote_specific tests
# ─────────────────────────────────────────────

def test_promote_specific_not_found(patch_globals, capsys):
    """Promoting nonexistent instinct should fail."""
    tree = patch_globals
    project = _make_project(tree)

    ret = _promote_specific(project, "nonexistent", force=True)
    assert ret == 1
    out = capsys.readouterr().out
    assert "not found" in out


def test_promote_specific_rejects_invalid_id(patch_globals, capsys):
    """Path-like instinct IDs should be rejected before file writes."""
    tree = patch_globals
    project = _make_project(tree)

    ret = _promote_specific(project, "../escape", force=True)
    assert ret == 1
    err = capsys.readouterr().err
    assert "Invalid instinct ID" in err


def test_promote_specific_already_global(patch_globals, capsys):
    """Promoting an instinct that already exists globally should fail."""
    tree = patch_globals
    project = _make_project(tree)

    # Write same-id instinct in both project and global
    (project["instincts_personal"] / "shared.yaml").write_text(SAMPLE_INSTINCT_YAML)
    global_yaml = SAMPLE_INSTINCT_YAML  # same id: test-instinct
    (tree["global_personal"] / "shared.yaml").write_text(global_yaml)

    ret = _promote_specific(project, "test-instinct", force=True)
    assert ret == 1
    out = capsys.readouterr().out
    assert "already exists in global" in out


def test_promote_specific_success(patch_globals, capsys):
    """Promote a project instinct to global with --force."""
    tree = patch_globals
    project = _make_project(tree)

    (project["instincts_personal"] / "inst.yaml").write_text(SAMPLE_INSTINCT_YAML)

    ret = _promote_specific(project, "test-instinct", force=True)
    assert ret == 0
    out = capsys.readouterr().out
    assert "Promoted" in out

    # Verify file was created in global dir
    promoted_file = tree["global_personal"] / "test-instinct.yaml"
    assert promoted_file.exists()
    content = promoted_file.read_text()
    assert "scope: global" in content
    assert "promoted_from: abc123" in content


# ─────────────────────────────────────────────
# _promote_auto tests
# ─────────────────────────────────────────────

def test_promote_auto_no_candidates(patch_globals, capsys):
    """Auto-promote with no cross-project instincts should say so."""
    tree = patch_globals
    project = _make_project(tree)

    # Empty registry
    tree["registry_file"].write_text("{}")

    ret = _promote_auto(project, force=True, dry_run=False)
    assert ret == 0
    out = capsys.readouterr().out
    assert "No instincts qualify" in out


def test_promote_auto_dry_run(patch_globals, capsys):
    """Dry run should list candidates but not write files."""
    tree = patch_globals

    # Create two projects with the same high-confidence instinct
    p1 = _make_project(tree, pid="proj1", pname="project-one")
    p2 = _make_project(tree, pid="proj2", pname="project-two")

    high_conf_yaml = """\
---
id: cross-project-instinct
trigger: "when reviewing"
confidence: 0.95
domain: security
scope: project
---

## Action
Always review for injection.
"""
    (p1["instincts_personal"] / "cross.yaml").write_text(high_conf_yaml)
    (p2["instincts_personal"] / "cross.yaml").write_text(high_conf_yaml)

    # Write registry
    registry = {
        "proj1": {"name": "project-one", "root": "/a", "remote": "", "last_seen": "2025-01-01T00:00:00Z"},
        "proj2": {"name": "project-two", "root": "/b", "remote": "", "last_seen": "2025-01-01T00:00:00Z"},
    }
    tree["registry_file"].write_text(json.dumps(registry))

    project = p1
    ret = _promote_auto(project, force=True, dry_run=True)
    assert ret == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "cross-project-instinct" in out

    # Verify no file was created
    assert not (tree["global_personal"] / "cross-project-instinct.yaml").exists()


def test_promote_auto_writes_file(patch_globals, capsys):
    """Auto-promote with force should write global instinct file."""
    tree = patch_globals

    p1 = _make_project(tree, pid="proj1", pname="project-one")
    p2 = _make_project(tree, pid="proj2", pname="project-two")

    high_conf_yaml = """\
---
id: universal-pattern
trigger: "when coding"
confidence: 0.85
domain: general
scope: project
---

## Action
Use descriptive variable names.
"""
    (p1["instincts_personal"] / "uni.yaml").write_text(high_conf_yaml)
    (p2["instincts_personal"] / "uni.yaml").write_text(high_conf_yaml)

    registry = {
        "proj1": {"name": "project-one", "root": "/a", "remote": "", "last_seen": "2025-01-01T00:00:00Z"},
        "proj2": {"name": "project-two", "root": "/b", "remote": "", "last_seen": "2025-01-01T00:00:00Z"},
    }
    tree["registry_file"].write_text(json.dumps(registry))

    ret = _promote_auto(p1, force=True, dry_run=False)
    assert ret == 0

    promoted = tree["global_personal"] / "universal-pattern.yaml"
    assert promoted.exists()
    content = promoted.read_text()
    assert "scope: global" in content
    assert "auto-promoted" in content


def test_promote_auto_skips_invalid_id(patch_globals, capsys):
    tree = patch_globals

    p1 = _make_project(tree, pid="proj1", pname="project-one")
    p2 = _make_project(tree, pid="proj2", pname="project-two")

    bad_id_yaml = """\
---
id: ../escape
trigger: "when coding"
confidence: 0.9
domain: general
scope: project
---

## Action
Invalid id should be skipped.
"""
    (p1["instincts_personal"] / "bad.yaml").write_text(bad_id_yaml)
    (p2["instincts_personal"] / "bad.yaml").write_text(bad_id_yaml)

    registry = {
        "proj1": {"name": "project-one", "root": "/a", "remote": "", "last_seen": "2025-01-01T00:00:00Z"},
        "proj2": {"name": "project-two", "root": "/b", "remote": "", "last_seen": "2025-01-01T00:00:00Z"},
    }
    tree["registry_file"].write_text(json.dumps(registry))

    ret = _promote_auto(p1, force=True, dry_run=False)
    assert ret == 0
    err = capsys.readouterr().err
    assert "Skipping invalid instinct ID" in err
    assert not (tree["global_personal"] / "../escape.yaml").exists()


# ─────────────────────────────────────────────
# _find_cross_project_instincts tests
# ─────────────────────────────────────────────

def test_find_cross_project_empty_registry(patch_globals):
    tree = patch_globals
    tree["registry_file"].write_text("{}")
    result = _find_cross_project_instincts()
    assert result == {}


def test_find_cross_project_single_project(patch_globals):
    """Single project should return nothing (need 2+)."""
    tree = patch_globals
    p1 = _make_project(tree, pid="proj1", pname="project-one")
    (p1["instincts_personal"] / "inst.yaml").write_text(SAMPLE_INSTINCT_YAML)

    registry = {"proj1": {"name": "project-one", "root": "/a", "remote": "", "last_seen": "2025-01-01T00:00:00Z"}}
    tree["registry_file"].write_text(json.dumps(registry))

    result = _find_cross_project_instincts()
    assert result == {}


def test_find_cross_project_shared_instinct(patch_globals):
    """Same instinct ID in 2 projects should be found."""
    tree = patch_globals
    p1 = _make_project(tree, pid="proj1", pname="project-one")
    p2 = _make_project(tree, pid="proj2", pname="project-two")

    (p1["instincts_personal"] / "shared.yaml").write_text(SAMPLE_INSTINCT_YAML)
    (p2["instincts_personal"] / "shared.yaml").write_text(SAMPLE_INSTINCT_YAML)

    registry = {
        "proj1": {"name": "project-one", "root": "/a", "remote": "", "last_seen": "2025-01-01T00:00:00Z"},
        "proj2": {"name": "project-two", "root": "/b", "remote": "", "last_seen": "2025-01-01T00:00:00Z"},
    }
    tree["registry_file"].write_text(json.dumps(registry))

    result = _find_cross_project_instincts()
    assert "test-instinct" in result
    assert len(result["test-instinct"]) == 2


# ─────────────────────────────────────────────
# load_registry tests
# ─────────────────────────────────────────────

def test_load_registry_missing_file(patch_globals):
    result = load_registry()
    assert result == {}


def test_load_registry_corrupt_json(patch_globals):
    tree = patch_globals
    tree["registry_file"].write_text("not json at all {{{")
    result = load_registry()
    assert result == {}


def test_load_registry_valid(patch_globals):
    tree = patch_globals
    data = {"abc": {"name": "test", "root": "/test"}}
    tree["registry_file"].write_text(json.dumps(data))
    result = load_registry()
    assert result == data


def test_load_registry_uses_utf8_encoding(monkeypatch):
    calls = []

    def fake_open(path, mode="r", *args, **kwargs):
        calls.append(kwargs.get("encoding"))
        return io.StringIO("{}")

    monkeypatch.setattr(_mod, "open", fake_open, raising=False)
    assert load_registry() == {}
    assert calls == ["utf-8"]


def test_validate_instinct_id():
    assert _validate_instinct_id("good-id_1.0")
    assert not _validate_instinct_id("../bad")
    assert not _validate_instinct_id("bad/name")
    assert not _validate_instinct_id(".hidden")


def test_update_registry_atomic_replaces_file(patch_globals):
    tree = patch_globals
    _update_registry("abc123", "demo", "/repo", "https://example.com/repo.git")
    data = json.loads(tree["registry_file"].read_text())
    assert "abc123" in data
    leftovers = list(tree["registry_file"].parent.glob(".projects.json.tmp.*"))
    assert leftovers == []


# ─────────────────────────────────────────────
# Confidence Decay Tests
# ─────────────────────────────────────────────

def test_confidence_decay_calculation():
    """Instinct with last_observed=90 days ago, confidence=0.8 → decayed to ~0.41."""
    from datetime import datetime, timezone, timedelta
    past = datetime.now(timezone.utc) - timedelta(days=90)
    instinct = {
        'id': 'test',
        'confidence': 0.8,
        'last_observed': past.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    decayed = _calculate_decayed_confidence(instinct)
    # 0.8 * (0.8 ** (90/30)) = 0.8 * 0.8^3 = 0.8 * 0.512 = 0.4096 ≈ 0.41
    assert decayed == pytest.approx(0.41, abs=0.02)


def test_confidence_decay_no_decay_recent():
    """Instinct with last_observed=today should keep original confidence."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    instinct = {
        'id': 'test',
        'confidence': 0.8,
        'last_observed': now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    decayed = _calculate_decayed_confidence(instinct)
    assert decayed == 0.8


def test_confidence_decay_no_last_observed():
    """Instinct without last_observed should return original confidence."""
    instinct = {'id': 'test', 'confidence': 0.8}
    decayed = _calculate_decayed_confidence(instinct)
    assert decayed == 0.8


def test_confidence_decay_high_rate():
    """Instinct with confidence >= 0.9 should decay at slower rate (0.9)."""
    from datetime import datetime, timezone, timedelta
    past = datetime.now(timezone.utc) - timedelta(days=90)
    instinct = {
        'id': 'test',
        'confidence': 0.95,
        'last_observed': past.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    decayed = _calculate_decayed_confidence(instinct)
    # 0.95 * (0.9 ** 3) = 0.95 * 0.729 = 0.69255 ≈ 0.69
    assert decayed == pytest.approx(0.69, abs=0.02)


def test_confidence_decay_floor_at_zero():
    """Very old instincts should floor at 0.0 (not go negative)."""
    from datetime import datetime, timezone, timedelta
    far_past = datetime.now(timezone.utc) - timedelta(days=3650)
    instinct = {
        'id': 'test',
        'confidence': 0.5,
        'last_observed': far_past.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    decayed = _calculate_decayed_confidence(instinct)
    assert decayed == 0.0


def test_apply_confidence_decay_adds_original():
    """_apply_confidence_decay should store original confidence."""
    from datetime import datetime, timezone, timedelta
    past = datetime.now(timezone.utc) - timedelta(days=30)
    instincts = [{
        'id': 'test',
        'confidence': 0.8,
        'last_observed': past.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }]
    _apply_confidence_decay(instincts)
    assert instincts[0]['original_confidence'] == 0.8
    assert instincts[0]['confidence'] < 0.8


def test_apply_confidence_decay_no_last_observed_unchanged():
    """Instincts without last_observed should not be modified."""
    instincts = [{'id': 'test', 'confidence': 0.8}]
    _apply_confidence_decay(instincts)
    assert 'original_confidence' not in instincts[0]
    assert instincts[0]['confidence'] == 0.8


def test_get_instincts_eligible_for_deprecation():
    """Instincts below 0.3 should be returned."""
    instincts = [
        {'id': 'low', 'confidence': 0.2},
        {'id': 'high', 'confidence': 0.8},
        {'id': 'mid', 'confidence': 0.3},
    ]
    eligible = _get_instincts_eligible_for_deprecation(instincts)
    assert len(eligible) == 1
    assert eligible[0]['id'] == 'low'


def test_confidence_decay_status_no_decay_flag(patch_globals, monkeypatch, capsys):
    """--no-decay flag should show original confidence values."""
    from datetime import datetime, timezone, timedelta
    past = datetime.now(timezone.utc) - timedelta(days=90)

    inst_file = patch_globals['global_personal'] / 'test.yaml'
    inst_file.write_text(f"""\
---
id: test-instinct
trigger: "when testing"
confidence: 0.8
domain: testing
last_observed: {past.strftime("%Y-%m-%dT%H:%M:%SZ")}
---

## Action
Test.
""")

    args = SimpleNamespace(decay=False, min_confidence=0.0, domain=None, show_deprecated=False, show_config=False, show_identity=False, format='normal')
    result = cmd_status(args)
    captured = capsys.readouterr()
    assert '80%' in captured.out
    assert 'orig' not in captured.out


def test_confidence_decay_status_decay_flag(patch_globals, monkeypatch, capsys):
    """With decay enabled (default), should show original in parentheses."""
    from datetime import datetime, timezone, timedelta
    past = datetime.now(timezone.utc) - timedelta(days=90)

    inst_file = patch_globals['global_personal'] / 'test.yaml'
    inst_file.write_text(f"""\
---
id: test-instinct
trigger: "when testing"
confidence: 0.8
domain: testing
last_observed: {past.strftime("%Y-%m-%dT%H:%M:%SZ")}
---

## Action
Test.
""")

    args = SimpleNamespace(decay=True, min_confidence=0.0, domain=None, show_deprecated=False, show_config=False, show_identity=False, format='normal')
    result = cmd_status(args)
    captured = capsys.readouterr()
    assert 'orig' in captured.out
    assert '41%' in captured.out
    assert '80% orig' in captured.out


# ─────────────────────────────────────────────
# Deprecate / Deprecated tests
# ─────────────────────────────────────────────

def test_move_to_deprecated(patch_globals):
    """Moving a file to deprecated should succeed."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    inst_file = project["instincts_personal"] / "test.yaml"
    inst_file.write_text("""\
---
id: test-instinct
trigger: "when testing"
confidence: 0.8
domain: testing
---

## Action
Test.
""")
    result = _move_to_deprecated(inst_file, project)
    assert result == True
    assert not inst_file.exists()
    deprecated_dir = Path(str(project["instincts_personal"]).replace("/personal", "/deprecated"))
    assert deprecated_dir.exists()
    assert (deprecated_dir / "test.yaml").exists()


def test_auto_deprecate_moves_low_confidence(patch_globals, monkeypatch):
    """Instinct with decayed confidence < 0.3 should be auto-deprecated."""
    from datetime import datetime, timezone, timedelta
    project = _make_project(patch_globals, "test-proj", "test-project")
    past = datetime.now(timezone.utc) - timedelta(days=365)
    inst_file = project["instincts_personal"] / "low.yaml"
    inst_file.write_text(f"""\
---
id: low-confidence
trigger: "when testing"
confidence: 0.2
domain: testing
last_observed: {past.strftime("%Y-%m-%dT%H:%M:%SZ")}
---

## Action
Do risky thing.
""")

    deprecated_ids = _auto_deprecate(project)
    assert "low-confidence" in deprecated_ids
    assert not inst_file.exists()
    deprecated_dir = Path(str(project["instincts_personal"]).replace("/personal", "/deprecated"))
    assert (deprecated_dir / "low.yaml").exists()


def test_auto_deprecate_skips_high_confidence(patch_globals, monkeypatch):
    """Instinct with high confidence should NOT be deprecated."""
    from datetime import datetime, timezone, timedelta
    project = _make_project(patch_globals, "test-proj", "test-project")
    past = datetime.now(timezone.utc) - timedelta(days=180)
    inst_file = project["instincts_personal"] / "high.yaml"
    inst_file.write_text(f"""\
---
id: high-confidence
trigger: "when testing"
confidence: 0.9
domain: testing
last_observed: {past.strftime("%Y-%m-%dT%H:%M:%SZ")}
---

## Action
Safe practice.
""")

    deprecated_ids = _auto_deprecate(project)
    assert "high-confidence" not in deprecated_ids
    assert inst_file.exists()


def test_auto_deprecate_skips_user_profile(patch_globals, monkeypatch):
    """User-profile instincts should NOT be auto-deprecated even with low confidence."""
    from datetime import datetime, timezone, timedelta
    project = _make_project(patch_globals, "test-proj", "test-project")
    past = datetime.now(timezone.utc) - timedelta(days=365)
    inst_file = project["instincts_personal"] / "user.yaml"
    inst_file.write_text(f"""\
---
id: user-pref
trigger: "when coding"
confidence: 0.1
domain: user-profile
last_observed: {past.strftime("%Y-%m-%dT%H:%M:%SZ")}
---

## Action
User preference.
""")

    deprecated_ids = _auto_deprecate(project)
    assert "user-pref" not in deprecated_ids
    assert inst_file.exists()


def test_load_deprecated_instincts(patch_globals):
    """load_all_instincts should NOT include deprecated by default."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    normal_file = project["instincts_personal"] / "normal.yaml"
    normal_file.write_text("""\
---
id: normal
trigger: "when testing"
confidence: 0.8
domain: testing
---

## Action
Test.
""")
    deprecated_dir = Path(str(project["instincts_personal"]).replace("/personal", "/deprecated"))
    deprecated_dir.mkdir(parents=True, exist_ok=True)
    dep_file = deprecated_dir / "deprecated.yaml"
    dep_file.write_text("""\
---
id: deprecated-instinct
trigger: "when old"
confidence: 0.1
domain: testing
---

## Action
Old way.
""")

    instincts = load_all_instincts(project)
    ids = [i['id'] for i in instincts]
    assert "normal" in ids
    assert "deprecated-instinct" not in ids


def test_user_profile_instinct_separate_section(patch_globals, monkeypatch, capsys):
    """User-profile instincts should appear in a separate section."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    (project["instincts_personal"] / "user.yaml").write_text("""\
---
id: user-style
trigger: "when communicating"
confidence: 0.8
domain: user-profile
---

## Action
Prefer concise responses.
""")
    (project["instincts_personal"] / "code.yaml").write_text("""\
---
id: code-style
trigger: "when writing code"
confidence: 0.7
domain: code-style
---

## Action
Use functional patterns.
""")

    args = SimpleNamespace(decay=True, min_confidence=0.0, domain=None, show_deprecated=False, show_config=False, show_identity=False, format='normal')
    result = cmd_status(args)
    captured = capsys.readouterr()
    assert '[USER]' in captured.out or 'user-profile'.upper() in captured.out
    assert 'code-style' in captured.out
    assert 'user-style' in captured.out


def test_status_shows_user_profile_count(patch_globals, monkeypatch, capsys):
    """Status header should show user-profile instinct count."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    (project["instincts_personal"] / "user.yaml").write_text("""\
---
id: user-style
trigger: "when communicating"
confidence: 0.8
domain: user-profile
---

## Action
Prefer concise.
""")

    args = SimpleNamespace(decay=True, min_confidence=0.0, domain=None, show_deprecated=False, show_config=False, show_identity=False, format='normal')
    result = cmd_status(args)
    captured = capsys.readouterr()
    assert 'User-profile' in captured.out or 'user-profile' in captured.out


def test_status_domain_filter(patch_globals, monkeypatch, capsys):
    """--domain user-profile filter should show only user-profile instincts."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    (project["instincts_personal"] / "user.yaml").write_text("""\
---
id: user-style
trigger: "when communicating"
confidence: 0.8
domain: user-profile
---
## Action
Prefer concise.
""")
    (project["instincts_personal"] / "code.yaml").write_text("""\
---
id: code-style
trigger: "when writing code"
confidence: 0.7
domain: code-style
---
## Action
Use patterns.
""")

    args = SimpleNamespace(decay=True, min_confidence=0.0, domain='user-profile', show_deprecated=False, show_config=False, show_identity=False, format='normal')
    result = cmd_status(args)
    captured = capsys.readouterr()
    assert 'user-style' in captured.out
    assert 'code-style' not in captured.out


def test_load_user_profile_instincts(patch_globals):
    """_load_user_profile_instincts should return only user-profile instincts."""
    project = _make_project(patch_globals, "test-proj", "test-project")

    (project["instincts_personal"] / "user.yaml").write_text("""\
---
id: user-style
trigger: "when communicating"
confidence: 0.8
domain: user-profile
---
## Action
Prefer concise.
""")
    (project["instincts_personal"] / "code.yaml").write_text("""\
---
id: code-style
trigger: "when writing code"
confidence: 0.7
domain: code-style
---
## Action
Use patterns.
""")

    result = _load_user_profile_instincts(project)
    ids = [i['id'] for i in result]
    assert 'user-style' in ids
    assert 'code-style' not in ids


# ─────────────────────────────────────────────
# Identity Tests
# ─────────────────────────────────────────────


def test_identity_json_auto_created(patch_globals):
    """identity.json should be auto-created with defaults."""
    identity_file = patch_globals["homunculus"] / "identity.json"
    assert not identity_file.exists()
    _create_default_identity()
    assert identity_file.exists()
    data = json.loads(identity_file.read_text())
    assert data["version"] == "1.0"
    assert data["technical_level"] == "intermediate"


def test_identity_json_not_overwritten(patch_globals):
    """Calling _create_default_identity again should not overwrite existing."""
    identity_file = patch_globals["homunculus"] / "identity.json"
    identity_file.parent.mkdir(parents=True, exist_ok=True)
    identity_file.write_text(json.dumps({"version": "1.0", "technical_level": "advanced", "name": "Test User"}))
    _create_default_identity()
    data = json.loads(identity_file.read_text())
    assert data["technical_level"] == "advanced"
    assert data["name"] == "Test User"


def test_identity_validation_valid():
    """Valid identity should return no errors."""
    data = {
        "version": "1.0",
        "technical_level": "expert",
        "preferences": {
            "communication_style": "detailed",
            "response_language": "en",
            "likes_type_hints": True,
            "likes_comments": "thorough"
        }
    }
    errors = _validate_identity(data)
    assert errors == []


def test_identity_validation_invalid():
    """Invalid technical_level should return an error."""
    data = {"technical_level": "novice"}
    errors = _validate_identity(data)
    assert len(errors) >= 1
    assert "novice" in errors[0]


def test_identity_inject_empty():
    """Default identity should produce empty injection."""
    data = dict(IDENTITY_DEFAULTS)
    data["updated"] = "2026-01-01T00:00:00Z"
    text = _inject_identity_prompt(data)
    assert text == ""


def test_identity_inject_custom():
    """Custom identity should produce formatted injection."""
    data = {
        "version": "1.0",
        "updated": "2026-01-01T00:00:00Z",
        "name": "Test User",
        "technical_level": "expert",
        "preferences": {
            "communication_style": "detailed",
            "response_language": "en",
            "likes_type_hints": True,
            "likes_comments": "thorough"
        },
        "expertise_areas": ["python", "typescript"]
    }
    text = _inject_identity_prompt(data)
    assert "## User Profile" in text
    assert "Technical Level: expert" in text
    assert "Test User" in text
    assert "python" in text
    assert len(text) <= 500


# ─────────────────────────────────────────────
# cmd_analyze tests
# ─────────────────────────────────────────────

def _write_observations(project: dict, tool: str, count: int, event: str = "tool_complete"):
    """Helper to write observations to a project's observations file."""
    obs_file = Path(project["observations_file"])
    obs_file.parent.mkdir(parents=True, exist_ok=True)
    with open(obs_file, "a") as f:
        for i in range(count):
            obs = {
                "timestamp": "2026-01-01T00:00:00Z",
                "event": event,
                "tool": tool,
                "args": "{}",
                "project_id": project["id"],
                "project_name": project["name"],
            }
            f.write(json.dumps(obs) + "\n")


def test_analyze_insufficient_observations(patch_globals, monkeypatch, capsys):
    """Analyze with <20 observations should skip."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)
    _write_observations(project, "read", 5)

    args = SimpleNamespace(dry_run=False, all_projects=False, no_interactive=True, min_observations=20)
    result = cmd_analyze(args)
    captured = capsys.readouterr()
    assert "Need at least" in captured.out
    assert result == 0


def test_analyze_with_sufficient_observations(patch_globals, monkeypatch, capsys):
    """Analyze with >=20 observations should find patterns."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)
    _write_observations(project, "edit", 25)

    args = SimpleNamespace(dry_run=False, all_projects=False, no_interactive=True, min_observations=20)
    result = cmd_analyze(args)
    captured = capsys.readouterr()
    assert "Patterns found" in captured.out or "edit" in captured.out
    pending_dir = project["project_dir"] / "instincts" / "pending"
    pending_files = list(pending_dir.glob("*.yaml")) if pending_dir.exists() else []
    assert len(pending_files) >= 1
    assert result == 0


def test_analyze_dry_run(patch_globals, monkeypatch, capsys):
    """Analyze --dry-run should not create files."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)
    _write_observations(project, "write", 25)

    args = SimpleNamespace(dry_run=True, all_projects=False, no_interactive=True, min_observations=20)
    result = cmd_analyze(args)
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    pending_dir = project["project_dir"] / "instincts" / "pending"
    pending_files = list(pending_dir.glob("*.yaml")) if pending_dir.exists() else []
    assert len(pending_files) == 0
    assert result == 0


def test_analyze_no_observations(patch_globals, monkeypatch, capsys):
    """Analyze with no observations file should no-op."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    args = SimpleNamespace(dry_run=False, all_projects=False, no_interactive=True, min_observations=20)
    result = cmd_analyze(args)
    captured = capsys.readouterr()
    assert "No observations file found" in captured.out
    assert result == 0


def test_analyze_multiple_tools(patch_globals, monkeypatch, capsys):
    """Analyze with observations from multiple tools should find patterns for each."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    _write_observations(project, "edit", 15)
    _write_observations(project, "read", 15)

    args = SimpleNamespace(dry_run=False, all_projects=False, no_interactive=True, min_observations=20)
    result = cmd_analyze(args)
    assert result == 0


def test_analyze_idempotent(patch_globals, monkeypatch, capsys):
    """Running analyze twice should not create duplicate pending instincts."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)
    _write_observations(project, "edit", 25)

    args = SimpleNamespace(dry_run=False, all_projects=False, no_interactive=True, min_observations=20)
    cmd_analyze(args)
    capsys.readouterr()

    pending_dir = project["project_dir"] / "instincts" / "pending"
    first_count = len(list(pending_dir.glob("*.yaml"))) if pending_dir.exists() else 0

    cmd_analyze(args)
    capsys.readouterr()

    second_count = len(list(pending_dir.glob("*.yaml"))) if pending_dir.exists() else 0
    assert first_count == second_count


# ─────────────────────────────────────────────
# Confidence Decay Lifecycle Tests
# ─────────────────────────────────────────────

def test_decay_lifecycle_full(patch_globals, monkeypatch, capsys):
    """End-to-end: instinct with old last_observed should show decayed confidence."""
    from datetime import datetime, timezone, timedelta
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).strftime('%Y-%m-%dT%H:%M:%SZ')
    personal_dir = project['project_dir'] / "instincts" / "personal"
    personal_dir.mkdir(parents=True, exist_ok=True)
    instinct_file = personal_dir / "test-instinct.yaml"
    instinct_file.write_text(f"""---
id: test-instinct
trigger: "when testing"
confidence: 0.8
domain: testing
last_observed: {ninety_days_ago}
---

## Action
Test action
""", encoding="utf-8")

    instincts = _mod.load_all_instincts(project)
    instinct = instincts[0]
    assert instinct['confidence'] == 0.8

    decayed = _mod._apply_confidence_decay(instincts)
    assert decayed[0]['confidence'] == pytest.approx(0.41, abs=0.02)
    assert decayed[0].get('original_confidence') == 0.8


def test_decay_user_profile_not_deprecated(patch_globals, monkeypatch, capsys):
    """User-profile instincts should NOT be auto-deprecated even with low confidence via decay."""
    from datetime import datetime, timezone, timedelta
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    old_date = (datetime.now(timezone.utc) - timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%SZ')
    personal_dir = project['project_dir'] / "instincts" / "personal"
    personal_dir.mkdir(parents=True, exist_ok=True)
    instinct_file = personal_dir / "user-pref.yaml"
    instinct_file.write_text(f"""---
id: user-pref-test
trigger: "when user prefers concise responses"
confidence: 0.5
domain: user-profile
last_observed: {old_date}
---

## Action
Be concise
""", encoding="utf-8")

    deprecated = _mod._auto_deprecate(project)
    assert instinct_file.exists()
    assert deprecated is None or len(deprecated) == 0


# ─────────────────────────────────────────────
# Analyze Lifecycle Test
# ─────────────────────────────────────────────

def test_analyze_lifecycle(patch_globals, monkeypatch, capsys):
    """Full lifecycle: create observations, analyze, verify pending instinct structure."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    _write_observations(project, "bash", 30)

    args = SimpleNamespace(dry_run=False, all_projects=False, no_interactive=True, min_observations=20)
    result = cmd_analyze(args)
    assert result == 0
    capsys.readouterr()

    pending_dir = project["project_dir"] / "instincts" / "pending"
    pending_files = list(pending_dir.glob("*.yaml")) if pending_dir.exists() else []
    assert len(pending_files) >= 1

    content = pending_files[0].read_text()
    assert "id:" in content
    assert "confidence:" in content
    assert "domain:" in content
    assert "run-commands" in content or "bash" in content

    cmd_analyze(args)
    capsys.readouterr()
    pending_files_again = list(pending_dir.glob("*.yaml")) if pending_dir.exists() else []
    assert len(pending_files_again) == len(pending_files)


# ─────────────────────────────────────────────
# Prompt Injection Tests
# ─────────────────────────────────────────────

def test_injection_formatting(patch_globals, monkeypatch, capsys):
    """Simulate injection formatting logic for high-confidence instincts."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    personal_dir = project['project_dir'] / "instincts" / "personal"
    personal_dir.mkdir(parents=True, exist_ok=True)

    for i, (name, conf) in enumerate([
        ("high-a", 0.9), ("high-b", 0.8), ("high-c", 0.7),
        ("low-a", 0.3), ("low-b", 0.4),
    ]):
        (personal_dir / f"{name}.yaml").write_text(f"""---
id: {name}
trigger: "when testing {name}"
confidence: {conf}
domain: testing
---

## Action
Test {name}
""", encoding="utf-8")

    instincts = _mod.load_all_instincts(project)
    high_conf = [i for i in instincts if i.get('confidence', 0) >= 0.7]
    assert len(high_conf) == 3

    project_name = "test-project"
    lines = [f"## Active Instincts for {project_name}"]
    for inst in sorted(high_conf, key=lambda x: -x['confidence']):
        pct = round(inst['confidence'] * 100)
        lines.append(f"- {inst.get('domain', 'general')} ({pct}%): {inst.get('trigger', '')}")

    block = "\n".join(lines)
    assert len(block) > 0
    assert "90%" in block
    assert "70%" in block


def test_injection_token_budget(patch_globals, monkeypatch, capsys):
    """Test 2000 char limit enforcement (highest confidence first)."""
    project = _make_project(patch_globals, "test-proj", "test-project")
    monkeypatch.setattr(_mod, "detect_project", lambda: project)

    personal_dir = project['project_dir'] / "instincts" / "personal"
    personal_dir.mkdir(parents=True, exist_ok=True)

    for i in range(10):
        conf = round(0.5 + (i * 0.05), 2)
        (personal_dir / f"instinct-{i}.yaml").write_text(f"""---
id: instinct-{i}
trigger: "when user wants to do something very specific and detailed with lots of words to test {i}"
confidence: {conf}
domain: testing
---

## Action
Do thing {i}
""", encoding="utf-8")

    instincts = _mod.load_all_instincts(project)
    high_conf = sorted([i for i in instincts if i.get('confidence', 0) >= 0.7], key=lambda x: -x['confidence'])

    MAX_CHARS = 2000
    block = "## Active Instincts for test-project\n"
    included = []
    for inst in high_conf:
        line = f"- {inst.get('domain', 'general')} ({round(inst['confidence']*100)}%): {inst.get('trigger', '')}\n"
        if len(block + line) > MAX_CHARS:
            break
        block += line
        included.append(inst)

    assert len(included) > 0
    assert included[0]['confidence'] == max(i['confidence'] for i in high_conf)
    assert len(block) <= MAX_CHARS
