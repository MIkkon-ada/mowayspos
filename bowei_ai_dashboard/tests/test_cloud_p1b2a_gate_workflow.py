from pathlib import Path


def test_production_runtime_gate_installs_poppler_before_backend_pytest():
    workflow = (
        Path(__file__).resolve().parents[2]
        / ".github/workflows/cloud-p1b2a-gate.yml"
    ).read_text(encoding="utf-8")

    install_index = workflow.index("sudo apt-get install -y poppler-utils")
    pytest_index = workflow.index("python -m pytest tests -q")

    assert install_index < pytest_index
