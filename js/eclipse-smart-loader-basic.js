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

const NODE_NAME = "Smart Loader Basic [Eclipse]";

app.registerExtension({
    name: "Eclipse.SmartLoaderBasic",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const node = this;
            
            // Helper function to get widget value
            const getWidgetValue = (widgetName) => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                return widget ? widget.value : undefined;
            };
            
            const setWidgetValue = (widgetName, value) => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                if (!widget) return;
                
                // Cross-platform: normalize backslashes in path values for combo widgets
                if (typeof value === 'string' && value.includes('\\') && widget.options?.values) {
                    const normalized = value.replace(/\\\\/g, '/');
                    if (widget.options.values.includes(normalized)) {
                        value = normalized;
                    }
                }
                if (widget.value !== value) {
                    widget.value = value;
                    if (widget.callback) {
                        widget.callback(value);
                    }
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
                
                const modelType = getWidgetValue("model_type");
                const configureClip = getWidgetValue("configure_clip");
                const configureVae = getWidgetValue("configure_vae");
                const configureLora = getWidgetValue("configure_model_only_lora");
                const clipSource = getWidgetValue("clip_source");
                const clipCount = parseInt(getWidgetValue("clip_count")) || 1;
                const vaeSource = getWidgetValue("vae_source");
                const loraCount = parseInt(getWidgetValue("lora_count")) || 3;
                
                const isStandard = (modelType === "Standard Checkpoint");
                const isUNet = (modelType === "UNet Model");
                const isGGUF = (modelType === "GGUF Model");
                const useExternalClip = (clipSource === "External");
                const useExternalVae = (vaeSource === "External");
                
                // Filter model and CLIP options based on model type
                filterModelOptions();
                filterClipOptions();
                
                // Model Selection
                setWidgetVisible("ckpt_name", isStandard);
                setWidgetVisible("unet_name", isUNet);
                setWidgetVisible("gguf_name", isGGUF);
                setWidgetVisible("weight_dtype", isUNet);
                
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
                "model_type",
                "configure_clip",
                "configure_vae",
                "configure_model_only_lora",
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
                        debouncedUpdateVisibility();
                    };
                }
            });
            
            // Refresh model file lists from server (checkpoints, VAE, CLIP, LoRAs, etc.)
            const refreshModelFileLists = async () => {
                try {
                    const response = await fetch('/eclipse/model_files_all');
                    if (!response.ok) return;
                    
                    const lists = await response.json();
                    
                    // Helper to update a widget's options
                    const updateWidgetOptions = (widgetName, values) => {
                        const widget = node.widgets?.find(w => w.name === widgetName);
                        if (widget && widget.options && widget.options.values) {
                            const oldValues = widget.options.values;
                            widget.options.values = values;
                            // Check if current value is still valid
                            if (!values.includes(widget.value)) {
                                // Cross-platform: normalize backslashes from Windows workflows
                                const normalized = widget.value.replace(/\\\\/g, '/');
                                if (normalized !== widget.value && values.includes(normalized)) {
                                    widget.value = normalized;
                                } else {
                                    widget.value = values[0] || "None";
                                }
                            }
                            // Log if new files were added
                            const newFiles = values.filter(v => !oldValues.includes(v));
                            if (newFiles.length > 0) {
                                // // // console.log(`[Smart Loader Basic] New ${widgetName} files: ${newFiles.join(', ')}`);
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
                    console.warn('[Smart Loader Basic] Failed to refresh model file lists:', e);
                }
            };
            
            // Initial setup - defer slightly to ensure node has valid ID
            // LiteGraph assigns ID after onNodeCreated returns
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    updateVisibility(true);
                    refreshModelFileLists();
                }
            }, 0);
            
            // Lazy init for when node becomes visible - only refresh model lists
            // NOTE: updateVisibility() removed - state is already set, no need to recalculate on redraw
            setupLazyInit(node, function() {
                refreshModelFileLists();
            });
            
            // Hook into onConfigure to refresh model lists when workflow is loaded
            const onConfigure = node.onConfigure;
            node.onConfigure = function(info) {
                if (onConfigure) {
                    onConfigure.apply(this, arguments);
                }
                
                // Refresh model file lists when workflow is configured (page reload / workflow open)
                refreshModelFileLists();
                
                // Defer visibility update until after LiteGraph finishes restoring widget values
                setTimeout(() => {
                    updateVisibility(true);
                }, 100);
            };
            
            return r;
        };
    },
});
