"""Publish only the lab services on the assigned personal Gateway listener."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("staging", "production"))
    args = parser.parse_args()
    namespace = os.environ["KUBE_NAMESPACE"]
    if namespace != "itmo-student-01":
        raise RuntimeError("Gateway profile is bound to itmo-student-01")
    services = (("iris", "esolovev-iris"), ("search-staging", "esolovev-search-staging-mlops-search"))
    if args.target == "production":
        services = (("search", "esolovev-search-prod-mlops-search"),)
    output = Path("lab2/evidence/gateway")
    output.mkdir(parents=True, exist_ok=True)
    for host_prefix, service in services:
        name = "esolovev-" + host_prefix
        hostname = host_prefix + ".itmo-student-01.37.18.117.114.sslip.io"
        route = {"apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute",
                 "metadata": {"name": name, "namespace": namespace,
                              "labels": {"app.kubernetes.io/managed-by": "itmo-mlops"}},
                 "spec": {"parentRefs": [{"name": "itmo-shared", "namespace": "envoy-gateway-system",
                                          "sectionName": "http-student-01"}], "hostnames": [hostname],
                          "rules": [{"matches": [{"path": {"type": "PathPrefix", "value": "/"}}],
                                     "backendRefs": [{"name": service, "port": 80}]}]}}
        command = ["kubectl", "--request-timeout=15s", "-n", namespace]
        body = json.dumps(route)
        subprocess.run(command + ["apply", "--dry-run=server", "-f", "-"], input=body, text=True, check=True)
        subprocess.run(command + ["apply", "-f", "-"], input=body, text=True, check=True)
        for _ in range(30):
            actual = json.loads(subprocess.check_output(command + ["get", "httproute", name, "-o", "json"], text=True))
            parents = [parent for parent in actual.get("status", {}).get("parents", [])
                       if parent["parentRef"].get("name") == "itmo-shared"
                       and parent["parentRef"].get("sectionName") == "http-student-01"]
            generation = actual["metadata"]["generation"]
            if any(all(any(condition["type"] == kind and condition["status"] == "True"
                               and condition.get("observedGeneration") == generation
                               for condition in parent.get("conditions", []))
                           for kind in ("Accepted", "ResolvedRefs")) for parent in parents):
                break
            time.sleep(2)
        else:
            raise RuntimeError("Gateway did not accept route " + name)
        (output / (name + ".json")).write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8")
        print("Gateway accepted http://" + hostname)


if __name__ == "__main__":
    main()
