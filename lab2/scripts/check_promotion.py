import argparse
import json
import subprocess
from pathlib import Path


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
        ], text=True))
        image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
        assert image.endswith("@" + args.digest), image
        meta = json.loads(Path(f"evidence/{release}/normal/candidate/meta.json").read_text())
        assert meta["image_digest"] == args.digest and meta["ranking_mode"] == "normal", meta
        report[suffix] = {"image": image, "meta": meta}
    assert report["staging"]["image"] == report["prod"]["image"]
    assert report["staging"]["meta"]["index_version"] == report["prod"]["meta"]["index_version"]
    Path("evidence/promotion.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
