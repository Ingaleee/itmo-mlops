"""Check a registry mirror against the original immutable release before deployment."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def verify(plan):
    if not re.fullmatch(r"[0-9a-f]{40}", plan["build_revision"]):
        raise ValueError("Invalid build revision")
    if not re.fullmatch(r"[0-9a-f]{12}", plan["index_version"]):
        raise ValueError("Invalid index version")
    values = {"BUILD_REVISION": plan["build_revision"], "INDEX_VERSION": plan["index_version"]}
    for name in ("iris", "search"):
        item = plan[name]
        if item["source_repository"] != f"ghcr.io/ingaleee/esolovev-{name}" or item["repository"] != f"docker.io/inga1e/esolovev-{name}":
            raise ValueError("Unexpected release repository")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"]):
            raise ValueError("Invalid immutable digest")
        # Compare bytes, preserving manifest indexes, SBOM and provenance entries.
        for repository in (item["source_repository"], item["repository"]):
            manifest = subprocess.check_output(
                ["docker", "buildx", "imagetools", "inspect", "--raw", repository + "@" + item["digest"]],
                timeout=60,
            )
            if "sha256:" + hashlib.sha256(manifest).hexdigest() != item["digest"]:
                raise ValueError("Registry manifest digest mismatch")
        values[name.upper() + "_IMAGE"] = item["repository"]
        values[name.upper() + "_DIGEST"] = item["digest"]
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("lab2/evidence/registry-mirror.json"))
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text(encoding="utf-8"))
    values = verify(plan)
    # Write deployment inputs only after BOTH mirrors have passed the check.
    with args.env_file.open("a", encoding="utf-8") as file:
        file.write("".join(key + "=" + value + "\n" for key, value in values.items()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"status": "passed", "release": plan, "manifests_identical": True}, indent=2) + "\n", encoding="utf-8")
    print("Both Docker Hub manifests match the original immutable release")


if __name__ == "__main__":
    main()
