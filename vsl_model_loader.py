"""vsl_model_loader — diffusion model loader with per-model sampler presets.

Pick a model, tune cfg/steps/sampler/scheduler, press "Save preset". Later,
choosing the model auto-applies the saved preset. Presets live in
vsl_model_presets.json next to this file.
"""
import os
import json
import threading

import torch
import folder_paths
import comfy.sd
import comfy.samplers
from server import PromptServer
from aiohttp import web

_PRESET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vsl_model_presets.json")
_PRESET_FIELDS = ("cfg", "steps", "sampler_name", "scheduler", "weight_dtype")
_lock = threading.Lock()

# Live references (not copies) so scheduler/sampler additions from other packs
# (e.g. ComfyUI-MOSS-Shift-Scheduler) stay in sync with KSampler's own lists.
_SAMPLERS = comfy.samplers.KSampler.SAMPLERS
_SCHEDULERS = comfy.samplers.KSampler.SCHEDULERS
_WEIGHT_DTYPES = ["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"]


def _load_presets():
    try:
        with open(_PRESET_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_presets(data):
    with _lock:
        tmp = _PRESET_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, _PRESET_PATH)


def _model_source_name(model):
    """Return the source diffusion-model name when ComfyUI kept it."""
    patcher = getattr(model, "patcher", model)
    cached = getattr(patcher, "cached_patcher_init", None)
    if isinstance(cached, tuple) and len(cached) >= 2:
        args = cached[1]
        if isinstance(args, tuple) and args and isinstance(args[0], str):
            return args[0]
    return None


def _find_preset(model_name):
    if not model_name:
        return None
    presets = _load_presets()
    normalized = str(model_name).replace("/", "\\")
    candidates = [normalized]
    if "\\" not in normalized:
        candidates.append(os.path.basename(normalized))
    for key in candidates:
        if key in presets:
            return presets[key]
    for key, preset in presets.items():
        if str(key).replace("/", "\\") == normalized:
            return preset
    return None


@PromptServer.instance.routes.post("/vsl/model-preset/save")
async def vsl_save_model_preset(request):
    try:
        body = await request.json()
        name = str(body.get("unet_name") or "").strip()
        if not name:
            return web.json_response({"ok": False, "error": "unet_name is required"}, status=400)
        preset = {field: body[field] for field in _PRESET_FIELDS if field in body}
        data = _load_presets()
        data[name] = preset
        _save_presets(data)
        return web.json_response({"ok": True, "preset": preset})
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=500)


@PromptServer.instance.routes.get("/vsl/model-preset/list")
async def vsl_list_model_presets(request):
    return web.json_response({"ok": True, "presets": _load_presets()})


class VSLModelLoader:
    """The sampler_name/scheduler outputs use the options LIST as their type —
    the only shape the backend's validate_node_input() accepts for list-typed
    combo inputs (subgraphs, converted KSampler widgets)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "unet_name": (folder_paths.get_filename_list("diffusion_models"),),
                "cfg": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "sampler_name": (_SAMPLERS,),
                "scheduler": (_SCHEDULERS,),
                "weight_dtype": (_WEIGHT_DTYPES, {"advanced": True}),
            },
            "optional": {
                "model": ("MODEL",),
            },
        }

    RETURN_TYPES = ("MODEL", "FLOAT", "INT", _SAMPLERS, _SCHEDULERS)
    RETURN_NAMES = ("model", "cfg", "steps", "sampler_name", "scheduler")
    FUNCTION = "load"
    CATEGORY = "VSL"

    def load(self, unet_name, cfg, steps, sampler_name, scheduler,
             weight_dtype="default", model=None):
        # When a MODEL is connected, reuse it.  The source path retained by
        # ComfyUI is used only to select the matching preset; no second load.
        source_name = _model_source_name(model) if model is not None else unet_name
        preset = _find_preset(source_name)
        if preset:
            cfg = preset.get("cfg", cfg)
            steps = preset.get("steps", steps)
            sampler_name = preset.get("sampler_name", sampler_name)
            scheduler = preset.get("scheduler", scheduler)
        if model is not None:
            return (model, float(cfg), int(steps), str(sampler_name), str(scheduler))

        model_options = {}
        if weight_dtype == "fp8_e4m3fn":
            model_options["dtype"] = torch.float8_e4m3fn
        elif weight_dtype == "fp8_e4m3fn_fast":
            model_options["dtype"] = torch.float8_e4m3fn
            model_options["fp8_optimizations"] = True
        elif weight_dtype == "fp8_e5m2":
            model_options["dtype"] = torch.float8_e5m2

        unet_path = folder_paths.get_full_path_or_raise("diffusion_models", unet_name)
        model = comfy.sd.load_diffusion_model(unet_path, model_options=model_options)
        return (model, float(cfg), int(steps), str(sampler_name), str(scheduler))
