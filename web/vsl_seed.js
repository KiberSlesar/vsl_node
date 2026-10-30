import { app } from "/scripts/app.js";

const NODE_NAME = "vsl_seed";
const MAX_SEED = 1125899906842624;

const RANDOMIZE_LABEL = "🎲 Randomize Each Time";
const NEW_FIXED_LABEL = "🎲 New Fixed Random";
const USE_LAST_LABEL = "♻️ (Use Last Queued Seed)";

function newFixedRandom() {
  return Math.floor(Math.random() * MAX_SEED) + 1;
}

app.registerExtension({
  name: "vsl.seed.rgthree_clone",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_NAME) return;
    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      origCreated?.apply(this, arguments);
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

      // "Randomize Each Time": seed = -1 sentinel; the server (and the queue
      // pipeline) materialize a fresh random seed on every run.
      addButton(RANDOMIZE_LABEL, "Каждый прогон — новый случайный сид (seed = -1)", () => {
        seedWidget.value = -1;
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });

      // "New Fixed Random": freeze one concrete random seed now.
      addButton(NEW_FIXED_LABEL, "Новый случайный сид и зафиксировать", () => {
        seedWidget.value = newFixedRandom();
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });

      // "Use Last Queued Seed": bring back the seed of the previous run.
      addButton(USE_LAST_LABEL, "Вернуть сид последнего прогона", () => {
        const last = node.__vslLastSeed;
        if (last == null) {
          window.alert("Сид последнего прогона ещё не известен.");
          return;
        }
        seedWidget.value = last;
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });
    };

    const origExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function () {
      origExecuted?.apply(this, arguments);
      const seedWidget = this.widgets?.find((w) => w.name === "seed");
      const value = seedWidget?.value;
      if (typeof value === "number" && value >= 0) {
        this.__vslLastSeed = value;
      }
    };
  },
});
