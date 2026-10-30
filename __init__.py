from server import PromptServer
from aiohttp import web
from .vsl_text_concentrate import VSLTextConcentrate

@PromptServer.instance.routes.get("/vsl/router-presets")
async def vsl_router_presets(request):
    from .vsl_prompt_helper import _load_presets
    return web.json_response({"presets": _load_presets()})


@PromptServer.instance.routes.post("/vsl/router-presets/save")
async def vsl_router_presets_save(request):
    from .vsl_prompt_helper import _load_presets, _save_preset
    data = await request.json()
    name = str(data.get("name") or "").strip()
    if not name or name == "(none)":
        return web.json_response({"ok": False, "error": "preset name is empty"}, status=400)
    _save_preset(name, {
        "router_url": str(data.get("router_url") or "").strip(),
        "api_key": str(data.get("api_key") or "").strip(),
        "model": str(data.get("model") or "").strip(),
        "proxy": str(data.get("proxy") or "").strip(),
    })
    return web.json_response({"ok": True, "presets": _load_presets()})


@PromptServer.instance.routes.post("/vsl/router-presets/delete")
async def vsl_router_presets_delete(request):
    from .vsl_prompt_helper import _delete_preset, _load_presets
    data = await request.json()
    name = str(data.get("name") or "").strip()
    if not name or name == "(none)":
        return web.json_response({"ok": False, "error": "preset name is empty"}, status=400)
    _delete_preset(name)
    return web.json_response({"ok": True, "presets": _load_presets()})


@PromptServer.instance.routes.get("/vsl/style-favorites")
async def vsl_style_favorites_list(request):
    from .vsl_style_selector import _load_favorites
    return web.json_response({"favorites": _load_favorites()})


@PromptServer.instance.routes.post("/vsl/style-favorites/toggle")
async def vsl_style_favorites_toggle(request):
    from .vsl_style_selector import _toggle_favorite
    data = await request.json()
    name = str(data.get("name") or "").strip()
    if not name:
        return web.json_response({"ok": False, "error": "style name is empty"}, status=400)
    return web.json_response({"ok": True, "favorites": _toggle_favorite(name)})


from .vsl_prompt_helper import VSLPromptHelper
from .vsl_any_reroute import VSLAnyReroute
from .vsl_image_size import VSLImageSize
from .vsl_image_resize import VSLImageResize
from .vsl_image_compare import VSLImageCompare
from .vsl_seed import VSLSeed
from .vsl_minmax_size import VSLMinMaxSize
from .vsl_model_loader import VSLModelLoader
from .vsl_style_selector import VSLStyleSelector

NODE_CLASS_MAPPINGS = {
    "vsl_text_concentrate": VSLTextConcentrate,
    "vsl_prompt_helper": VSLPromptHelper,
    "vsl_any_reroute": VSLAnyReroute,
    "vsl_image_size": VSLImageSize,
    "vsl_image_resize": VSLImageResize,
    "vsl_image_compare": VSLImageCompare,
    "vsl_seed": VSLSeed,
    "vsl_minmax_size": VSLMinMaxSize,
    "vsl_model_loader": VSLModelLoader,
    "vsl_Style_Selector": VSLStyleSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "vsl_text_concentrate": "VSL Text Concentrate",
    "vsl_prompt_helper": "VSL Prompt Helper",
    "vsl_any_reroute": "VSL Any Reroute",
    "vsl_image_size": "VSL Image Size",
    "vsl_image_resize": "VSL Image Resize",
    "vsl_image_compare": "vsl_image_compare",
    "vsl_seed": "vsl_seed",
    "vsl_minmax_size": "VSL Min/Max Size",
    "vsl_model_loader": "VSL Model Loader (Presets)",
    "vsl_Style_Selector": "vsl_Style_Selector",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
