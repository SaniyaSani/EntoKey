from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from diptera_id.embedding import patch_size_hint, validate_image_size


ROOT = Path(__file__).resolve().parents[1]


def test_dinov3_patch_size_validation():
    assert patch_size_hint("facebook/dinov3-vits16-pretrain-lvd1689m") == 16
    assert patch_size_hint("facebook/dinov2-base") == 14
    validate_image_size("facebook/dinov3-vits16-pretrain-lvd1689m", 512)
    with pytest.raises(ValueError):
        validate_image_size("facebook/dinov3-vits16-pretrain-lvd1689m", 518)


def test_wholefly_profile_is_whole_image_only():
    profile = json.loads((ROOT / "configs/wholefly_foundation_v08.json").read_text(encoding="utf-8"))
    assert profile["embedding"]["model"].startswith("facebook/dinov3-")
    assert profile["embedding"]["include_whole"] is True
    assert profile["embedding"]["tile_grid"] == 1
    assert profile["embedding"]["strategy"] == "whole_image_only"
    assert profile["embedding"]["segmentation_required"] is False
    assert profile["embedding"]["specimen_crop_required"] is False
    assert profile["experiments"]["multi_crop_tiles"]["enabled"] is False
    assert profile["optional_modules"]["enable_only_after_error_analysis"] is True


def test_wholefly_colab_is_valid_and_uses_new_runner():
    notebook = json.loads((ROOT / "notebooks/WholeFly_Foundation_v08_Colab.ipynb").read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    text = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    assert "run_wholefly_v08.py" in text
    assert "source_status_v08.py" in text
    assert "dinov3-vits16" in text


def test_source_status_runs_on_example_config():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/source_status_v08.py"), "--config", str(ROOT / "configs/sources_wholefly_v08.example.json")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "iNaturalist" in completed.stdout
    assert "GBIF" in completed.stdout
    assert "DiSSCo" in completed.stdout


def test_default_crop_helper_returns_exactly_one_whole_image():
    from PIL import Image
    from scripts.embed_multiview import crops_for
    image = Image.new("RGB", (320, 180), "white")
    crops = crops_for(image, tile_grid=1, include_whole=True)
    assert len(crops) == 1
    assert crops[0].size == image.size
