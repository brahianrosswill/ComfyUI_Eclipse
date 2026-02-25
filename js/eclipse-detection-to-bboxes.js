/* eclipse-detection-to-bboxes.js - Minified for ComfyUI Eclipse */
import { app } from './comfy/index.js';
import { debounce, canvasDirtyBatcher, notifyVue, smartResize } from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Detection to Bboxes [Eclipse]';
app.registerExtension({
    name: 'Eclipse.DetectionToBboxes',
    async beforeRegisterNodeDef(e, i, t) {
        if (i.name !== NODE_NAME) return;
        const n = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = n ? n.apply(this, arguments) : void 0,
                i = this,
                t = (e, t) => {
                    const n = i.widgets?.find((i) => i.name === e);
                    n && ((n.hidden = !t), n.options && (n.options.hidden = !t));
                },
                o = (e) => {
                    const t = i.widgets?.find((i) => i.name === e);
                    return t ? t.value : null;
                },
                s = () => {
                    const e = o('get_mask_from_image'),
                        n = o('combine_masks');
                    (t('detect_color', e),
                        t('threshold', e),
                        t('min_area', e),
                        t('indices', !n),
                        notifyVue(i),
                        smartResize(i));
                },
                c = debounce(s, 100),
                a = i.widgets?.find((e) => 'get_mask_from_image' === e.name);
            if (a) {
                const e = a.callback;
                a.callback = function () {
                    (e && e.apply(this, arguments), c());
                };
            }
            const r = i.widgets?.find((e) => 'combine_masks' === e.name);
            if (r) {
                const e = r.callback;
                r.callback = function () {
                    (e && e.apply(this, arguments), c());
                };
            }
            i._Eclipse_initialized || ((i._Eclipse_initialized = !0), s());
            const d = i.onConfigure;
            return (
                (i.onConfigure = function (e) {
                    (d && d.apply(this, arguments),
                        setTimeout(() => {
                            s();
                        }, 100));
                }),
                e
            );
        };
    },
});
