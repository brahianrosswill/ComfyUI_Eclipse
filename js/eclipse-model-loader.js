/* eclipse-model-loader.js - Multi-select feature widget + visibility for Model Loader [Eclipse] */
import { app } from './comfy/index.js';
import {
    debounce,
    canvasDirtyBatcher,
    smartResize,
    createWidgetVisibilityManager,
    isVueMode,
    onVueModeChange,
} from './eclipse-widget-performance-utils.js';
import { injectComboChipCSS, createComboChipWidget as _createComboChipWidget } from './eclipse-combo-chip.js';
import { fetchSharedModelFiles } from './eclipse-loader-shared.js';

const NODE_CONFIGS = {
    'Model Loader [Eclipse]': { extName: 'Eclipse.ModelLoader', cssPrefix: 'ml' },
    'Model Loader Pipe [Eclipse]': { extName: 'Eclipse.ModelLoaderPipe', cssPrefix: 'mlp' },
};
const NODE_NAMES = Object.keys(NODE_CONFIGS);

// Must match Python MODEL_LOADER_FEATURE_OPTIONS order
const FEATURE_OPTIONS = ['lora', 'model_sampling', 'block_swap', 'memory_cleanup'];
const DEFAULT_FEATURES = ['memory_cleanup'];

for (const prefix of new Set(Object.values(NODE_CONFIGS).map(c => c.cssPrefix))) {
    injectComboChipCSS(prefix);
}

// Map each feature to the widgets it controls
const FEATURE_WIDGETS = {
    lora: ['lora_count', 'lora_name_1', 'lora_weight_1', 'lora_name_2', 'lora_weight_2', 'lora_name_3', 'lora_weight_3'],
    model_sampling: ['sampling_method', 'sampling_subtype', 'shift', 'base_shift', 'sampling_width', 'sampling_height', 'original_timesteps', 'zsnr', 'sigma_max', 'sigma_min'],
    block_swap: ['blocks_to_swap', 'offload_embeddings'],
    memory_cleanup: [],
};

// Model-type-driven widgets (always controlled by model_type, not features)
const MODEL_TYPE_WIDGETS = ['ckpt_name', 'unet_name', 'nunchaku_name', 'qwen_name', 'zimage_name', 'gguf_name', 'weight_dtype', 'data_type', 'cache_threshold', 'attention', 'i2f_mode', 'cpu_offload', 'num_blocks_on_gpu', 'use_pin_memory', 'gguf_dequant_dtype', 'gguf_patch_dtype', 'gguf_patch_on_device'];

const ALL_FEATURE_CONTROLLED = Object.values(FEATURE_WIDGETS).flat();
const ALL_CONTROLLED = ALL_FEATURE_CONTROLLED.concat(MODEL_TYPE_WIDGETS);

function createComboChipWidget(node, savedValue, origIdx, cssPrefix) {
    return _createComboChipWidget({ node, options: FEATURE_OPTIONS, savedValue, origIdx, cssPrefix });
}

