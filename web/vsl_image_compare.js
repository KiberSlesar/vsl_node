import { api } from "/scripts/api.js";
import { app } from "/scripts/app.js";

const NODE_NAME = "vsl_image_compare";
const PANEL_WIDGET = "vsl_compare_panel";
const MIN_HEIGHT = 180;

function ensureCss() {
  if (document.getElementById("vsl-compare-css")) return;
  const style = document.createElement("style");
  style.id = "vsl-compare-css";
  style.textContent = `
.vsl-cmp-root{box-sizing:border-box;width:100%;height:100%;display:flex;flex-direction:column;gap:4px;padding:4px;color:#bbb;font:11px/1.3 sans-serif;overflow:hidden;}
.vsl-cmp-stage{position:relative;flex:1 1 auto;min-height:110px;overflow:hidden;border:1px solid #555;border-radius:4px;background:#1c1c1c;touch-action:none;}
.vsl-cmp-stage img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;user-select:none;-webkit-user-drag:none;}
.vsl-cmp-stage.is-empty img{visibility:hidden;}
.vsl-cmp-seam{position:absolute;top:0;bottom:0;z-index:2;width:1px;margin-left:-0.5px;background:#aaa;opacity:0;pointer-events:none;}
.vsl-cmp-status{position:absolute;inset:0;z-index:3;display:flex;align-items:center;justify-content:center;color:#888;pointer-events:none;}
.vsl-cmp-status:empty{display:none;}
.vsl-cmp-badges span{position:absolute;top:6px;z-index:3;width:20px;height:20px;border-radius:3px;background:rgba(0,0,0,.6);color:#ccc;font-weight:600;text-align:center;line-height:20px;pointer-events:none;}
.vsl-cmp-badges span[hidden]{display:none;}
.vsl-cmp-footer{display:flex;align-items:center;gap:6px;flex:none;height:22px;}
.vsl-cmp-caption{flex:1;min-width:0;color:#888;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.vsl-cmp-tools{display:flex;gap:4px;flex:none;}
.vsl-cmp-tools button{padding:2px 8px;background:#3a3a3a;color:#ccc;border:1px solid #555;border-radius:3px;cursor:pointer;font:10px/1.3 sans-serif;}
.vsl-cmp-tools button:hover{background:#4a4a4a;}
.vsl-cmp-tools button.active{background:#666;color:#fff;border-color:#888;}
`;
  document.head.appendChild(style);
}

function clampFraction(x) {
  return Math.max(0, Math.min(1, x));
}

function applyClip(state) {
  const f = clampFraction(state.fraction);
  state.imageA.style.clipPath = `inset(0 ${((1 - f) * 100).toFixed(2)}% 0 0)`;
  state.seam.style.left = `${(f * 100).toFixed(2)}%`;
  state.seam.style.opacity = f > 0 && f < 1 ? "1" : "0";
  const width = state.stage.clientWidth || 0;
  const place = (badge, left) => {
    badge.hidden = left == null;
    if (left != null) badge.style.left = `${left}px`;
  };
  if (f <= 0) {
    place(state.badgeA, null);
    place(state.badgeB, Math.round((width - 20) / 2));
  } else if (f >= 1) {
    place(state.badgeA, Math.round((width - 20) / 2));
    place(state.badgeB, null);
  } else {
    const seam = f * width;
    place(state.badgeA, Math.round(seam - 25) >= 4 ? Math.round(seam - 25) : null);
    place(state.badgeB, Math.round(seam + 5) + 20 <= width - 4 ? Math.round(seam + 5) : null);
  }
}

function updateButtons(state) {
  const mode = state.node.properties?.vsl_compare_mode || "slide";
  state.slideBtn.classList.toggle("active", mode === "slide");
  state.aBtn.classList.toggle("active", mode === "toggle" && !state.showingB);
  state.bBtn.classList.toggle("active", mode === "toggle" && state.showingB);
}

function setEmpty(state, text) {
  state.stage.classList.add("is-empty");
  state.status.textContent = text;
  state.caption.textContent = "";
}

function setReady(state) {
  state.stage.classList.remove("is-empty");
  state.status.textContent = "";
  const a = state.refs?.a || {};
  const b = state.refs?.b || {};
  state.caption.textContent = a.width > 0
    ? (b.width > 0 && (b.width !== a.width || b.height !== a.height)
        ? `A ${a.width}×${a.height} · B ${b.width}×${b.height}`
        : `${a.width}×${a.height}`)
    : "";
}

function loadPreviews(state, refs) {
  state.refs = refs;
  state.loaded = 0;
  setEmpty(state, "Загрузка превью…");
  const q = (r) => `filename=${encodeURIComponent(r.filename)}&subfolder=${encodeURIComponent(r.subfolder || "")}&type=temp`;
  state.imageA.src = api.apiURL(`/view?${q(refs.a)}`);
  state.imageB.src = api.apiURL(`/view?${q(refs.b)}`);
}

function findCompareImages(message) {
  const a = message?.a_images?.[0] ?? null;
  const b = message?.b_images?.[0] ?? null;
  return a?.filename && b?.filename ? { a, b } : null;
}

