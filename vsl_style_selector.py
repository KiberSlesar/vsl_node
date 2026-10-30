import json
import threading
from pathlib import Path

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / "clio_styles.json").read_text(encoding="utf-8"))
STYLE_BY_NAME = {x["name"]: x for x in DATA}
NAMES = [x["name"] for x in DATA]
CATEGORIES = sorted({x.get("section", "Other") for x in DATA})

_FAVORITES_PATH = Path(__file__).with_name("vsl_style_favorites.json")
_fav_lock = threading.Lock()


def _load_favorites():
    try:
        data = json.loads(_FAVORITES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    favorites = data.get("favorites") if isinstance(data, dict) else None
    return [str(name) for name in favorites] if isinstance(favorites, list) else []


def _toggle_favorite(name):
    with _fav_lock:
        favorites = _load_favorites()
        if name in favorites:
            favorites = [item for item in favorites if item != name]
        else:
            favorites.append(name)
        tmp = _FAVORITES_PATH.with_name(_FAVORITES_PATH.name + ".tmp")
        tmp.write_text(
            json.dumps({"favorites": favorites}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(_FAVORITES_PATH)
        return favorites

class VSLStyleSelector:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {
            "style": ([""] + NAMES, {"default": NAMES[0], "tooltip": "Empty = nothing selected: the node outputs an empty prompt. Click a thumbnail to select, click it again to deselect."}),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("style_prompt",)
    FUNCTION = "get_prompt"
    CATEGORY = "VSL/Prompt"
    DESCRIPTION = "Browse style previews by category and output the selected style prompt."

    def get_prompt(self, style="Anime Style"):
        prose = STYLE_BY_NAME.get(style or "", {}).get("prompt")
        if not prose:
            return ("",)
        return (f"Style: {style}: {prose}.",)

NODE_CLASS_MAPPINGS = {"vsl_Style_Selector": VSLStyleSelector}
NODE_DISPLAY_NAME_MAPPINGS = {"vsl_Style_Selector": "vsl_Style_Selector"}
