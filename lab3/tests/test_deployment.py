from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from deploy import resources


def test_teaching_budget_is_below_actual_4G_quota():
    docs = resources(
        "registry/app@sha256:" + "a" * 64, "registry/ollama@sha256:" + "b" * 64
    )
    cpu = 0
    memory = 0
    for doc in docs:
        if doc["kind"] != "Deployment":
            continue
        pod = doc["spec"]["template"]["spec"]
        assert pod["automountServiceAccountToken"] is False
        assert doc["spec"]["strategy"]["type"] == "Recreate"
        for container in pod["containers"]:
            limits = container["resources"]["limits"]
            assert not any("gpu" in key for key in limits)
            cpu += int(limits["cpu"][:-1])
            memory += int(limits["memory"][:-2]) * 1024**2
            assert container["securityContext"]["readOnlyRootFilesystem"]
    assert cpu == 2200 and memory == 3758096384
    assert cpu <= 2600 and memory < 4_000_000_000
    assert all(
        d.get("spec", {}).get("type") not in {"NodePort", "LoadBalancer"} for d in docs
    )


def test_model_persists_and_mcp_is_independent():
    docs = resources("app", "ollama")
    llm = next(
        d
        for d in docs
        if d["kind"] == "Deployment" and d["metadata"]["name"] == "llm-local"
    )
    assert (
        llm["spec"]["template"]["spec"]["volumes"][0]["persistentVolumeClaim"][
            "claimName"
        ]
        == "knowledge-models"
    )
    mcp = next(
        d for d in docs if d["kind"] == "Service" and d["metadata"]["name"] == "kb-mcp"
    )
    assert mcp["spec"]["type"] == "ClusterIP"
    assert mcp["spec"]["ports"][0]["port"] == 8000
    assert not any(d["kind"] == "HTTPRoute" for d in docs)


def test_public_build_context_is_allowlist_without_corpus():
    root = Path(__file__).resolve().parents[1]
    ignore = (root / ".dockerignore").read_text()
    assert ignore.startswith("*\n") and "!app/**" in ignore
    assert "!artifacts" not in ignore and "!evidence" not in ignore
