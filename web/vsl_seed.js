import { app } from "/scripts/app.js";

const NODE_NAME = "vsl_seed";
const MAX_SEED = 1125899906842624;

function randomSeed() {
  return Math.floor(Math.random() * MAX_SEED) + 1;
}

app.registerExtension({
  name: "vsl.seed.buttons",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData?.name !== NODE_NAME) return;
    const origCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      origCreated?.apply(this, arguments);
      const node = this;
      const seedWidget = node.widgets?.find((w) => w.name === "seed");
      if (!seedWidget) return;
      let lastSeed = null;

      const addButton = (label, title, handler) => {
        const btn = node.addWidget("button", label, null, () => handler(), { serialize: false });
        btn.advanced = false;
        return btn;
      };

      addButton("🎲 Random", "Новый случайный сид", () => {
        lastSeed = seedWidget.value;
        seedWidget.value = randomSeed();
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });
      addButton("+1", "Инкремент сида", () => {
        lastSeed = seedWidget.value;
        seedWidget.value = Math.min(MAX_SEED, (seedWidget.value || 0) + 1);
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });
      addButton("-1", "Декремент сида", () => {
        lastSeed = seedWidget.value;
        seedWidget.value = (seedWidget.value || 0) - 1;
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });
      addButton("♻ Last", "Вернуть предыдущий сид", () => {
        if (lastSeed == null) return;
        const current = seedWidget.value;
        seedWidget.value = lastSeed;
        lastSeed = current;
        seedWidget.callback?.(seedWidget.value);
        node.setDirtyCanvas?.(true, true);
      });
    };
  },
});
