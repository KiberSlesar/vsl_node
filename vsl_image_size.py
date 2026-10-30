import math


def _gcd(a, b):
    a = abs(int(a))
    b = abs(int(b))
    while b:
        a, b = b, a % b
    return a or 1


def _aspect_ratio(width, height):
    width = int(width)
    height = int(height)
    if width <= 0 or height <= 0:
        return "0:0"
    g = _gcd(width, height)
    return f"{width // g}:{height // g}"


def _megapixels(width, height):
    return (int(width) * int(height)) / 1_000_000


def _format_info(width, height):
    ratio = _aspect_ratio(width, height)
    mp = _megapixels(width, height)
    return f"{ratio}  |  {int(width)} x {int(height)}  |  {mp:.2f} MP"


class VSLImageSize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "measure"
    CATEGORY = "VSL/Image"
    OUTPUT_NODE = True

    def measure(self, image):
        if image is None:
            raise ValueError("image is required")
        shape = getattr(image, "shape", None)
        if shape is None or len(shape) < 3:
            raise ValueError("image must be a ComfyUI IMAGE tensor [B,H,W,C]")
        height = int(shape[1])
        width = int(shape[2])
        info = _format_info(width, height)
        return {
            "ui": {"text": [info]},
            "result": (width, height),
        }
