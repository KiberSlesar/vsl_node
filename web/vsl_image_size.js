import { app } from "../../../scripts/app.js";
import { ComfyWidgets } from "../../../scripts/widgets.js";

app.registerExtension({
  name: "vsl.image_size.preview",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "vsl_image_size") {
      return;
    }

    function populate(text) {
      const value = Array.isArray(text) ? text[0] : text;
      const label = value == null ? "" : String(value);
      if (!this.widgets) {
        this.widgets = [];
      }
      let widget = this.widgets.find((w) => w.name === "size_info");
      if (!widget) {
        widget = ComfyWidgets.STRING(
          this,
          "size_info",
          ["STRING", { multiline: false }],
          app
        ).widget;
        widget.inputEl.readOnly = true;
        widget.inputEl.style.opacity = 0.85;
        widget.serializeValue = () => undefined;
      }
      widget.value = label;
      requestAnimationFrame(() => {
        const sz = this.computeSize();
        if (sz[0] < this.size[0]) {
          sz[0] = this.size[0];
        }
        if (sz[1] < this.size[1]) {
          sz[1] = this.size[1];
        }
        this.onResize?.(sz);
        app.graph.setDirtyCanvas(true, false);
      });
    }

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      populate.call(this, message?.text);
    };
  },
});
