import argparse
import json
import os
import subprocess
from pathlib import Path
from verify_release import require


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="esolovev")
    parser.add_argument("--namespace", default="mlops-students")
    parser.add_argument("--digest", required=True)
    args = parser.parse_args()
    report = {}
    for suffix in ("staging", "prod"):
        release = f"{args.prefix}-search-{suffix}"
        deployment = json.loads(subprocess.check_output([
            "kubectl", "-n", args.namespace, "get", "deployment", release + "-mlops-search", "-o", "json"
        ], text=True, timeout=20))
        image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
        require(image.endswith("@" + args.digest), "promotion Deployment digest mismatch")
        meta = json.loads(Path(f"evidence/{release}/normal/candidate/meta.json").read_text())
        require(meta["image_digest"] == args.digest and meta["ranking_mode"] == "normal", "promotion metadata mismatch")
        require(meta["environment"] == ("production" if suffix == "prod" else "staging"), "promotion environment mismatch")
        acceptance = json.loads(Path(f"evidence/{release}/normal/candidate/acceptance.json").read_text())
        require(acceptance["status"] == "passed", "promotion acceptance missing")
        if os.getenv("BUILD_REVISION"):
            require(meta["build_revision"] == os.environ["BUILD_REVISION"], "promotion build revision mismatch")
        if os.getenv("INDEX_VERSION"):
            require(meta["index_version"] == os.environ["INDEX_VERSION"], "promotion index mismatch")
        report[suffix] = {"image": image, "meta": meta}
    require(report["staging"]["image"] == report["prod"]["image"], "promotion images differ")
    for key in ("index_version", "artifact_sha256", "build_revision"):
        require(report["staging"]["meta"][key] == report["prod"]["meta"][key], "promotion identity differs: " + key)
    Path("evidence/promotion.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
