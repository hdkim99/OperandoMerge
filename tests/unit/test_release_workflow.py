from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_release_workflow_checks_clean_environment_dependencies() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    install_and_check = """\
      - run: /tmp/operandomerge-release/bin/pip install dist/*.whl
      - run: /tmp/operandomerge-release/bin/python -m pip check
"""
    assert install_and_check in workflow
