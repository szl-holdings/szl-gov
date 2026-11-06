"""Run the forbidden-domain workflow's scan step for real, in throwaway trees.

The step used to call ripgrep, which GitHub's Ubuntu runners do not ship; its
`|| true` turned "rg: command not found" into a clean result on every run.
These tests execute the exact script from the workflow so a scanner that
cannot run fails the gate instead of passing it.
"""
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/forbidden-domain.yml"
STEP = "- name: Scan for forbidden domain references"
DOMAIN = "a11oy" + ".com"  # assembled so this file is not itself a hit


def _gnu_grep_with_pcre():
    if not shutil.which("bash") or not shutil.which("grep"):
        return False
    probe = subprocess.run(["grep", "-P", "(?<!-)x", "-"], input="x\n", capture_output=True, text=True,
                           check=False)
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not _gnu_grep_with_pcre(),
    reason="needs bash and GNU grep with -P (PCRE), as on the ubuntu-latest runner the workflow uses",
)


def _scan_script():
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == STEP)
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    indent = len(lines[run]) - len(lines[run].lstrip())
    body = []
    for line in lines[run + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return textwrap.dedent("\n".join(body)) + "\n"


def _run(tree, path=None):
    env = None if path is None else {"PATH": str(path)}
    return subprocess.run([shutil.which("bash"), "-c", _scan_script()], cwd=tree, env=env,
                          capture_output=True, text=True, check=False)


def test_clean_tree_and_guard_contexts_pass(tmp_path):
    (tmp_path / "README.md").write_text(
        f"Product: a-11-oy.com\nNever link {DOMAIN}; it is not a surface.\n", encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK: no forbidden domain references" in result.stdout


def test_unguarded_reference_fails(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "page.md").write_text(f"Visit https://{DOMAIN} today\n", encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "::error::Forbidden domain references found" in result.stdout
    assert f"docs/page.md:1:Visit https://{DOMAIN} today" in result.stdout


def test_git_directory_is_not_scanned(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "COMMIT_EDITMSG").write_text(f"mention {DOMAIN}\n", encoding="utf-8")
    assert _run(tmp_path).returncode == 0


def test_missing_scanner_fails_instead_of_reporting_clean(tmp_path):
    (tmp_path / "page.md").write_text(f"https://{DOMAIN}\n", encoding="utf-8")
    empty_path = tmp_path / "no-tools"
    empty_path.mkdir()
    result = _run(tmp_path, path=empty_path)  # bash builtins only: no grep on PATH
    assert result.returncode != 0
    assert "refusing to report clean" in result.stdout
    assert "OK:" not in result.stdout
