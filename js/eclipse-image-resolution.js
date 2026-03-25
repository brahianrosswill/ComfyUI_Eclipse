import { app } from './comfy/index.js';
import { notifyVue, smartResize } from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Image Resolution [Eclipse]';
app.registerExtension({
    name: 'Eclipse.ImageResolution',
    async beforeRegisterNodeDef(e, i, t) {
        if (i.name !== NODE_NAME) return;
        const n = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = n ? n.apply(this, arguments) : void 0,
                i = this,
                t = i.widgets?.find((e) => 'resolution' === e.name),
                o = i.widgets?.find((e) => 'width' === e.name),
                s = i.widgets?.find((e) => 'height' === e.name);
            if (!t || !o || !s) return (console.warn('[Eclipse.ImageResolution] Required widgets not found'), e);
            const d = (e, i) => {
                    e && ((e.hidden = !i), e.options && (e.options.hidden = !i));
                },
                a = (e) => {
                    const t = 'Custom' === e;
                    (d(o, t),
                        d(s, t),
                        notifyVue(i),
                        setTimeout(() => {
                            smartResize(i, { minWidth: 0, minHeight: 50, padding: 0 });
                        }, 50));
                },
                p = t.callback;
            return (
                (t.callback = function (e) {
                    (p && p.apply(this, arguments), a(e));
                }),
                setTimeout(() => {
                    a(t.value);
                }, 10),
                e
            );
        };
        const o = e.prototype.onConfigure;
        e.prototype.onConfigure = function (e) {
            o && o.apply(this, arguments);
            const i = this,
                t = i.widgets?.find((e) => 'resolution' === e.name);
            t &&
                setTimeout(() => {
                    const e = 'Custom' === t.value,
                        n = i.widgets?.find((e) => 'width' === e.name),
                        o = i.widgets?.find((e) => 'height' === e.name),
                        s = (e, i) => {
                            e && ((e.hidden = !i), e.options && (e.options.hidden = !i));
                        };
                    (s(n, e), s(o, e), notifyVue(i), smartResize(i, { minWidth: 0, minHeight: 50, padding: 0 }));
                }, 50);
        };
    },
});
