"""The runtime pins in requirements.txt and pyproject.toml must agree.

CI and the truth checks install requirements.txt; `pip install -e .` installs
pyproject.toml's dependencies. A bump to only one of them leaves the installed
package metadata contradicting the version the suites ran against (pip reports
"szl-gov 0.1.0 requires cryptography==50.0.1, but you have cryptography 50.0.2").
"""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;#]+)")


def _pins(lines):
    pins = {}
    for line in lines:
        match = PIN.fullmatch(line.split("#", 1)[0].strip())
        if match:
            pins[match.group(1).lower().replace("_", "-")] = match.group(2)
    return pins


def test_pyproject_dependencies_pin_what_requirements_txt_pins():
    required = _pins((ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert required, "requirements.txt pins no runtime dependency"
    assert _pins(project["dependencies"]) == required
