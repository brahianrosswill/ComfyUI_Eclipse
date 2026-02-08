/** Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*
* Dynamic widget visibility for Smart Loader
* Adds LoRA configuration management with dynamic slot visibility
*/

import { app, api } from './comfy/index.js';
import {
    debounce,
    isNodeVisible,
    canvasDirtyBatcher,
    setupLazyInit
} from './eclipse-widget-performance-utils.js';

const NODE_NAME = "Smart Loader [Eclipse]";

// Module-level shared fetch promises to prevent thundering herd
// when multiple Smart Loader nodes exist in the same workflow
let _pendingTemplateListFetch = null;
let _pendingModelFilesFetch = null;

async function fetchSharedTemplateList() {
    if (_pendingTemplateListFetch) return _pendingTemplateListFetch;
    _pendingTemplateListFetch = fetch('/eclipse/loader_templates_list')
        .then(r => r.ok ? r.json() : null)
        .catch(e => { console.error('Failed to fetch template list:', e); return null; })
        .finally(() => { _pendingTemplateListFetch = null; });
    return _pendingTemplateListFetch;
}

async function fetchSharedModelFiles() {
    if (_pendingModelFilesFetch) return _pendingModelFilesFetch;
    _pendingModelFilesFetch = fetch('/eclipse/model_files_all')
        .then(r => r.ok ? r.json() : null)
        .catch(e => { console.warn('[Smart Loader] Failed to fetch model files:', e); return null; })
        .finally(() => { _pendingModelFilesFetch = null; });
    return _pendingModelFilesFetch;
}

// Cross-node template list synchronization
// When a template is saved/deleted in any Smart Loader node, all others get updated
const TEMPLATE_CHANGED_EVENT = 'eclipse-loader-templates-changed';

function broadcastTemplateListChanged(templates, sourceNodeId) {
    if (!templates) return;
    document.dispatchEvent(new CustomEvent(TEMPLATE_CHANGED_EVENT, {
        detail: { templates, sourceNodeId }
    }));
}

