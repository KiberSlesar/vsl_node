import { app } from "/scripts/app.js";
const ROOT = new URL("./", import.meta.url);
const START_H = 360;
const FAVORITES_TAB = "Favorites";
let indexPromise;
function loadIndex() {
  if (!indexPromise) indexPromise = fetch(new URL("clio-index.json", ROOT)).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });
  return indexPromise;
}

let favorites = new Set();
async function loadFavorites() {
  try {
    const res = await fetch("/vsl/style-favorites");
    const data = await res.json();
    favorites = new Set(data.favorites || []);
  } catch (e) {
    console.warn("[vsl] favorites load failed:", e);
  }
}
async function toggleFavorite(name) {
  try {
    const res = await fetch("/vsl/style-favorites/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await res.json();
    favorites = new Set(data.favorites || []);
  } catch (e) {
    console.warn("[vsl] favorite toggle failed:", e);
  }
}

app.registerExtension({
  name: "vsl.style.selector.gallery",
  async nodeCreated(node) {
    if (node.comfyClass !== "vsl_Style_Selector") return;
    let style = node.widgets?.find(w => w.name === "style");
    if (!style && node.addWidget) {
      style = node.addWidget("combo", "style", "", () => node.setDirtyCanvas(true, true));
    }
    if (style) {
      style.hidden = true;
      style.serialize = true;
      style.options ||= {};
      style.options.hidden = true;
      style.options.serialize = true;
      style.computeSize = () => [0, 0];
      style.draw = () => {};
    }
    const box = document.createElement("div");
    box.style.cssText = "width:100%;height:100%;display:flex;flex-direction:column;min-height:0;overflow:hidden;color:#ddd;font:12px sans-serif;padding:6px;box-sizing:border-box";
    const topRow = document.createElement("div");
    topRow.style.cssText = "display:flex;gap:5px;margin-bottom:5px;flex:0 0 auto";
    const categorySelect = document.createElement("select");
    categorySelect.style.cssText = "flex:1 1 auto;min-width:0;padding:6px;background:#333;color:#eee;border:1px solid #666";
    const mkZoomBtn = (text, title) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = text;
      b.title = title;
      b.style.cssText = "flex:0 0 auto;width:30px;padding:0;background:#333;color:#eee;border:1px solid #666;cursor:pointer;font:14px sans-serif;line-height:1";
      return b;
    };
    const zoomIn = mkZoomBtn("+", "Крупнее");
    const zoomOut = mkZoomBtn("−", "Мельче");
    topRow.append(categorySelect, zoomOut, zoomIn);
    let columns = parseInt(localStorage.getItem("vsl_style_zoom") || "4", 10);
    if (!Number.isFinite(columns)) columns = 4;
    columns = Math.min(8, Math.max(2, columns));
    const grid = document.createElement("div");
    grid.style.cssText = "display:grid;gap:5px;flex:1 1 auto;min-height:0;height:0;overflow-y:auto;overflow-x:hidden;align-content:start";
    const applyZoom = () => {
      grid.style.gridTemplateColumns = `repeat(${columns},minmax(0,1fr))`;
      try { localStorage.setItem("vsl_style_zoom", String(columns)); } catch (e) { /* ignore */ }
      zoomIn.disabled = columns <= 2;
      zoomOut.disabled = columns >= 8;
    };
    zoomIn.onclick = () => { if (columns > 2) { columns -= 1; applyZoom(); } };
    zoomOut.onclick = () => { if (columns < 8) { columns += 1; applyZoom(); } };
    applyZoom();
    const label = document.createElement("div");
    label.style.cssText = "padding-top:5px;flex:0 0 auto";
    const overlay = document.createElement("div");
    overlay.style.cssText = "display:none;position:absolute;inset:0;background:#111;z-index:5;cursor:pointer";
    const overlayImg = document.createElement("img");
    overlayImg.style.cssText = "width:100%;height:100%;object-fit:contain;display:block;pointer-events:none";
    overlay.append(overlayImg);
    overlay.onclick = () => { overlay.style.display = "none"; };
    box.style.position = "relative";
    box.append(topRow, grid, label, overlay);
    const widget = node.addDOMWidget("clio_gallery", "div", box, { serialize: false, getValue: () => "", setValue: () => {} });
    widget.computeSize = (width) => [width || 360, START_H];
    if (!node.size || node.size[1] < START_H + 40) node.setSize?.([node.size?.[0] || 360, START_H + 40]);
    let data, selectedCategory = "";
    categorySelect.onchange = () => { selectedCategory = categorySelect.value; refresh(); };
    function refresh() {
      if (!data) return;
      categorySelect.value = selectedCategory;
      const items = selectedCategory === FAVORITES_TAB
        ? data.styles.filter(s => favorites.has(s.name))
        : data.styles.filter(s => s.category === selectedCategory);
      grid.replaceChildren();
      for (const item of items) {
        const isSelected = item.name === style?.value;
        const tile = document.createElement("button");
        tile.type = "button";
        tile.title = item.name;
        tile.style.cssText = `padding:0;border:${isSelected ? "3px solid #e661ff;box-shadow:0 0 10px rgba(230,97,255,0.75)" : "2px solid #444"};background:#222;color:#eee;cursor:pointer;min-width:0;position:relative`;
        if (isSelected) {
          const check = document.createElement("div");
          check.textContent = "✓";
          check.style.cssText = "position:absolute;top:2px;left:2px;font:12px sans-serif;line-height:1.2;padding:0 3px;border-radius:4px;background:#e661ff;color:#fff;user-select:none;pointer-events:none";
          tile.append(check);
        }
        const im = document.createElement("img");
        im.src = new URL(item.image, ROOT).href;
        im.alt = item.name;
        im.style.cssText = "display:block;width:100%;aspect-ratio:1;object-fit:cover";
        const caption = document.createElement("span");
        caption.textContent = item.name;
        caption.style.cssText = "display:block;font:10px sans-serif;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:2px";
        const fav = document.createElement("div");
        fav.textContent = favorites.has(item.name) ? "★" : "☆";
        fav.title = favorites.has(item.name) ? "Remove from favorites" : "Add to favorites";
        fav.style.cssText = "position:absolute;top:2px;right:2px;cursor:pointer;font:14px sans-serif;line-height:1.2;padding:0 3px;border-radius:4px;background:rgba(0,0,0,0.55);color:#ffd24a;user-select:none";
        fav.onclick = async (e) => {
          e.stopPropagation();
          await toggleFavorite(item.name);
          refresh();
        };
        fav.ondblclick = (e) => { e.preventDefault(); e.stopPropagation(); };
        tile.append(im, caption, fav);
        tile.onclick = () => {
          if (style) {
            style.value = style.value === item.name ? "" : item.name;
            style.callback?.(style.value);
            node.setDirtyCanvas(true, true);
          }
          refresh();
        };
        tile.ondblclick = (e) => {
          if (e.target === fav) return;
          e.preventDefault();
          e.stopPropagation();
          overlayImg.src = im.src;
          overlayImg.alt = item.name;
          overlay.style.display = "block";
        };
        grid.append(tile);
      }
      label.textContent = `Selected: ${style?.value || "none"} · ${items.length} styles`;
    }
    await loadFavorites();
    try {
      data = await loadIndex();
      selectedCategory = data.styles.find(s => s.name === style?.value)?.category || data.categories[0] || "";
      categorySelect.replaceChildren(...[FAVORITES_TAB, ...data.categories].map(c => {
        const o = document.createElement("option");
        o.value = c;
        o.textContent = c;
        return o;
      }));
      categorySelect.value = selectedCategory;
      if (style) {
        style.options ||= {};
        style.options.values = ["", ...data.styles.map(s => s.name)];
      }
      refresh();
    } catch (e) {
      label.textContent = `Gallery error: ${e.message}`;
    }
  },
});
