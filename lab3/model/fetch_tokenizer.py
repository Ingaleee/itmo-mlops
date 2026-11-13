"""Fetch a pinned public tokenizer, with no Hugging Face account or SDK."""

import hashlib
from pathlib import Path
import urllib.request

URL = "https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/resolve/cdbee75f17c01a7cc42f958dc650907174af0554/tokenizer.json"
SHA256 = "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4"

if __name__ == "__main__":
    target = Path(__file__).with_name("qwen3-tokenizer.json")
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != SHA256:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise RuntimeError("Tokenizer checksum mismatch")
        target.write_bytes(data)
    print("Pinned tokenizer verified")
