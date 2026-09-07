#!/usr/bin/env python3
"""Pre-cache the selected DINO backbone and print its basic configuration."""
from __future__ import annotations

import argparse
from transformers import AutoImageProcessor, AutoModel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="facebook/dinov3-vits16-pretrain-lvd1689m")
    args = parser.parse_args()
    try:
        print(f"Caching processor: {args.model}")
        AutoImageProcessor.from_pretrained(args.model)
        print(f"Caching model: {args.model}")
        model = AutoModel.from_pretrained(args.model)
    except Exception as exc:
        if "dinov3" in args.model.lower():
            raise SystemExit(
                "Could not access DINOv3. The official checkpoint is gated on Hugging Face: "
                "accept the model terms in your HF account, run `huggingface-cli login`, and retry.\n"
                f"Original error: {exc}"
            )
        raise
    params = sum(parameter.numel() for parameter in model.parameters())
    print({
        "model": args.model,
        "parameters": params,
        "hidden_size": getattr(model.config, "hidden_size", None),
        "patch_size": getattr(model.config, "patch_size", None),
    })


if __name__ == "__main__":
    main()
