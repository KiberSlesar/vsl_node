class VSLMinMaxSize:
    """Pick the larger or smaller of width/height. Single INT output."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": ("INT", {"default": 1024, "min": 1, "max": 16384, "step": 1}),
                "height": ("INT", {"default": 1024, "min": 1, "max": 16384, "step": 1}),
                "mode": (["max", "min"], {"default": "max"}),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "pick"
    CATEGORY = "VSL"
    OUTPUT_NODE = True

    def pick(self, width, height, mode):
        w = int(width)
        h = int(height)
        value = max(w, h) if mode == "max" else min(w, h)
        return {
            "ui": {"text": [f"{mode}({w}, {h}) = {value}"]},
            "result": (value,),
        }
