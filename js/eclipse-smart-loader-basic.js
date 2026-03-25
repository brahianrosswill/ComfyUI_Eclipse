import { app, api } from './comfy/index.js';
import {
    debounce,
    canvasDirtyBatcher,
    smartResize,
    createWidgetVisibilityManager,
} from './eclipse-widget-performance-utils.js';
import { fetchSharedModelFiles } from './eclipse-loader-shared.js';
const NODE_NAME = 'Smart Loader Basic [Eclipse]';
app.registerExtension({
    name: 'Eclipse.SmartLoaderBasic',
    async beforeRegisterNodeDef(e, n, i) {
        if (n.name !== NODE_NAME) return;
        const o = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = o ? o.apply(this, arguments) : void 0,
                n = this,
                i = createWidgetVisibilityManager(n),
                t = (e) => i.getValue(e),
                a = (e, n) => i.setVisible(e, n),
                c = {},
                s = {},
                l = () => {
                    if (-1 === n.id) return;
                    const e = t('model_type'),
                        i = t('configure_clip'),
                        o = t('configure_vae'),
                        l = t('configure_model_only_lora'),
                        r = t('clip_source'),
                        _ = parseInt(t('clip_count')) || 1,
                        p = t('vae_source'),
                        u = parseInt(t('lora_count')) || 3,
                        d = 'Standard Checkpoint' === e,
                        m = 'UNet Model' === e,
                        f = 'GGUF Model' === e,
                        g = 'External' === r,
                        v = 'External' === p;
                    ((() => {
                        const e = t('model_type'),
                            i = {
                                ckpt_name: {
                                    show: 'Standard Checkpoint' === e,
                                    extensions: ['.safetensors', '.ckpt', '.pt', '.bin', '.sft'],
                                },
                                unet_name: {
                                    show: 'UNet Model' === e,
                                    extensions: ['.safetensors', '.pt', '.bin', '.sft'],
                                },
                                gguf_name: { show: 'GGUF Model' === e, extensions: ['.gguf'] },
                            };
                        Object.entries(i).forEach(([e, i]) => {
                            const o = n.widgets?.find((n) => n.name === e);
                            if (!o || !o.options) return;
                            s[e] || (s[e] = [...o.options.values]);
                            const t = s[e].filter((e) => {
                                if ('None' === e) return !0;
                                const n = e.toLowerCase();
                                return i.extensions.some((e) => n.endsWith(e));
                            });
                            if (((o.options.values = t), !t.includes(o.value))) {
                                const e = o.value.replace(/\\/g, '/');
                                e !== o.value && t.includes(e) ? (o.value = e) : (o.value = 'None');
                            }
                        });
                    })(),
                        ['clip_name1', 'clip_name2', 'clip_name3', 'clip_name4'].forEach((e) => {
                            const i = n.widgets?.find((n) => n.name === e);
                            i && i.options && (c[e] || (c[e] = [...i.options.values]), (i.options.values = c[e]));
                        }),
                        a('ckpt_name', d),
                        a('unet_name', m),
                        a('gguf_name', f),
                        a('weight_dtype', m),
                        a('gguf_dequant_dtype', f),
                        a('gguf_patch_dtype', f),
                        a('gguf_patch_on_device', f),
                        a('model_device', !0),
                        a('clip_device', i),
                        a('vae_device', o),
                        a('clip_source', i),
                        a('clip_count', i && g),
                        a('clip_name1', i && g && _ >= 1),
                        a('clip_name2', i && g && _ >= 2),
                        a('clip_name3', i && g && _ >= 3),
                        a('clip_name4', i && g && _ >= 4),
                        a('clip_type', i && g),
                        a('enable_clip_layer', i && d),
                        a('stop_at_clip_layer', i && d),
                        a('vae_source', o),
                        a('vae_name', o && v),
                        a('lora_count', l));
                    for (let e = 1; e <= 3; e++) {
                        const n = l && e <= u;
                        (a(`lora_switch_${e}`, n), a(`lora_name_${e}`, n), a(`lora_weight_${e}`, n));
                    }
                    smartResize(n);
                },
                r = debounce(l, 100);
            [
                'model_type',
                'configure_clip',
                'configure_vae',
                'configure_model_only_lora',
                'clip_source',
                'clip_count',
                'vae_source',
                'lora_count',
            ].forEach((e) => {
                const i = n.widgets?.find((n) => n.name === e);
                if (i) {
                    const e = i.callback;
                    i.callback = function () {
                        (e && e.apply(this, arguments), r());
                    };
                }
            });
            const _ = async () => {
                try {
                    const i = await fetchSharedModelFiles();
                    if (!i) return;
                    const o = (e, i) => {
                            const o = n.widgets?.find((n) => n.name === e);
                            if (o && o.options && o.options.values) {
                                const e = o.options.values;
                                if (((o.options.values = i), !i.includes(o.value))) {
                                    const e = o.value.replace(/\\\\/g, '/');
                                    e !== o.value && i.includes(e) ? (o.value = e) : (o.value = i[0] || 'None');
                                }
                                i.filter((n) => !e.includes(n)).length;
                            }
                        };
                    (i.checkpoints && o('ckpt_name', i.checkpoints),
                        i.diffusion_models && o('unet_name', i.diffusion_models),
                        i.diffusion_models_gguf && o('gguf_name', i.diffusion_models_gguf),
                        i.vae && o('vae_name', i.vae),
                        i.clip_combined &&
                            (o('clip_name1', i.clip_combined),
                            o('clip_name2', i.clip_combined),
                            o('clip_name3', i.clip_combined),
                            o('clip_name4', i.clip_combined)),
                        i.loras && (o('lora_name_1', i.loras), o('lora_name_2', i.loras), o('lora_name_3', i.loras)),
                        canvasDirtyBatcher.markDirty(n, !0, !0));
                } catch (e) {
                    console.warn('[Smart Loader Basic] Failed to refresh model file lists:', e);
                }
            };
            setTimeout(() => {
                n._Eclipse_initialized || ((n._Eclipse_initialized = !0), l(), _());
            }, 0);
            n._Eclipse_refreshLists = _;
            const p = n.onConfigure;
            return (
                (n.onConfigure = function (e) {
                    (p && p.apply(this, arguments),
                        _(),
                        setTimeout(() => {
                            l();
                        }, 100));
                }),
                e
            );
        };
    },

    async refreshComboInNodes() {
        const nodes = app.graph?._nodes || [];
        for (const node of nodes) {
            if (node.type === NODE_NAME && node._Eclipse_refreshLists) {
                node._Eclipse_refreshLists();
            }
        }
    },
});
