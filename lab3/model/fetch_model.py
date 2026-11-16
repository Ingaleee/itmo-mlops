"""Download pinned public Qwen GGUF/tokenizer and verify published fingerprints."""

import hashlib
import argparse
import os
from pathlib import Path
import urllib.request

URL = "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/a06e946bb6b655725eafa393f4a9745d460374c9/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
SHA256 = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    target = args.directory / "blobs" / ("sha256-" + SHA256)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and checksum(target) == SHA256:
        print("Existing model SHA-256 verified")
        return
    temporary = target.with_name(target.name + ".partial")
    downloaded = 0
    with (
        urllib.request.urlopen(URL, timeout=60) as response,
        temporary.open("wb") as file,
    ):
        for block in iter(lambda: response.read(4 * 1024 * 1024), b""):
            file.write(block)
            downloaded += len(block)
            # Dirty page cache is charged to the init container as well. Bound
            # it while downloading multi-GB weights under a cgroup memory limit.
            if downloaded % (32 * 1024 * 1024) == 0:
                file.flush()
                os.fsync(file.fileno())
                if hasattr(os, "posix_fadvise"):
                    os.posix_fadvise(file.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            if downloaded % (128 * 1024 * 1024) == 0:
                print(f"Downloaded {downloaded // 1024 // 1024} MiB", flush=True)
    if checksum(temporary) != SHA256:
        raise RuntimeError("Downloaded GGUF checksum differs from the assignment")
    temporary.replace(target)
    print(f"GGUF verified: {downloaded} bytes, sha256:{SHA256}", flush=True)


if __name__ == "__main__":
    main()
