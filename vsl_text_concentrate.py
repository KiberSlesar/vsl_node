class VSLTextConcentrate:
    """Join up to four optional text inputs with a configurable separator."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "separator": ("STRING", {"default": ",", "multiline": False}),
            },
            "optional": {
                "text_1": ("STRING", {"default": "", "multiline": True}),
                "text_2": ("STRING", {"default": "", "multiline": True}),
                "text_3": ("STRING", {"default": "", "multiline": True}),
                "text_4": ("STRING", {"default": "", "multiline": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "concentrate"
    CATEGORY = "VSL/Text"

    def concentrate(self, separator=",", text_1="", text_2="", text_3="", text_4=""):
        separator = "," if separator is None else str(separator)
        values = [text_1, text_2, text_3, text_4]
        result = separator.join(str(value) for value in values if value is not None and str(value) != "")
        return (result,)
