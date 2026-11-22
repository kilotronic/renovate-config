"""The preset's rules, proven on the names and settings they exist for. CI also runs
Renovate's own validator over every preset (.github/workflows/ci.yml)."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ("default.json", "automerge.json")


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


DEFAULT = load("default.json")
AUTOMERGE = load("automerge.json")

# The shared check tools: the six separate repos and the one they are merging into.
CHECK_TOOLS = [
    "kilotronic/checks",
    "kilotronic/lint",
    "kilotronic/git-identity",
    "kilotronic/secret-scan",
    "kilotronic/data-leak-check",
    "kilotronic/vendored-license-check",
    "kilotronic/red-on-logic",
]


def js_regex(pattern: str) -> re.Pattern[str]:
    """A Renovate `/.../` pattern as a Python regex (the patterns here use no flags)."""
    assert pattern.startswith("/") and pattern.endswith("/"), pattern
    return re.compile(pattern[1:-1])


def matches(rule: dict, name: str) -> bool:
    return any(js_regex(p).search(name) for p in rule.get("matchPackageNames", []))


def rule_with(preset: dict, **wanted) -> dict:
    found = [
        r
        for r in preset.get("packageRules", [])
        if all(r.get(k) == v for k, v in wanted.items())
    ]
    assert len(found) == 1, f"want one rule with {wanted}, found {len(found)}"
    return found[0]


def test_every_preset_says_what_it_is_for():
    for name in PRESETS:
        preset = load(name)
        assert preset["$schema"] == "https://docs.renovatebot.com/renovate-schema.json"
        assert preset["description"]
        for rule in preset.get("packageRules", []):
            assert rule.get("description"), rule


def test_actions_pinned_to_commits_with_version_comments():
    assert "helpers:pinGitHubActionDigests" in DEFAULT["extends"]


def test_pre_commit_manager_on():
    # Off by default in Renovate; it is the one that moves pre-commit `rev:` pins.
    assert DEFAULT["pre-commit"] == {"enabled": True}


def test_runs_on_a_weekly_schedule_but_security_fixes_at_any_time():
    assert DEFAULT["schedule"] == ["before 9am on monday"]
    assert DEFAULT["timezone"]
    assert DEFAULT["vulnerabilityAlerts"]["schedule"] == ["at any time"]


def test_waits_three_days_before_offering_a_release():
    assert DEFAULT["minimumReleaseAge"] == "3 days"
    assert DEFAULT["vulnerabilityAlerts"]["minimumReleaseAge"] is None


@pytest.mark.parametrize("name", CHECK_TOOLS)
def test_check_tools_grouped_in_one_update(name):
    group = rule_with(DEFAULT, groupName="kilotronic check tools")
    assert matches(group, name)
    # A reusable workflow's package is the repo; its dep name carries the path.
    assert matches(group, f"{name}/.github/workflows/ci.yml")


@pytest.mark.parametrize(
    "name",
    ["kilotronic/keys", "kilotronic/lint-extra", "someone/lint", "actions/checkout"],
)
def test_other_packages_stay_out_of_the_check_tools_group(name):
    assert not matches(rule_with(DEFAULT, groupName="kilotronic check tools"), name)


def test_check_tools_group_covers_every_manager_that_pins_them():
    group = rule_with(DEFAULT, groupName="kilotronic check tools")
    assert {"github-actions", "pre-commit"} <= set(group["matchManagers"])


def test_check_tools_group_wins_over_the_actions_group():
    # Later packageRules win in Renovate: a grouping rule below this one would split a
    # tool's Action pin and its pre-commit rev into two PRs, and they would skew.
    rules = DEFAULT["packageRules"]
    groups = [i for i, r in enumerate(rules) if "groupName" in r]
    tools = rules.index(rule_with(DEFAULT, groupName="kilotronic check tools"))
    assert groups[-1] == tools


@pytest.mark.parametrize("name", CHECK_TOOLS)
def test_check_tools_take_dotted_releases_only(name):
    # Each tool also keeps a moving major tag (v1); a bare major must never be offered.
    rule = next(
        r
        for r in DEFAULT["packageRules"]
        if "allowedVersions" in r and matches(r, name)
    )
    allowed = js_regex(rule["allowedVersions"])
    assert allowed.search("v1.3.2")
    assert not allowed.search("v1")
    assert not allowed.search("v1.3")


def test_python_minors_and_majors_held():
    rule = next(
        r for r in DEFAULT["packageRules"] if r.get("matchDepNames") == ["python"]
    )
    assert set(rule["matchUpdateTypes"]) == {"major", "minor"}
    assert rule["enabled"] is False


def test_default_never_automerges():
    text = json.dumps(DEFAULT)
    assert '"automerge"' not in text


def test_automerge_preset_merges_non_major_only_when_checks_pass():
    rule = rule_with(AUTOMERGE, automerge=True)
    assert set(rule["matchUpdateTypes"]) == {"minor", "patch", "pin", "digest"}
    assert AUTOMERGE["automergeStrategy"] == "squash"  # the only merge method allowed
    assert AUTOMERGE.get("ignoreTests") is not True
    # GitHub's own auto-merge waits for the required checks only, so a red check that
    # isn't required (git-identity in some repos) would not stop it. Renovate's merge
    # waits for every check to be green.
    assert AUTOMERGE["platformAutomerge"] is False


def test_own_validator_pin_is_kept_current():
    # This repo's renovate.json reads the npx pin in ci.yml; a reworded line would be
    # silently skipped and the validator would stop moving.
    own = load("renovate.json")
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    (manager,) = own["customManagers"]
    found = [
        m.groupdict()
        for pattern in manager["matchStrings"]
        for m in re.finditer(pattern.replace("(?<", "(?P<"), ci)
    ]
    assert [f["depName"] for f in found] == ["renovate"]


def test_copier_manager_off_until_templates_are_public_and_tagged():
    # The answers files name a private template by copier's gh: shorthand and pin a
    # commit id: every run would log a package lookup failure.
    assert DEFAULT["copier"]["enabled"] is False
    assert DEFAULT["copier"]["description"]
