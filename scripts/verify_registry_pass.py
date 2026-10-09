"""Check registry credential storage without emitting the credential."""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
import subprocess


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    root = Path(os.environ["COURSE_REGISTRY_AUTH_ROOT"]).resolve()
    require((root / ".itmo-registry-auth").is_file(), "Missing isolated store marker")
    config_path = Path(os.environ["DOCKER_CONFIG"]) / "config.json"
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    require(config.get("credsStore") == "pass", "Docker is not using pass")
    require(not config.get("credHelpers"), "Unexpected registry helper override")
    require(
        not any(value.get("auth") or value.get("identitytoken") for value in config.get("auths", {}).values()),
        "Docker config contains embedded registry credentials",
    )
    store = Path(os.environ["PASSWORD_STORE_DIR"])
    require((store / ".gpg-id").is_file(), "pass was not initialized")
    encrypted = list(store.rglob("*.gpg"))
    require(bool(encrypted), "No encrypted credential entry was created")

    # Capture helper output only in memory; never include it in logs or artifacts.
    result = subprocess.run(
        ["docker-credential-pass", "get"], input="ghcr.io\n", text=True,
        capture_output=True, timeout=15, check=False,
    )
    require(result.returncode == 0, "Credential helper could not decrypt its entry")
    credential = json.loads(result.stdout)
    require(credential.get("Username") == os.environ["GITHUB_ACTOR"], "Unexpected registry username")
    expected = os.environ["REGISTRY_TOKEN"]
    require(bool(expected), "Missing registry token")
    require(hmac.compare_digest(credential.get("Secret", ""), expected), "Credential roundtrip mismatch")
    require(expected.encode() not in config_bytes, "Token found in Docker config")
    require(all(expected.encode() not in path.read_bytes() for path in encrypted), "Token stored unencrypted")

    report = {
        "status": "passed", "registry": "ghcr.io", "credential_store": "pass",
        "pass_initialized": True, "docker_login": "succeeded", "credential_roundtrip": "passed",
        "embedded_auth": False, "encrypted_entries": len(encrypted),
        "execution_host": "GitHub-hosted Ubuntu 24.04 runner",
        "teaching_vm_checked": False,
    }
    evidence = Path("lab1/evidence/registry-credentials")
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