function buildPanel(node) {
  if (node.__vslCompare) return node.__vslCompare;
  ensureCss();

  const root = document.createElement("div");
  root.className = "vsl-cmp-root";
  const stage = document.createElement("div");
  stage.className = "vsl-cmp-stage is-empty";
  const imageB = document.createElement("img");
  const imageA = document.createElement("img");
  const seam = document.createElement("div");
  seam.className = "vsl-cmp-seam";
  const status = document.createElement("div");
  status.className = "vsl-cmp-status";
  status.textContent = "Запустите ноду — появятся превью A/B";
  const badges = document.createElement("div");
  badges.className = "vsl-cmp-badges";
  const badgeA = document.createElement("span");
  const badgeB = document.createElement("span");
  badgeA.textContent = "A";
  badgeB.textContent = "B";
  badges.append(badgeA, badgeB);
  stage.append(imageB, imageA, seam, status, badges);

  const footer = document.createElement("div");
  footer.className = "vsl-cmp-footer";
  const caption = document.createElement("div");
  caption.className = "vsl-cmp-caption";
  const tools = document.createElement("div");
  tools.className = "vsl-cmp-tools";
  const mkBtn = (text, title) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.title = title;
    return b;
  };
  const slideBtn = mkBtn("SLIDE", "Шторка следует за курсором");
  const aBtn = mkBtn("A", "Показать только A");
  const bBtn = mkBtn("B", "Показать только B");
  tools.append(slideBtn, aBtn, bBtn);
  footer.append(caption, tools);
  root.append(stage, footer);

  const widget = node.addDOMWidget(PANEL_WIDGET, "vsl_compare", root, {
    serialize: false,
    hideOnZoom: false,
    getMinHeight: () => MIN_HEIGHT,
  });
  widget.serialize = false;
  widget.computeSize = (width) => [width || 360, Math.max(MIN_HEIGHT, node.size?.[1] || MIN_HEIGHT)];
  if (!node.size || node.size[1] < MIN_HEIGHT + 40) node.setSize?.([node.size?.[0] || 360, MIN_HEIGHT + 60]);

  const state = (node.__vslCompare = {
    node, stage, imageA, imageB, seam, status, caption, badgeA, badgeB,
    slideBtn, aBtn, bBtn, refs: null, fraction: 1, loaded: 0, showingB: false,
  });
  applyClip(state);
  updateButtons(state);

  const modeOf = () => node.properties?.vsl_compare_mode || "slide";
  slideBtn.addEventListener("click", (e) => {
    e.preventDefault(); e.stopPropagation();
    node.properties ??= {};
    node.properties.vsl_compare_mode = "slide";
    state.showingB = false;
    state.fraction = 1;
    applyClip(state);
    updateButtons(state);
    node.setDirtyCanvas?.(true, true);
  });
  for (const [btn, showingB] of [[aBtn, false], [bBtn, true]]) {
    btn.addEventListener("click", (e) => {
      e.preventDefault(); e.stopPropagation();
      node.properties ??= {};
      node.properties.vsl_compare_mode = "toggle";
      node.properties.vsl_compare_side = showingB ? "B" : "A";
      state.showingB = showingB;
      state.fraction = showingB ? 0 : 1;
      applyClip(state);
      updateButtons(state);
      node.setDirtyCanvas?.(true, true);
    });
  }

  stage.addEventListener("pointermove", (e) => {
    if (tools.contains(e.target)) return;
    if (!state.refs || modeOf() !== "slide") return;
    const rect = stage.getBoundingClientRect();
    state.fraction = clampFraction((e.clientX - rect.left) / rect.width);
    applyClip(state);
  });
  stage.addEventListener("pointerleave", (e) => {
    if (!state.refs || modeOf() !== "slide") return;
    const rect = stage.getBoundingClientRect();
    const f = (e.clientX - rect.left) / rect.width;
    state.fraction = f < 0.5 ? 0 : 1;
    applyClip(state);
  });

  const onLoad = () => {
    state.loaded += 1;
    if (state.loaded >= 2) {
      setReady(state);
      node.setDirtyCanvas?.(true, true);
    }
  };
  imageA.addEventListener("load", onLoad);
  imageB.addEventListener("load", onLoad);
  const onError = () => setEmpty(state, "Не удалось загрузить превью");
  imageA.addEventListener("error", onError);
  imageB.addEventListener("error", onError);

  return state;
}

app.registerExtension({
  name: "vsl.image_compare.panel",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_NAME) return;
    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      origCreated?.apply(this, arguments);
      buildPanel(this);
    };
    const origExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      origExecuted?.apply(this, arguments);
      const state = buildPanel(this);
      const refs = findCompareImages(message);
      if (refs) loadPreviews(state, refs);
      else setEmpty(state, "Прогона не было сравнения превью");
      app.canvas?.setDirty?.(true, true);
    };
    const origConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      origConfigure?.apply(this, arguments);
      queueMicrotask(() => {
        const state = buildPanel(this);
        state.showingB = this.properties?.vsl_compare_side === "B";
        if ((this.properties?.vsl_compare_mode || "slide") === "toggle") {
          state.fraction = state.showingB ? 0 : 1;
        }
        applyClip(state);
        updateButtons(state);
      });
    };
    const origRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      origRemoved?.apply(this, arguments);
      this.__vslCompare = null;
    };
  },
});
