def _coerce_coefficient(value):
    """Parse the multiplier string (accepts '1.5' and '1,5'); must be finite."""
    text = str(value if value is not None else "").strip().replace(",", ".")
    if not text:
        raise ValueError("coefficient is required (for example 1.5)")
    try:
        coefficient = float(text)
    except ValueError:
        raise ValueError(f"coefficient must be a number, got {value!r}") from None
    if coefficient != coefficient or coefficient in (float("inf"), float("-inf")):
        raise ValueError(f"coefficient must be a finite number, got {value!r}")
    return coefficient


def _scaled(size, coefficient):
    """Multiply a size by the coefficient; normalized to a positive integer."""
    return max(1, int(abs(size * coefficient) + 0.5))


class VSLImageResize:
    """Scale the input image's width/height by a coefficient string."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "coefficient": ("STRING", {"default": "1.0", "multiline": False}),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "resize"
    CATEGORY = "VSL/Image"
    OUTPUT_NODE = True

    def resize(self, image, coefficient="1.0"):
        if image is None:
            raise ValueError("image is required")
        shape = getattr(image, "shape", None)
        if shape is None or len(shape) < 3:
            raise ValueError("image must be a ComfyUI IMAGE tensor [B,H,W,C]")
        height = int(shape[1])
        width = int(shape[2])
        coefficient = _coerce_coefficient(coefficient)
        new_width = _scaled(width, coefficient)
        new_height = _scaled(height, coefficient)
        info = f"x{coefficient:g}  |  {width} x {height} -> {new_width} x {new_height}"
        return {
            "ui": {"text": [info]},
            "result": (new_width, new_height),
        }
