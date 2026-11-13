"""Count the exact pinned model vocabulary before sending any model request."""

import hashlib
import os
from pathlib import Path
from tokenizers import Tokenizer

TOKENIZER_SHA = "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4"  # gitleaks:allow (public model vocabulary SHA-256)


class Budget:
    def __init__(self, path=None):
        path = Path(
            path
            or os.getenv(
                "TOKENIZER_PATH",
                Path(__file__).resolve().parents[1] / "model/qwen3-tokenizer.json",
            )
        )
        if hashlib.sha256(path.read_bytes()).hexdigest() != TOKENIZER_SHA:
            raise RuntimeError("Tokenizer fingerprint mismatch")
        self.tokenizer = Tokenizer.from_file(str(path))

    def count(self, messages):
        # Mirrors model/Modelfile; the generous ceiling also reserves provider framing.
        text = ""
        for message in messages:
            text += (
                "<|im_start|>"
                + message["role"]
                + "\n"
                + message["content"]
                + "<|im_end|>\n"
            )
        text += "<|im_start|>assistant\n"
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def chunks(self, paragraph, size=150):
        # Split at word boundaries while measuring with the model tokenizer.
        current = []
        for word in paragraph.split():
            candidate = " ".join([*current, word])
            if (
                current
                and len(self.tokenizer.encode(candidate, add_special_tokens=False).ids)
                > size
            ):
                yield " ".join(current)
                current = []
            current.append(word)
        if current:
            yield " ".join(current)
