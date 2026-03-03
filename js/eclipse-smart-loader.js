/* eclipse-smart-loader.js - Minified for ComfyUI Eclipse */
import { app, api } from './comfy/index.js';
import {
    debounce,
    canvasDirtyBatcher,
    notifyVue,
    smartResize,
    createWidgetVisibilityManager,
} from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Smart Loader [Eclipse]';
let _pendingTemplateListFetch = null,
    _pendingModelFilesFetch = null;
async function fetchSharedTemplateList() {
    if (_pendingTemplateListFetch) return _pendingTemplateListFetch;
    const e = Date.now();
    return (
        (_pendingTemplateListFetch = fetch(`/eclipse/loader_templates_list?v=${e}`)
            .then((e) => (e.ok ? e.json() : null))
            .catch((e) => (console.error('Failed to fetch template list:', e), null))
            .finally(() => {
                _pendingTemplateListFetch = null;
            })),
        _pendingTemplateListFetch
    );
}
async function fetchSharedModelFiles() {
    if (_pendingModelFilesFetch) return _pendingModelFilesFetch;
    const e = Date.now();
    return (
        (_pendingModelFilesFetch = fetch(`/eclipse/model_files_all?v=${e}`)
            .then((e) => (e.ok ? e.json() : null))
            .catch((e) => (console.warn('[Smart Loader] Failed to fetch model files:', e), null))
            .finally(() => {
                _pendingModelFilesFetch = null;
            })),
        _pendingModelFilesFetch
    );
}
const TEMPLATE_CHANGED_EVENT = 'eclipse-loader-templates-changed';
function broadcastTemplateListChanged(e, n) {
    e && document.dispatchEvent(new CustomEvent(TEMPLATE_CHANGED_EVENT, { detail: { templates: e, sourceNodeId: n } }));
}
app.registerExtension({
    name: 'Eclipse.SmartLoader',
    async beforeRegisterNodeDef(e, n, a) {
        if (n.name !== NODE_NAME) return;
        const t = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = t ? t.apply(this, arguments) : void 0,
                n = this,
                a = createWidgetVisibilityManager(n);
            let o = 'None',
                i = 'None',
                _ = !1;
            const l = async () => {
                    try {
                        const e = await fetchSharedTemplateList();
                        if (e) {
                            const a = n.widgets?.find((e) => 'template_name' === e.name);
                            a &&
                                a.options &&
                                a.options.values &&
                                ((a.options.values = e),
                                e.includes(a.value) || (a.value = 'None'),
                                canvasDirtyBatcher.markDirty(n, !0, !0));
                        }
                        return e;
                    } catch (e) {
                        return (console.error('Failed to refresh template list:', e), null);
                    }
                },
                s = async () => {
                    try {
                        const e = await fetchSharedModelFiles();
                        if (!e) return;
                        const a = (e, a) => {
                            const t = n.widgets?.find((n) => n.name === e);
                            if (t && t.options && t.options.values) {
                                const e = t.options.values;
                                if (((t.options.values = a), !a.includes(t.value))) {
                                    const e = t.value.replace(/\\/g, '/');
                                    e !== t.value && a.includes(e) ? (t.value = e) : (t.value = a[0] || 'None');
                                }
                                a.filter((n) => !e.includes(n)).length;
                            }
                        };
                        (e.checkpoints && a('ckpt_name', e.checkpoints),
                            e.diffusion_models &&
                                (a('unet_name', e.diffusion_models),
                                a('nunchaku_name', e.diffusion_models),
                                a('qwen_name', e.diffusion_models)),
                            e.diffusion_models_gguf && a('gguf_name', e.diffusion_models_gguf),
                            e.vae && a('vae_name', e.vae),
                            e.clip_combined &&
                                (a('clip_name1', e.clip_combined),
                                a('clip_name2', e.clip_combined),
                                a('clip_name3', e.clip_combined),
                                a('clip_name4', e.clip_combined)),
                            e.loras &&
                                (a('lora_name_1', e.loras), a('lora_name_2', e.loras), a('lora_name_3', e.loras)),
                            canvasDirtyBatcher.markDirty(n, !0, !0));
                    } catch (e) {
                        console.warn('[Smart Loader] Failed to refresh model file lists:', e);
                    }
                },
                c = async () => {
                    const e = g('template_action'),
                        a = g('template_name'),
                        t = g('new_template_name');
                    if ((await l(), 'None' === e))
                        (d('template_name', 'None'),
                            d('new_template_name', ''),
                            d('model_type', 'Standard Checkpoint'),
                            d('ckpt_name', 'None'),
                            d('unet_name', 'None'),
                            d('nunchaku_name', 'None'),
                            d('qwen_name', 'None'),
                            d('zimage_name', 'None'),
                            d('gguf_name', 'None'),
                            d('weight_dtype', 'default'),
                            d('data_type', 'bfloat16'),
                            d('cache_threshold', 0),
                            d('attention', 'flash-attention2'),
                            d('i2f_mode', 'enabled'),
                            d('cpu_offload', 'auto'),
                            d('num_blocks_on_gpu', 30),
                            d('use_pin_memory', 'enable'),
                            d('gguf_dequant_dtype', 'default'),
                            d('gguf_patch_dtype', 'default'),
                            d('gguf_patch_on_device', !1),
                            d('configure_clip', !0),
                            d('configure_vae', !0),
                            d('configure_model_only_lora', !1),
                            d('configure_model_sampling', !1),
                            d('sampling_method', 'None'),
                            d('sampling_subtype', 'eps'),
                            d('shift', 3),
                            d('base_shift', 0.5),
                            d('sampling_width', 1024),
                            d('sampling_height', 1024),
                            d('original_timesteps', 50),
                            d('zsnr', !1),
                            d('sigma_max', 120),
                            d('sigma_min', 0.002),
                            d('clip_source', 'Baked'),
                            d('clip_count', '1'),
                            d('clip_name1', 'None'),
                            d('clip_name2', 'None'),
                            d('clip_name3', 'None'),
                            d('clip_name4', 'None'),
                            d('clip_type', 'flux'),
                            d('enable_clip_layer', !0),
                            d('stop_at_clip_layer', -2),
                            d('vae_source', 'Baked'),
                            d('vae_name', 'None'),
                            d('lora_count', '1'),
                            d('lora_switch_1', !1),
                            d('lora_name_1', 'None'),
                            d('lora_weight_1', 1),
                            d('lora_switch_2', !1),
                            d('lora_name_2', 'None'),
                            d('lora_weight_2', 1),
                            d('lora_switch_3', !1),
                            d('lora_name_3', 'None'),
                            d('lora_weight_3', 1),
                            d('model_device', 'auto'),
                            d('clip_device', 'auto'),
                            d('vae_device', 'auto'),
                            d('memory_cleanup', !0),
                            v(),
                            console.log('[Smart Loader] ✓ All fields reset to defaults'));
                    else if ('Load' === e && a && 'None' !== a) await u(a);
                    else if ('Save' === e && t && t.trim()) {
                        const e = t.trim(),
                            a = (() => {
                                const e = {},
                                    n = g('model_type'),
                                    a = g('configure_clip'),
                                    t = g('configure_vae'),
                                    o = g('configure_model_only_lora'),
                                    i = g('configure_model_sampling');
                                if (
                                    ((e.model_type = n),
                                    (e.configure_clip = a),
                                    (e.configure_vae = t),
                                    (e.configure_model_only_lora = o),
                                    (e.configure_model_sampling = i),
                                    'Standard Checkpoint' === n)
                                ) {
                                    const n = g('ckpt_name');
                                    n && 'None' !== n && (e.ckpt_name = n);
                                } else if ('UNet Model' === n) {
                                    const n = g('unet_name');
                                    (n && 'None' !== n && (e.unet_name = n), (e.weight_dtype = g('weight_dtype')));
                                } else if ('Nunchaku Flux' === n) {
                                    const n = g('nunchaku_name');
                                    (n && 'None' !== n && (e.nunchaku_name = n),
                                        (e.data_type = g('data_type')),
                                        (e.cache_threshold = g('cache_threshold')),
                                        (e.attention = g('attention')),
                                        (e.i2f_mode = g('i2f_mode')),
                                        (e.cpu_offload = g('cpu_offload')));
                                } else if ('Nunchaku Qwen' === n) {
                                    const n = g('qwen_name');
                                    (n && 'None' !== n && (e.qwen_name = n),
                                        (e.cpu_offload = g('cpu_offload')),
                                        (e.num_blocks_on_gpu = g('num_blocks_on_gpu')),
                                        (e.use_pin_memory = g('use_pin_memory')));
                                } else if ('Nunchaku ZImage' === n) {
                                    const n = g('zimage_name');
                                    (n && 'None' !== n && (e.zimage_name = n),
                                        (e.cpu_offload = g('cpu_offload')),
                                        (e.num_blocks_on_gpu = g('num_blocks_on_gpu')),
                                        (e.use_pin_memory = g('use_pin_memory')));
                                } else if ('GGUF Model' === n) {
                                    const n = g('gguf_name');
                                    (n && 'None' !== n && (e.gguf_name = n),
                                        (e.gguf_dequant_dtype = g('gguf_dequant_dtype')),
                                        (e.gguf_patch_dtype = g('gguf_patch_dtype')),
                                        (e.gguf_patch_on_device = g('gguf_patch_on_device')));
                                }
                                if (a) {
                                    const a = g('clip_source');
                                    if (
                                        ((e.clip_source = a),
                                        'Standard Checkpoint' === n &&
                                            ((e.enable_clip_layer = g('enable_clip_layer')),
                                            (e.stop_at_clip_layer = g('stop_at_clip_layer'))),
                                        'External' === a)
                                    ) {
                                        ((e.clip_count = g('clip_count')), (e.clip_type = g('clip_type')));
                                        for (let n = 1; n <= 4; n++) {
                                            const a = g(`clip_name${n}`);
                                            a && 'None' !== a && (e[`clip_name${n}`] = a);
                                        }
                                    }
                                }
                                if (t) {
                                    const n = g('vae_source');
                                    if (((e.vae_source = n), 'External' === n)) {
                                        const n = g('vae_name');
                                        n && 'None' !== n && (e.vae_name = n);
                                    }
                                }
                                if (o) {
                                    e.lora_count = g('lora_count');
                                    for (let n = 1; n <= 3; n++)
                                        ((e[`lora_switch_${n}`] = g(`lora_switch_${n}`)),
                                            (e[`lora_name_${n}`] = g(`lora_name_${n}`)),
                                            (e[`lora_weight_${n}`] = g(`lora_weight_${n}`)));
                                }
                                if (i) {
                                    const n = g('sampling_method');
                                    ((e.sampling_method = n),
                                        (e.shift = g('shift')),
                                        ('Flux' !== n && 'LTXV' !== n) || (e.base_shift = g('base_shift')),
                                        'Flux' === n
                                            ? ((e.sampling_width = g('sampling_width')),
                                              (e.sampling_height = g('sampling_height')))
                                            : 'LCM' === n
                                              ? ((e.original_timesteps = g('original_timesteps')), (e.zsnr = g('zsnr')))
                                              : 'ContinuousEDM' === n
                                                ? ((e.sampling_subtype = g('sampling_subtype')),
                                                  (e.sigma_max = g('sigma_max')),
                                                  (e.sigma_min = g('sigma_min')))
                                                : 'ContinuousV' === n &&
                                                  ((e.sigma_max = g('sigma_max')), (e.sigma_min = g('sigma_min'))));
                                }
                                return e;
                            })();
                        try {
                            const t = await api.fetchApi('/eclipse/loader_templates/save', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ name: e, config: a }),
                                }),
                                o = await t.json();
                            if (o.success) {
                                (broadcastTemplateListChanged(await l(), n.id),
                                    d('template_action', 'Load'),
                                    d('template_name', e),
                                    d('new_template_name', ''),
                                    v());
                            } else console.error(`[Smart Loader] Save failed: ${o.error}`);
                        } catch (e) {
                            console.error('[Smart Loader] Save request failed:', e);
                        }
                    }
                },
                C = async () => {
                    const a = g('template_name');
                    if (!a || 'None' === a) return;
                    try {
                        const e = await api.fetchApi('/eclipse/loader_templates/delete', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ name: a }),
                            }),
                            t = await e.json();
                        if (t.success) {
                            (broadcastTemplateListChanged(await l(), n.id),
                                d('template_name', 'None'),
                                d('new_template_name', ''),
                                d('model_type', 'Standard Checkpoint'),
                                d('ckpt_name', 'None'),
                                d('unet_name', 'None'),
                                d('nunchaku_name', 'None'),
                                d('qwen_name', 'None'),
                                d('zimage_name', 'None'),
                                d('gguf_name', 'None'),
                                d('weight_dtype', 'default'),
                                d('data_type', 'bfloat16'),
                                d('cache_threshold', 0),
                                d('attention', 'flash-attention2'),
                                d('i2f_mode', 'enabled'),
                                d('cpu_offload', 'auto'),
                                d('num_blocks_on_gpu', 30),
                                d('use_pin_memory', 'enable'),
                                d('gguf_dequant_dtype', 'default'),
                                d('gguf_patch_dtype', 'default'),
                                d('gguf_patch_on_device', !1),
                                d('configure_clip', !0),
                                d('configure_vae', !0),
                                d('configure_model_only_lora', !1),
                                d('configure_model_sampling', !1),
                                d('sampling_method', 'None'),
                                d('sampling_subtype', 'eps'),
                                d('shift', 3),
                                d('base_shift', 0.5),
                                d('sampling_width', 1024),
                                d('sampling_height', 1024),
                                d('original_timesteps', 50),
                                d('zsnr', !1),
                                d('sigma_max', 120),
                                d('sigma_min', 0.002),
                                d('clip_source', 'Baked'),
                                d('clip_count', '1'),
                                d('clip_name1', 'None'),
                                d('clip_name2', 'None'),
                                d('clip_name3', 'None'),
                                d('clip_name4', 'None'),
                                d('clip_type', 'flux'),
                                d('enable_clip_layer', !0),
                                d('stop_at_clip_layer', -2),
                                d('vae_source', 'Baked'),
                                d('vae_name', 'None'),
                                d('lora_count', '1'),
                                d('lora_switch_1', !1),
                                d('lora_name_1', 'None'),
                                d('lora_weight_1', 1),
                                d('lora_switch_2', !1),
                                d('lora_name_2', 'None'),
                                d('lora_weight_2', 1),
                                d('lora_switch_3', !1),
                                d('lora_name_3', 'None'),
                                d('lora_weight_3', 1),
                                d('model_device', 'auto'),
                                d('clip_device', 'auto'),
                                d('vae_device', 'auto'),
                                d('memory_cleanup', !0),
                                v(),
                                console.log('[Smart Loader] ✓ Template deleted, fields reset'));
                        } else console.error(`[Smart Loader] Delete failed: ${t.error}`);
                    } catch (e) {
                        console.error('[Smart Loader] Delete request failed:', e);
                    }
                };
            let m = null;
            const p = { None: '🔄 Reset Template Fields', Load: '🗑️ Delete Template', Save: '💾 Save Template' },
                d = (e, a) => {
                    const t = n.widgets?.find((n) => n.name === e);
                    if (t)
                        if (
                            'toggle' === t.type ||
                            e.includes('_switch_') ||
                            e.startsWith('configure_') ||
                            e.includes('enable_')
                        ) {
                            const e = Boolean(a);
                            (_ || t.value !== e) && ((t.value = e), t.callback && !_ && t.callback(e));
                        } else {
                            if ('string' == typeof a && a.includes('\\') && t.options?.values) {
                                const e = a.replace(/\\\\/g, '/');
                                t.options.values.includes(e) && (a = e);
                            }
                            t.value !== a && ((t.value = a), t.callback && !_ && t.callback(a));
                        }
                },
                u = async (e) => {
                    const a = await (async (e) => {
                        if (!e || 'None' === e) return null;
                        try {
                            const n = new Date().getTime(),
                                a = await fetch(`/eclipse/loader_templates/${e}.json?t=${n}`, { cache: 'no-store' });
                            if (a.ok) return await a.json();
                        } catch (n) {
                            console.error(`Failed to load template ${e}:`, n);
                        }
                        return null;
                    })(e);
                    if (a) {
                        _ = !0;
                        try {
                            (d('model_type', 'Standard Checkpoint'),
                                d('ckpt_name', 'None'),
                                d('unet_name', 'None'),
                                d('nunchaku_name', 'None'),
                                d('qwen_name', 'None'),
                                d('gguf_name', 'None'),
                                d('weight_dtype', 'default'),
                                d('data_type', 'bfloat16'),
                                d('cache_threshold', 0),
                                d('attention', 'flash-attention2'),
                                d('i2f_mode', 'enabled'),
                                d('cpu_offload', 'auto'),
                                d('num_blocks_on_gpu', 30),
                                d('use_pin_memory', 'enable'),
                                d('gguf_dequant_dtype', 'default'),
                                d('gguf_patch_dtype', 'default'),
                                d('gguf_patch_on_device', !1),
                                d('configure_clip', !0),
                                d('configure_vae', !0),
                                d('configure_model_only_lora', !1),
                                d('configure_model_sampling', !1),
                                d('sampling_method', 'None'),
                                d('shift', 3),
                                d('base_shift', 0.5),
                                d('sampling_width', 1024),
                                d('sampling_height', 1024),
                                d('clip_source', 'Baked'),
                                d('clip_count', '1'),
                                d('clip_name1', 'None'),
                                d('clip_name2', 'None'),
                                d('clip_name3', 'None'),
                                d('clip_name4', 'None'),
                                d('clip_type', 'flux'),
                                d('enable_clip_layer', !0),
                                d('stop_at_clip_layer', -2),
                                d('vae_source', 'Baked'),
                                d('vae_name', 'None'),
                                d('lora_count', '1'));
                            for (let e = 1; e <= 3; e++)
                                (d(`lora_switch_${e}`, !1), d(`lora_name_${e}`, 'None'), d(`lora_weight_${e}`, 1));
                            (void 0 !== a.model_type && d('model_type', a.model_type),
                                void 0 !== a.weight_dtype && d('weight_dtype', a.weight_dtype),
                                void 0 !== a.model_type && d('model_type', a.model_type),
                                void 0 !== a.weight_dtype && d('weight_dtype', a.weight_dtype),
                                void 0 !== a.configure_clip && d('configure_clip', a.configure_clip),
                                void 0 !== a.configure_vae && d('configure_vae', a.configure_vae),
                                void 0 !== a.configure_model_only_lora &&
                                    d('configure_model_only_lora', a.configure_model_only_lora),
                                void 0 !== a.configure_model_sampling &&
                                    d('configure_model_sampling', a.configure_model_sampling),
                                void 0 !== a.sampling_method && d('sampling_method', a.sampling_method),
                                void 0 !== a.sampling_subtype && d('sampling_subtype', a.sampling_subtype),
                                void 0 !== a.shift && d('shift', a.shift),
                                void 0 !== a.base_shift && d('base_shift', a.base_shift),
                                void 0 !== a.sampling_width && d('sampling_width', a.sampling_width),
                                void 0 !== a.sampling_height && d('sampling_height', a.sampling_height),
                                void 0 !== a.original_timesteps && d('original_timesteps', a.original_timesteps),
                                void 0 !== a.zsnr && d('zsnr', a.zsnr),
                                void 0 !== a.sigma_max && d('sigma_max', a.sigma_max),
                                void 0 !== a.sigma_min && d('sigma_min', a.sigma_min),
                                void 0 !== a.data_type && d('data_type', a.data_type),
                                void 0 !== a.cache_threshold && d('cache_threshold', a.cache_threshold),
                                void 0 !== a.attention && d('attention', a.attention),
                                void 0 !== a.i2f_mode && d('i2f_mode', a.i2f_mode),
                                void 0 !== a.cpu_offload && d('cpu_offload', a.cpu_offload),
                                void 0 !== a.num_blocks_on_gpu && d('num_blocks_on_gpu', a.num_blocks_on_gpu),
                                void 0 !== a.use_pin_memory && d('use_pin_memory', a.use_pin_memory),
                                void 0 !== a.gguf_dequant_dtype && d('gguf_dequant_dtype', a.gguf_dequant_dtype),
                                void 0 !== a.gguf_patch_dtype && d('gguf_patch_dtype', a.gguf_patch_dtype),
                                void 0 !== a.gguf_patch_on_device && d('gguf_patch_on_device', a.gguf_patch_on_device),
                                void 0 !== a.clip_source && d('clip_source', a.clip_source),
                                void 0 !== a.clip_count && d('clip_count', a.clip_count),
                                void 0 !== a.clip_name1 && d('clip_name1', a.clip_name1),
                                void 0 !== a.clip_name2 && d('clip_name2', a.clip_name2),
                                void 0 !== a.clip_name3 && d('clip_name3', a.clip_name3),
                                void 0 !== a.clip_name4 && d('clip_name4', a.clip_name4),
                                void 0 !== a.clip_type && d('clip_type', a.clip_type),
                                void 0 !== a.enable_clip_layer && d('enable_clip_layer', a.enable_clip_layer),
                                void 0 !== a.stop_at_clip_layer && d('stop_at_clip_layer', a.stop_at_clip_layer),
                                void 0 !== a.vae_source && d('vae_source', a.vae_source),
                                void 0 !== a.vae_name && d('vae_name', a.vae_name),
                                void 0 !== a.lora_count && d('lora_count', a.lora_count));
                            for (let e = 1; e <= 3; e++)
                                (void 0 !== a[`lora_switch_${e}`] && d(`lora_switch_${e}`, a[`lora_switch_${e}`]),
                                    void 0 !== a[`lora_name_${e}`] && d(`lora_name_${e}`, a[`lora_name_${e}`]),
                                    void 0 !== a[`lora_weight_${e}`] && d(`lora_weight_${e}`, a[`lora_weight_${e}`]));
                            (void 0 !== a.ckpt_name && d('ckpt_name', a.ckpt_name),
                                void 0 !== a.unet_name && d('unet_name', a.unet_name),
                                void 0 !== a.nunchaku_name && d('nunchaku_name', a.nunchaku_name),
                                void 0 !== a.qwen_name && d('qwen_name', a.qwen_name),
                                void 0 !== a.gguf_name && d('gguf_name', a.gguf_name));
                        } finally {
                            ((_ = !1), y(), canvasDirtyBatcher.markDirty(n, !0, !0));
                        }
                    }
                },
                r = (e, n) => a.setVisible(e, n),
                g = (e) => a.getValue(e),
                f = {},
                h = {},
                v = () => {
                    if (-1 === n.id) return;
                    const e = g('template_action'),
                        a = g('model_type'),
                        t = g('configure_clip'),
                        o = g('configure_vae'),
                        i = g('configure_model_only_lora'),
                        _ = g('configure_model_sampling'),
                        l = g('sampling_method'),
                        s = g('clip_source'),
                        d = parseInt(g('clip_count')) || 1,
                        u = g('vae_source'),
                        v = parseInt(g('lora_count')) || 3,
                        y = 'Standard Checkpoint' === a,
                        w = 'UNet Model' === a,
                        N = 'Nunchaku Flux' === a,
                        b = 'Nunchaku Qwen' === a,
                        k = 'Nunchaku ZImage' === a,
                        E = 'GGUF Model' === a,
                        L = 'External' === s,
                        F = 'External' === u;
                    ((() => {
                        const e = g('model_type'),
                            a = {
                                ckpt_name: {
                                    show: 'Standard Checkpoint' === e,
                                    extensions: ['.safetensors', '.ckpt', '.pt', '.bin', '.sft'],
                                },
                                unet_name: {
                                    show: 'UNet Model' === e,
                                    extensions: ['.safetensors', '.pt', '.bin', '.sft'],
                                },
                                nunchaku_name: {
                                    show: 'Nunchaku Flux' === e,
                                    extensions: ['.safetensors', '.pt', '.bin', '.sft'],
                                },
                                qwen_name: {
                                    show: 'Nunchaku Qwen' === e,
                                    extensions: ['.safetensors', '.pt', '.bin', '.sft'],
                                },
                                zimage_name: {
                                    show: 'Nunchaku ZImage' === e,
                                    extensions: ['.safetensors', '.pt', '.bin', '.sft'],
                                },
                                gguf_name: { show: 'GGUF Model' === e, extensions: ['.gguf'] },
                            };
                        Object.entries(a).forEach(([e, a]) => {
                            const t = n.widgets?.find((n) => n.name === e);
                            if (!t || !t.options) return;
                            h[e] || (h[e] = [...t.options.values]);
                            const o = h[e].filter((e) => {
                                if ('None' === e) return !0;
                                const n = e.toLowerCase();
                                return a.extensions.some((e) => n.endsWith(e));
                            });
                            if (((t.options.values = o), !o.includes(t.value))) {
                                const e = t.value.replace(/\\/g, '/');
                                e !== t.value && o.includes(e) ? (t.value = e) : (t.value = 'None');
                            }
                        });
                    })(),
                        ['clip_name1', 'clip_name2', 'clip_name3', 'clip_name4'].forEach((e) => {
                            const a = n.widgets?.find((n) => n.name === e);
                            a && a.options && (f[e] || (f[e] = [...a.options.values]), (a.options.values = f[e]));
                        }));
                    const T = 'Save' === e,
                        B = 'Load' === e,
                        G = g('template_name');
                    (r('template_name', B),
                        r('new_template_name', T),
                        (() => {
                            const e = g('template_action'),
                                a = B ? (G && 'None' !== G) : !0;
                            const btnAction = B ? C : c;
                            if (a && !m) {
                                (m = n.addWidget('button', p[e] || e, null, btnAction)), (m.serialize = !1);
                            } else if (a && m) {
                                const a = p[e] || e;
                                (m.name !== a && ((m.name = a), notifyVue(n)), m.callback = btnAction);
                            } else if (!a && m) {
                                const e = n.widgets.indexOf(m);
                                (e >= 0 && n.widgets.splice(e, 1), (m = null));
                            }
                        })(),
                        r('ckpt_name', y),
                        r('unet_name', w),
                        r('nunchaku_name', N),
                        r('qwen_name', b),
                        r('zimage_name', k),
                        r('gguf_name', E),
                        r('weight_dtype', w),
                        r('data_type', N),
                        r('cache_threshold', N),
                        r('attention', N),
                        r('i2f_mode', N),
                        r('cpu_offload', N || b || k),
                        r('num_blocks_on_gpu', b || k),
                        r('use_pin_memory', b || k),
                        r('gguf_dequant_dtype', E),
                        r('gguf_patch_dtype', E),
                        r('gguf_patch_on_device', E),
                        r('model_device', !0),
                        r('clip_device', t),
                        r('vae_device', o),
                        r('clip_source', t),
                        r('clip_count', t && L),
                        r('clip_name1', t && L && d >= 1),
                        r('clip_name2', t && L && d >= 2),
                        r('clip_name3', t && L && d >= 3),
                        r('clip_name4', t && L && d >= 4),
                        r('clip_type', t && L),
                        r('enable_clip_layer', t && y),
                        r('stop_at_clip_layer', t && y),
                        r('vae_source', o),
                        r('vae_name', o && F),
                        r('lora_count', i));
                    for (let e = 1; e <= 3; e++) {
                        const n = i && e <= v;
                        (r(`lora_switch_${e}`, n), r(`lora_name_${e}`, n), r(`lora_weight_${e}`, n));
                    }
                    r('sampling_method', _);
                    const x = 'Flux' === l,
                        S = 'LTXV' === l,
                        W = 'LCM' === l,
                        $ = 'ContinuousEDM' === l,
                        D = $ || 'ContinuousV' === l;
                    (r('shift', _ && 'None' !== l && !W && !D),
                        r('base_shift', _ && (x || S)),
                        r('sampling_width', _ && x),
                        r('sampling_height', _ && x),
                        r('original_timesteps', _ && W),
                        r('zsnr', _ && W),
                        r('sampling_subtype', _ && $),
                        r('sigma_max', _ && D),
                        r('sigma_min', _ && D),
                        smartResize(n));
                },
                y = debounce(v, 100);
            [
                'template_action',
                'template_name',
                'model_type',
                'configure_clip',
                'configure_vae',
                'configure_model_only_lora',
                'configure_model_sampling',
                'sampling_method',
                'clip_source',
                'clip_count',
                'vae_source',
                'lora_count',
            ].forEach((e) => {
                const a = n.widgets?.find((n) => n.name === e);
                if (a) {
                    const n = a.callback;
                    a.callback = function () {
                        if ((n && n.apply(this, arguments), 'template_action' === e || 'template_name' === e)) {
                            const n = g('template_action'),
                                a = g('template_name');
                            ('template_action' === e && 'Save' === n && a && 'None' !== a && d('new_template_name', a),
                                'Load' === n &&
                                    a &&
                                    'None' !== a &&
                                    ((a === i && n === o) || (u(a), (i = a), (o = n))));
                        }
                        if ('sampling_method' === e) {
                            const e = g('sampling_method'),
                                n = g('shift'),
                                a = { SD3: 3, AuraFlow: 1.73, Flux: 1.15, 'Stable Cascade': 2, LTXV: 2.05 };
                            ((Object.values(a).some((e) => Math.abs(n - e) < 0.01) || 3 === n) &&
                                a[e] &&
                                d('shift', a[e]),
                                'ContinuousEDM' === e
                                    ? (d('sigma_max', 120), d('sigma_min', 0.002))
                                    : 'ContinuousV' === e && (d('sigma_max', 500), d('sigma_min', 0.03)));
                        }
                        y();
                    };
                }
            });
            const w = (e) => {
                const { templates: a, sourceNodeId: t } = e.detail;
                if (t === n.id) return;
                if (!a) return;
                const o = n.widgets?.find((e) => 'template_name' === e.name);
                o &&
                    o.options &&
                    o.options.values &&
                    ((o.options.values = a),
                    a.includes(o.value) || (o.value = 'None'),
                    canvasDirtyBatcher.markDirty(n, !0, !0));
            };
            document.addEventListener(TEMPLATE_CHANGED_EVENT, w);
            const N = n.onRemoved;
            ((n.onRemoved = function () {
                (document.removeEventListener(TEMPLATE_CHANGED_EVENT, w), N && N.apply(this, arguments));
            }),
                setTimeout(() => {
                    n._Eclipse_initialized || ((n._Eclipse_initialized = !0), v(), l(), s());
                }, 0));
            const b = n.onConfigure;
            return (
                (n.onConfigure = function (e) {
                    (b && b.apply(this, arguments),
                        s(),
                        setTimeout(() => {
                            const e = g('template_action'),
                                n = g('template_name');
                            'Load' === e && n && 'None' !== n ? u(n) : v();
                        }, 100));
                }),
                e
            );
        };
    },
});
