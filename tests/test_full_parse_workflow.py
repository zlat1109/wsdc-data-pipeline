"""full-parse.yml must not re-hit WSDC or publish CSVs off main."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "full-parse.yml").read_text(encoding="utf-8")
CLOUD_PARSE = (ROOT / "scripts" / "cloud_parse.py").read_text(encoding="utf-8")


def _output_files() -> tuple[str, ...]:
    match = re.search(r"OUTPUT_FILES = (\([^)]+\))", CLOUD_PARSE, re.S)
    assert match, "OUTPUT_FILES missing in cloud_parse.py"
    return ast.literal_eval(match.group(1).replace("\n", " "))


def _artifact_csv_names() -> list[str]:
    match = re.search(
        r"name: parser-csvs\n\s+path: \|\n((?:[ \t]+data/.+\n)+)",
        WORKFLOW,
    )
    assert match, "parser-csvs upload block missing"
    names = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if line.startswith("data/"):
            names.append(line.removeprefix("data/"))
    return names


def test_parser_artifact_matches_cloud_parse_outputs():
    assert set(_artifact_csv_names()) == set(_output_files())


PUBLISHING_WORKFLOWS = (
    "full-parse.yml",
    "sync-events-list.yml",
    "force-rebuild-calendar-site.yml",
    "docs.yml",
)


def test_csv_commit_only_pushes_main():
    script = (ROOT / "scripts" / "commit_data_to_main.sh").read_text(encoding="utf-8")
    assert "commit_data_to_main.sh" in WORKFLOW
    assert "GITHUB_REF_NAME" in script
    assert '!= "main"' in script
    assert "git push origin HEAD:main" not in WORKFLOW
    assert re.search(r"^\s+git push\s*$", WORKFLOW, re.M) is None


def test_data_commit_reports_pytest_check_before_push():
    script = (ROOT / "scripts" / "commit_data_to_main.sh").read_text(encoding="utf-8")
    assert "gh pr create" not in script
    assert "-f name=pytest" in script
    check_at = script.index('gh api "repos/${REPO}/check-runs"')
    assert script.index("--ignore=tests/test_data_processors.py") < check_at
    assert check_at < script.index('git push origin "HEAD:main"')
    tests_yml = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    for flag in ("--ignore=tests/test_data_analytics.py", "--ignore=tests/test_data_processors.py"):
        assert flag in tests_yml


def test_publishing_workflows_can_write_check_runs():
    for name in PUBLISHING_WORKFLOWS:
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "commit_data_to_main.sh" in text, name
        assert re.search(r"^  checks: write$", text, re.M), name
        assert re.search(r"^\s+git push\s*$", text, re.M) is None, name


def test_reuse_parse_artifact_skips_wsdc_http():
    assert "reuse_parse_artifact_run_id" in WORKFLOW
    assert "inputs.reuse_parse_artifact_run_id == ''" in WORKFLOW
    assert "Download parser CSVs from a previous run" in WORKFLOW
