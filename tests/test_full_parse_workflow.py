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


def test_csv_commit_only_pushes_main():
    assert "${GITHUB_REF_NAME}" in WORKFLOW
    assert '!= "main"' in WORKFLOW
    assert "git push origin HEAD:main" in WORKFLOW
    assert re.search(r"^\s+git push\s*$", WORKFLOW, re.M) is None


def test_reuse_parse_artifact_skips_wsdc_http():
    assert "reuse_parse_artifact_run_id" in WORKFLOW
    assert "inputs.reuse_parse_artifact_run_id == ''" in WORKFLOW
    assert "Download parser CSVs from a previous run" in WORKFLOW
