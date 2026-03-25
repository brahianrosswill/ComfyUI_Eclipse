import { app } from './comfy/index.js';
import { notifyVue, smartResize } from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Video Resolution [Eclipse]';
app.registerExtension({
    name: 'Eclipse.VideoResolution',
    async beforeRegisterNodeDef(e, i, t) {
        if (i.name !== NODE_NAME) return;
        const o = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = o ? o.apply(this, arguments) : void 0,
                i = this,
                t = i.widgets?.find((e) => 'resolution' === e.name),
                n = i.widgets?.find((e) => 'width' === e.name),
                s = i.widgets?.find((e) => 'height' === e.name);
            if (!t || !n || !s) return (console.warn('[Eclipse.VideoResolution] Required widgets not found'), e);
            const d = (e, i) => {
                    e && ((e.hidden = !i), e.options && (e.options.hidden = !i));
                },
                p = (e) => {
                    const t = 'Custom' === e;
                    (d(n, t),
                        d(s, t),
                        notifyVue(i),
                        setTimeout(() => {
                            smartResize(i, { minWidth: 0, minHeight: 50, padding: 0 });
                        }, 50));
                },
                r = t.callback;
            return (
                (t.callback = function (e) {
                    (r && r.apply(this, arguments), p(e));
                }),
                setTimeout(() => {
                    p(t.value);
                }, 10),
                e
            );
        };
        const n = e.prototype.onConfigure;
        e.prototype.onConfigure = function (e) {
            n && n.apply(this, arguments);
            const i = this,
                t = i.widgets?.find((e) => 'resolution' === e.name);
            t &&
                setTimeout(() => {
                    const e = 'Custom' === t.value,
                        o = i.widgets?.find((e) => 'width' === e.name),
                        n = i.widgets?.find((e) => 'height' === e.name),
                        s = (e, i) => {
                            e && ((e.hidden = !i), e.options && (e.options.hidden = !i));
                        };
                    (s(o, e), s(n, e), notifyVue(i), smartResize(i, { minWidth: 0, minHeight: 50, padding: 0 }));
                }, 50);
        };
    },
});
