# vsl_node

A pack of custom ComfyUI nodes: LLM-powered prompt generation, a visual style gallery, and a set of handy utilities.

[Русская версия](README.md)

## Installation

Via git clone (recommended — easy to update later):

```
cd ComfyUI/custom_nodes
git clone https://github.com/KiberSlesar/vsl_node.git
```

Restart ComfyUI — the nodes will appear under the `VSL/...` categories.

Updating to the latest version:

```
cd ComfyUI/custom_nodes/vsl_node
git pull
```

You can also simply copy the directory into `ComfyUI/custom_nodes/` — the result is the same.

Nothing needs to be configured after installation: LLM presets, model settings and favorites are created automatically on first use. Optionally copy the `*.example` templates to files without the `.example` suffix — e.g. `vsl_router_presets.json.example` → `vsl_router_presets.json`.

## Nodes

### VSL Prompt Helper
Takes your description (e.g. "a girl in a red dress in a garden") and turns it into a ready-made prompt for a specific image generation model. The node sends the request to a large language model (LLM) which adds details, translates or organizes tags — depending on the selected mode.

- **Modes:** `Enhance` — expands and enriches the request; `Translate Only` — only translates; `Skip` — bypasses the LLM and returns the text as-is.
- **Target models:** Krea 2 (realism / anime / neutral), Anima, Illustrious, Qwen 2.1 text2img, Qwen 2.1 Image Edit, MOSS Image, MOSS Image Layout (element layout via bounding boxes).
- **Connection:** any OpenAI-compatible endpoint — a local llama-router, NVIDIA NIM, OpenRouter-style gateways. You can specify a model, an API key and a proxy (`http://` and `socks5://`). Frequently used connections can be saved as presets (Save / Update / Delete buttons) and picked from a dropdown list.
- **Extras:** negative prompt, extra/quality insertions, face and emotion analysis, bounding box support for MOSS layouts.
- **Outputs:** `prompt` (the main prompt), `extra_prompt`, `face_emotion`, `raw_debug` (debug info), `negative_prompt`, `canvas_size`.

### vsl_Style_Selector
A visual gallery of 414 styles with previews grouped by category. Clicking a preview selects a style; clicking it again clears the selection — then the node outputs an empty text. The star in the corner of a preview adds the style to favorites (the `Favorites` tab shows only favorites), and the −/+ buttons resize the previews. Outputs a ready-made description of the selected style.

### VSL Text Concentrate
Joins up to four text inputs into one using a configurable separator (comma by default). Empty inputs are skipped.

### VSL Image Size
Measures an image and outputs its width and height (INT); the node panel also shows the aspect ratio, pixel size and megapixels.

### VSL Image Resize
Like VSL Image Size, but with a multiplication coefficient: takes the input image's width and height, multiplies them by the number from the coefficient string (e.g. `1.5`, `0.5` or `1,5`) and outputs the result. Values are normalized — the output is always positive (at least 1). The node panel shows the original and the new size.

### vsl_image_compare
A/B comparison of two images on one gray panel: the seam follows the pointer (SLIDE), or the A/B buttons flip the whole picture. `image_a` passes through unchanged, so the node can sit mid-graph. Previews go to the temp folder and don't pollute outputs.

### vsl_seed
Seed with buttons: 🎲 Random, +1, -1, ♻ Last (restore the previous seed). Magic values `-1` (random), `-2` (increment), `-3` (decrement) work via the API too — the server generates a seed and writes it back into the workflow metadata.

### VSL Min/Max Size
Picks the larger or smaller of width/height (a `max` / `min` switch) and outputs it as a single number. Handy for automatic size adjustment.

### VSL Model Loader (Presets)
Loads a diffusion model and outputs its saved generation settings along with it: CFG, steps, sampler, scheduler, weight dtype. Settings sets are stored per model and served via the `/vsl/model-presets*` HTTP routes — no need to tune parameters by hand every time.

### VSL Any Reroute
A universal "pass-through" for any data type: accepts and returns any connected signal, helping to route links neatly across the canvas.

## Local settings (not in the repository)

Local files are created next to the nodes (templates — `*.example`):

- `vsl_router_presets.json` — LLM connection presets (router_url, api_key, model, proxy). **Contains API keys — never committed to git.**
- `vsl_model_presets.json` — saved model settings.
- `vsl_style_favorites.json` — favorite gallery styles.

The files are optional: the nodes work without them and they are created automatically on first save.

## Notes

- `web/previews/` — 414 style previews for the vsl_Style_Selector gallery.
- `vsl_prompts.json` — system prompts (11 keys), read at import time; editing requires a ComfyUI restart.
