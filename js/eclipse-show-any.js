import { app, ComfyWidgets } from './comfy/index.js';
const NODE_NAME = 'Show Any [Eclipse]';
app.registerExtension({
    name: 'Eclipse.showAny',
    async beforeRegisterNodeDef(t, s, i) {
        if (s.name !== NODE_NAME) return;
        function e(t) {
            if (this.widgets) {
                const t = this.widgets.findIndex((t) => 'text' === t.name);
                if (-1 !== t) {
                    for (let s = t; s < this.widgets.length; s++) this.widgets[s].onRemove?.();
                    this.widgets.length = t;
                }
            }
            for (const s of t) {
                const t = ComfyWidgets.STRING(this, 'text', ['STRING', { multiline: !0 }], i).widget;
                ((t.inputEl.readOnly = !0),
                    (t.inputEl.style.opacity = 0.6),
                    (t.inputEl.style.cursor = 'default'),
                    (t.value = s));
            }
            requestAnimationFrame(() => {
                const t = this.computeSize();
                (t[0] < this.size[0] && (t[0] = this.size[0]),
                    t[1] < this.size[1] && (t[1] = this.size[1]),
                    this.onResize?.(t),
                    i.graph.setDirtyCanvas(!0, !1));
            });
        }
        const o = t.prototype.onNodeCreated;
        t.prototype.onNodeCreated = function () {
            const t = o ? o.apply(this, arguments) : void 0,
                s = this,
                e = this.widgets?.find((t) => 'show_images' === t.name);
            if (e) {
                const t = e.callback;
                ((e.callback = function (e) {
                    (t && t.apply(this, arguments), (s.showImages = 'show' === e), i.graph.setDirtyCanvas(!0, !1));
                }),
                    (s.showImages = 'show' === e.value));
            }
            return t;
        };
        const n = t.prototype.onDrawBackground;
        t.prototype.onDrawBackground = function (t) {
            const s = this.imgs;
            (!1 === this.showImages && this.imgs && (this.imgs = null),
                n && n.apply(this, arguments),
                s && null === this.imgs && (this.imgs = s));
        };
        const h = t.prototype.onExecuted;
        t.prototype.onExecuted = function (t) {
            (h?.apply(this, arguments), t.text && e.call(this, t.text));
        };
        const a = t.prototype.onConfigure;
        t.prototype.onConfigure = function () {
            a?.apply(this, arguments);
            const t = this.widgets?.find((t) => 'show_images' === t.name);
            t && (this.showImages = 'show' === t.value);
        };
        const p = t.prototype.onConnectionsChange;
        t.prototype.onConnectionsChange = function () {
            p?.apply(this, arguments);
            const t = this.inputs?.some((t) => null !== t.link && void 0 !== t.link);
            if (!t) {
                if (this.widgets) {
                    const t = this.widgets.findIndex((t) => 'text' === t.name);
                    if (-1 !== t) {
                        for (let s = t; s < this.widgets.length; s++) this.widgets[s].onRemove?.();
                        this.widgets.length = t;
                    }
                }
                ((this.imgs = null), i.graph.setDirtyCanvas(!0, !1));
            }
        };
    },
});
