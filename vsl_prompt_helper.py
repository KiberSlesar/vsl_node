import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
import hashlib
import threading
from pathlib import Path


_PROMPTS_PATH = Path(__file__).with_name("vsl_prompts.json")
with _PROMPTS_PATH.open("r", encoding="utf-8") as _handle:
    _VSL_PROMPTS = json.load(_handle)

_TAGS_PATH = Path(__file__).with_name("anima_basic_tags.json")
with _TAGS_PATH.open("r", encoding="utf-8") as _handle:
    _ANIMA_BASIC_TAGS = json.load(_handle)

def _tag_dictionary(underscore=False):
    groups = _ANIMA_BASIC_TAGS.get("groups") or {}
    lines = []
    for name, tags in groups.items():
        if not tags:
            continue
        if underscore:
            tags = [tag if str(tag).startswith("score_") else str(tag).replace(" ", "_") for tag in tags]
        lines.append(f"{name}: " + ", ".join(tags))
    return "\n".join(lines)

KREA_2_REALISM_SYSTEM_PROMPT = _VSL_PROMPTS["KREA_2_REALISM_SYSTEM_PROMPT"]
KREA_2_ANIME_SYSTEM_PROMPT = _VSL_PROMPTS["KREA_2_ANIME_SYSTEM_PROMPT"]
KREA_2_NEUTRAL_SYSTEM_PROMPT = _VSL_PROMPTS["KREA_2_NEUTRAL_SYSTEM_PROMPT"]
ANIMA_SYSTEM_PROMPT = _VSL_PROMPTS["ANIMA_SYSTEM_PROMPT"] + _tag_dictionary(underscore=False)
ILLUSTRIOUS_SYSTEM_PROMPT = _VSL_PROMPTS["ILLUSTRIOUS_SYSTEM_PROMPT"] + _tag_dictionary(underscore=True)
FACE_EMOTION_SYSTEM_PROMPT = _VSL_PROMPTS["FACE_EMOTION_SYSTEM_PROMPT"]
TRANSLATE_ONLY_SYSTEM_PROMPT = _VSL_PROMPTS["TRANSLATE_ONLY_SYSTEM_PROMPT"]
QWEN_T2I_SYSTEM_PROMPT = _VSL_PROMPTS["QWEN_T2I_SYSTEM_PROMPT"]
QWEN_IMAGE_EDIT_SYSTEM_PROMPT = _VSL_PROMPTS["QWEN_IMAGE_EDIT_SYSTEM_PROMPT"]
MOSS_CAPTION_SYSTEM_PROMPT = _VSL_PROMPTS["MOSS_CAPTION_SYSTEM_PROMPT"]
MOSS_LAYOUT_SYSTEM_PROMPT = _VSL_PROMPTS["MOSS_LAYOUT_SYSTEM_PROMPT"]

def _illustrious_tag_set():
    tags = set()
    for values in (_ANIMA_BASIC_TAGS.get("groups") or {}).values():
        for tag in values or []:
            raw = str(tag).strip()
            if not raw:
                continue
            tags.add(raw)
            tags.add(raw.replace(" ", "_"))
            tags.add(raw.replace("_", " "))
    return tags

_ILLUSTRIOUS_TAG_SET = _illustrious_tag_set()

_PROMPT_VER = "sys-instructions-v15"
_QWEN_EDIT_LANGUAGE_LOCK = (
    "LANGUAGE LOCK — this block overrides later examples if they conflict.\n"
    "Decision (A): rewritten_prompt descriptive prose (outside double quotes) MUST always be English, "
    "regardless of the language of the user instruction. Never write Chinese or any other non-English "
    "descriptive prose.\n"
    "Decision (B) for quoted in-image text is unchanged.\n"
)
_TARGET_MODELS = (
    "Krea 2",
    "Anima",
    "Illustrious",
    "Qwen 2.1 text2img",
    "Qwen 2.1 Image Edit",
    "MOSS Image",
    "MOSS Image Layout",
)
_QWEN_MODELS = ("Qwen 2.1 text2img", "Qwen 2.1 Image Edit")
_MOSS_LAYOUT_MODEL = "MOSS Image Layout"
_MOSS_MODELS = ("MOSS Image", _MOSS_LAYOUT_MODEL)
_DEFAULT_QUALITY_PROMPT = "detailed face, detailed hair, detailed hands, detailed legs, detailed body"
_DEFAULT_NEGATIVE_PROMPT = "worst quality, low quality, low score, bad score, lowres, blurry, jpeg artifacts, bad anatomy, bad proportions, deformed, mutated, extra limbs, extra fingers, missing fingers, bad hands, poorly drawn face, ugly, watermark, signature, text, logo, censored"
_PREAMBLE_RE = re.compile(
    r"^\s*(?:here(?:'s| is) the (?:expanded )?prompt\s*:\s*|expanded prompt\s*:\s*|final prompt\s*:\s*)",
    re.IGNORECASE,
)
_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.DOTALL | re.IGNORECASE)
_SAFETY_MAX_TOKENS = 4096
_REASONING_BUDGETS = {
    "off": 0,
    "256": 256,
    "512": 512,
    "1K": 1024,
    "2K": 2048,
    "unlimited": -1,
}

_PRESETS_PATH = Path(__file__).with_name("vsl_router_presets.json")
_presets_lock = threading.Lock()


def _load_presets():
    try:
        with _PRESETS_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    presets = data.get("presets") if isinstance(data, dict) else None
    if not isinstance(presets, dict):
        return {}
    return {
        str(name): record
        for name, record in presets.items()
        if isinstance(record, dict)
    }