for (const [nodeName, cfg] of Object.entries(NODE_CONFIGS)) {
app.registerExtension({
    name: cfg.extName,
    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== nodeName) return;
        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const ret = origOnNodeCreated ? origOnNodeCreated.apply(this, arguments) : void 0;
            const node = this;
            const vis = createWidgetVisibilityManager(node);
            node._Eclipse_vis = vis;
            const g = (name) => vis.getValue(name);
            const d = (name, show) => vis.setVisible(name, show);

            // --- Features multi-select setup (dual-path) ---
            const autoFeaturesW = node.widgets?.find(w => w.name === 'features');
            let featWidget;

            if (isVueMode()) {
                const origIdx = autoFeaturesW ? node.widgets.indexOf(autoFeaturesW) : 0;
                let savedValue = DEFAULT_FEATURES.slice();
                if (autoFeaturesW) {
                    if (Array.isArray(autoFeaturesW.value) && autoFeaturesW.value.length > 0) {
                        savedValue = autoFeaturesW.value.slice();
                    }
                    autoFeaturesW.onRemove?.();
                    node.widgets.splice(node.widgets.indexOf(autoFeaturesW), 1);
                }
                featWidget = createComboChipWidget(node, savedValue, origIdx, cfg.cssPrefix);
            } else {
                const origIdx = autoFeaturesW ? node.widgets.indexOf(autoFeaturesW) : 0;
                let savedValue = DEFAULT_FEATURES.slice();
                if (autoFeaturesW) {
                    if (Array.isArray(autoFeaturesW.value) && autoFeaturesW.value.length > 0) {
                        savedValue = autoFeaturesW.value.slice();
                    }
                    autoFeaturesW.hidden = true;
                    if (autoFeaturesW.options) autoFeaturesW.options.hidden = true;
                    if (Array.isArray(autoFeaturesW.value) && autoFeaturesW.value.length === 0) {
                        autoFeaturesW.value = savedValue.slice();
                    }
                }
                featWidget = createComboChipWidget(node, savedValue, origIdx + 1, cfg.cssPrefix);
                node._Eclipse_backingFeaturesW = autoFeaturesW;
            }

            // Disable block_swap chip when ComfyUI 0.18.0+ handles offloading natively
            fetch('/eclipse/config/all').then(r => r.json()).then(eclipseCfg => {
                if (eclipseCfg?.has_native_dynamic_vram && featWidget?.setDisabledChips) {
                    featWidget.setDisabledChips(new Set(['block_swap']));
                }
            }).catch(() => {});

            // Cache original file lists for extension filtering
            const origModelLists = {};

            const updateVisibility = () => {
                if (node.id === -1) return;

                // Get selected features
                const raw = vis.getValue('features');
                const feats = new Set(Array.isArray(raw) ? raw : []);

                const modelType = g('model_type');
                const enableClipLayer = g('enable_clip_layer');
                const loraCount = parseInt(g('lora_count')) || 1;
                const samplingMethod = g('sampling_method');

                const isStandard = modelType === 'Standard Checkpoint';
                const isUnet = modelType === 'UNet Model';
                const isNunchakuFlux = modelType === 'Nunchaku Flux';
                const isNunchakuQwen = modelType === 'Nunchaku Qwen';
                const isNunchakuZImage = modelType === 'Nunchaku ZImage';
                const isGGUF = modelType === 'GGUF Model';
                const isNunchaku = isNunchakuFlux || isNunchakuQwen || isNunchakuZImage;

                const hasLora = feats.has('lora');
                const hasModelSampling = feats.has('model_sampling');
                const hasBlockSwap = feats.has('block_swap') && !isNunchaku;

                // Filter model file dropdowns by extension
                const modelFileRules = {
                    ckpt_name: { show: isStandard, extensions: ['.safetensors', '.ckpt', '.pt', '.bin', '.sft'] },
                    unet_name: { show: isUnet, extensions: ['.safetensors', '.pt', '.bin', '.sft'] },
                    nunchaku_name: { show: isNunchakuFlux, extensions: ['.safetensors', '.pt', '.bin', '.sft'] },
                    qwen_name: { show: isNunchakuQwen, extensions: ['.safetensors', '.pt', '.bin', '.sft'] },
                    zimage_name: { show: isNunchakuZImage, extensions: ['.safetensors', '.pt', '.bin', '.sft'] },
                    gguf_name: { show: isGGUF, extensions: ['.gguf'] },
                };
                Object.entries(modelFileRules).forEach(([wName, rule]) => {
                    const w = node.widgets?.find((x) => x.name === wName);
                    if (!w || !w.options) return;
                    origModelLists[wName] || (origModelLists[wName] = [...w.options.values]);
                    const filtered = origModelLists[wName].filter((v) => {
                        if (v === 'None') return true;
                        const low = v.toLowerCase();
                        return rule.extensions.some((ext) => low.endsWith(ext));
                    });
                    w.options.values = filtered;
                    if (!filtered.includes(w.value)) {
                        const norm = (w.value || '').replace(/\\/g, '/');
                        if (norm !== w.value && filtered.includes(norm)) w.value = norm;
                        else w.value = 'None';
                    }
                });

                // Model file selectors
                d('ckpt_name', isStandard);
                d('unet_name', isUnet);
                d('nunchaku_name', isNunchakuFlux);
                d('qwen_name', isNunchakuQwen);
                d('zimage_name', isNunchakuZImage);
                d('gguf_name', isGGUF);

                // Model-type-specific options
                d('weight_dtype', isUnet);
                d('data_type', isNunchakuFlux);
                d('cache_threshold', isNunchakuFlux);
                d('attention', isNunchakuFlux);
                d('i2f_mode', isNunchakuFlux);
                d('cpu_offload', isNunchakuFlux || isNunchakuQwen || isNunchakuZImage);
                d('num_blocks_on_gpu', isNunchakuQwen || isNunchakuZImage);
                d('use_pin_memory', isNunchakuQwen || isNunchakuZImage);
                d('gguf_dequant_dtype', isGGUF);
                d('gguf_patch_dtype', isGGUF);
                d('gguf_patch_on_device', isGGUF);

                // CLIP layer trimming — Standard Checkpoint only
                d('enable_clip_layer', isStandard);
                d('stop_at_clip_layer', isStandard && enableClipLayer);

                // LoRA section (feature-controlled)
                d('lora_count', hasLora);
                for (let i = 1; i <= 3; i++) {
                    const show = hasLora && i <= loraCount;
                    d(`lora_name_${i}`, show);
                    d(`lora_weight_${i}`, show);
                }

                // Model sampling section (feature-controlled)
                d('sampling_method', hasModelSampling);
                const isFlux = samplingMethod === 'Flux';
                const isLTXV = samplingMethod === 'LTXV';
                const isLCM = samplingMethod === 'LCM';
                const isContinuousEDM = samplingMethod === 'ContinuousEDM';
                const isContinuousV = samplingMethod === 'ContinuousV';
                const isContinuous = isContinuousEDM || isContinuousV;
                d('shift', hasModelSampling && samplingMethod !== 'None' && !isLCM && !isContinuous);
                d('base_shift', hasModelSampling && (isFlux || isLTXV));
                d('sampling_width', hasModelSampling && isFlux);
                d('sampling_height', hasModelSampling && isFlux);
                d('original_timesteps', hasModelSampling && isLCM);
                d('zsnr', hasModelSampling && isLCM);
                d('sampling_subtype', hasModelSampling && isContinuousEDM);
                d('sigma_max', hasModelSampling && isContinuous);
                d('sigma_min', hasModelSampling && isContinuous);

                // BlockSwap (feature-controlled, hidden for Nunchaku)
                d('blocks_to_swap', hasBlockSwap);
                d('offload_embeddings', hasBlockSwap);

                smartResize(node);
            };

            const debouncedUpdate = debounce(updateVisibility, 100);

            // --- Features callback ---
            const origFeatCallback = featWidget?.callback;
            if (featWidget) {
                featWidget.callback = function (value) {
                    origFeatCallback?.call(this, value);
                    if (node._Eclipse_backingFeaturesW) {
                        node._Eclipse_backingFeaturesW.value = featWidget.value;
                    }
                    updateVisibility();
                };
            }

            // Hook widget callbacks for visibility triggers
            [
                'model_type',
                'enable_clip_layer',
                'lora_count',
                'sampling_method',
            ].forEach((wName) => {
                const w = node.widgets?.find((x) => x.name === wName);
                if (w) {
                    const orig = w.callback;
                    w.callback = function () {
                        orig && orig.apply(this, arguments);
                        debouncedUpdate();
                    };
                }
            });

            // Fetch fresh model file lists from server
            const refreshModelFiles = async () => {
                try {
                    const data = await fetchSharedModelFiles();
                    if (!data) return;
                    const applyList = (wName, list) => {
                        const w = node.widgets?.find((x) => x.name === wName);
                        if (w && w.options && w.options.values) {
                            w.options.values = list;
                            if (!list.includes(w.value)) {
                                const norm = (w.value || '').replace(/\\/g, '/');
                                if (norm !== w.value && list.includes(norm)) w.value = norm;
                                else w.value = list[0] || 'None';
                            }
                        }
                    };
                    if (data.checkpoints) applyList('ckpt_name', data.checkpoints);
                    if (data.diffusion_models) {
                        applyList('unet_name', data.diffusion_models);
                        applyList('nunchaku_name', data.diffusion_models);
                        applyList('qwen_name', data.diffusion_models);
                        applyList('zimage_name', data.diffusion_models);
                    }
                    if (data.diffusion_models_gguf) applyList('gguf_name', data.diffusion_models_gguf);
                    if (data.loras) {
                        applyList('lora_name_1', data.loras);
                        applyList('lora_name_2', data.loras);
                        applyList('lora_name_3', data.loras);
                    }
                    canvasDirtyBatcher.markDirty(node, true, true);
                } catch (e) {
                    console.warn('[Model Loader] Failed to refresh model file lists:', e);
                }
            };

            node._Eclipse_refreshLists = refreshModelFiles;

            // Initialize
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    updateVisibility();
                    refreshModelFiles();
                }
            }, 0);

            const origOnConfigure = node.onConfigure;
            node.onConfigure = function (config) {
                origOnConfigure && origOnConfigure.apply(this, arguments);
                refreshModelFiles();
                setTimeout(() => { updateVisibility(); }, 100);
            };

            return ret;
        };
    },
    async refreshComboInNodes() {
        const nodes = app.graph?._nodes || [];
        for (const node of nodes) {
            if (NODE_NAMES.includes(node.comfyClass) && node._Eclipse_refreshLists) {
                node._Eclipse_refreshLists();
            }
        }
    },
    async setup() {
        onVueModeChange(() => {
            const graph = app.graph;
            if (!graph?._nodes) return;
            for (let i = 0; i < graph._nodes.length; i++) {
                const n = graph._nodes[i];
                if (NODE_NAMES.includes(n.comfyClass)) {
                    try {
                        const savedWidgets = {};
                        n.widgets?.forEach(w => { savedWidgets[w.name] = w.value; });
                        n.onNodeCreated?.call(n);
                        n.widgets?.forEach(w => { if (savedWidgets[w.name] !== undefined) w.value = savedWidgets[w.name]; });
                    } catch (e) { console.warn('[Model Loader] mode switch recreate error:', e); }
                }
            }
            graph.setDirtyCanvas?.(true, true);
        });
    },
});
} // end for NODE_CONFIGS
