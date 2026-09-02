from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel

from .device import best_device


@dataclass
class DINOEmbedder:
    model_name: str = "facebook/dinov2-small"
    device: str | None = None

    def __post_init__(self) -> None:
        self.device = self.device or best_device()
        self.processor = AutoImageProcessor.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.eval().to(self.device)

    @torch.inference_mode()
    def embed_images(self, images: Iterable[Image.Image]) -> np.ndarray:
        images = [img.convert("RGB") for img in images]
        if not images:
            return np.empty((0, 384), dtype=np.float32)

        inputs = self.processor(images=images, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        outputs = self.model(**inputs)

        pooled = getattr(outputs, "pooler_output", None)
        if pooled is None:
            pooled = outputs.last_hidden_state[:, 0]

        emb = pooled.detach().float().cpu().numpy().astype(np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        emb = emb / np.clip(norms, 1e-12, None)
        return emb

    def embed_one(self, image: Image.Image) -> np.ndarray:
        return self.embed_images([image])[0]
