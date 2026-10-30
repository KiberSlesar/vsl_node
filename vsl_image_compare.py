"""VSL Image Compare: A/B slider preview on the node, image_a passes through."""
from __future__ import annotations

import random
import string
from pathlib import Path

from PIL import Image

try:
    import folder_paths
except ImportError:  # offline tests import without ComfyUI
    folder_paths = None


def _temp_prefix() -> str:
    """Unique temp prefix per node instance so parallel compares don't clash."""
    return "vsl_compare_" + "".join(random.choices(string.ascii_lowercase, k=5))


def _first_frame_to_pil(image) -> Image.Image:
    """First frame of a BHWC float batch as a PIL image."""
    import torch
    if not isinstance(image, torch.Tensor) or image.ndim != 4:
        raise ValueError("Compare expected a BHWC IMAGE batch.")
    if int(image.shape[0]) < 1:
        raise ValueError("Compare received an empty IMAGE batch.")
    frame = image[0].detach().cpu().float().clamp(0.0, 1.0).mul(255.0).round().to(torch.uint8)
    array = frame.numpy()
    if array.shape[-1] == 1:
        array = array[..., 0]
    elif array.shape[-1] > 3:
        array = array[..., :3]
    return Image.fromarray(array)


def _save_temp_preview(image, prefix: str) -> dict:
    """Write one preview PNG to the temp folder; returns its ui.images entry."""
    if folder_paths is None:
        raise RuntimeError("Compare requires ComfyUI's folder_paths at runtime.")
    preview = _first_frame_to_pil(image)
    full_output_folder, filename, counter, subfolder, _prefix = folder_paths.get_save_image_path(
        prefix, folder_paths.get_temp_directory(), preview.width, preview.height
    )
    file = f"{filename}_{counter:05}_.png"
    preview.save(Path(full_output_folder) / file, compress_level=4)
    return {
        "filename": file,
        "subfolder": subfolder,
        "type": "temp",
        "width": preview.width,
        "height": preview.height,
    }


class VSLImageCompare:
    CATEGORY = "VSL/Image"
    DESCRIPTION = (
        "Shows A and B on one gray panel: slide across to reveal B up to the "
        "pointer, or use the A/B buttons to flip the whole panel. "
        "image_a passes through unchanged so the node can sit mid-graph."
    )

    def __init__(self):
        self._prefix = _temp_prefix()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_a": ("IMAGE", {"tooltip": "Baseline batch; its first frame is preview A."}),
                "image_b": ("IMAGE", {"tooltip": "Comparison batch; its first frame is preview B."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image_a",)
    OUTPUT_NODE = True
    FUNCTION = "compare"

    def compare(self, image_a, image_b):
        try:
            ui = {
                "a_images": [_save_temp_preview(image_a, self._prefix)],
                "b_images": [_save_temp_preview(image_b, self._prefix)],
            }
        except Exception as exc:  # preview failure must not kill the run
            detail = str(exc).encode("ascii", "replace").decode("ascii")
            print(f"[vsl_compare] preview unavailable ({detail}).")
            return {"result": (image_a,)}
        return {"ui": ui, "result": (image_a,)}
