const appApi = window.comfyAPI?.app?.app || window.app;

const PRESET_FIELDS = ["cfg", "steps", "sampler_name", "scheduler", "weight_dtype"];

function getWidget(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function readPreset(node) {
  const preset = { unet_name: getWidget(node, "unet_name")?.value };
  for (const name of PRESET_FIELDS) {
    const widget = getWidget(node, name);
    if (widget) preset[name] = widget.value;
  }
  return preset;
}

function applyPreset(node, preset) {
  let applied = 0;
  for (const name of PRESET_FIELDS) {
    const widget = getWidget(node, name);
    if (widget && preset[name] !== undefined && widget.value !== preset[name]) {
      widget.value = preset[name];
      applied += 1;
    }
  }
  node.setDirtyCanvas?.(true, true);
  return applied;
}

async function fetchPresets() {
  const request = window.comfyAPI?.api?.fetchApi || window.api?.fetchApi || window.fetch;
  const response = await request("/vsl/model-preset/list");
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || "Preset list failed");
  return data.presets || {};
}

async function savePreset(node) {
  const body = readPreset(node);
  if (!body.unet_name) throw new Error("No model selected");
  const request = window.comfyAPI?.api?.fetchApi || window.api?.fetchApi || window.fetch;
  const response = await request("/vsl/model-preset/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || "Preset save failed");
  return data.preset;
}

appApi.registerExtension({
  name: "vsl.model.loader",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "vsl_model_loader") return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onCreated?.apply(this, arguments);

      const button = document.createElement("button");
      button.textContent = "\u{1F4BE} Save preset";
      button.type = "button";
      button.style.cssText =
        "width:100%;height:28px;cursor:pointer;pointer-events:auto;margin-top:4px";
      button.onclick = () =>
        savePreset(this)
          .then((preset) => alert(`Preset saved for ${getWidget(this, "unet_name")?.value}:\n${JSON.stringify(preset, null, 2)}`))
          .catch((e) => alert(e.message));
      this.addDOMWidget("vsl_save_preset", "VSL Save Preset", button, { serialize: false });

      const modelWidget = getWidget(this, "unet_name");
      if (modelWidget) {
        const node = this;
        const original = modelWidget.callback;
        modelWidget.callback = async function (value) {
          if (original) original.apply(node, arguments);
          try {
            const presets = await fetchPresets();
            const preset = presets[value];
            if (preset) applyPreset(node, preset);
          } catch (e) {
            console.warn("[vsl_model_loader] preset load failed:", e);
          }
        };
      }
      return result;
    };
  },
});
