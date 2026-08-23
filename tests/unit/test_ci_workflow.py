from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_general_ci_uses_secured_dgx_jobs_and_complete_runtime_path() -> None:
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    fork_gate = (
        "github.event_name != 'pull_request' ||\n"
        "      github.event.pull_request.head.repo.full_name == github.repository"
    )
    assert workflow.count("runs-on: [self-hosted, dgx-spark]") == 2
    assert workflow.count(fork_gate) == 2
    assert "ubuntu-latest" not in workflow
    assert "git clean" not in workflow
    assert "git status --porcelain" in workflow
    assert "workflow_dispatch:" in workflow
    assert "PIP_NO_CACHE_DIR" in workflow
    assert "--only-binary=:all:" in workflow
    assert "-m ruff check ." in workflow
    assert "-m mypy src" in workflow
    assert "-m pytest" in workflow
    assert "-m build" in workflow
    assert "-m pip check" in workflow
    assert "examples/showcase/generate_showcase.py" in workflow
    assert "xvfb-run -a" in workflow
