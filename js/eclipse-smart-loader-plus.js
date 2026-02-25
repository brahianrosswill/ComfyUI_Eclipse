/* eclipse-smart-loader-plus.js - Minified for ComfyUI Eclipse */
import { app, api } from './comfy/index.js';
import {
    debounce,
    canvasDirtyBatcher,
    notifyVue,
    smartResize,
    createWidgetVisibilityManager,
} from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Smart Loader Plus [Eclipse]';
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
            .catch((e) => (console.warn('[Smart Loader+] Failed to fetch model files:', e), null))
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
    name: 'Eclipse.SmartLoaderPlus',
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
                                    const e = (null != t.value ? String(t.value) : '').replace(/\\/g, '/');
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
                        console.warn('[Smart Loader+] Failed to refresh model file lists:', e);
                    }
                },
                c = async () => {
                    const e = g('template_action'),
                        a = g('template_name'),
                        t = g('new_template_name');
                    if ((await l(), 'None' === e))
                        (u('template_name', 'None'),
                            u('new_template_name', ''),
                            u('model_type', 'Standard Checkpoint'),
                            u('ckpt_name', 'None'),
                            u('unet_name', 'None'),
                            u('nunchaku_name', 'None'),
                            u('qwen_name', 'None'),
                            u('zimage_name', 'None'),
                            u('gguf_name', 'None'),
                            u('weight_dtype', 'default'),
                            u('data_type', 'bfloat16'),
                            u('cache_threshold', 0),
                            u('attention', 'flash-attention2'),
                            u('i2f_mode', 'enabled'),
                            u('cpu_offload', 'auto'),
                            u('num_blocks_on_gpu', 30),
                            u('use_pin_memory', 'enable'),
                            u('gguf_dequant_dtype', 'default'),
                            u('gguf_patch_dtype', 'default'),
                            u('gguf_patch_on_device', !1),
                            u('configure_clip', !0),
                            u('configure_vae', !0),
                            u('configure_latent', !0),
                            u('configure_sampler', !0),
                            u('configure_model_only_lora', !1),
                            u('configure_model_sampling', !1),
                            u('sampling_method', 'None'),
                            u('sampling_subtype', 'eps'),
                            u('shift', 3),
                            u('base_shift', 0.5),
                            u('sampling_width', 1024),
                            u('sampling_height', 1024),
                            u('original_timesteps', 50),
                            u('zsnr', !1),
                            u('sigma_max', 120),
                            u('sigma_min', 0.002),
                            u('clip_source', 'Baked'),
                            u('clip_count', '1'),
                            u('clip_name1', 'None'),
                            u('clip_name2', 'None'),
                            u('clip_name3', 'None'),
                            u('clip_name4', 'None'),
                            u('clip_type', 'flux'),
                            u('enable_clip_layer', !0),
                            u('stop_at_clip_layer', -2),
                            u('vae_source', 'Baked'),
                            u('vae_name', 'None'),
                            u('resolution', '1024x1024 (1:1)'),
                            u('width', 1024),
                            u('height', 1024),
                            u('lora_count', '1'),
                            u('lora_switch_1', !1),
                            u('lora_name_1', 'None'),
                            u('lora_weight_1', 1),
                            u('lora_switch_2', !1),
                            u('lora_name_2', 'None'),
                            u('lora_weight_2', 1),
                            u('lora_switch_3', !1),
                            u('lora_name_3', 'None'),
                            u('lora_weight_3', 1),
                            u('sampler_name', 'euler'),
                            u('scheduler', 'normal'),
                            u('steps', 20),
                            u('cfg', 8),
                            u('flux_guidance', 3.5),
                            u('batch_size', 1),
                            u('model_device', 'auto'),
                            u('clip_device', 'auto'),
                            u('vae_device', 'auto'),
                            u('memory_cleanup', !0),
                            v(),
                            console.log('[Smart Loader+] ✓ All fields reset to defaults'));
                    else if ('Load' === e && a && 'None' !== a) await r(a);
                    else if ('Save' === e && t && t.trim()) {
                        const e = t.trim(),
                            a = (() => {
                                const e = {},
                                    n = g('model_type'),
                                    a = g('configure_clip'),
                                    t = g('configure_vae'),
                                    o = g('configure_latent'),
                                    i = g('configure_sampler'),
                                    _ = g('configure_model_only_lora'),
                                    l = g('configure_model_sampling');
                                if (
                                    ((e.model_type = n),
                                    (e.configure_clip = a),
                                    (e.configure_vae = t),
                                    (e.configure_latent = o),
                                    (e.configure_sampler = i),
                                    (e.configure_model_only_lora = _),
                                    (e.configure_model_sampling = l),
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
                                    const n = g('resolution');
                                    ((e.resolution = n),
                                        'Custom' === n && ((e.width = g('width')), (e.height = g('height'))));
                                }
                                if (i) {
                                    ((e.sampler_name = g('sampler_name')),
                                        (e.scheduler = g('scheduler')),
                                        (e.steps = g('steps')),
                                        (e.cfg = g('cfg')));
                                    const a = g('clip_type');
                                    ('Nunchaku Flux' === n ||
                                        (['flux', 'flux2'].includes(a) && ['UNet Model', 'GGUF Model'].includes(n))) &&
                                        (e.flux_guidance = g('flux_guidance'));
                                }
                                if (_) {
                                    e.lora_count = g('lora_count');
                                    for (let n = 1; n <= 3; n++)
                                        ((e[`lora_switch_${n}`] = g(`lora_switch_${n}`)),
                                            (e[`lora_name_${n}`] = g(`lora_name_${n}`)),
                                            (e[`lora_weight_${n}`] = g(`lora_weight_${n}`)));
                                }
                                if (l) {
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
                                    u('template_action', 'Load'),
                                    u('template_name', e),
                                    u('new_template_name', ''),
                                    v());
                            } else console.error(`[Smart Loader+] Save failed: ${o.error}`);
                        } catch (e) {
                            console.error('[Smart Loader+] Save request failed:', e);
                        }
                    } else if ('Delete' === e && a && 'None' !== a)
                        try {
                            const e = await api.fetchApi('/eclipse/loader_templates/delete', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ name: a }),
                                }),
                                t = await e.json();
                            if (t.success) {
                                (broadcastTemplateListChanged(await l(), n.id),
                                    u('template_action', 'Load'),
                                    u('template_name', 'None'),
                                    v());
                            } else console.error(`[Smart Loader+] Delete failed: ${t.error}`);
                        } catch (e) {
                            console.error('[Smart Loader+] Delete request failed:', e);
                        }
                };
            let m = null;
            const p = { None: '🔄 Reset Template Fields', Save: '💾 Save Template', Delete: '🗑️ Delete Template' },
                u = (e, a) => {
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
                r = async (e) => {
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
                            (u('model_type', 'Standard Checkpoint'),
                                u('ckpt_name', 'None'),
                                u('unet_name', 'None'),
                                u('nunchaku_name', 'None'),
                                u('qwen_name', 'None'),
                                u('gguf_name', 'None'),
                                u('weight_dtype', 'default'),
                                u('data_type', 'bfloat16'),
                                u('cache_threshold', 0),
                                u('attention', 'flash-attention2'),
                                u('i2f_mode', 'enabled'),
                                u('cpu_offload', 'auto'),
                                u('num_blocks_on_gpu', 30),
                                u('use_pin_memory', 'enable'),
                                u('gguf_dequant_dtype', 'default'),
                                u('gguf_patch_dtype', 'default'),
                                u('gguf_patch_on_device', !1),
                                u('configure_clip', !0),
                                u('configure_vae', !0),
                                u('configure_latent', !1),
                                u('configure_sampler', !1),
                                u('configure_model_only_lora', !1),
                                u('configure_model_sampling', !1),
                                u('sampling_method', 'None'),
                                u('shift', 3),
                                u('base_shift', 0.5),
                                u('sampling_width', 1024),
                                u('sampling_height', 1024),
                                u('clip_source', 'Baked'),
                                u('clip_count', '1'),
                                u('clip_name1', 'None'),
                                u('clip_name2', 'None'),
                                u('clip_name3', 'None'),
                                u('clip_name4', 'None'),
                                u('clip_type', 'flux'),
                                u('enable_clip_layer', !0),
                                u('stop_at_clip_layer', -2),
                                u('vae_source', 'Baked'),
                                u('vae_name', 'None'),
                                u('resolution', '1024x1024 (1:1)'),
                                u('width', 1024),
                                u('height', 1024),
                                u('batch_size', 1),
                                u('lora_count', '1'));
                            for (let e = 1; e <= 3; e++)
                                (u(`lora_switch_${e}`, !1), u(`lora_name_${e}`, 'None'), u(`lora_weight_${e}`, 1));
                            (u('sampler_name', 'euler'),
                                u('scheduler', 'normal'),
                                u('steps', 20),
                                u('cfg', 8),
                                u('flux_guidance', 3.5),
                                void 0 !== a.model_type && u('model_type', a.model_type),
                                void 0 !== a.weight_dtype && u('weight_dtype', a.weight_dtype),
                                void 0 !== a.model_type && u('model_type', a.model_type),
                                void 0 !== a.weight_dtype && u('weight_dtype', a.weight_dtype),
                                void 0 !== a.configure_clip && u('configure_clip', a.configure_clip),
                                void 0 !== a.configure_vae && u('configure_vae', a.configure_vae),
                                void 0 !== a.configure_latent && u('configure_latent', a.configure_latent),
                                void 0 !== a.configure_sampler && u('configure_sampler', a.configure_sampler),
                                void 0 !== a.configure_model_only_lora &&
                                    u('configure_model_only_lora', a.configure_model_only_lora),
                                void 0 !== a.configure_model_sampling &&
                                    u('configure_model_sampling', a.configure_model_sampling),
                                void 0 !== a.sampling_method && u('sampling_method', a.sampling_method),
                                void 0 !== a.sampling_subtype && u('sampling_subtype', a.sampling_subtype),
                                void 0 !== a.shift && u('shift', a.shift),
                                void 0 !== a.base_shift && u('base_shift', a.base_shift),
                                void 0 !== a.sampling_width && u('sampling_width', a.sampling_width),
                                void 0 !== a.sampling_height && u('sampling_height', a.sampling_height),
                                void 0 !== a.original_timesteps && u('original_timesteps', a.original_timesteps),
                                void 0 !== a.zsnr && u('zsnr', a.zsnr),
                                void 0 !== a.sigma_max && u('sigma_max', a.sigma_max),
                                void 0 !== a.sigma_min && u('sigma_min', a.sigma_min),
                                void 0 !== a.data_type && u('data_type', a.data_type),
                                void 0 !== a.cache_threshold && u('cache_threshold', a.cache_threshold),
                                void 0 !== a.attention && u('attention', a.attention),
                                void 0 !== a.i2f_mode && u('i2f_mode', a.i2f_mode),
                                void 0 !== a.cpu_offload && u('cpu_offload', a.cpu_offload),
                                void 0 !== a.num_blocks_on_gpu && u('num_blocks_on_gpu', a.num_blocks_on_gpu),
                                void 0 !== a.use_pin_memory && u('use_pin_memory', a.use_pin_memory),
                                void 0 !== a.gguf_dequant_dtype && u('gguf_dequant_dtype', a.gguf_dequant_dtype),
                                void 0 !== a.gguf_patch_dtype && u('gguf_patch_dtype', a.gguf_patch_dtype),
                                void 0 !== a.gguf_patch_on_device && u('gguf_patch_on_device', a.gguf_patch_on_device),
                                void 0 !== a.clip_source && u('clip_source', a.clip_source),
                                void 0 !== a.clip_count && u('clip_count', a.clip_count),
                                void 0 !== a.clip_name1 && u('clip_name1', a.clip_name1),
                                void 0 !== a.clip_name2 && u('clip_name2', a.clip_name2),
                                void 0 !== a.clip_name3 && u('clip_name3', a.clip_name3),
                                void 0 !== a.clip_name4 && u('clip_name4', a.clip_name4),
                                void 0 !== a.clip_type && u('clip_type', a.clip_type),
                                void 0 !== a.enable_clip_layer && u('enable_clip_layer', a.enable_clip_layer),
                                void 0 !== a.stop_at_clip_layer && u('stop_at_clip_layer', a.stop_at_clip_layer),
                                void 0 !== a.vae_source && u('vae_source', a.vae_source),
                                void 0 !== a.vae_name && u('vae_name', a.vae_name),
                                void 0 !== a.resolution && u('resolution', a.resolution),
                                void 0 !== a.width && u('width', a.width),
                                void 0 !== a.height && u('height', a.height),
                                void 0 !== a.batch_size && u('batch_size', a.batch_size),
                                void 0 !== a.lora_count && u('lora_count', a.lora_count));
                            for (let e = 1; e <= 3; e++)
                                (void 0 !== a[`lora_switch_${e}`] && u(`lora_switch_${e}`, a[`lora_switch_${e}`]),
                                    void 0 !== a[`lora_name_${e}`] && u(`lora_name_${e}`, a[`lora_name_${e}`]),
                                    void 0 !== a[`lora_weight_${e}`] && u(`lora_weight_${e}`, a[`lora_weight_${e}`]));
                            (void 0 !== a.sampler_name
                                ? u('sampler_name', a.sampler_name)
                                : void 0 !== a.sampler && u('sampler_name', a.sampler),
                                void 0 !== a.scheduler && u('scheduler', a.scheduler),
                                void 0 !== a.steps && u('steps', a.steps),
                                void 0 !== a.cfg && u('cfg', a.cfg),
                                void 0 !== a.flux_guidance && u('flux_guidance', a.flux_guidance),
                                void 0 !== a.ckpt_name && u('ckpt_name', a.ckpt_name),
                                void 0 !== a.unet_name && u('unet_name', a.unet_name),
                                void 0 !== a.nunchaku_name && u('nunchaku_name', a.nunchaku_name),
                                void 0 !== a.qwen_name && u('qwen_name', a.qwen_name),
                                void 0 !== a.gguf_name && u('gguf_name', a.gguf_name));
                        } finally {
                            ((_ = !1), v(), n.setDirtyCanvas(!0, !0));
                        }
                    } else v();
                },
                d = (e, n) => a.setVisible(e, n),
                g = (e) => a.getValue(e),
                f = {},
                h = {},
                v = () => {
                    if (-1 === n.id) return;
                    const e = g('template_action'),
                        a = g('model_type'),
                        t = g('configure_clip'),
                        o = g('configure_vae'),
                        i = g('configure_latent'),
                        _ = g('configure_sampler'),
                        l = g('configure_model_only_lora'),
                        s = g('configure_model_sampling'),
                        u = g('sampling_method'),
                        r = g('clip_source'),
                        v = parseInt(g('clip_count')) || 1,
                        y = g('clip_type'),
                        w = g('vae_source'),
                        N = g('resolution'),
                        b = parseInt(g('lora_count')) || 3,
                        k = 'Standard Checkpoint' === a,
                        x = 'UNet Model' === a,
                        E = 'Nunchaku Flux' === a,
                        F = 'Nunchaku Qwen' === a,
                        L = 'Nunchaku ZImage' === a,
                        T = 'GGUF Model' === a,
                        S = 'External' === r,
                        C = 'External' === w,
                        M = 'Custom' === N,
                        $ = E || ('flux' === y && (x || T));
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
                                const e = (null != t.value ? String(t.value) : '').replace(/\\/g, '/');
                                e !== t.value && o.includes(e) ? (t.value = e) : (t.value = 'None');
                            }
                        });
                    })(),
                        ['clip_name1', 'clip_name2', 'clip_name3', 'clip_name4'].forEach((e) => {
                            const a = n.widgets?.find((n) => n.name === e);
                            a && a.options && (f[e] || (f[e] = [...a.options.values]), (a.options.values = f[e]));
                        }));
                    const D = 'Save' === e;
                    (d('template_name', 'Load' === e || 'Delete' === e),
                        d('new_template_name', D),
                        (() => {
                            const e = g('template_action'),
                                a = 'Load' !== e;
                            if (a && !m) ((m = n.addWidget('button', p[e] || e, null, c)), (m.serialize = !1));
                            else if (a && m) {
                                const a = p[e] || e;
                                m.name !== a && ((m.name = a), notifyVue(n));
                            } else if (!a && m) {
                                const e = n.widgets.indexOf(m);
                                (e >= 0 && n.widgets.splice(e, 1), (m = null));
                            }
                        })(),
                        d('ckpt_name', k),
                        d('unet_name', x),
                        d('nunchaku_name', E),
                        d('qwen_name', F),
                        d('zimage_name', L),
                        d('gguf_name', T),
                        d('weight_dtype', x),
                        d('data_type', E),
                        d('cache_threshold', E),
                        d('attention', E),
                        d('i2f_mode', E),
                        d('cpu_offload', E || F || L),
                        d('num_blocks_on_gpu', F || L),
                        d('use_pin_memory', F || L),
                        d('gguf_dequant_dtype', T),
                        d('gguf_patch_dtype', T),
                        d('gguf_patch_on_device', T),
                        d('model_device', !0),
                        d('clip_device', t),
                        d('vae_device', o),
                        d('clip_source', t),
                        d('clip_count', t && S),
                        d('clip_name1', t && S && v >= 1),
                        d('clip_name2', t && S && v >= 2),
                        d('clip_name3', t && S && v >= 3),
                        d('clip_name4', t && S && v >= 4),
                        d('clip_type', t && S),
                        d('enable_clip_layer', t && k),
                        d('stop_at_clip_layer', t && k),
                        d('vae_source', o),
                        d('vae_name', o && C),
                        d('lora_count', l));
                    for (let e = 1; e <= 3; e++) {
                        const n = l && e <= b;
                        (d(`lora_switch_${e}`, n), d(`lora_name_${e}`, n), d(`lora_weight_${e}`, n));
                    }
                    (d('resolution', i),
                        d('width', i && M),
                        d('height', i && M),
                        d('batch_size', i),
                        d('sampler_name', _),
                        d('scheduler', _),
                        d('steps', _),
                        d('cfg', _),
                        d('flux_guidance', _ && $),
                        d('sampling_method', s));
                    const z = 'Flux' === u,
                        q = 'LTXV' === u,
                        V = 'LCM' === u,
                        A = 'ContinuousEDM' === u,
                        j = A || 'ContinuousV' === u;
                    (d('shift', s && 'None' !== u && !V && !j),
                        d('base_shift', s && (z || q)),
                        d('sampling_width', s && z && !i),
                        d('sampling_height', s && z && !i),
                        d('original_timesteps', s && V),
                        d('zsnr', s && V),
                        d('sampling_subtype', s && A),
                        d('sigma_max', s && j),
                        d('sigma_min', s && j),
                        smartResize(n));
                },
                y = debounce(v, 100);
            [
                'template_action',
                'template_name',
                'model_type',
                'configure_clip',
                'configure_vae',
                'configure_latent',
                'configure_sampler',
                'configure_model_only_lora',
                'configure_model_sampling',
                'sampling_method',
                'clip_source',
                'clip_count',
                'clip_type',
                'vae_source',
                'resolution',
                'lora_count',
            ].forEach((e) => {
                const a = n.widgets?.find((n) => n.name === e);
                if (a) {
                    const n = a.callback;
                    a.callback = function () {
                        if ((n && n.apply(this, arguments), 'template_action' === e || 'template_name' === e)) {
                            const n = g('template_action'),
                                a = g('template_name');
                            ('template_action' === e && 'Save' === n && a && 'None' !== a && u('new_template_name', a),
                                'Load' === n &&
                                    a &&
                                    'None' !== a &&
                                    ((a === i && n === o) || (r(a), (i = a), (o = n))));
                        }
                        if ('sampling_method' === e) {
                            const e = g('sampling_method'),
                                n = g('shift'),
                                a = { SD3: 3, AuraFlow: 1.73, Flux: 1.15, 'Stable Cascade': 2, LTXV: 2.05 };
                            ((Object.values(a).some((e) => Math.abs(n - e) < 0.01) || 3 === n) &&
                                a[e] &&
                                u('shift', a[e]),
                                'ContinuousEDM' === e
                                    ? (u('sigma_max', 120), u('sigma_min', 0.002))
                                    : 'ContinuousV' === e && (u('sigma_max', 500), u('sigma_min', 0.03)));
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
                            'Load' === e && n && 'None' !== n ? r(n) : v();
                        }, 100));
                }),
                e
            );
        };
    },
});