def _write_presets(presets):
    tmp = _PRESETS_PATH.with_name(_PRESETS_PATH.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump({"presets": presets}, handle, ensure_ascii=False, indent=2)
    tmp.replace(_PRESETS_PATH)


def _save_preset(name, record):
    with _presets_lock:
        presets = _load_presets()
        presets[name] = record
        _write_presets(presets)


def _delete_preset(name):
    with _presets_lock:
        presets = _load_presets()
        if name in presets:
            del presets[name]
            _write_presets(presets)


def _api_root(base_url):
    """Normalise a gateway base URL to the API root.

    Accepts http://host:8080, http://host:8080/v1, https://openrouter.ai and
    https://openrouter.ai/api; chat calls go to <root>/v1/chat/completions.
    """
    raw = str(base_url or "").strip()
    if not raw:
        raise ValueError("router_url is empty")
    if "://" not in raw:
        raw = "http://" + raw
    parts = urllib.parse.urlsplit(raw)
    path = parts.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    if (parts.hostname or "").lower() == "openrouter.ai" and not path:
        path = "/api"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")


def _api_headers(api_key=None, json_body=False):
    headers = {"Accept": "application/json"}
    if json_body:
        headers["Content-Type"] = "application/json"
    key = str(api_key or "").strip()
    if key:
        headers["Authorization"] = "Bearer " + key
    return headers


def _clean_proxy(value):
    raw = str(value or "").strip()
    return "" if raw.lower() in ("none", "null", "-") else raw


def _opener(proxy=""):
    """Return an urlopen-compatible callable honouring an optional proxy.

    socks5://host:port (or socks5h://) uses SOCKS5 via PySocks; http://host:port
    uses an HTTP proxy; a bare host:port is treated as SOCKS5. Empty = direct.
    """
    raw = _clean_proxy(proxy)
    if not raw:
        return urllib.request.urlopen
    parts = urllib.parse.urlsplit(raw if "://" in raw else "socks5://" + raw)
    scheme = (parts.scheme or "").lower()
    if scheme in ("socks5", "socks5h"):
        return _socks_opener(parts, rdns=(scheme == "socks5h"))
    if scheme in ("http", "https"):
        handler = urllib.request.ProxyHandler({"http": raw, "https": raw})
        return urllib.request.build_opener(handler).open
    raise ValueError(f"Unsupported proxy scheme: {parts.scheme!r} (use socks5:// or http://)")


def _socks_opener(parts, rdns=True):
    try:
        import socks
    except ImportError as exc:
        raise RuntimeError("SOCKS5 proxy support needs the PySocks package (pip install pysocks)") from exc
    proxy_host, proxy_port = parts.hostname, parts.port or 1080
    username = urllib.parse.unquote(parts.username) if parts.username else None
    password = urllib.parse.unquote(parts.password) if parts.password else None

    def _connect(host, port, timeout):
        sock = socks.socksocket()
        sock.set_proxy(
            socks.SOCKS5, proxy_host, proxy_port, rdns=rdns,
            username=username, password=password,
        )
        sock.settimeout(timeout)
        sock.connect((host, port))
        return sock

    import http.client

    class SocksHTTPConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = _connect(self.host, self.port or 80, self.timeout)

    class SocksHTTPSConnection(http.client.HTTPSConnection):
        def connect(self):
            raw_sock = _connect(self.host, self.port or 443, self.timeout)
            self.sock = self._context.wrap_socket(raw_sock, server_hostname=self.host)

    class SocksHTTPHandler(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(SocksHTTPConnection, req)

    class SocksHTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(SocksHTTPSConnection, req)

    return urllib.request.build_opener(SocksHTTPHandler, SocksHTTPSHandler).open


def _normalize_krea_style(krea_style):
    value = str(krea_style or "").strip().lower()
    if value in ("anime", "аниме"):
        return "anime"
    if value in ("none", "no style", "без стиля", "без_стиля", "neutral", "нейтральный"):
        return "none"
    return "realism"


def _normalize_target_model(target_model):
    value = str(target_model or "").strip()
    aliases = {
        "translate only": "Krea 2",  # legacy workflows default to Enhance
        "translate": "Krea 2",
        "krea 2": "Krea 2",
        "krea": "Krea 2",
        "anima": "Anima",
        "illustrious": "Illustrious",
        "illustrous": "Illustrious",
        "noobai": "Illustrious",
        "qwen 2.1 text2img": "Qwen 2.1 text2img",
        "qwen text2img": "Qwen 2.1 text2img",
        "qwen t2i": "Qwen 2.1 text2img",
        "qwen 2.1 image edit": "Qwen 2.1 Image Edit",
        "qwen image edit": "Qwen 2.1 Image Edit",
        "qwen edit": "Qwen 2.1 Image Edit",
        "moss image": "MOSS Image",
        "moss": "MOSS Image",
        "moss image caption": "MOSS Image",
        "moss caption": "MOSS Image",
        "moss image layout": "MOSS Image Layout",
        "moss layout": "MOSS Image Layout",
        "moss image bbox": "MOSS Image Layout",
    }
    return aliases.get(value.lower(), value)


def _system_prompt(target_model, krea_style, user_text=""):
    target = _normalize_target_model(target_model)
    if target == "Translate Only":
        return TRANSLATE_ONLY_SYSTEM_PROMPT
    if target == "Qwen 2.1 text2img":
        return QWEN_T2I_SYSTEM_PROMPT
    if target == "Qwen 2.1 Image Edit":
        return _QWEN_EDIT_LANGUAGE_LOCK + "\n" + QWEN_IMAGE_EDIT_SYSTEM_PROMPT
    if target == "MOSS Image":
        return MOSS_CAPTION_SYSTEM_PROMPT
    if target == "MOSS Image Layout":
        return MOSS_LAYOUT_SYSTEM_PROMPT
    if target == "Anima":
        return ANIMA_SYSTEM_PROMPT
    if target == "Illustrious":
        return ILLUSTRIOUS_SYSTEM_PROMPT
    style = _normalize_krea_style(krea_style)
    if style == "anime":
        return KREA_2_ANIME_SYSTEM_PROMPT
    if style == "none":
        return KREA_2_NEUTRAL_SYSTEM_PROMPT
    return KREA_2_REALISM_SYSTEM_PROMPT


def _moss_box_place(box, width, height):
    """Describe where a box sits in words, so caption mode never prints numbers."""
    y0, x0, y1, x1 = box["bbox"]
    if box["absolute"]:
        pass
    elif width and height:
        y0, x0, y1, x1 = [value * (height if i % 2 == 0 else width) / 1000.0 for i, value in enumerate(box["bbox"])]
    else:
        return ""
    if not (width and height):
        return ""
    cx = (x0 + x1) / 2.0 / width
    cy = (y0 + y1) / 2.0 / height
    area = max(0.0, (x1 - x0)) * max(0.0, (y1 - y0)) / float(width * height)
    horizontal = "left" if cx < 0.34 else ("right" if cx > 0.66 else "centre")
    vertical = "top" if cy < 0.34 else ("bottom" if cy > 0.66 else "middle")
    if horizontal == "centre" and vertical == "middle":
        place = "the centre"
    elif horizontal == "centre":
        place = f"the {vertical} centre"
    elif vertical == "middle":
        place = f"the {horizontal} half"
    else:
        place = f"the {vertical} {horizontal}"
    if area >= 0.45:
        size = "most of the canvas"
    elif area >= 0.2:
        size = "a large part of the canvas"
    elif area >= 0.06:
        size = "a moderate part of the canvas"
    else:
        size = "a small part of the canvas"
    return f"{place}, {size}"


def _moss_adapt_editor_elements(elements):
    """Accept the web editor's raw shape: {x, y, width, height, metadata:{...}}.

    The frontend widget can hand the node its editor state instead of the
    compiled element array, so translate it into the same dict shape that
    _moss_parse_elements already understands.
    """
    if not isinstance(elements, (list, tuple)):
        return elements
    adapted = []
    for element in elements:
        if not isinstance(element, dict) or "bbox" in element:
            adapted.append(element)
            continue
        if not all(key in element for key in ("x", "y", "width", "height")):
            adapted.append(element)
            continue
        meta = element.get("metadata") or {}
        adapted.append(
            {
                "type": meta.get("type") or "obj",
                "bbox": [
                    element["y"],
                    element["x"],
                    element["y"] + element["height"],
                    element["x"] + element["width"],
                ],
                "coord_space": "abs",
                "desc": meta.get("desc") or "",
                "text": meta.get("text") or "",
                "palette": meta.get("palette") or [],
            }
        )
    return adapted


def _moss_parse_elements(elements):
    """Read the element array coming from Create Bounding Boxes.

    Each element looks like {"type": "object"|"text", "bbox": [y0,x0,y1,x1],
    "desc": "...", "text": "...", "color_palette": [...]} with the box in the
    editor's 0-1000 scale. Returns a list of normalised dicts, or None when the
    socket is not wired or carries nothing usable.
    """
    if elements is None:
        return None
    if isinstance(elements, str):
        raw = elements.strip()
        if not raw:
            return None
        parsed = VSLPromptHelper._extract_json_object(raw)
        if parsed is None:
            return None
        elements = parsed
    if isinstance(elements, dict):
        elements = elements.get("elements") or elements.get("element") or [elements]
    if not isinstance(elements, (list, tuple)) or not elements:
        return None

    boxes = []
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        box = element.get("bbox")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        try:
            box = [float(value) for value in box]
        except (TypeError, ValueError):
            continue
        # The editor emits an absolute pixel box when it has a canvas, and the
        # 0-1000 scale otherwise. Detect the scale so both wirings work.
        is_absolute = any(value > 1000.0 for value in box) or element.get("coord_space") == "abs"
        kind = str(element.get("type") or "").strip().lower()
        kind = "text" if kind == "text" else "object"
        boxes.append(
            {
                "index": index,
                "type": kind,
                "bbox": box,
                "absolute": is_absolute,
                "desc": str(element.get("desc") or element.get("description") or "").strip(),
                "text": str(element.get("text") or ""),
                "palette": element.get("color_palette") or element.get("palette"),
            }
        )
    return boxes or None


def _moss_centered_box(box, width, height, absolute, location):
    """Convert an editor box into MOSS-centered yxyx integers.

    Mirrors the core MOSS-Image layout conversion: floor the low edges, ceil the
    high edges, then subtract the canvas center. Out-of-range boxes are rejected
    instead of being silently clipped.
    """
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise RuntimeError(f"MOSS element {location}: bbox must be [y0,x0,y1,x1]")
    numbers = [float(value) for value in box]
    if any(value != value or value in (float("inf"), float("-inf")) for value in numbers):
        raise RuntimeError(f"MOSS element {location}: bbox must contain finite numbers")
    if absolute:
        y0, x0, y1, x1 = numbers
    else:
        y0, x0, y1, x1 = [value * (height if i % 2 == 0 else width) / 1000.0 for i, value in enumerate(numbers)]
    if not (y0 < y1 and x0 < x1):
        raise RuntimeError(f"MOSS element {location}: bbox must have positive width and height")
    if y0 < 0 or x0 < 0 or y1 > height or x1 > width:
        raise RuntimeError(
            f"MOSS element {location}: bbox {[round(v, 1) for v in numbers]} "
            f"falls outside the {width}x{height} canvas"
        )
    return [
        math.floor(round(y0, 9)) - height // 2,
        math.floor(round(x0, 9)) - width // 2,
        math.ceil(round(y1, 9)) - height // 2,
        math.ceil(round(x1, 9)) - width // 2,
    ]


def _moss_elements_request(boxes, canvas_size=None, scene_request=""):
    """Build the user message asking the LLM to rewrite every box description."""
    width, height = canvas_size if canvas_size else (0, 0)
    lines = [
        "Rewrite the description of every box below. Keep boxes, types and copy exactly as given.",
        "Return JSON: {\"summary\": {\"caption\": \"...\"}, \"items\": [{\"desc\": \"...\"}, ...]} "
        "with one item per box, in the same order.",
        "",
    ]
    if str(scene_request or "").strip():
        lines.append(f"Scene the user asked for: {str(scene_request).strip()}")
    if canvas_size:
        lines.append(f"Canvas: {width}x{height} pixels, origin top-left.")
    lines.append(f"Boxes ({len(boxes)}), in composition order:")
    for position, box in enumerate(boxes, start=1):
        y0, x0, y1, x1 = box["bbox"]
        if box["absolute"]:
            where = f"pixels x {round(x0)}-{round(x1)}, y {round(y0)}-{round(y1)}"
        else:
            where = f"0-1000 scale x {round(x0)}-{round(x1)}, y {round(y0)}-{round(y1)}"
        parts = [f"{position}. type={box['type']}", where]
        if box["type"] == "text":
            parts.append("words already fixed in the layout, do not repeat them")
        parts.append(f"current description: {box['desc'] or '(empty)'}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _moss_unwrap_rewrites(raw_text, boxes):
    """Pull the rewritten descriptions out of the LLM output, in box order."""
    draft = VSLPromptHelper._extract_json_object(raw_text)
    if isinstance(draft, dict) and "items" not in draft:
        for value in draft.values():
            if isinstance(value, dict) and isinstance(value.get("items"), list):
                draft = value
                break
    if not isinstance(draft, dict):
        raise RuntimeError("MOSS layout: model did not return valid JSON")

    summary = draft.get("summary")
    if isinstance(summary, str):
        summary = {"caption": summary}
    caption = str((summary or {}).get("caption") or "").strip() if isinstance(summary, dict) else ""

    items = draft.get("items")
    if not isinstance(items, list):
        raise RuntimeError("MOSS layout: model returned no items array")

    rewrites = []
    for item in items:
        if isinstance(item, str):
            rewrites.append(item.strip())
        elif isinstance(item, dict):
            rewrites.append(
                str(
                    item.get("desc")
                    or item.get("caption")
                    or item.get("description")
                    or ""
                ).strip()
            )
        else:
            rewrites.append("")
    # Trust only the boxes the user drew: extra items are ignored, missing ones
    # keep the user's original description.
    rewrites = rewrites[: len(boxes)]
    while len(rewrites) < len(boxes):
        rewrites.append("")
    return caption, rewrites


def _moss_compose_layout(boxes, caption, rewrites, width, height, character_boxes=""):
    """Assemble the final MOSS layout from the user's boxes and new descriptions."""
    characters = {int(value) for value in re.findall(r"\d+", str(character_boxes or ""))}
    items = []
    phrases = []
    for position, box in enumerate(boxes):
        label = box["type"]
        if label != "text" and position + 1 in characters:
            label = "character"
        item_caption = rewrites[position] or box["desc"]
        if not item_caption:
            item_caption = box["text"].strip() or ("Text element." if box["type"] == "text" else "Object element.")
        compiled = {"label": label, "caption": item_caption}
        if box["type"] == "text":
            compiled["text"] = box["text"]
        palette = box["palette"]
        if isinstance(palette, list):
            palette = [str(value).strip() for value in palette if str(value).strip()]
            if palette:
                compiled["palette"] = palette
        compiled["bbox"] = _moss_centered_box(box["bbox"], width, height, box["absolute"], f"#{position + 1}")
        items.append(compiled)
        phrases.append(item_caption)

    summary_caption = caption.strip() or " ".join(phrases).strip()
    layout = {
        "summary": {"caption": summary_caption},
        "items": items,
        "bbox_coord_space": "abs_centralized",
        "bbox_format": "yxyx",
    }
    return json.dumps(layout, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class VSLPromptHelper:
    _cache = {}
    _cache_lock = threading.Lock()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "user_request": ("STRING", {"multiline": True, "default": ""}),
                "mode": (["Enhance", "Translate Only", "Skip"], {"default": "Enhance"}),
                "target_model": ([
                    "Krea 2",
                    "Anima",
                    "Illustrious",
                    "Qwen 2.1 text2img",
                    "Qwen 2.1 Image Edit",
                    "MOSS Image",
                    "MOSS Image Layout",
                ], {"default": "Krea 2"}),
                "krea_style": (["реализм", "аниме", "без стиля"], {"default": "реализм"}),
                "preset": (["(none)"] + sorted(_load_presets().keys()), {"default": "(none)", "tooltip": "Connection preset (router_url/api_key/model/proxy). Selected preset overrides the connection fields where it has values. Save/Delete via the buttons under the widgets."}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_output_tokens": (["512", "1K", "2K", "4K"], {"default": "1K"}),
                "reasoning_budget": (["off", "256", "512", "1K", "2K", "unlimited"], {"default": "off"}),
                "cache_mode": (["cache", "no_cache"], {"default": "cache"}),
                "enable_face_emotion": ("BOOLEAN", {"default": False, "advanced": True}),
                "enable_extra_prompt": ("BOOLEAN", {"default": False, "advanced": True}),
                "enable_quality_prompt": ("BOOLEAN", {"default": False, "advanced": True}),
                "extra_prompt": ("STRING", {"multiline": True, "default": "", "advanced": True}),
                "quality_prompt": ("STRING", {"multiline": True, "default": _DEFAULT_QUALITY_PROMPT, "advanced": True}),
                "negative_prompt": ("STRING", {"multiline": True, "default": _DEFAULT_NEGATIVE_PROMPT, "advanced": True}),
                "extra_position": (["before", "after"], {"default": "before", "advanced": True}),
                "model": ("STRING", {"default": "", "multiline": False, "advanced": True, "tooltip": "Model ID for the chat call. Empty = auto: the single loaded model from the router. Required for OpenRouter-style gateways."}),
                "api_key": ("STRING", {"default": "", "multiline": False, "advanced": True, "tooltip": "Optional API key, sent as 'Authorization: Bearer <key>'. Empty = no auth (local llama.cpp)."}),
                "router_url": ("STRING", {"default": "http://192.168.88.11:8080", "multiline": False, "advanced": True}),
                "proxy": ("STRING", {"default": "", "multiline": False, "advanced": True, "tooltip": "Optional proxy: socks5://host:port (SOCKS5) or http://host:port (HTTP). Bare host:port = SOCKS5. Empty = direct connection."}),
            },
            "optional": {
                "text": ("STRING", {"forceInput": True, "multiline": True, "default": ""}),
                "system_instructions": ("STRING", {"forceInput": True, "multiline": True, "default": ""}),
                "elements": ("ARRAY", {"tooltip": "Boxes from Create Bounding Boxes; MOSS Image Layout rewrites their descriptions and keeps their geometry."}),
                "canvas_width": ("INT", {"forceInput": True, "default": 1024, "min": 16, "max": 16384, "step": 16}),
                "canvas_height": ("INT", {"forceInput": True, "default": 1024, "min": 16, "max": 16384, "step": 16}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt", "extra_prompt", "face_emotion", "raw_debug", "negative_prompt", "canvas_size")
    FUNCTION = "generate_prompt"
    CATEGORY = "VSL/Prompt"

    @staticmethod
    def _net_debug(url, exc=None):
        """Diagnostic dump for router connectivity failures. Print-first, never text-only."""
        try:
            from urllib.parse import urlsplit
            parts = urlsplit(url)
            print(f"[vsl-prompt] url={url!r}", flush=True)
            print(f"[vsl-prompt]   repr={url!r} scheme={parts.scheme!r} host={parts.hostname!r} "
                  f"port={parts.port!r} path={parts.path!r}", flush=True)
        except Exception as err:
            print(f"[vsl-prompt] url parse failed: {err}", flush=True)
            print(f"[vsl-prompt]   raw repr={url!r}", flush=True)
        try:
            import os
            print(f"[vsl-prompt] env http_proxy={os.environ.get('http_proxy')!r} "
                  f"HTTP_PROXY={os.environ.get('HTTP_PROXY')!r} "
                  f"no_proxy={os.environ.get('no_proxy')!r} NO_PROXY={os.environ.get('NO_PROXY')!r}", flush=True)
            print(f"[vsl-prompt] urllib getproxies()={urllib.request.getproxies()}", flush=True)
        except Exception as err:
            print(f"[vsl-prompt] proxy probe failed: {err}", flush=True)
        try:
            import socket
            from urllib.parse import urlsplit
            parts = urlsplit(url)
            host, port = parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)
            addrs = sorted({info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
            print(f"[vsl-prompt] dns {host} -> {addrs}", flush=True)
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            print(f"[vsl-prompt] tcp connect {host}:{port} -> OK", flush=True)
        except Exception as err:
            print(f"[vsl-prompt] tcp connect FAILED {type(err).__name__}: {err}", flush=True)
        if exc is not None:
            reason = getattr(exc, "reason", exc)
            print(f"[vsl-prompt] exception {type(exc).__name__}: {reason!r}", flush=True)

    @staticmethod
    def _get_json(url, timeout, api_key=None, proxy=""):
        request = urllib.request.Request(url, headers=_api_headers(api_key))
        try:
            with _opener(proxy)(request, timeout=timeout) as response:
                print(f"[vsl-prompt] GET {url!r} -> {response.status} via {response.geturl()!r}", flush=True)
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            VSLPromptHelper._net_debug(url, exc)
            raise

    @classmethod
    def _current_model(cls, base_url, api_key=None, proxy=""):
        root = _api_root(base_url)
        data = None
        last_error = None
        for endpoint in (root + "/models", root + "/v1/models"):
            try:
                data = cls._get_json(endpoint, 10, api_key, proxy)
                break
            except Exception as exc:
                last_error = exc
        if data is None:
            raise RuntimeError(f"Cannot list models at {root}: {last_error}")
        items = data.get("data") or []
        # Router exposes status.value=loaded; standalone llama-server does not.
        loaded = [item for item in items if (item.get("status") or {}).get("value") == "loaded"]
        if loaded:
            items = loaded
        else:
            items = [item for item in items if item.get("id")]
        if len(items) != 1:
            raise RuntimeError(
                "automatic model detection needs exactly one candidate model; found "
                + str(len(items))
                + ". Fill the 'model' field (or the preset's model) to choose explicitly."
            )
        return items[0].get("id")

    @classmethod
    def IS_CHANGED(cls, cache_mode="cache", **kwargs):
        if str(cache_mode) == "no_cache":
            return float("nan")
        return None

    @staticmethod
    def _illustrious_spaces(text):
        value = str(text or "")
        if not value:
            return value
        parts = re.split(r"(\s*BREAK\s*)", value)
        out = []
        for part in parts:
            if part.strip() == "BREAK":
                out.append(" BREAK ")
                continue
            tokens = []
            for raw in part.split(","):
                token = raw.strip()
                if not token:
                    continue
                if token.startswith("score_"):
                    tokens.append(token)
                elif token in _ILLUSTRIOUS_TAG_SET or token.replace(" ", "_") in _ILLUSTRIOUS_TAG_SET:
                    if not token.startswith("score_"):
                        token = token.replace(" ", "_")
                    tokens.append(token)
                else:
                    tokens.append(token)
            out.append(", ".join(tokens))
        return "".join(out).strip()

    @staticmethod
    def _maybe_illustrious_spaces(target_model, text):
        if _normalize_target_model(target_model) != "Illustrious":
            return str(text or "").strip()
        return VSLPromptHelper._illustrious_spaces(text)

    @staticmethod
    def _clean_part(text):
        return str(text or "").strip().strip(",").strip()

    @staticmethod
    def _join_prompt_parts(*parts):
        chunks = []
        for part in parts:
            text = VSLPromptHelper._clean_part(part)
            if text:
                chunks.append(text)
        return ", ".join(chunks)

    @staticmethod
    def _add_extra_prompt(llm_prompt, extra_prompt="", extra_position="before", quality_prompt=""):
        generated = str(llm_prompt or "").strip()
        extra = VSLPromptHelper._clean_part(extra_prompt)
        quality = VSLPromptHelper._clean_part(quality_prompt)
        if not extra and not quality:
            return generated
        if "\n" in generated:
            tag_line, caption = generated.split("\n", 1)
            caption = caption.lstrip("\n")
            if extra_position == "after":
                tag_line = VSLPromptHelper._join_prompt_parts(tag_line, extra, quality)
            else:
                tag_line = VSLPromptHelper._join_prompt_parts(extra, tag_line, quality)
            return tag_line + "\n\n" + caption.strip() if caption.strip() else tag_line
        if " BREAK " in f" {generated} ":
            blocks = [part.strip() for part in generated.split("BREAK")]
            if extra_position == "after":
                blocks[0] = VSLPromptHelper._join_prompt_parts(blocks[0], extra, quality)
            else:
                blocks[0] = VSLPromptHelper._join_prompt_parts(extra, blocks[0], quality)
            return " BREAK ".join(block for block in blocks if block)
        if extra_position == "after":
            return VSLPromptHelper._join_prompt_parts(generated, extra, quality)
        return VSLPromptHelper._join_prompt_parts(extra, generated, quality)

    @staticmethod
    def _extract_llm_text(message):
        """Return only the final prompt. Never use reasoning/<think> as the image prompt."""
        content = str(message.get("content") or "").strip()
        if "<channel|>" in content:
            content = content.rsplit("<channel|>", 1)[-1].strip()
        content = content.replace("<|channel|>", "").strip()
        return content

    @staticmethod
    def _strip_preamble(output):
        text = _THINK_RE.sub("", str(output or "")).strip()
        text = re.sub(r"</think>", "", text, flags=re.IGNORECASE).strip()
        return _PREAMBLE_RE.sub("", text).strip()

    @staticmethod
    def _resolve_user_text(user_request, text=None):
        wired = str(text or "").strip()
        if wired:
            return wired
        return str(user_request or "").strip()

    @staticmethod
    def _active_extra(enable_extra_prompt, extra_prompt):
        if not enable_extra_prompt:
            return ""
        return extra_prompt

    @staticmethod
    def _active_quality(enable_quality_prompt, quality_prompt):
        if not enable_quality_prompt:
            return ""
        return quality_prompt

    @staticmethod
    def _extract_json_object(text):
        decoder = json.JSONDecoder()
        raw = str(text or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw).strip()
        for match in re.finditer(r"[\{\[]", raw):
            try:
                obj, _ = decoder.raw_decode(raw[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, (dict, list)):
                return obj
        return None

    @staticmethod
    def _parse_model_output(target_model, output):
        text = str(output or "").strip()
        if target_model not in _QWEN_MODELS:
            return text
        obj = VSLPromptHelper._extract_json_object(text)
        if not isinstance(obj, dict):
            raise RuntimeError("Qwen model did not return valid JSON prompt")
        rewritten = str(obj.get("rewritten_prompt") or "").strip()
        if not rewritten:
            raise RuntimeError("Qwen JSON is missing rewritten_prompt")
        obj["rewritten_prompt"] = rewritten
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _compose_final_prompt(target_model, llm_prompt, extra_prompt, extra_position, quality_prompt):
        if target_model in _QWEN_MODELS:
            return str(llm_prompt or "").strip()
        if target_model in _MOSS_MODELS:
            # MOSS takes one self-contained prompt: a compiled layout JSON must stay
            # byte-identical, and a caption must not gain comma-separated tag soup.
            base = VSLPromptHelper._clean_part(llm_prompt)
            extra = VSLPromptHelper._clean_part(extra_prompt)
            quality = VSLPromptHelper._clean_part(quality_prompt)
            if base.startswith("{"):
                # Appending prose after a layout JSON would make it unparseable.
                return base
            text = base
            if extra:
                text = f"{extra} {text}" if extra_position != "after" else f"{text} {extra}"
            if quality:
                text = f"{text} {quality}"
            return text.strip()
        prompt = llm_prompt
        if target_model == "Illustrious":
            prompt = VSLPromptHelper._strip_llm_count_if_extra_has_count(prompt, extra_prompt)
        prompt = VSLPromptHelper._add_extra_prompt(prompt, extra_prompt, extra_position, quality_prompt)
        return VSLPromptHelper._maybe_illustrious_spaces(target_model, prompt)

    @staticmethod
    def _append_system_instructions(system_prompt, system_instructions):
        extra = str(system_instructions or "").strip()
        if not extra:
            return str(system_prompt or "")
        return (
            str(system_prompt or "").rstrip()
            + "\n\nADDITIONAL SYSTEM INSTRUCTIONS (follow these as part of the system prompt):\n"
            + extra
        )

    @staticmethod
    def _uses_length_hint(target_model):
        return target_model not in ("Translate Only",) + _QWEN_MODELS + _MOSS_MODELS

    @staticmethod
    def _moss_boxes_hint(target_model, boxes):
        """Tell the layout model how many boxes it must describe."""
        if target_model != _MOSS_LAYOUT_MODEL:
            return ""
        if not boxes:
            return (
                "\n\nNO BOXES: the user supplied no bounding boxes, so there is no layout to "
                "improve. Output only a plain caption paragraph describing the finished image. "
                "Do not output JSON, coordinates or any layout structure."
            )
        return (
            f"\n\nBOX COUNT LOCK — exactly {len(boxes)} boxes were supplied. Your \"items\" array "
            f"must contain exactly {len(boxes)} entries, one per box, in the same order.\n"
            "GROUNDING LOCK — the boxes belong to the scene the user asked for. Describe only "
            "things that fit that request and the boxes' types, positions and current "
            "descriptions. Never substitute a different subject, and when a box has no "
            "description, infer it from the user's request and the neighbouring boxes."
        )

    @staticmethod
    def _moss_caption_lock(target_model, boxes=None):
        """MOSS captions are the whole positive prompt: no sizes, no JSON.

        When boxes come in, the caption has to describe the subjects those boxes
        mark instead of turning into a free landscape description.
        """
        if target_model != "MOSS Image":
            return ""
        lock = (
            "\n\nFORMAT LOCK — output only the caption prose. Do not output JSON, YAML, "
            "brackets, key/value pairs, aspect ratios, resolutions, pixel sizes or canvas sizes. "
            "Do not add quality tags or a negative prompt."
        )
        count = len(boxes or [])
        if count:
            plural = "" if count == 1 else "es"
            lock += (
                f"\n\nBOX INPUT LOCK — {count} bounding box{plural} came in with this request, each with a "
                "short description. Cover the element inside every box, in the given order.\n"
                "CONSISTENCY LOCK — invented detail is allowed: you may add colour, material, clothing, "
                "light, background and atmosphere that makes the picture concrete. What is not allowed "
                "is contradicting the request or the boxes: same subject, same count, same pose and "
                "position, same stated colours, same stated condition, nothing that reverses or negates "
                "what the user wrote. A box description overrides any invented appearance for that "
                "element. Never mention boxes, coordinates or the drawing of them."
            )
        return lock

    @staticmethod
    def _render_boxes_for_caption(boxes, scene_request=""):
        """Render the user's boxes as a short text block for caption mode.

        Caption mode cannot take a JSON layout, so the boxes travel as plain
        sentences: what each box marks and how much of the frame it covers.
        """
        if not boxes:
            return ""
        lines = ["Elements the user marked with boxes, in order:"]
        for position, box in enumerate(boxes, start=1):
            y0, x0, y1, x1 = box["bbox"]
            where = box.get("where") or ""
            label = box["desc"] or box["text"].strip() or (
                "text element" if box["type"] == "text" else "unlabelled element"
            )
            line = f"- box {position}: {label}"
            if where:
                line += f", covering {where}"
            if box["type"] == "text" and box["text"].strip():
                line += f', the wording inside it is "{box["text"].strip()}"'
            lines.append(line)
        lines.append(
            "Describe each of these elements and add nothing that contradicts them. "
            "Never mention this list, the boxes, their positions or the size of the canvas."
        )
        return "\n".join(lines)

    @staticmethod
    def _box_labels(box_block=""):
        """Pull the raw descriptions out of a rendered box block, in order."""
        labels = []
        for line in str(box_block or "").splitlines():
            line = line.strip()
            if not line.startswith("- box "):
                continue
            label = line.split(":", 1)[1] if ":" in line else line
            label = label.split(", covering")[0].strip().rstrip(",")
            if label and label not in labels:
                labels.append(label)
        return labels

    @staticmethod
    def _append_verbatim_boxes(text, box_block=""):
        """Translate Only: keep the user's box descriptions untranslated.

        The helper translation also turned the rendered box lines into prose, so the
        labels are re-attached afterwards as a plain comma list. A label that the
        translation already contains verbatim is not repeated.
        """
        base = str(text or "").strip()
        labels = [label for label in VSLPromptHelper._box_labels(box_block) if label not in base]
        if not labels:
            return base
        joined = ", ".join(labels)
        return f"{base}, {joined}" if base else joined

    @staticmethod
    def _append_box_descriptions(text, box_block=""):
        """Add the user's box descriptions to a prompt without any model rewriting.

        Used by Skip mode (LLM bypassed) and by Translate Only, where the only
        rewriting allowed is translation. Descriptions go in verbatim, comma
        separated, the way a tag-style positive prompt expects them.
        """
        base = str(text or "").strip()
        labels = VSLPromptHelper._box_labels(box_block)
        if not labels:
            return base
        joined = ", ".join(labels)
        return f"{base}, {joined}" if base else joined

    @staticmethod
    def _moss_caption_request(boxes, scene_request=""):
        """User message for caption mode when boxes are wired."""
        scene = str(scene_request or "").strip()
        block = VSLPromptHelper._render_boxes_for_caption(boxes, scene)
        if not block:
            return scene
        return f"{scene}\n\n{block}".strip() if scene else block

    @staticmethod
    def _count_tag_re():
        return re.compile(r"^(?:\d+girls?|\d+boys?|1other|1futa|2futa|solo|solo_focus|multiple_girls|multiple_boys|couple|group)$")

    @staticmethod
    def _extract_count_tags(text):
        counts = []
        rest = []
        pattern = VSLPromptHelper._count_tag_re()
        for raw in str(text or "").replace("\n", ",").split(","):
            token = raw.strip().strip("_")
            if not token:
                continue
            key = token.replace(" ", "_")
            if pattern.match(key):
                if key not in counts:
                    counts.append(key)
            else:
                rest.append(token)
        return counts, rest

    @staticmethod
    def _strip_llm_count_if_extra_has_count(prompt, extra_prompt):
        counts, _ = VSLPromptHelper._extract_count_tags(extra_prompt)
        if not counts:
            return prompt
        text = str(prompt or "").strip()
        if not text:
            return text
        pattern = VSLPromptHelper._count_tag_re()
        if "\n" in text:
            tag_line, caption = text.split("\n", 1)
            kept = [tok.strip() for tok in tag_line.split(",") if tok.strip() and not pattern.match(tok.strip().replace(" ", "_"))]
            cleaned = ", ".join(kept)
            return cleaned + "\n" + caption if caption.strip() else cleaned
        blocks = [part.strip() for part in re.split(r"\s*BREAK\s*", text)]
        first = blocks[0]
        kept = [tok.strip() for tok in first.split(",") if tok.strip() and not pattern.match(tok.strip().replace(" ", "_"))]
        blocks[0] = ", ".join(kept)
        return " BREAK ".join(block for block in blocks if block)

    @staticmethod
    def _length_hint(max_output_tokens):
        n = VSLPromptHelper._max_tokens(max_output_tokens)
        return (
            f"\n\nKeep the final prompt concise, roughly under {n} tokens. "
            "Finish the prompt completely; do not stop mid-sentence or mid-tag."
        )

    @staticmethod
    def _max_tokens(max_output_tokens):
        if str(max_output_tokens) == "512":
            return 512
        return int(str(max_output_tokens).rstrip("K")) * 1024

    @staticmethod
    def _reasoning_budget_tokens(reasoning_budget):
        key = str(reasoning_budget or "off").strip()
        if key not in _REASONING_BUDGETS:
            raise ValueError(f"Unsupported reasoning_budget: {reasoning_budget}")
        return _REASONING_BUDGETS[key]

    @staticmethod
    def _reasoning_fields(reasoning_budget):
        budget = VSLPromptHelper._reasoning_budget_tokens(reasoning_budget)
        if budget == 0:
            return {
                "reasoning_format": "deepseek",
                "reasoning_effort": "none",
                "chat_template_kwargs": {"enable_thinking": False},
                "reasoning_budget_tokens": 0,
            }
        return {
            "reasoning_format": "deepseek",
            "chat_template_kwargs": {"enable_thinking": True},
            "reasoning_budget_tokens": budget,
        }

    @classmethod
    def _chat(cls, base_url, payload, timeout=180, api_key=None, proxy=""):
        root = _api_root(base_url)
        url = root + "/v1/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=_api_headers(api_key, json_body=True),
            method="POST",
        )
        try:
            with _opener(proxy)(request, timeout=timeout) as response:
                print(f"[vsl-prompt] POST {url!r} -> {response.status}", flush=True)
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"LLM endpoint HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            VSLPromptHelper._net_debug(url, exc)
            raise RuntimeError(f"Cannot connect to LLM endpoint at {root} (proxy={_clean_proxy(proxy) or 'direct'}): {exc.reason}") from exc

    def generate_prompt(
        self,
        user_request,
        target_model="Krea 2",
        mode="Enhance",
        krea_style="реализм",
        router_url="http://192.168.88.11:8080",
        temperature=0.7,
        max_output_tokens="1K",
        reasoning_budget="off",
        cache_mode="cache",
        enable_face_emotion=False,
        enable_extra_prompt=False,
        enable_quality_prompt=False,
        extra_prompt="",
        quality_prompt=_DEFAULT_QUALITY_PROMPT,
        negative_prompt=_DEFAULT_NEGATIVE_PROMPT,
        extra_position="before",
        system_instructions="",
        text=None,
        elements=None,
        canvas_width=1024,
        canvas_height=1024,
        model="",
        api_key="",
        preset="(none)",
        preset_action="use",
        preset_name="",
        proxy="",
        **kwargs,
    ):
        # --- connection presets: save/delete as run side effects, then resolve ---
        preset_sel = str(preset or "(none)").strip()
        action = str(preset_action or "use").strip()
        save_name = str(preset_name or "").strip()
        if action not in ("use", "save", "delete"):
            raise ValueError(f"Unsupported preset_action: {preset_action}")
        if action == "save":
            name = save_name or (preset_sel if preset_sel not in ("", "(none)") else "")
            if not name:
                raise ValueError("preset_action=save needs preset_name or a selected preset")
            _save_preset(name, {
                "router_url": str(router_url or "").strip(),
                "api_key": str(api_key or "").strip(),
                "model": str(model or "").strip(),
                "proxy": str(proxy or "").strip(),
            })
        elif action == "delete":
            name = save_name or preset_sel
            if name in ("", "(none)"):
                raise ValueError("preset_action=delete needs preset_name or a selected preset")
            _delete_preset(name)
        record = None
        if action != "delete" and preset_sel not in ("", "(none)"):
            record = _load_presets().get(preset_sel)
            if not isinstance(record, dict):
                raise ValueError(f"Unknown preset: {preset_sel}")
            # A selected preset is authoritative for the whole connection
            # block, INCLUDING empty fields: no stale value may survive a
            # preset switch. Blank router_url falls back to the default below.
            router_url = str(record.get("router_url") or "").strip()
            api_key = str(record.get("api_key") or "").strip()
            model = str(record.get("model") or "").strip()
            proxy = str(record.get("proxy") or "").strip()
        api_key = str(api_key or "").strip()
        model = str(model or "").strip()
        proxy = _clean_proxy(proxy)
        text = self._resolve_user_text(user_request, text if text is not None else kwargs.get("text"))
        extra_prompt = self._active_extra(enable_extra_prompt, extra_prompt)
        quality_prompt = self._active_quality(enable_quality_prompt, quality_prompt)
        mode = str(mode or "Enhance").strip()
        if mode not in ("Enhance", "Translate Only", "Skip"):
            raise ValueError(f"Unsupported mode: {mode}")
        translate_only = mode == "Translate Only"
        boxes = _moss_parse_elements(_moss_adapt_editor_elements(elements))
        canvas_w = int(canvas_width or 0) or 1024
        canvas_h = int(canvas_height or 0) or 1024
        if boxes:
            for box in boxes:
                box["where"] = _moss_box_place(box, canvas_w, canvas_h)
        canvas_out = f"{canvas_w}x{canvas_h}"
        box_block = self._render_boxes_for_caption(boxes) if boxes else ""
        if mode == "Skip":
            # Skip bypasses the LLM, so the boxes are the only thing that can still
            # reach the prompt: append their descriptions verbatim.
            text = self._append_box_descriptions(text, box_block)
            return (text, "", "", "skip: LLM bypassed", str(negative_prompt or "").strip(), canvas_out)
        target_model = _normalize_target_model(target_model)
        if target_model not in _TARGET_MODELS:
            raise ValueError(f"Unsupported target model: {target_model}")
        if translate_only:
            enable_face_emotion = False
        if not text:
            # With boxes wired the copy may live in the boxes alone.
            text = str(user_request or "").strip()
        if target_model == _MOSS_LAYOUT_MODEL and boxes:
            scene_hint = str(user_request or "").strip()
            text = _moss_elements_request(boxes, (canvas_w, canvas_h), scene_hint)
        elif target_model == "MOSS Image" and boxes and not translate_only:
            # Caption mode has no JSON layout, so the boxes ride along with the
            # request as plain sentences. Without this the model silently drops
            # them and invents a whole scene around the first box label.
            # Translate Only is excluded: there the request is translated as-is and
            # the box labels are appended verbatim afterwards.
            text = self._moss_caption_request(boxes, text or user_request)
        if not text:
            raise ValueError("user_request cannot be empty")
        style = _normalize_krea_style(krea_style)
        if target_model == _MOSS_LAYOUT_MODEL and not boxes and not translate_only:
            # No boxes wired: behave exactly like the plain MOSS caption mode.
            target_model = "MOSS Image"
        system_prompt = TRANSLATE_ONLY_SYSTEM_PROMPT if translate_only else _system_prompt(target_model, style)
        if not translate_only:
            system_prompt += self._moss_boxes_hint(target_model, boxes)
            system_prompt += self._moss_caption_lock(target_model, boxes)
        if not translate_only and self._uses_length_hint(target_model):
            system_prompt += self._length_hint(max_output_tokens)
        system_prompt = self._append_system_instructions(system_prompt, system_instructions)
        base_url = str(router_url or "http://192.168.88.11:8080").strip().rstrip("/")
        print(f"[vsl-prompt] router_url raw={router_url!r} -> base_url={base_url!r}", flush=True)
        if model:
            # Explicit model: no /models call, works with OpenRouter-style gateways.
            print(f"[vsl-prompt] model explicitly set: {model!r}", flush=True)
        else:
            model = self._current_model(base_url, api_key, proxy)
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "ver": _PROMPT_VER,
                    "endpoint": _api_root(base_url),
                    "api_fp": hashlib.sha256(api_key.encode()).hexdigest()[:12] if api_key else "",
                    "proxy": proxy,
                    "mode": mode,
                    "target_model": target_model,
                    "krea_style": style if target_model == "Krea 2" else "",
                    "boxes": boxes if boxes else "",
                    "canvas": canvas_out if target_model == _MOSS_LAYOUT_MODEL else "",
                    "model": model,
                    "text": text,
                    "system_instructions": str(system_instructions or "").strip(),
                    "temperature": float(temperature),
                    "max_output_tokens": max_output_tokens,
                    "reasoning_budget": self._reasoning_budget_tokens(reasoning_budget),
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        face_cache_key = hashlib.sha256(
            json.dumps({"model": model, "text": text, "kind": "face_emotion"}, sort_keys=True).encode()
        ).hexdigest()
        if cache_mode == "cache":
            with self._cache_lock:
                cached = self._cache.get(cache_key)
                cached_face = self._cache.get(face_cache_key)
            if cached is not None and (not enable_face_emotion or cached_face is not None):
                extra_out = self._maybe_illustrious_spaces(target_model, extra_prompt)
                quality_out = self._maybe_illustrious_spaces(target_model, quality_prompt)
                negative_out = self._maybe_illustrious_spaces(target_model, negative_prompt)
                final_prompt = cached if mode == "Translate Only" else self._compose_final_prompt(
                    target_model, cached, extra_out, extra_position, quality_out
                )
                if translate_only and boxes:
                    final_prompt = self._append_verbatim_boxes(final_prompt, box_block)
                return (
                    final_prompt,
                    extra_out,
                    cached_face or "",
                    "cache_hit",
                    negative_out,
                    canvas_out,
                )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2 if translate_only else float(temperature),
            "top_p": 0.9,
            "max_tokens": _SAFETY_MAX_TOKENS,
            "stream": False,
        }
        if not api_key:
            # llama.cpp/router-only reasoning knobs; OpenAI-style gateways manage
            # reasoning per model and reject or ignore these fields.
            payload.update(self._reasoning_fields(reasoning_budget))
        result = self._chat(base_url, payload, api_key=api_key, proxy=proxy)
        try:
            choice = result["choices"][0]
            message = choice["message"]
            output = self._extract_llm_text(message)
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("llama.cpp returned no assistant text: " + json.dumps(result)[:1000]) from exc
        output = self._strip_preamble(output)
        if str(choice.get("finish_reason") or "") == "length":
            raise RuntimeError("llama.cpp hit the safety token ceiling before finishing the prompt")
        if not output:
            raise RuntimeError("llama.cpp returned an empty prompt")
        if not translate_only:
            output = self._parse_model_output(target_model, output)
        if target_model == _MOSS_LAYOUT_MODEL:
            if boxes:
                caption, rewrites = _moss_unwrap_rewrites(output, boxes)
                output = _moss_compose_layout(boxes, caption, rewrites, canvas_w, canvas_h)
            else:
                # No boxes wired: the layout model degrades to a plain caption.
                output = self._clean_part(output)
        raw_parts = ["PROMPT_RESPONSE=" + json.dumps(result, ensure_ascii=False)]

        face_output = ""
        if enable_face_emotion:
            face_payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": FACE_EMOTION_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "temperature": min(float(temperature), 0.5),
                "top_p": 0.9,
                "max_tokens": _SAFETY_MAX_TOKENS,
                "stream": False,
            }
            if not api_key:
                face_payload.update(self._reasoning_fields(reasoning_budget))
            try:
                face_result = self._chat(base_url, face_payload, api_key=api_key, proxy=proxy)
                raw_parts.append("FACE_RESPONSE=" + json.dumps(face_result, ensure_ascii=False))
                face_message = face_result.get("choices", [{}])[0].get("message", {})
                face_output = self._strip_preamble(self._extract_llm_text(face_message))
            except Exception as exc:
                raw_parts.append("FACE_ERROR=" + repr(exc))
                face_output = ""

        with self._cache_lock:
            self._cache = {cache_key: output}
            if enable_face_emotion:
                self._cache[face_cache_key] = face_output
        extra_out = self._maybe_illustrious_spaces(target_model, extra_prompt)
        quality_out = self._maybe_illustrious_spaces(target_model, quality_prompt)
        negative_out = self._maybe_illustrious_spaces(target_model, negative_prompt)
        if translate_only and boxes:
            # Only the request is translated; box descriptions stay in the user's
            # own words and are appended verbatim as a separate list.
            output = self._append_verbatim_boxes(output, box_block)
        final_prompt = output if translate_only else self._compose_final_prompt(
            target_model, output, extra_out, extra_position, quality_out
        )
        return (
            final_prompt,
            extra_out,
            face_output,
            "\n".join(raw_parts),
            negative_out,
            canvas_out,
        )
