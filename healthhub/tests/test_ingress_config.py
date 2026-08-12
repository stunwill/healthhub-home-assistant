from pathlib import Path


def test_ingress_port_matches_healthhub_runtime_port() -> None:
    root = Path(__file__).resolve().parents[1]
    config = (root / "config.yaml").read_text(encoding="utf-8")
    run_script = (root / "run.sh").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")

    assert "ingress: true" in config
    assert "ingress_port: 8098" in config
    assert "--port 8098" in run_script
    assert "127.0.0.1:8098/api/v1/health" in dockerfile
