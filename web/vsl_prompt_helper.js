import { app } from "../../../scripts/app.js";

function setWidgetHeight(widget, px) {
  const el = widget?.inputEl || widget?.element;
  if (!el) {
    return;
  }
  el.style.minHeight = `${px}px`;
  el.style.height = `${px}px`;
}

function widget(node, name) {
  return node.widgets?.find((w) => w.name === name);
}

async function fetchPresets() {
  const res = await fetch("/vsl/router-presets");
  const data = await res.json();
  return data?.presets || {};
}

function refreshPresetOptions(node, presets) {
  const preset = widget(node, "preset");
  if (!preset?.options) {
    return;
  }
  const names = Object.keys(presets)
    .filter((name) => name && name !== "(none)")
    .sort();
  preset.options.values = ["(none)", ...names];
  if (!preset.options.values.includes(preset.value)) {
    preset.value = "(none)";
  }
}

async function applyPreset(node, name) {
  if (!name || name === "(none)") {
    return;
  }
  try {
    const rec = (await fetchPresets())[name];
    if (!rec) {
      return;
    }
    // The preset is authoritative for the whole connection block: values it
    // does not define are cleared so nothing stale survives a preset switch.
    for (const key of ["router_url", "api_key", "model", "proxy"]) {
      const target = widget(node, key);
      if (target) {
        target.value = String(rec[key] ?? "");
      }
    }
  } catch (err) {
    console.warn("[vsl] router preset load failed:", err);
  }
}

async function savePreset(node) {
  const name = window.prompt("Имя пресета:", "");
  if (!name || !name.trim()) {
    return;
  }
  const payload = { name: name.trim() };
  for (const key of ["router_url", "api_key", "model", "proxy"]) {
    payload[key] = String(widget(node, key)?.value ?? "");
  }
  try {
    const res = await fetch("/vsl/router-presets/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(await res.text());
    }
    const data = await res.json();
    refreshPresetOptions(node, data.presets || {});
    const preset = widget(node, "preset");
    if (preset) {
      preset.value = payload.name;
    }
  } catch (err) {
    console.warn("[vsl] preset save failed:", err);
    window.alert(`Не удалось сохранить пресет: ${err}`);
  }
}

async function updatePreset(node) {
  const preset = widget(node, "preset");
  const name = preset?.value;
  if (!name || name === "(none)") {
    window.alert("Сначала выберите пресет в списке.");
    return;
  }
  const payload = { name };
  for (const key of ["router_url", "api_key", "model", "proxy"]) {
    payload[key] = String(widget(node, key)?.value ?? "");
  }
  try {
    const res = await fetch("/vsl/router-presets/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(await res.text());
    }
    const data = await res.json();
    refreshPresetOptions(node, data.presets || {});
  } catch (err) {
    console.warn("[vsl] preset update failed:", err);
    window.alert(`Не удалось обновить пресет: ${err}`);
  }
}

async function deletePreset(node) {
  const preset = widget(node, "preset");
  const name = preset?.value;
  if (!name || name === "(none)") {
    window.alert("Сначала выберите пресет в списке.");
    return;
  }
  if (!window.confirm(`Удалить пресет "${name}"?`)) {
    return;
  }
  try {
    const res = await fetch("/vsl/router-presets/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) {
      throw new Error(await res.text());
    }
    const data = await res.json();
    refreshPresetOptions(node, data.presets || {});
  } catch (err) {
    console.warn("[vsl] preset delete failed:", err);
    window.alert(`Не удалось удалить пресет: ${err}`);
  }
}

app.registerExtension({
  name: "vsl.prompt_helper.widget_size",
  async nodeCreated(node) {
    if (node.comfyClass !== "vsl_prompt_helper") {
      return;
    }
    const extra = widget(node, "extra_prompt");
    const quality = widget(node, "quality_prompt");
    const negative = widget(node, "negative_prompt");
    setWidgetHeight(extra, 48);
    setWidgetHeight(quality, 88);
    setWidgetHeight(negative, 88);

    const preset = widget(node, "preset");
    if (preset) {
      const original = preset.callback;
      preset.callback = function (value, ...rest) {
        if (typeof original === "function") {
          original.call(this, value, ...rest);
        }
        applyPreset(node, value);
      };
    }

    const makeButton = (name, handler) => {
      const btn = node.addWidget("button", name, null, handler, { serialize: false });
      // Hide with the node's advanced fields (same flag as INPUT_TYPES advanced).
      btn.advanced = true;
      btn.options = btn.options || {};
      btn.options.advanced = true;
      return btn;
    };
    makeButton("Save preset", () => savePreset(node));
    makeButton("Update preset", () => updatePreset(node));
    makeButton("Delete preset", () => deletePreset(node));
  },
});
