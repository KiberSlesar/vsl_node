import { api } from "/scripts/api.js";
import { app } from "/scripts/app.js";

const NODE_NAME = "vsl_seed";
const MAX_SEED = 1125899906842624;

const RANDOMIZE_LABEL = "🎲 Randomize Each Time";
const NEW_FIXED_LABEL = "🎲 New Fixed Random";
const USE_LAST_LABEL = "♻️ (Use Last Queued Seed)";

function newRandomSeed() {
  return Math.floor(Math.random() * MAX_SEED) + 1;
}

// Exactly like rgthree: intercept the queue call, materialize the special
// seeds (-1 random, -2 increment, -3 decrement) into real numbers BEFORE the
// prompt is built, write them into the widget so the UI shows the seed that
// actually ran, and remember it for "Use Last Queued Seed".
function materializeSeeds() {
  for (const node of app.graph?._nodes ?? []) {
    if (node?.comfyClass !== NODE_NAME) continue;
    const w = node.widgets?.find((x) => x.name === "seed");
    if (!w) continue;
    let value = Number(w.value);
    if (node.__vslRandomize) {
      value = -1;
    }
    if (value === -1) {
      value = newRandomSeed();
    } else if (value === -2 || value === -3) {
      const base = typeof node.__vslLastSeed === "number" ? node.__vslLastSeed : 0;
      value = value === -2 ? Math.min(MAX_SEED, base + 1) : Math.max(0, base - 1);
    } else {
      node.__vslLastSeed = value;
      continue;
    }
    w.value = value;
    node.__vslLastSeed = value;
    node.setDirtyCanvas?.(true, true);
  }
}

let queueHijacked = false;
function hijackQueue() {
  if (queueHijacked) return;
  queueHijacked = true;
  const original = api.queuePrompt?.bind(api);
  if (!original) return;
  api.queuePrompt = async function (...args) {
    try {
      materializeSeeds();
    } catch (err) {
      console.warn("[vsl_seed] seed materialization failed:", err);
    }
    return original(...args);
  };
}

app.registerExtension({
  name: "vsl.seed.rgthree_clone",
  setup() {
    hijackQueue();
  },
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_NAME) return;
    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      origCreated?.apply(this, arguments);
      hijackQueue();
      const node = this;
      // rgthree Seed look
      node.color = node.color || "#223";
      node.bgcolor = node.bgcolor || "#335";

      const seedWidget = node.widgets?.find((w) => w.name === "seed");
      if (!seedWidget) return;

      const addButton = (label, title, handler) => {
        const btn = node.addWidget("button", label, null, handler, { serialize: false });
        btn.advanced = false;
        return btn;
      };

      const randomizeBtn = addButton(RANDOMIZE_LABEL, "Каждый прогон — новый случайный сид", () => {
        node.__vslRandomize = !node.__vslRandomize;
        randomizeBtn.name = RANDOMIZE_LABEL + (node.__vslRandomize ? " ✓" : "");
        if (node.__vslRandomize) {
          seedWidget.value = -1;
        } else {
          seedWidget.value = typeof node.__vslLastSeed === "number" ? node.__vslLastSeed : newRandomSeed();
        }
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });

      addButton(NEW_FIXED_LABEL, "Новый случайный сид и зафиксировать", () => {
        node.__vslRandomize = false;
        randomizeBtn.name = RANDOMIZE_LABEL;
        seedWidget.value = newRandomSeed();
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });

      addButton(USE_LAST_LABEL, "Вернуть сид последнего прогона", () => {
        const last = node.__vslLastSeed;
        if (last == null) {
          window.alert("Сид последнего прогона ещё не известен.");
          return;
        }
        node.__vslRandomize = false;
        randomizeBtn.name = RANDOMIZE_LABEL;
        seedWidget.value = last;
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });

      // Restore the randomize mode saved in the workflow (-1 sentinel).
      if (Number(seedWidget.value) === -1) {
        node.__vslRandomize = true;
        randomizeBtn.name = RANDOMIZE_LABEL + " ✓";
      }
    };
  },
});
