class AnyType(str):
    """Wildcard ComfyUI type that accepts and returns any connected value."""

    def __ne__(self, other):
        return False


ANY_TYPE = AnyType("*")


class VSLAnyReroute:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (ANY_TYPE, {"forceInput": True}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, **kwargs):
        return True

    RETURN_TYPES = (ANY_TYPE,)
    RETURN_NAMES = ("value",)
    FUNCTION = "route"
    CATEGORY = "VSL/Utils"

    def route(self, value):
        return (value,)
