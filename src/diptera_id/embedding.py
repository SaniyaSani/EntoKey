from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import torch
from PIL import Image, ImageOps
from transformers import AutoImageProcessor, AutoModel

from .device import best_device


@dataclass
class DINOEmbedder:
    model_name: str = "facebook/dinov2-small"
    device: str | None = None
    image_size: int = 224

    def __post_init__(self) -> None:
        self.device = self.device or best_device()
        self.processor = AutoImageProcessor.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.eval().to(self.device)

    @torch.inference_mode()
    def embed_images(self, images: Iterable[Image.Image]) -> np.ndarray:
        images = [img.convert("RGB") for img in images]
        if not images:
            dimension = int(getattr(self.model.config, "hidden_size", 384))
            return np.empty((0, dimension), dtype=np.float32)

        processor_args = {"images": images, "return_tensors": "pt"}
        if self.image_size != 224:
            images = [
                ImageOps.pad(image, (self.image_size, self.image_size), method=Image.Resampling.LANCZOS, color=(127, 127, 127))
                for image in images
            ]
            processor_args.update({"images": images, "do_resize": False, "do_center_crop": False})
        inputs = self.processor(**processor_args)
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

    def embed_multicrop(self, image: Image.Image, tile_grid: int = 2, include_whole: bool = True) -> np.ndarray:
        """Fuse a whole-image view with non-overlapping high-detail tiles."""
        image = image.convert("RGB")
        crops: list[Image.Image] = [image] if include_whole else []
        if tile_grid > 1:
            width, height = image.size
            for row in range(tile_grid):
                for column in range(tile_grid):
                    left = round(column * width / tile_grid)
                    right = round((column + 1) * width / tile_grid)
                    top = round(row * height / tile_grid)
                    bottom = round((row + 1) * height / tile_grid)
                    crops.append(image.crop((left, top, right, bottom)))
        if not crops:
            crops = [image]
        vectors = self.embed_images(crops)
        fused = vectors.mean(axis=0)
        return (fused / max(float(np.linalg.norm(fused)), 1e-12)).astype(np.float32)