app.registerExtension({
    name: "Eclipse.SmartLoader",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const node = this;
            
            let lastTemplateAction = "None";
            let lastTemplateName = "None";
            let pendingTemplateSave = null;
            let pendingTemplateDelete = false;
            let isApplyingTemplate = false; // Flag to prevent callbacks during template load
            
            // Refresh template list from server (deduplicated across node instances)
            const refreshTemplateList = async () => {
                try {
                    const templates = await fetchSharedTemplateList();
                    if (templates) {
                        const templateWidget = node.widgets?.find(w => w.name === "template_name");
                        if (templateWidget && templateWidget.options && templateWidget.options.values) {
                            templateWidget.options.values = templates;
                            if (!templates.includes(templateWidget.value)) {
                                templateWidget.value = "None";
                            }
                            canvasDirtyBatcher.markDirty(node, true, true);
                        }
                    }
                    return templates;
                } catch (e) {
                    console.error('Failed to refresh template list:', e);
                    return null;
                }
            };
            
            // Refresh model file lists from server (deduplicated across node instances)
            const refreshModelFileLists = async () => {
                try {
                    const lists = await fetchSharedModelFiles();
                    if (!lists) return;
                    
                    // Helper to update a widget's options
                    const updateWidgetOptions = (widgetName, values) => {
                        const widget = node.widgets?.find(w => w.name === widgetName);
                        if (widget && widget.options && widget.options.values) {
                            const oldValues = widget.options.values;
                            widget.options.values = values;
                            // Check if current value is still valid
                            if (!values.includes(widget.value)) {
                                // Cross-platform: normalize backslashes from Windows workflows
                                const normalized = widget.value.replace(/\\/g, '/');
                                if (normalized !== widget.value && values.includes(normalized)) {
                                    widget.value = normalized;
                                } else {
                                    widget.value = values[0] || "None";
                                }
                            }
                            // Log if new files were added
                            const newFiles = values.filter(v => !oldValues.includes(v));
                            if (newFiles.length > 0) {
                                // // // console.log(`[Smart Loader] New ${widgetName} files: ${newFiles.join(', ')}`);
                            }
                        }
                    };
                    
                    // Update checkpoint dropdown
                    if (lists.checkpoints) {
                        updateWidgetOptions("ckpt_name", lists.checkpoints);
                    }
                    
                    // Update UNet/diffusion_models dropdown
                    if (lists.diffusion_models) {
                        updateWidgetOptions("unet_name", lists.diffusion_models);
                        updateWidgetOptions("nunchaku_name", lists.diffusion_models);
                        updateWidgetOptions("qwen_name", lists.diffusion_models);
                    }
                    
                    // Update GGUF dropdown
                    if (lists.diffusion_models_gguf) {
                        updateWidgetOptions("gguf_name", lists.diffusion_models_gguf);
                    }
                    
                    // Update VAE dropdown
                    if (lists.vae) {
                        updateWidgetOptions("vae_name", lists.vae);
                    }
                    
                    // Update CLIP dropdowns (combined from clip and text_encoders)
                    if (lists.clip_combined) {
                        updateWidgetOptions("clip_name1", lists.clip_combined);
                        updateWidgetOptions("clip_name2", lists.clip_combined);
                        updateWidgetOptions("clip_name3", lists.clip_combined);
                        updateWidgetOptions("clip_name4", lists.clip_combined);
                    }
                    
                    // Update LoRA dropdowns
                    if (lists.loras) {
                        updateWidgetOptions("lora_name_1", lists.loras);
                        updateWidgetOptions("lora_name_2", lists.loras);
                        updateWidgetOptions("lora_name_3", lists.loras);
                    }
                    
                    canvasDirtyBatcher.markDirty(node, true, true);
                } catch (e) {
                    console.warn('[Smart Loader] Failed to refresh model file lists:', e);
                }
            };
            
            // Template action handler
            const handleTemplateAction = async () => {
                const templateAction = getWidgetValue("template_action");
                const templateName = getWidgetValue("template_name");
                const newTemplateName = getWidgetValue("new_template_name");
                
                await refreshTemplateList();
                
                if (templateAction === "Load" && templateName && templateName !== "None") {
                    await applyTemplate(templateName);
                    // // // console.log(`✓ Template loaded: ${templateName}`);
                } else if (templateAction === "Save" && newTemplateName && newTemplateName.trim()) {
                    // // // console.log(`✓ Queueing workflow to save template: ${newTemplateName}`);
                    pendingTemplateSave = newTemplateName.trim();
                    app.queuePrompt(0, 1);
                } else if (templateAction === "Delete" && templateName && templateName !== "None") {
                    // // // console.log(`✓ Queueing workflow to delete template: ${templateName}`);
                    pendingTemplateDelete = true;
                    app.queuePrompt(0, 1);
                }
            };
            
            let templateButton = null;
            
            const updateTemplateButton = () => {
                const templateAction = getWidgetValue("template_action");
                const hasAction = (templateAction !== "None");
                
                if (hasAction && !templateButton) {
                    templateButton = node.addWidget("button", "Execute Template Action", null, handleTemplateAction);
                    templateButton.serialize = false;
                } else if (!hasAction && templateButton) {
                    const buttonIndex = node.widgets.indexOf(templateButton);
                    if (buttonIndex >= 0) {
                        node.widgets.splice(buttonIndex, 1);
                    }
                    templateButton = null;
                }
            };
            
            const setWidgetValue = (widgetName, value) => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                if (!widget) return;
                
                // For BOOLEAN widgets, ensure proper value setting
                if (widget.type === "toggle" || widgetName.includes("_switch_") || widgetName.startsWith("configure_") || widgetName.includes("enable_")) {
                    // Force boolean conversion and update
                    const boolValue = Boolean(value);
                    
                    // When applying template, always set the value to force visual update
                    if (isApplyingTemplate || widget.value !== boolValue) {
                        widget.value = boolValue;
                        // Only trigger callback if not applying template
                        if (widget.callback && !isApplyingTemplate) {
                            widget.callback(boolValue);
                        }
                    }
                } else {
                    // Cross-platform: normalize backslashes in path values for combo widgets
                    if (typeof value === 'string' && value.includes('\\') && widget.options?.values) {
                        const normalized = value.replace(/\\\\/g, '/');
                        if (widget.options.values.includes(normalized)) {
                            value = normalized;
                        }
                    }
                    // For other widgets, normal assignment
                    if (widget.value !== value) {
                        widget.value = value;
                        // Only trigger callback if not applying template
                        if (widget.callback && !isApplyingTemplate) {
                            widget.callback(value);
                        }
                    }
                }
            };
            
            const loadTemplateConfig = async (templateName) => {
                if (!templateName || templateName === "None") return null;
                
                try {
                    // Add cache-busting parameter to force fresh fetch
                    const cacheBuster = new Date().getTime();
                    const response = await fetch(`/eclipse/loader_templates/${templateName}.json?t=${cacheBuster}`, {
                        cache: 'no-store'
                    });
                    if (response.ok) {
                        return await response.json();
                    }
                } catch (e) {
                    console.error(`Failed to load template ${templateName}:`, e);
                }
                return null;
            };
            
            const applyTemplate = async (templateName) => {
                const config = await loadTemplateConfig(templateName);
                if (!config) return;
                
                // Set flag to prevent callbacks during template application
                isApplyingTemplate = true;
                
                try {
                    // Reset ALL values to their defaults first to avoid leftover values
                
                // Model selection - reset to defaults
                setWidgetValue("model_type", "Standard Checkpoint");
                setWidgetValue("ckpt_name", "None");
                setWidgetValue("unet_name", "None");
                setWidgetValue("nunchaku_name", "None");
                setWidgetValue("qwen_name", "None");
                setWidgetValue("gguf_name", "None");
                setWidgetValue("weight_dtype", "default");
                
                // Nunchaku settings - reset to defaults
                setWidgetValue("data_type", "bfloat16");
                setWidgetValue("cache_threshold", 0.0);
                setWidgetValue("attention", "flash-attention2");
                setWidgetValue("i2f_mode", "enabled");
                setWidgetValue("cpu_offload", "auto");
                setWidgetValue("num_blocks_on_gpu", 30);
                setWidgetValue("use_pin_memory", "enable");
                
                // GGUF settings - reset to defaults
                setWidgetValue("gguf_dequant_dtype", "default");
                setWidgetValue("gguf_patch_dtype", "default");
                setWidgetValue("gguf_patch_on_device", false);
                
                // Configuration toggles - reset to defaults
                setWidgetValue("configure_clip", true);
                setWidgetValue("configure_vae", true);
                setWidgetValue("configure_model_only_lora", false);
                setWidgetValue("configure_model_sampling", false);
                
                // Model Sampling settings - reset to defaults
                setWidgetValue("sampling_method", "None");
                setWidgetValue("shift", 3.0);
                setWidgetValue("base_shift", 0.5);
                setWidgetValue("sampling_width", 1024);
                setWidgetValue("sampling_height", 1024);
                
                // CLIP settings - reset to defaults
                setWidgetValue("clip_source", "Baked");
                setWidgetValue("clip_count", "1");
                setWidgetValue("clip_name1", "None");
                setWidgetValue("clip_name2", "None");
                setWidgetValue("clip_name3", "None");
                setWidgetValue("clip_name4", "None");
                setWidgetValue("clip_type", "flux");
                setWidgetValue("enable_clip_layer", true);
                setWidgetValue("stop_at_clip_layer", -2);
                
                // VAE settings - reset to defaults
                setWidgetValue("vae_source", "Baked");
                setWidgetValue("vae_name", "None");
                
                // LoRA settings - reset to defaults
                setWidgetValue("lora_count", "1");
                for (let i = 1; i <= 3; i++) {
                    setWidgetValue(`lora_switch_${i}`, false);
                    setWidgetValue(`lora_name_${i}`, "None");
                    setWidgetValue(`lora_weight_${i}`, 1.0);
                }
                
                // Now apply template values (overriding defaults where specified)
                if (config.model_type !== undefined) setWidgetValue("model_type", config.model_type);
                if (config.weight_dtype !== undefined) setWidgetValue("weight_dtype", config.weight_dtype);
                
                // Now apply template values (overriding defaults where specified)
                if (config.model_type !== undefined) setWidgetValue("model_type", config.model_type);
                if (config.weight_dtype !== undefined) setWidgetValue("weight_dtype", config.weight_dtype);
                
                if (config.configure_clip !== undefined) setWidgetValue("configure_clip", config.configure_clip);
                if (config.configure_vae !== undefined) setWidgetValue("configure_vae", config.configure_vae);
                if (config.configure_model_only_lora !== undefined) setWidgetValue("configure_model_only_lora", config.configure_model_only_lora);
                if (config.configure_model_sampling !== undefined) setWidgetValue("configure_model_sampling", config.configure_model_sampling);
                
                // Model Sampling settings
                if (config.sampling_method !== undefined) setWidgetValue("sampling_method", config.sampling_method);
                if (config.sampling_subtype !== undefined) setWidgetValue("sampling_subtype", config.sampling_subtype);
                if (config.shift !== undefined) setWidgetValue("shift", config.shift);
                if (config.base_shift !== undefined) setWidgetValue("base_shift", config.base_shift);
                if (config.sampling_width !== undefined) setWidgetValue("sampling_width", config.sampling_width);
                if (config.sampling_height !== undefined) setWidgetValue("sampling_height", config.sampling_height);
                if (config.original_timesteps !== undefined) setWidgetValue("original_timesteps", config.original_timesteps);
                if (config.zsnr !== undefined) setWidgetValue("zsnr", config.zsnr);
                if (config.sigma_max !== undefined) setWidgetValue("sigma_max", config.sigma_max);
                if (config.sigma_min !== undefined) setWidgetValue("sigma_min", config.sigma_min);
                
                // Nunchaku settings
                if (config.data_type !== undefined) setWidgetValue("data_type", config.data_type);
                if (config.cache_threshold !== undefined) setWidgetValue("cache_threshold", config.cache_threshold);
                if (config.attention !== undefined) setWidgetValue("attention", config.attention);
                if (config.i2f_mode !== undefined) setWidgetValue("i2f_mode", config.i2f_mode);
                if (config.cpu_offload !== undefined) setWidgetValue("cpu_offload", config.cpu_offload);
                if (config.num_blocks_on_gpu !== undefined) setWidgetValue("num_blocks_on_gpu", config.num_blocks_on_gpu);
                if (config.use_pin_memory !== undefined) setWidgetValue("use_pin_memory", config.use_pin_memory);
                
                // GGUF settings
                if (config.gguf_dequant_dtype !== undefined) setWidgetValue("gguf_dequant_dtype", config.gguf_dequant_dtype);
                if (config.gguf_patch_dtype !== undefined) setWidgetValue("gguf_patch_dtype", config.gguf_patch_dtype);
                if (config.gguf_patch_on_device !== undefined) setWidgetValue("gguf_patch_on_device", config.gguf_patch_on_device);
                
                // CLIP settings
                if (config.clip_source !== undefined) setWidgetValue("clip_source", config.clip_source);
                if (config.clip_count !== undefined) setWidgetValue("clip_count", config.clip_count);
                if (config.clip_name1 !== undefined) setWidgetValue("clip_name1", config.clip_name1);
                if (config.clip_name2 !== undefined) setWidgetValue("clip_name2", config.clip_name2);
                if (config.clip_name3 !== undefined) setWidgetValue("clip_name3", config.clip_name3);
                if (config.clip_name4 !== undefined) setWidgetValue("clip_name4", config.clip_name4);
                if (config.clip_type !== undefined) setWidgetValue("clip_type", config.clip_type);
                if (config.enable_clip_layer !== undefined) setWidgetValue("enable_clip_layer", config.enable_clip_layer);
                if (config.stop_at_clip_layer !== undefined) setWidgetValue("stop_at_clip_layer", config.stop_at_clip_layer);
                
                // VAE settings
                if (config.vae_source !== undefined) setWidgetValue("vae_source", config.vae_source);
                if (config.vae_name !== undefined) setWidgetValue("vae_name", config.vae_name);
                
                // LoRA settings
                if (config.lora_count !== undefined) setWidgetValue("lora_count", config.lora_count);
                for (let i = 1; i <= 3; i++) {
                    if (config[`lora_switch_${i}`] !== undefined) setWidgetValue(`lora_switch_${i}`, config[`lora_switch_${i}`]);
                    if (config[`lora_name_${i}`] !== undefined) setWidgetValue(`lora_name_${i}`, config[`lora_name_${i}`]);
                    if (config[`lora_weight_${i}`] !== undefined) setWidgetValue(`lora_weight_${i}`, config[`lora_weight_${i}`]);
                }
                
                // Model file selections
                if (config.ckpt_name !== undefined) setWidgetValue("ckpt_name", config.ckpt_name);
                if (config.unet_name !== undefined) setWidgetValue("unet_name", config.unet_name);
                if (config.nunchaku_name !== undefined) setWidgetValue("nunchaku_name", config.nunchaku_name);
                if (config.qwen_name !== undefined) setWidgetValue("qwen_name", config.qwen_name);
                if (config.gguf_name !== undefined) setWidgetValue("gguf_name", config.gguf_name);
                
                // // // console.log(`✓ Template '${templateName}' applied`);
                
                } finally {
                    // Always reset flag and update visibility, even if there's an error
                    isApplyingTemplate = false;
                    debouncedUpdateVisibility();
                    
                    // Force canvas redraw to ensure widget visuals are updated
                    canvasDirtyBatcher.markDirty(node, true, true);
                }
            };
            
            const setWidgetVisible = (widgetName, visible) => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                if (!widget) return;
                
                if (visible) {
                    if (widget.origType) {
                        widget.type = widget.origType;
                    } else if (widget.type === "converted-widget") {
                        widget.type = "combo";
                        widget.origType = "combo";
                    }
                    delete widget.computeSize;
                    widget.hidden = false;
                } else {
                    if (widget.type !== "converted-widget" && !widget.origType) {
                        widget.origType = widget.type;
                    }
                    widget.type = "converted-widget";
                    widget.computeSize = () => [0, -4];
                    widget.hidden = true;
                }
            };
            
            const getWidgetValue = (name) => {
                const widget = node.widgets?.find(w => w.name === name);
                return widget ? widget.value : null;
            };
            
            // Store original unfiltered CLIP options
            const originalClipOptions = {};
            
            // Store original unfiltered model options
            const originalModelOptions = {};
            
            // Filter model widget options based on model type
            const filterModelOptions = () => {
                const modelType = getWidgetValue("model_type");
                
                // Define which models to filter and their file extensions
                const modelWidgets = {
                    "ckpt_name": {
                        show: modelType === "Standard Checkpoint",
                        extensions: ['.safetensors', '.ckpt', '.pt', '.bin', '.sft']
                    },
                    "unet_name": {
                        show: modelType === "UNet Model",
                        extensions: ['.safetensors', '.pt', '.bin', '.sft']
                    },
                    "nunchaku_name": {
                        show: modelType === "Nunchaku Flux",
                        extensions: ['.safetensors', '.pt', '.bin', '.sft']
                    },
                    "qwen_name": {
                        show: modelType === "Nunchaku Qwen",
                        extensions: ['.safetensors', '.pt', '.bin', '.sft']
                    },
                    "zimage_name": {
                        show: modelType === "Nunchaku ZImage",
                        extensions: ['.safetensors', '.pt', '.bin', '.sft']
                    },
                    "gguf_name": {
                        show: modelType === "GGUF Model",
                        extensions: ['.gguf']
                    }
                };
                
                Object.entries(modelWidgets).forEach(([widgetName, config]) => {
                    const widget = node.widgets?.find(w => w.name === widgetName);
                    if (!widget || !widget.options) return;
                    
                    // Store original options on first run
                    if (!originalModelOptions[widgetName]) {
                        originalModelOptions[widgetName] = [...widget.options.values];
                    }
                    
                    // Get the full unfiltered list
                    const allOptions = originalModelOptions[widgetName];
                    
                    // Filter based on allowed extensions for this widget
                    const filteredOptions = allOptions.filter(name => {
                        if (name === "None") return true;
                        const nameLower = name.toLowerCase();
                        return config.extensions.some(ext => nameLower.endsWith(ext));
                    });
                    
                    // Update widget options
                    widget.options.values = filteredOptions;
                    
                    // If current value is filtered out, reset to "None"
                    if (!filteredOptions.includes(widget.value)) {
                        // Cross-platform: normalize backslashes from Windows workflows
                        const normalized = widget.value.replace(/\\/g, '/');
                        if (normalized !== widget.value && filteredOptions.includes(normalized)) {
                            widget.value = normalized;
                        } else {
                            widget.value = "None";
                        }
                    }
                });
            };
            
            // CLIP widget options - no filtering applied
            // All CLIP files (.gguf, .safetensors, etc.) can be used with any model type
            const filterClipOptions = () => {
                const clipWidgets = ["clip_name1", "clip_name2", "clip_name3", "clip_name4"];
                
                clipWidgets.forEach(widgetName => {
                    const widget = node.widgets?.find(w => w.name === widgetName);
                    if (!widget || !widget.options) return;
                    
                    // Store original options on first run
                    if (!originalClipOptions[widgetName]) {
                        originalClipOptions[widgetName] = [...widget.options.values];
                    }
                    
                    // Always show all CLIP files - no filtering by model type
                    widget.options.values = originalClipOptions[widgetName];
                });
            };
            
            const updateVisibility = (skipPerformanceChecks = false) => {
                // Skip if node doesn't have ID yet (during initial creation)
                if (node.id === -1) return;
                
                // Performance: Skip if node is not visible
                if (!skipPerformanceChecks && !isNodeVisible(node)) {
                    return;
                }
                
                const templateAction = getWidgetValue("template_action");
                const modelType = getWidgetValue("model_type");
                const configureClip = getWidgetValue("configure_clip");
                const configureVae = getWidgetValue("configure_vae");
                const configureLora = getWidgetValue("configure_model_only_lora");
                const configureModelSampling = getWidgetValue("configure_model_sampling");
                const samplingMethod = getWidgetValue("sampling_method");
                const clipSource = getWidgetValue("clip_source");
                const clipCount = parseInt(getWidgetValue("clip_count")) || 1;
                const vaeSource = getWidgetValue("vae_source");
                const loraCount = parseInt(getWidgetValue("lora_count")) || 3;
                
                const isStandard = (modelType === "Standard Checkpoint");
                const isUNet = (modelType === "UNet Model");
                const isNunchaku = (modelType === "Nunchaku Flux");
                const isQwen = (modelType === "Nunchaku Qwen");
                const isZImage = (modelType === "Nunchaku ZImage");
                const isGGUF = (modelType === "GGUF Model");
                const useExternalClip = (clipSource === "External");
                const useExternalVae = (vaeSource === "External");
                
                // Filter model and CLIP options based on model type
                filterModelOptions();
                filterClipOptions();
                
                // Template Management
                const isLoadOrDelete = (templateAction === "Load" || templateAction === "Delete");
                const isSave = (templateAction === "Save");
                setWidgetVisible("template_name", isLoadOrDelete);
                setWidgetVisible("new_template_name", isSave);
                updateTemplateButton();
                
                // Model Selection
                setWidgetVisible("ckpt_name", isStandard);
                setWidgetVisible("unet_name", isUNet);
                setWidgetVisible("nunchaku_name", isNunchaku);
                setWidgetVisible("qwen_name", isQwen);
                setWidgetVisible("zimage_name", isZImage);
                setWidgetVisible("gguf_name", isGGUF);
                setWidgetVisible("weight_dtype", isUNet);
                
                // Nunchaku Flux Options
                setWidgetVisible("data_type", isNunchaku);
                setWidgetVisible("cache_threshold", isNunchaku);
                setWidgetVisible("attention", isNunchaku);
                setWidgetVisible("i2f_mode", isNunchaku);
                
                // Shared Nunchaku Options (Qwen & ZImage)
                setWidgetVisible("cpu_offload", isNunchaku || isQwen || isZImage);
                
                // Nunchaku Qwen/ZImage Options
                setWidgetVisible("num_blocks_on_gpu", isQwen || isZImage);
                setWidgetVisible("use_pin_memory", isQwen || isZImage);
                
                // GGUF Options
                setWidgetVisible("gguf_dequant_dtype", isGGUF);
                setWidgetVisible("gguf_patch_dtype", isGGUF);
                setWidgetVisible("gguf_patch_on_device", isGGUF);
                
                // Device Selection
                setWidgetVisible("model_device", true); // Always visible
                setWidgetVisible("clip_device", configureClip);
                setWidgetVisible("vae_device", configureVae);
                
                // CLIP Configuration
                setWidgetVisible("clip_source", configureClip);
                setWidgetVisible("clip_count", configureClip && useExternalClip);
                setWidgetVisible("clip_name1", configureClip && useExternalClip && clipCount >= 1);
                setWidgetVisible("clip_name2", configureClip && useExternalClip && clipCount >= 2);
                setWidgetVisible("clip_name3", configureClip && useExternalClip && clipCount >= 3);
                setWidgetVisible("clip_name4", configureClip && useExternalClip && clipCount >= 4);
                setWidgetVisible("clip_type", configureClip && useExternalClip);
                setWidgetVisible("enable_clip_layer", configureClip && isStandard);
                setWidgetVisible("stop_at_clip_layer", configureClip && isStandard);
                
                // VAE Configuration
                setWidgetVisible("vae_source", configureVae);
                setWidgetVisible("vae_name", configureVae && useExternalVae);
                
                // LoRA Configuration
                setWidgetVisible("lora_count", configureLora);
                for (let i = 1; i <= 3; i++) {
                    const showSlot = configureLora && i <= loraCount;
                    setWidgetVisible(`lora_switch_${i}`, showSlot);
                    setWidgetVisible(`lora_name_${i}`, showSlot);
                    setWidgetVisible(`lora_weight_${i}`, showSlot);
                }
                
                // Model Sampling Configuration
                setWidgetVisible("sampling_method", configureModelSampling);
                
                // Method-specific visibility
                const hasMethod = samplingMethod !== "None";
                const isFluxSampling = (samplingMethod === "Flux");
                const isLTXVSampling = (samplingMethod === "LTXV");
                const isLCMSampling = (samplingMethod === "LCM");
                const isContinuousEDM = (samplingMethod === "ContinuousEDM");
                const isContinuousV = (samplingMethod === "ContinuousV");
                const needsContinuousParams = isContinuousEDM || isContinuousV;
                
                // Universal shift (all methods except None, LCM, and Continuous*)
                const needsShift = hasMethod && !isLCMSampling && !needsContinuousParams;
                setWidgetVisible("shift", configureModelSampling && needsShift);
                
                // Flux/LTXV base_shift parameter
                setWidgetVisible("base_shift", configureModelSampling && (isFluxSampling || isLTXVSampling));
                
                // Flux width/height parameters (only Flux, not LTXV)
                setWidgetVisible("sampling_width", configureModelSampling && isFluxSampling);
                setWidgetVisible("sampling_height", configureModelSampling && isFluxSampling);
                
                // LCM-specific parameters
                setWidgetVisible("original_timesteps", configureModelSampling && isLCMSampling);
                setWidgetVisible("zsnr", configureModelSampling && isLCMSampling);
                
                // ContinuousEDM subtype
                setWidgetVisible("sampling_subtype", configureModelSampling && isContinuousEDM);
                
                // Continuous sigma parameters (EDM and V)
                setWidgetVisible("sigma_max", configureModelSampling && needsContinuousParams);
                setWidgetVisible("sigma_min", configureModelSampling && needsContinuousParams);
                
                // Smart resize using requestAnimationFrame for better performance
                requestAnimationFrame(() => {
                    const computedSize = node.computeSize();
                    const currentSize = node.size;
                    
                    const minWidth = 259;
                    const minHeight = 100;
                    
                    let newWidth = Math.max(currentSize[0], minWidth);
                    let newHeight = Math.max(computedSize[1], minHeight);
                    
                    newHeight += 5;
                    
                    const heightDiff = Math.abs(currentSize[1] - newHeight);
                    const isGrowing = newHeight > currentSize[1];
                    
                    if (isGrowing || heightDiff > 10) {
                        node.setSize([newWidth, newHeight]);
                    }
                    
                    canvasDirtyBatcher.markDirty(node, true, false);
                });
            };
            
            // Create debounced version to prevent rapid-fire updates
            const debouncedUpdateVisibility = debounce(updateVisibility, 100);
            
            // Hook into relevant widgets
            const relevantWidgets = [
                "template_action",
                "template_name",
                "model_type",
                "configure_clip",
                "configure_vae",
                "configure_model_only_lora",
                "configure_model_sampling",
                "sampling_method",
                "clip_source",
                "clip_count",
                "vae_source",
                "lora_count",
            ];
            
            relevantWidgets.forEach(widgetName => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                if (widget) {
                    const originalCallback = widget.callback;
                    widget.callback = function() {
                        if (originalCallback) {
                            originalCallback.apply(this, arguments);
                        }
                        
                        if (widgetName === "template_action" || widgetName === "template_name") {
                            const templateAction = getWidgetValue("template_action");
                            const templateName = getWidgetValue("template_name");
                            
                            // Auto-fill new_template_name when switching to Save mode
                            if (widgetName === "template_action" && templateAction === "Save") {
                                // If there's a loaded template, copy its name to new_template_name
                                if (templateName && templateName !== "None") {
                                    setWidgetValue("new_template_name", templateName);
                                }
                            }
                            
                            if (templateAction === "Load" && templateName && templateName !== "None") {
                                if (templateName !== lastTemplateName || templateAction !== lastTemplateAction) {
                                    applyTemplate(templateName);
                                    lastTemplateName = templateName;
                                    lastTemplateAction = templateAction;
                                }
                            }
                        }
                        
                        // Auto-default shift when sampling_method changes (only if shift is still at default)
                        if (widgetName === "sampling_method") {
                            const samplingMethod = getWidgetValue("sampling_method");
                            const currentShift = getWidgetValue("shift");
                            
                            // Default shift values for each method
                            const defaultShifts = {
                                "SD3": 3.0,
                                "AuraFlow": 1.73,
                                "Flux": 1.15,
                                "Stable Cascade": 2.0,
                                "LTXV": 2.05
                            };
                            
                            // Check if current shift is close to any default (within 0.01 tolerance)
                            const isDefaultShift = Object.values(defaultShifts).some(
                                defShift => Math.abs(currentShift - defShift) < 0.01
                            ) || currentShift === 3.0; // Also check against initial default
                            
                            // If shift is still at a default value and method has a specific default, update it
                            if (isDefaultShift && defaultShifts[samplingMethod]) {
                                setWidgetValue("shift", defaultShifts[samplingMethod]);
                                // // // console.log(`[Model Sampling] Auto-set shift to ${defaultShifts[samplingMethod]} for ${samplingMethod}`);
                            }
                            
                            // Auto-set sigma defaults for Continuous methods
                            if (samplingMethod === "ContinuousEDM") {
                                setWidgetValue("sigma_max", 120.0);
                                setWidgetValue("sigma_min", 0.002);
                                // // // console.log(`[Model Sampling] Auto-set sigma_max=120.0, sigma_min=0.002 for ContinuousEDM`);
                            } else if (samplingMethod === "ContinuousV") {
                                setWidgetValue("sigma_max", 500.0);
                                setWidgetValue("sigma_min", 0.03);
                                // // // console.log(`[Model Sampling] Auto-set sigma_max=500.0, sigma_min=0.03 for ContinuousV`);
                            }
                        }
                        
                        debouncedUpdateVisibility();
                    };
                }
            });
            
            // Listen for execution events
            const onExecuted = node.onExecuted;
            node.onExecuted = async function(message) {
                if (onExecuted) {
                    onExecuted.apply(this, arguments);
                }
                
                if (pendingTemplateSave) {
                    const savedTemplateName = pendingTemplateSave;
                    pendingTemplateSave = null;
                    
                    // // // console.log(`✓ Save completed, refreshing template list...`);
                    await new Promise(resolve => setTimeout(resolve, 100));
                    const templates = await refreshTemplateList();
                    broadcastTemplateListChanged(templates, node.id);
                    
                    setWidgetValue("template_action", "Load");
                    setWidgetValue("template_name", savedTemplateName);
                    setWidgetValue("new_template_name", "");
                    updateVisibility();
                    // // // console.log(`✓ Switched to Load mode with template: ${savedTemplateName}`);
                }
                
                if (pendingTemplateDelete) {
                    pendingTemplateDelete = false;
                    
                    // // // console.log(`✓ Delete completed, refreshing template list...`);
                    await new Promise(resolve => setTimeout(resolve, 100));
                    const templates = await refreshTemplateList();
                    broadcastTemplateListChanged(templates, node.id);
                    
                    setWidgetValue("template_action", "Load");
                    setWidgetValue("template_name", "None");
                    updateVisibility();
                    // // // console.log(`✓ Template deleted, switched to Load mode`);
                }
            };
            
            // Listen for execution interrupts (store reference for cleanup)
            const _execInterruptHandler = async (event) => {
                // // // console.log('[SmartLoader] execution_interrupted event:', event.detail);
                
                if (pendingTemplateSave || pendingTemplateDelete) {
                    // // // console.log('[SmartLoader] Processing pending template operation...');
                    
                    if (pendingTemplateSave) {
                        const savedTemplateName = pendingTemplateSave;
                        pendingTemplateSave = null;
                        
                        // // // console.log(`✓ Save interrupted (as expected), refreshing template list...`);
                        await new Promise(resolve => setTimeout(resolve, 300));
                        const templates = await refreshTemplateList();
                        broadcastTemplateListChanged(templates, node.id);
                        
                        setWidgetValue("template_action", "Load");
                        setWidgetValue("template_name", savedTemplateName);
                        setWidgetValue("new_template_name", "");
                        updateVisibility();
                        // // // console.log(`✓ Switched to Load mode with template: ${savedTemplateName}`);
                    }
                    
                    if (pendingTemplateDelete) {
                        pendingTemplateDelete = false;
                        
                        // // // console.log(`✓ Delete interrupted (as expected), refreshing template list...`);
                        await new Promise(resolve => setTimeout(resolve, 300));
                        const templates = await refreshTemplateList();
                        broadcastTemplateListChanged(templates, node.id);
                        
                        setWidgetValue("template_action", "Load");
                        setWidgetValue("template_name", "None");
                        updateVisibility();
                        // // // console.log(`✓ Template deleted, switched to Load mode`);
                    }
                }
            };
            api.addEventListener("execution_interrupted", _execInterruptHandler);
            
            // Listen for template list changes from other nodes (cross-node sync)
            const _templateChangedHandler = (event) => {
                const { templates, sourceNodeId } = event.detail;
                if (sourceNodeId === node.id) return;
                if (!templates) return;
                const templateWidget = node.widgets?.find(w => w.name === "template_name");
                if (templateWidget && templateWidget.options && templateWidget.options.values) {
                    templateWidget.options.values = templates;
                    if (!templates.includes(templateWidget.value)) {
                        templateWidget.value = "None";
                    }
                    canvasDirtyBatcher.markDirty(node, true, true);
                }
            };
            document.addEventListener(TEMPLATE_CHANGED_EVENT, _templateChangedHandler);
            
            // Cleanup event listeners when node is removed to prevent leaks
            const _originalOnRemoved = node.onRemoved;
            node.onRemoved = function() {
                api.removeEventListener("execution_interrupted", _execInterruptHandler);
                document.removeEventListener(TEMPLATE_CHANGED_EVENT, _templateChangedHandler);
                if (_originalOnRemoved) _originalOnRemoved.apply(this, arguments);
            };
            
            // Initial setup - defer slightly to ensure node has valid ID
            // LiteGraph assigns ID after onNodeCreated returns
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    updateVisibility(true);
                    refreshTemplateList();
                    refreshModelFileLists();
                }
            }, 0);
            
            // Lazy init for when node becomes visible - only refresh lists
            // NOTE: updateVisibility() removed - state is already set, no need to recalculate on redraw
            setupLazyInit(node, function() {
                refreshTemplateList();
                refreshModelFileLists();
            });
            
            // Hook into onConfigure to reload template when workflow is loaded
            const onConfigure = node.onConfigure;
            node.onConfigure = function(info) {
                if (onConfigure) {
                    onConfigure.apply(this, arguments);
                }
                
                // Refresh model file lists when workflow is configured (page reload / workflow open)
                refreshModelFileLists();
                
                // After workflow is configured, check if a template is selected and reload it
                setTimeout(() => {
                    const templateAction = getWidgetValue("template_action");
                    const templateName = getWidgetValue("template_name");
                    
                    if (templateAction === "Load" && templateName && templateName !== "None") {
                        // // // console.log(`[SmartLoader] Workflow loaded, reapplying template: ${templateName}`);
                        applyTemplate(templateName);
                    } else {
                        // CRITICAL: Use skipPerformanceChecks=true for workflow load
                        // Nodes outside viewport must still have visibility configured
                        updateVisibility(true);
                    }
                }, 100);  // Standardized delay for LiteGraph widget value restoration
            };
            
            return r;
        };
    },
});
