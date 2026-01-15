// eclipse-smart-loader-lm-v2.js
// Dynamic UI for Smart Language Model Loader v2
//
// Handles:
// - Template-first workflow (template → family → method → models)
// - Dynamic dropdown updates based on template selection
// - Show/hide method-specific widgets
// - Model size/VRAM indicators

import { app, api } from './comfy/index.js';
import {
    debounce,
    isNodeVisible,
    canvasDirtyBatcher,
    setupLazyInit
} from './eclipse-widget-performance-utils.js';

const NODE_NAMES_V2 = [
    "Smart Language Model Loader v2 [Eclipse]"
];
const NODE_NAMES = NODE_NAMES_V2;
const LAST_SEED_BUTTON_LABEL = "♻️ (Use Last Queued Seed)";

const SPECIAL_SEED_RANDOM = -1;
const SPECIAL_SEED_INCREMENT = -2;
const SPECIAL_SEED_DECREMENT = -3;
const SPECIAL_SEEDS = [SPECIAL_SEED_RANDOM, SPECIAL_SEED_INCREMENT, SPECIAL_SEED_DECREMENT];

// Cache for discovered models (now list of dicts with: name, path, family, is_gguf, is_folder, is_fp8)
let discoveredModelsCache = null;
let lastCacheTime = 0;
const CACHE_DURATION = 5000; // 5 seconds

// Method support matrix - loaded from backend API
let METHOD_SUPPORT_V2 = null;
let methodSupportPromise = null;

// Fetch method support matrix from backend
async function fetchMethodSupport() {
    if (METHOD_SUPPORT_V2) return METHOD_SUPPORT_V2;
    
    // Prevent multiple concurrent fetches
    if (methodSupportPromise) return methodSupportPromise;
    
    methodSupportPromise = (async () => {
        try {
            const response = await fetch('/eclipse/smartlm_v2/method_support');
            if (response.ok) {
                METHOD_SUPPORT_V2 = await response.json();
                // // // console.log("[SmartLM] Loaded method support matrix from backend");
            } else {
                console.warn("[SmartLM] Failed to fetch method support, using fallback");
                METHOD_SUPPORT_V2 = getFallbackMethodSupport();
            }
        } catch (e) {
            console.warn("[SmartLM] Error fetching method support:", e);
            METHOD_SUPPORT_V2 = getFallbackMethodSupport();
        }
        return METHOD_SUPPORT_V2;
    })();
    
    return methodSupportPromise;
}

// Fallback matrix if API fails
function getFallbackMethodSupport() {
    return {
        "Transformers": {
            "Mistral": true,
            "Qwen": true,
            "Florence": false,
            "LLaVA": false,  // LLaVA only via Ollama registry
            "LLM (Text-Only)": true,
        },
        "GGUF (llama-cpp-python)": {
            "Mistral": false,
            "Qwen": true,
            "Florence": false,
            "LLaVA": false,  // LLaVA only via Ollama registry
            "LLM (Text-Only)": true,
        },
        "vLLM (Docker)": {
            "Mistral": true,
            "Qwen": true,
            "Florence": false,
            "LLaVA": false,  // LLaVA only via Ollama registry
            "LLM (Text-Only)": true,
        },
        "SGLang (Docker)": {
            "Mistral": true,
            "Qwen": true,
            "Florence": false,
            "LLaVA": false,  // LLaVA only via Ollama registry
            "LLM (Text-Only)": true,
        },
        "Ollama (Docker)": {
            "Mistral": true,
            "Qwen": true,
            "Florence": false,
            "LLaVA": true,  // Generic vision models from Ollama registry
            "LLM (Text-Only)": true,
        },
        "llama.cpp (Docker)": {
            "Mistral": true,
            "Qwen": true,
            "Florence": false,
            "LLaVA": false,  // LLaVA only via Ollama registry, not local GGUF
            "LLM (Text-Only)": true,
        },
    };
}

// Filter models by method and family using detected family from config.json
function filterModelsByMethodAndFamily(loadingMethod, modelFamily, discoveredModels) {
    if (!discoveredModels || !Array.isArray(discoveredModels)) return ["None"];
    
    // Handle both old format (strings) and new format (dicts with family)
    const isNewFormat = discoveredModels.length > 0 && typeof discoveredModels[0] === 'object';
    
    if (!isNewFormat) {
        // Legacy string format - use simple filtering
        const validModels = discoveredModels.filter(name => 
            !name.startsWith("(") && name !== "None"
        );
        if (validModels.length === 0) return ["None"];
        
        let compatible = [];
        if (loadingMethod === "GGUF (llama-cpp-python)") {
            compatible = validModels.filter(name => name.toLowerCase().endsWith('.gguf'));
        } else {
            compatible = validModels.filter(name => 
                name.endsWith('/') || name.toLowerCase().endsWith('.safetensors')
            );
        }
        return compatible.length > 0 ? ["None", ...compatible] : ["None"];
    }
    
    // New format with detected family from config.json
    let compatible = discoveredModels.filter(model => {
        // Filter by loading method (GGUF vs Transformers/vLLM/SGLang)
        if (loadingMethod === "GGUF (llama-cpp-python)") {
            // llama.cpp (local) only supports GGUF files
            if (!model.is_gguf) return false;
        } else if (loadingMethod === "Ollama (Docker)" || loadingMethod === "llama.cpp (Docker)") {
            // Docker backends (Ollama/llama.cpp) only support GGUF files
            // These support Mistral3 architecture which vLLM GGUF doesn't
            if (!model.is_gguf) return false;
        } else if (loadingMethod === "vLLM (Docker)" || loadingMethod === "SGLang (Docker)") {
            // vLLM/SGLang support GGUF (experimental) and non-GGUF formats
            // Allow both, but GGUF must be single-file
            // Note: vLLM/SGLang GGUF is experimental and under-optimized
        } else {
            // Transformers uses folders or safetensors (not GGUF)
            if (model.is_gguf) return false;
        }
        
        // Filter by model family using detected family from config.json
        const detectedFamily = model.family || "";
        
        // Family matching:
        // - "LLM (Text-Only)" matches "LLM (Text-Only)" detected family
        // - "Qwen" matches "Qwen" detected family
        // - "Mistral" matches "Mistral" detected family
        // - Also allow text-only models for any family if user selects them explicitly
        if (modelFamily === detectedFamily) {
            return true;
        }
        
        // Allow LLM (Text-Only) models to show in any text-capable family 
        // but only when the user explicitly selects LLM (Text-Only)
        // This prevents text-only Qwen models from showing under "Qwen" vision family
        
        return false;
    });
    
    // Extract names for the dropdown
    const names = compatible.map(model => model.name);
    
    return names.length > 0 ? ["None", ...names] : ["None"];
}

// Cache for templates with their metadata
let templatesCache = null;
let templatesLoadingPromise = null;

// Debouncing for execution-triggered refreshes
let executionRefreshTimeout = null;
let lastExecutionRefreshTime = 0;

// Invalidate template cache to force refresh
function invalidateTemplatesCache() {
    templatesCache = null;
    templatesLoadingPromise = null;
    // // // console.log("[SmartLM] Templates cache invalidated");
}

// Silent template cache invalidation (for execution-triggered refreshes)
function invalidateTemplatesCacheSilent() {
    templatesCache = null;
    templatesLoadingPromise = null;
}

// Invalidate discovered models cache to force refresh
function invalidateModelsCache() {
    discoveredModelsCache = null;
    lastCacheTime = 0;
    // // // console.log("[SmartLM] Discovered models cache invalidated");
}

// Silent models cache invalidation (for execution-triggered refreshes)
function invalidateModelsCacheSilent() {
    discoveredModelsCache = null;
    lastCacheTime = 0;
}

// Refresh template list for a specific node
async function refreshTemplateList(node) {
    try {
        // Invalidate caches first
        invalidateTemplatesCache();
        invalidateModelsCache();
        
        const response = await fetch('/eclipse/smartlm_templates_list');
        if (response.ok) {
            const templates = await response.json();
            const templateWidget = node.widgets?.find(w => w.name === "template_name");
            if (templateWidget && templateWidget.options && templateWidget.options.values) {
                const oldValues = [...templateWidget.options.values];
                updateDropdown(templateWidget, templates, "None");
                
                // Check if new templates were added
                const newTemplates = templates.filter(t => !oldValues.includes(t));
                if (newTemplates.length > 0) {
                    // // // console.log(`[SmartLM] New templates added: ${newTemplates.join(', ')}`);
                }
                
                node.setDirtyCanvas(true, true);
            }
        }
        
        // Also refresh the model_name dropdown (for newly downloaded models)
        const modelNameWidget = node.widgets?.find(w => w.name === "model_name");
        const modelFamilyWidget = node.widgets?.find(w => w.name === "model_family");
        const loadingMethodWidget = node.widgets?.find(w => w.name === "loading_method");
        
        if (modelNameWidget && modelFamilyWidget && loadingMethodWidget) {
            // Force refresh discovered models
            const discovered = await discoverModels(true);
            const method = loadingMethodWidget.value;
            const family = modelFamilyWidget.value;
            
            // filterModelsByMethodAndFamily uses config.json-based family detection
            let compatibleModels = filterModelsByMethodAndFamily(method, family, discovered);
            
            const oldModelValues = [...(modelNameWidget.options?.values || [])];
            updateDropdown(modelNameWidget, compatibleModels, compatibleModels[0] || "None");
            
            // Check if new models were added
            const newModels = compatibleModels.filter(m => !oldModelValues.includes(m));
            if (newModels.length > 0) {
                // // // console.log(`[SmartLM] New local models found: ${newModels.join(', ')}`);
            }

            // Also refresh mmproj_local dropdown if present
            const mmprojLocalWidget = node.widgets?.find(w => w.name === "mmproj_local");
            try {
                const mmprojResponse = await fetch('/eclipse/smartlm_v2/mmproj_list');
                if (mmprojResponse.ok && mmprojLocalWidget) {
                    const mmprojFiles = await mmprojResponse.json();
                    const oldMmprojValues = [...(mmprojLocalWidget.options?.values || [])];
                    updateDropdown(mmprojLocalWidget, mmprojFiles, mmprojFiles[0] || "None");
                    const newMmproj = mmprojFiles.filter(m => !oldMmprojValues.includes(m));
                    if (newMmproj.length > 0) {
                        // // // console.log(`[SmartLM] New mmproj files found: ${newMmproj.join(', ')}`);
                    }
                }
            } catch (e) {
                console.warn('[SmartLM] Failed to refresh mmproj list:', e);
            }
        }
    } catch (e) {
        console.error('[SmartLM] Failed to refresh template list:', e);
    }
}

// Separator tokens used in the preset prompts list (display-only markers)
const PRESET_SEPARATOR_TOKENS = {
    "__SEP__CUSTOM__": "──────── Direct / Custom ───────",
    "__SEP__VISION__": "──────── Vision tasks ───────",
    "__SEP__DETECTION__": "──────── Detection tasks ───────",
    "__SEP__TEXT__": "──────── Text tasks ───────",
    "__SEP__REFINE__": "──────── Refine tasks ───────"
};

// Caches and helper sets for preset prompts
let presetRawPrompts = null;
let presetPromptsCache = null; // cached DISPLAY list (with separators mapped)
let presetPromptsLoadingPromise = null; // prevent concurrent loads
let presetSeparatorDisplaySet = new Set(Object.values(PRESET_SEPARATOR_TOKENS));

// Sectioned lists (populated from server on startup)
// Keys: custom, vision, detection, text, refine (each is an array of display values)
let presetSections = { custom: [], vision: [], detection: [], text: [], refine: [] };

// Map from normalized display name -> full task metadata (name, id, prompt, families, system_prompt)
let presetTaskMap = {}; // filled by loadPresetPrompts

// Florence runtime mapping caches (created at load time)
let florenceDisplaySet = new Set();           // Set of human-readable Florence task display names
let florenceDisplayOrdered = [];              // Ordered list of Florence display names (preserves JSON key order)
let florenceKeyToDisplay = {};                // machine key -> display name mapping (for template matching)

// Module-level loader for preset prompts
async function loadPresetPrompts() {
    if (presetPromptsCache) return presetPromptsCache;
    
    // Prevent concurrent loads by returning existing promise
    if (presetPromptsLoadingPromise) {
        return presetPromptsLoadingPromise;
    }
    
    presetPromptsLoadingPromise = (async () => {
    try {
        const response = await fetch('/eclipse/smartlm_prompt_defaults');
        if (!response.ok) {
            throw new Error(`[SmartLM] Prompt defaults endpoint returned HTTP ${response.status}`);
        }
        const data = await response.json();

        // Expect authoritative _task_dict and _preset_prompts to be present
        if (!data || typeof data !== 'object' || !data._task_dict) {
            throw new Error('[SmartLM] Prompt defaults response missing "_task_dict" (no fallback enabled)');
        }

        const taskDict = data._task_dict || {};
        const presetData = data._preset_prompts || {};

        const custom = presetData.custom || [];
        const vision = presetData.vision || [
            "Simple Description", "Detailed Description", "Ultra Detailed Description",
            "Cinematic Description", "Image Analysis", "Video Summary", "Short Story", "OCR",
            "Tags", "Detailed Analysis", "Tags to Natural Language", "Refine Prompt"
        ];
        const detection = presetData.detection || [
            "Caption to Phrase Grounding", "Region Caption", "Dense Region Caption",
            "Region Proposal", "Referring Expression Segmentation", "OCR", "OCR With Region", "DocVQA"
        ];
        const text = presetData.text || [
            "Expand Text", "Refine & Expand Prompt", "Rewrite Style",
            "Tags to Natural Language", "Natural Language to Tags", "Translate to English",
            "Short Story", "Summarize"
        ];
        const refine = presetData.refine || [];

        // Filter out comment entries (lines starting with "_comment")
        const isCommentEntry = s => {
            if (!s) return false;
            if (typeof s === 'string') return s.toString().trim().toLowerCase().startsWith('_comment');
            // For object entries, check 'name' or 'id' fields
            if (typeof s === 'object') {
                const n = s.name || s.id || '';
                return n.toString().trim().toLowerCase().startsWith('_comment');
            }
            return false;
        };

        // Helper to extract display name from either a string or an object task
        const displayFromEntry = (e) => typeof e === 'string' ? e : (e.name || (e.id || '').toString());

        // Build presetSections (display names) and a task metadata map
        presetTaskMap = {};

        presetSections.custom = custom.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p));
        presetSections.vision = vision.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p));
        presetSections.detection = detection.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p));
        presetSections.text = text.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p));
        presetSections.refine = refine.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p));

        // Build presetTaskMap directly from authoritative taskDict (display -> meta)
        presetTaskMap = {};
        Object.entries(taskDict).forEach(([display, meta]) => {
            const norm = normalizeString(display);
            presetTaskMap[norm] = {
                name: meta.name || display,
                id: meta.id,
                prompt: meta.prompt,
                system_prompt: meta.system_prompt,
                description: meta.description || '',
                families: Array.isArray(meta.families) ? meta.families : (meta.families ? [meta.families] : ['all'])
            };
        });

        let presets = [];
        if (presetSections.custom.length || presetSections.vision.length || presetSections.detection.length || presetSections.text.length || presetSections.refine.length) {
            if (presetSections.custom.length) { presets.push(...presetSections.custom); }
            if (presetSections.vision.length) { presets.push("__SEP__VISION__"); presets.push(...presetSections.vision); }
            if (presetSections.detection.length) { presets.push("__SEP__DETECTION__"); presets.push(...presetSections.detection); }
            if (presetSections.text.length) { presets.push("__SEP__TEXT__"); presets.push(...presetSections.text); }
            if (presetSections.refine.length) { presets.push("__SEP__REFINE__"); presets.push(...presetSections.refine); }
        } else {
            // Legacy single list or dict format - filter out comment entries
            const raw = data._preset_prompts || [];
            if (Array.isArray(raw)) {
                presets = raw.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p));
            } else if (raw && typeof raw === 'object') {
                const merged = [];
                if (Array.isArray(raw.common)) merged.push(...raw.common.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p)));
                if (Array.isArray(raw.detection)) merged.push(...raw.detection.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p)));
                if (Array.isArray(raw.detection)) merged.push(...raw.detection.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p)));
                if (Array.isArray(raw.text)) merged.push(...raw.text.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p)));
                if (Array.isArray(raw.llm)) merged.push(...raw.llm.filter(p => !isCommentEntry(p)).map(p => displayFromEntry(p)));
                presets = Array.from(new Set(merged));
            } else {
                presets = [];
            }
        }

        presetRawPrompts = presets;
        const displayList = presets.map(p => PRESET_SEPARATOR_TOKENS[p] || p);
        presetPromptsCache = displayList;
        const sepValues = Object.values(PRESET_SEPARATOR_TOKENS);
        presetSeparatorDisplaySet = new Set(sepValues.filter(s => displayList.includes(s)));

        // Build Florence mapping by scanning task metadata maps (merged lists)
        florenceDisplaySet = new Set();
        florenceDisplayOrdered = [];
        florenceKeyToDisplay = {};

        // Scan in the JSON order: vision then detection then text, preserve order for Florence tasks
        const sectionsInOrder = [vision, detection, text];
        for (const section of sectionsInOrder) {
            for (const entry of section) {
                if (isCommentEntry(entry)) continue;
                const name = displayFromEntry(entry);
                const norm = normalizeString(name);
                const meta = presetTaskMap[norm] || null;
                const families = meta?.families || ['all'];
                const hasFlorence = families.some(f => f.toString().toLowerCase() === 'florence');
                if (hasFlorence) {
                    florenceDisplaySet.add(name);
                    florenceDisplayOrdered.push(name);
                    if (meta && meta.id) {
                        florenceKeyToDisplay[meta.id] = name;
                        florenceKeyToDisplay[meta.id.toLowerCase()] = name;
                    } else {
                        // No explicit id: map display name to itself for fallback matching (no separate display->key map)
                    }
                }
            }
        }

        // Debug: log mapping counts
        // // // console.log(`[SmartLM] Loaded presets: custom=${presetSections.custom.length}, vision=${presetSections.vision.length}, detection=${presetSections.detection.length}, text=${presetSections.text.length}`);
        // // // console.log(`[SmartLM] Florence mapping: ${florenceDisplayOrdered.length} display names, ${Object.keys(florenceKeyToDisplay).length} key mappings`);

        presetPromptsLoadingPromise = null; // Clear promise after successful load
        return displayList;
    } catch (e) {
        console.error("[SmartLM] Failed to load prompt defaults:", e);
        presetPromptsLoadingPromise = null; // Clear promise on error
        // Fail loudly - do not silently fallback
        throw e;
    }
    })();
    
    return presetPromptsLoadingPromise;
}

// Helper to safely update dropdowns
function updateDropdown(widget, values, defaultValue = null) {
    if (!widget) return;
    widget.options.values = values;
    const def = defaultValue !== null ? defaultValue : (values[0] || "None");
    if (!values.includes(widget.value)) {
        widget.value = def;
    }
}

// Normalize display strings for comparison
function normalizeString(s) {
    return (s || '').toString().replace(/\s+/g, ' ').trim().toLowerCase();
}

// Load all templates and cache them
async function loadAllTemplates() {
    if (templatesCache) {
        return templatesCache;
    }
    
    // Prevent concurrent loads by returning existing promise
    if (templatesLoadingPromise) {
        return templatesLoadingPromise;
    }
    
    templatesLoadingPromise = (async () => {
        try {
            const response = await fetch('/eclipse/smartlm_templates_list');
            if (!response.ok) {
                console.error("[SmartLM] Failed to fetch template list");
                return {};
            }
            
            const templateNames = await response.json();
            const templates = {};
            
            // Load each template to get its metadata (with cache busting)
            const cacheBuster = Date.now();
        for (const name of templateNames) {
            if (name === "None") continue;
            
            try {
                const templateResponse = await fetch(`/eclipse/smartlm_templates/${name}.json?v=${cacheBuster}`);
                if (templateResponse.ok) {
                    const config = await templateResponse.json();
                    templates[name] = config;
                } else {
                    console.warn(`[SmartLM] Failed to fetch template ${name}: ${templateResponse.status}`);
                }
            } catch (e) {
                console.warn(`[SmartLM] Failed to load template ${name}:`, e);
            }
        }
            
            // // // console.log(`[SmartLM] Loaded ${Object.keys(templates).length} templates`);
            templatesCache = templates;
            templatesLoadingPromise = null; // Clear promise after successful load
            return templates;
        } catch (error) {
            console.error("[SmartLM] Failed to load templates:", error);
            templatesLoadingPromise = null; // Clear promise on error
            return {};
        }
    })();
    
    return templatesLoadingPromise;
}

// Get all templates unfiltered (template-first workflow)
// Templates are no longer filtered by family/method - user sees all and selects first
function getAllTemplates(allTemplates) {
    const templateNames = Object.keys(allTemplates).sort();
    return ["None", ...templateNames];
}

// Discover models from backend
async function discoverModels(forceRefresh = false) {
    const now = Date.now();
    if (!forceRefresh && discoveredModelsCache && (now - lastCacheTime) < CACHE_DURATION) {
        return discoveredModelsCache;
    }
    
    try {
        // Fetch discovered models from backend (scans models/LLM/ folder)
        const response = await fetch('/eclipse/smartlm_v2/discover_models');
        if (response.ok) {
            const models = await response.json();
            // Response is array of dicts: {name, path, family, is_gguf, is_folder, is_fp8}
            // Family is detected from config.json architectures field
            discoveredModelsCache = models;
            lastCacheTime = now;
            return models;
        } else {
            console.warn("[SmartLM] Model discovery endpoint not found, using empty list");
            discoveredModelsCache = [];
            lastCacheTime = now;
            return [];
        }
    } catch (error) {
        console.warn("[SmartLM] Failed to discover models:", error);
        discoveredModelsCache = [];
        lastCacheTime = now;
        return [];
    }
}

// Helper function to show/hide widgets (matches v1 pattern)
function setWidgetVisible(node, widgetName, visible) {
    const widget = node.widgets?.find(w => w.name === widgetName);
    if (!widget) return;
    
    if (visible) {
        if (widget.origType) {
            widget.type = widget.origType;
        } else if (widget.type === "converted-widget") {
            // Fallback: infer original type from widget properties
            // STRING widgets with multiline are "customtext", without are "text"
            // COMBO widgets are "combo"
            if (widget.options?.multiline === true || widget.inputEl?.tagName === "TEXTAREA") {
                widget.type = "customtext";
            } else if (widget.options?.values) {
                widget.type = "combo";
            } else {
                // Default to text for simple string inputs
                widget.type = "text";
            }
            widget.origType = widget.type;
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
}

// Helper to set widget value (node-scoped, triggers callback if present)
function setWidgetValue(node, widgetName, value) {
    const widget = node.widgets?.find(w => w.name === widgetName);
    if (!widget) return;

    // Boolean/toggle-like widgets
    if (widget.type === "toggle" || widgetName.includes("_switch_") || widgetName.startsWith("configure_") || widgetName.includes("enable_")) {
        const boolValue = Boolean(value);
        if (widget.value !== boolValue) {
            widget.value = boolValue;
            if (widget.callback) widget.callback(boolValue);
        }
    } else {
        if (widget.value !== value) {
            widget.value = value;
            if (widget.callback) widget.callback(value);
        }
    }
}

// Widget visibility control
function updateWidgetVisibility(node, loadingMethod, modelFamily, skipPerformanceChecks = false) {
    // Skip if node doesn't have ID yet (during initial creation)
    if (node.id === -1) return;
    
    // Performance: Skip if node is not visible
    if (!skipPerformanceChecks && !isNodeVisible(node)) {
        return;
    }
    
    if (!node.widgets) return;
    
    // Get source widgets
    const modelSource = node.widgets?.find(w => w.name === "model_source")?.value || "Local";
    const mmprojSource = node.widgets?.find(w => w.name === "mmproj_source")?.value || "Local";
    const taskWidget = node.widgets?.find(w => w.name === "task");
    
    // Check if text input is connected (hide user_prompt if connected)
    const textInput = node.inputs?.find(input => input.name === "text");
    const isTextConnected = textInput && textInput.link != null;
    
    // Method-specific widgets
    const isTransformers = loadingMethod === "Transformers";
    const isGGUF = loadingMethod === "GGUF (llama-cpp-python)";
    const isVLLMDocker = loadingMethod === "vLLM (Docker)";
    const isVLLMNative = loadingMethod === "vLLM (Native)";
    const isVLLM = isVLLMDocker || isVLLMNative;  // Any vLLM variant
    const isSGLangDocker = loadingMethod === "SGLang (Docker)";
    const isOllamaDocker = loadingMethod === "Ollama (Docker)";
    const isLlamaCppDocker = loadingMethod === "llama.cpp (Docker)";
    const isAnyDocker = isVLLMDocker || isSGLangDocker || isOllamaDocker || isLlamaCppDocker;
    
    // Model family checks
    const isFlorence = modelFamily === "Florence";
    const isLLM = modelFamily === "LLM (Text-Only)";
    
    // Model source checks
    const isHuggingFace = modelSource === "HuggingFace";
    const isLocal = modelSource === "Local";
    
    // MMProj source checks (only for GGUF)
    const isMMProjHF = mmprojSource === "HuggingFace";
    const isMMProjLocal = mmprojSource === "Local";
    
    // Detection task check - derive list from loaded preset detection section (do not hardcode)
    const detectionTasks = (presetSections.detection || []).map(name => {
        const meta = presetTaskMap[normalizeString(name)];
        return meta && meta.id ? meta.id : null;
    }).filter(Boolean);
    const currentTask = taskWidget?.value || "";
    // Map display name to ID (for Florence) when possible
    let currentTaskId = currentTask;
    if (isFlorence) {
        const meta = presetTaskMap[normalizeString(currentTask)];
        if (meta && meta.id) currentTaskId = meta.id;
    }
    const isDetectionTask = isFlorence && detectionTasks.includes(currentTaskId);
    
    // Show/hide method-specific widgets
    // Quantization: show for Transformers (4bit/8bit/bf16) and vLLM (bitsandbytes/awq/gptq/fp8)
    // Hide for Ollama/llama.cpp Docker (they handle quantization internally via GGUF)
    setWidgetVisible(node, "quantization", isTransformers || isVLLM);
    setWidgetVisible(node, "attention_mode", isTransformers);
    // Context size: show for vision models using GGUF/llama.cpp Docker (images consume many tokens)
    // Hide for LLM (Text-Only) - text inputs are small, max_tokens controls output length
    setWidgetVisible(node, "context_size", (isGGUF || isLlamaCppDocker) && !isLLM);
    // MMProj source: for GGUF and llama.cpp Docker (both use local GGUF files with mmproj)
    // Hide for LLM (Text-Only) - text-only models don't use vision projectors
    const needsMMProj = (isGGUF || isLlamaCppDocker) && !isLLM;
    setWidgetVisible(node, "mmproj_source", needsMMProj);
    // Docker container controls: show for all Docker backends
    setWidgetVisible(node, "auto_start_container", isAnyDocker);
    setWidgetVisible(node, "auto_stop_container", isAnyDocker);
    
    // Memory management widgets:
    // For Docker backends: hide (use auto_stop_container instead)
    // For GGUF/Transformers/vLLM Native: show both (we can cache and reuse with KV cache clearing)
    setWidgetVisible(node, "memory_cleanup", !isAnyDocker);
    setWidgetVisible(node, "keep_model_loaded", !isAnyDocker);
    
    // Show/hide model source widgets
    // All Docker backends: show model_source and related widgets (templates handle model selection)
    setWidgetVisible(node, "model_source", true);
    setWidgetVisible(node, "repo_id", isHuggingFace);
    setWidgetVisible(node, "local_path", false);  // Deprecated - always hidden, use model_name for local models
    setWidgetVisible(node, "model_name", isLocal);
    
    // Show/hide mmproj source widgets (for GGUF and llama.cpp Docker)
    setWidgetVisible(node, "mmproj_url", needsMMProj && isMMProjHF);
    setWidgetVisible(node, "mmproj_path", false);  // Deprecated - always hidden, used internally for downloaded path
    setWidgetVisible(node, "mmproj_local", needsMMProj && isMMProjLocal);
    
    // Show/hide detection-specific widgets (only for Florence + detection tasks)
    setWidgetVisible(node, "detection_filter_threshold", isDetectionTask);
    setWidgetVisible(node, "nms_iou_threshold", isDetectionTask);
    

    
    // Florence detection tasks that support multi-prompt mode
    const florenceMultiPromptTasks = [
        "caption_to_phrase_grounding",
        "referring_expression_segmentation",
        "open_vocabulary_detection",
    ];
    const isFlorenceMultiPromptTask = isFlorence && florenceMultiPromptTasks.includes(currentTask);
    
    // Multi-task mode visibility
    // For Florence: only show for detection tasks (uses prompt splitting: "eyes;face;mouth")
    // For other families: show always (uses task chaining)
    const multiTaskModeWidget = node.widgets?.find(w => w.name === "multi_task_mode");
    const taskCountWidget = node.widgets?.find(w => w.name === "task_count");
    
    if (isFlorence) {
        // Florence: show multi_task_mode only for detection tasks (multi-prompt mode)
        setWidgetVisible(node, "multi_task_mode", isFlorenceMultiPromptTask);
        // If not a multi-prompt task, force multi_task_mode to false
        if (!isFlorenceMultiPromptTask && multiTaskModeWidget && multiTaskModeWidget.value === true) {
            multiTaskModeWidget.value = false;
        }
    } else {
        // Other families: always show multi_task_mode
        setWidgetVisible(node, "multi_task_mode", true);
    }
    
    // Florence uses prompt splitting (";"), not additional task dropdowns
    // So hide task_count and task_2/3/4 for Florence
    const multiTaskEnabled = multiTaskModeWidget?.value === true;
    const taskCount = taskCountWidget?.value || 2;
    
    // Show task_count only when multi_task_mode is enabled AND not Florence
    setWidgetVisible(node, "task_count", multiTaskEnabled && !isFlorence);
    
    // Show task_2/3/4 based on count (only for non-Florence)
    setWidgetVisible(node, "task_2", multiTaskEnabled && !isFlorence && taskCount >= 2);
    setWidgetVisible(node, "task_3", multiTaskEnabled && !isFlorence && taskCount >= 3);
    setWidgetVisible(node, "task_4", multiTaskEnabled && !isFlorence && taskCount >= 4);
    
    // Show/hide user_prompt - hidden when text input is connected
    // For Florence, user_prompt is only used for detection tasks (Florence uses image+task for non-detection)
    if (isTextConnected) {
        // Text connection takes precedence; hide the user_prompt (but keep its value intact in case the connection is removed)
        setWidgetVisible(node, "user_prompt", false);
    } else if (isFlorence) {
        // Florence: show user_prompt only for detection tasks
        setWidgetVisible(node, "user_prompt", isDetectionTask);
        // Only clear user_prompt if presets are fully loaded (detectionTasks has values)
        // This prevents clearing during early initialization when presetSections isn't loaded yet
        const presetsLoaded = presetSections.detection && presetSections.detection.length > 0;
        if (presetsLoaded && !isDetectionTask && !isTextConnected) {
            setWidgetValue(node, "user_prompt", "");
        }
    } else {
        // Qwen, Mistral, LLM: always show user_prompt (when text not connected)
        setWidgetVisible(node, "user_prompt", true);
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
}

app.registerExtension({
    name: "Eclipse.SmartLoaderLMv2",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (!NODE_NAMES.includes(nodeData.name)) return;
        
        // // // console.log("[SmartLM] Registering extension");
        
        // Pre-load method support matrix from backend
        await fetchMethodSupport();
        
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const node = this;
            
            // Get widgets
            const getWidget = (name) => node.widgets?.find(w => w.name === name);
            
            const setWidgetValue = (name, value) => {
                const widget = getWidget(name);
                if (widget && widget.value !== value) {
                    widget.value = value;
                    if (widget.callback) {
                        widget.callback(value);
                    }
                }
            };

            // Populate follow-up task dropdowns (task_2 / task_3 / task_4)
            const populateFollowups = async (family) => {
                const task2Widget = getWidget("task_2");
                const task3Widget = getWidget("task_3");
                const task4Widget = getWidget("task_4");
                const presets = await loadPresetPrompts();
                populateTaskWidgetWithPresets(task2Widget, presets, false, family, true);
                populateTaskWidgetWithPresets(task3Widget, presets, false, family, true);
                populateTaskWidgetWithPresets(task4Widget, presets, false, family, true);
            };
            
            // Load template configuration from server
            const loadTemplate = async (templateName) => {
                if (!templateName || templateName === "None") {
                    return null;
                }
                
                try {
                    // Add cache buster to ensure we get the latest template version
                    const cacheBuster = Date.now();
                    const response = await fetch(`/eclipse/smartlm_templates/${templateName}.json?v=${cacheBuster}`);
                    if (response.ok) {
                        const config = await response.json();
                        // // // console.log(`[SmartLM] Loaded template: ${templateName}`, config);
                        return config;
                    }
                } catch (error) {
                    console.error(`[SmartLM] Failed to load template ${templateName}:`, error);
                }
                return null;
            };
            
            const modelFamilyWidget = getWidget("model_family");
            const loadingMethodWidget = getWidget("loading_method");
            const templateNameWidget = getWidget("template_name");
            const modelNameWidget = getWidget("model_name");
            const quantizationWidget = getWidget("quantization");
            
            if (!modelFamilyWidget || !loadingMethodWidget || !modelNameWidget) {
                console.error("[SmartLM] Required widgets not found");
                return r;
            }
            
            // Quantization value mapping: internal value -> display name
            // Templates store internal values (e.g., "4bit"), widgets show display names (e.g., "4-bit (Lowest VRAM)")
            const QUANT_INTERNAL_TO_DISPLAY = {
                "auto": "Auto (Best for VRAM)",
                "4bit": "4-bit (Lowest VRAM)",
                "8bit": "8-bit (Balanced)",
                "fp16": "None (FP16)",
                "bf16": "None (BF16)",
                "fp32": "None (FP32)",
            };
            
            // Convert quantization value from template internal format to widget display format
            const quantToDisplay = (internal) => {
                return QUANT_INTERNAL_TO_DISPLAY[internal] || internal;
            };
            
            // Quantization options for different backends
            // vLLM bitsandbytes only supports 4-bit, not 8-bit
            const QUANT_OPTIONS_FULL = [
                "Auto (Best for VRAM)",
                "4-bit (Lowest VRAM)",
                "8-bit (Balanced)",
                "None (FP16)",
                "None (BF16)",
                "None (FP32)"
            ];
            const QUANT_OPTIONS_VLLM = [
                "Auto (Best for VRAM)",
                "4-bit (Lowest VRAM)",
                "None (FP16)",
                "None (BF16)",
                "None (FP32)"
            ];
            
            // Store original quantization options
            const originalQuantOptions = quantizationWidget ? [...(quantizationWidget.options?.values || QUANT_OPTIONS_FULL)] : QUANT_OPTIONS_FULL;
            
            // Function to update quantization dropdown based on loading method
            const updateQuantizationOptions = (method) => {
                if (!quantizationWidget) return;
                
                const isVLLM = method === "vLLM (Docker)" || method === "vLLM (Native)";
                const newOptions = isVLLM ? QUANT_OPTIONS_VLLM : QUANT_OPTIONS_FULL;
                
                quantizationWidget.options.values = newOptions;
                
                // If current value is 8-bit and switching to vLLM, reset to 4-bit
                if (isVLLM && quantizationWidget.value === "8-bit (Balanced)") {
                    quantizationWidget.value = "4-bit (Lowest VRAM)";
                    // // // console.log("[SmartLM] vLLM doesn't support 8-bit, switched to 4-bit");
                }
                
                // Ensure current value is still valid
                if (!newOptions.includes(quantizationWidget.value)) {
                    quantizationWidget.value = newOptions[0];
                }
            };
            
            // Load all templates once - store promise for proper async handling
            let allTemplates = {};
            let templatesLoaded = false;
            const templatesPromise = loadAllTemplates().then(templates => {
                allTemplates = templates;
                templatesLoaded = true;
                // // // console.log(`[SmartLM] Loaded ${Object.keys(allTemplates).length} templates`);
                return templates;
            });

            // Preload preset prompts into memory for fast filtering at startup
            loadPresetPrompts().catch(e => { console.warn('[SmartLM] Failed to preload prompt defaults:', e); });
            
            // Function to get all available methods (no family filtering)
            const getSupportedMethods = (modelFamily) => {
                const matrix = METHOD_SUPPORT_V2 || getFallbackMethodSupport();
                const allMethods = Object.keys(matrix);
                // Return all methods - no filtering by family
                return allMethods;
            };
            
            // Get task widget  
            const taskWidget = getWidget("task");
            
            // Preset prompts and dropdown helper are provided at module scope (shared). Use module-level helpers.
            
            function getAllowedNextTasks(currentDisplay, modelFamily) {
                // For follow-up tasks, show text and refine tasks (excludes Florence/vision)
                if (modelFamily === "Florence") return [];
                // Combine text and refine tasks for follow-up task dropdowns
                const textTasks = Array.isArray(presetSections.text) ? [...presetSections.text] : [];
                const refineTasks = Array.isArray(presetSections.refine) ? [...presetSections.refine] : [];
                // Build list with separator between text and refine sections
                let list = [...textTasks];
                if (refineTasks.length > 0) {
                    list.push("__SEP__REFINE__");
                    list.push(...refineTasks);
                }

                return list.filter(name => {
                    if (presetSeparatorDisplaySet.has(name)) return false;
                    const meta = presetTaskMap[normalizeString(name)];
                    // Exclude Florence tasks explicitly
                    if (meta && Array.isArray(meta.families) && meta.families.some(f => f.toString().toLowerCase() === 'florence')) return false;
                    // Show if families contains 'all' OR explicitly contains the current family
                    if (!meta || !meta.families) return true; // legacy: show
                    const families = meta.families.map(f => f.toString().toLowerCase());
                    if (families.includes('all')) return true;
                    if (families.includes(modelFamily.toLowerCase())) return true;
                    return false;
                });
            }

            function populateTaskWidgetWithPresets(widget, presets, skipReset=false, modelFamily=null, forNextTask=false) {
                if (!widget) return;
                // Determine which options to show based on modelFamily and whether this is a follow-up task
                let options = [];
                const normalize = normalizeString;

                if (forNextTask) {
                    // Follow-up tasks: only show text tasks (excludes Florence)
                    options = getAllowedNextTasks(widget.value, modelFamily);
                } else {
                    options = [...presets];
                    if (modelFamily === "Florence") {
                        // Show all Florence tasks (preserve order and remove separators)
                        options = florenceDisplayOrdered.filter(opt => !presetSeparatorDisplaySet.has(opt));
                    } else {
                        // Filter tasks by family compatibility
                        // Tasks are shown if their families array includes:
                        // - "all" (universal task for all families)
                        // - The current model family name (case-insensitive match)
                        // e.g., families: ["qwen", "Florence"] shows for Qwen family
                        options = options.filter(opt => {
                            if (presetSeparatorDisplaySet.has(opt)) return true; // keep separators
                            const meta = presetTaskMap[normalizeString(opt)];
                            if (!meta || !meta.families) return true; // legacy: show
                            const families = meta.families.map(f => f.toString().toLowerCase());
                            // Show if "all" is in families (universal task)
                            if (families.includes('all')) return true;
                            // Show if current model family is in families (case-insensitive)
                            // e.g., "Qwen" matches ["qwen", "Florence"]
                            if (families.includes(modelFamily.toLowerCase())) return true;
                            return false;
                        });
                    }
                }

                widget.options.values = options;

                // Find first non-separator default (for the current filtered options)
                const firstNonSep = options.find(v => !presetSeparatorDisplaySet.has(v));
                if (skipReset) {
                    if (!options.includes(widget.value) || presetSeparatorDisplaySet.has(widget.value)) {
                        widget.value = firstNonSep || "";
                    }
                } else {
                    if (!options.includes(widget.value) || presetSeparatorDisplaySet.has(widget.value)) {
                        widget.value = firstNonSep || "";
                    }
                }

                // Attach a guard to prevent selecting separators (only necessary when separators are present)
                if (!widget._Eclipse_separatorGuarded) {
                    const originalCb = widget.callback;
                    widget.callback = function(value) {
                        // If user selected a separator, auto-skip to nearest non-separator
                        if (presetSeparatorDisplaySet.has(value)) {
                            const opts = widget.options.values || [];
                            let idx = opts.indexOf(value);
                            let newVal = null;
                            // Try forward
                            for (let i = idx + 1; i < opts.length; i++) {
                                if (!presetSeparatorDisplaySet.has(opts[i])) { newVal = opts[i]; break; }
                            }
                            // Try backward
                            if (!newVal) {
                                for (let i = idx - 1; i >= 0; i--) {
                                    if (!presetSeparatorDisplaySet.has(opts[i])) { newVal = opts[i]; break; }
                                }
                            }
                            // Fallback to first non-separator
                            if (!newVal) newVal = opts.find(v => !presetSeparatorDisplaySet.has(v)) || "";
                            setWidgetValue(widget.name, newVal);
                            return; // do not call original callback with separator
                        }

                        if (originalCb) {
                            originalCb.apply(this, arguments);
                        }
                    };
                    widget._Eclipse_separatorGuarded = true;
                }
            }
            
            // Function to update task dropdown - now uses preset prompts (no family filtering)
            // skipReset: if true, don't reset task value (used when template will set it later)
            const updateTaskDropdown = async (family, skipReset = false) => {
                if (!taskWidget) return;
                const presets = await loadPresetPrompts();
                populateTaskWidgetWithPresets(taskWidget, presets, skipReset, family);
                
                // Only log if task count changed or debug mode
                if (!node._Eclipse_lastTaskCount || node._Eclipse_lastTaskCount !== presets.length) {
                    // // // console.log(`[SmartLM] Updated tasks (presets): ${presets.length}`);
                    node._Eclipse_lastTaskCount = presets.length;
                }
            };
            
            // Function to update loading method dropdown (filtered by family)
            // skipTemplateUpdate: if true, don't update template dropdown and don't reset task (used when template is the source)
            const updateMethodDropdown = async (family, skipTemplateUpdate = false) => {
                const supportedMethods = getSupportedMethods(family);
                
                // Update dropdown options
                updateDropdown(loadingMethodWidget, supportedMethods, supportedMethods[0] || "Transformers");
                
                // Update task list for new family (skip reset if loading from template)
                await updateTaskDropdown(family, skipTemplateUpdate);
                
                // Update model list for new method
                await updateModelDropdown(loadingMethodWidget.value, family);
                
                // Only log if methods changed
                const methodsKey = supportedMethods.join(',');
                if (!node._Eclipse_lastMethods || node._Eclipse_lastMethods !== methodsKey) {
                    // // // console.log(`[SmartLM] Updated methods for ${family}:`, supportedMethods);
                    node._Eclipse_lastMethods = methodsKey;
                }
            };
            
            // Function to update template dropdown (unfiltered - shows ALL templates)
            const updateTemplateDropdown = async () => {
                if (!templateNameWidget) return;
                
                // Ensure templates are loaded
                if (!templatesLoaded) {
                    await templatesPromise;
                }
                
                // Template-first workflow: show ALL templates unfiltered
                const allTemplateNames = getAllTemplates(templatesCache);
                
                // Update dropdown options
                updateDropdown(templateNameWidget, allTemplateNames, allTemplateNames[0] || "None");
                
                // Only log if templates count changed or debug mode
                const currentCount = allTemplateNames.length - 1;
                if (!node._Eclipse_lastTemplateCount || node._Eclipse_lastTemplateCount !== currentCount) {
                    // // // console.log(`[SmartLM] Updated templates (unfiltered): ${currentCount}`);
                    node._Eclipse_lastTemplateCount = currentCount;
                }
            };
            
            // Function to update model name dropdown
            const updateModelDropdown = async (method, family) => {
                const discovered = await discoverModels();
                // filterModelsByMethodAndFamily now uses config.json-based family detection
                let compatibleModels = filterModelsByMethodAndFamily(method, family, discovered);
                
                // Log how many models matched the family from config.json
                const total = discovered.length;
                const matched = compatibleModels.length - 1; // Subtract "None"
                if (matched === 0 && total > 0) {
                    // // // console.log(`[SmartLM] No models matched family "${family}" (${total} models scanned - check config.json for family detection)`);
                }
                
                // Update dropdown options
                updateDropdown(modelNameWidget, compatibleModels, compatibleModels[0] || "None");
                
                // Only log if model count changed for this method+family combination
                const modelsKey = `${method}+${family}:${matched}`;
                if (!node._Eclipse_lastModels || node._Eclipse_lastModels !== modelsKey) {
                    // // // console.log(`[SmartLM] Updated models for ${method} + ${family}: ${matched} models`);
                    node._Eclipse_lastModels = modelsKey;
                }
            };
            
            // Function to update all visibility
            const updateVisibility = (method, family, skipPerformanceChecks = false) => {
                updateWidgetVisibility(node, method, family, skipPerformanceChecks);
            };
            
            // Create debounced version to prevent rapid-fire updates
            const debouncedUpdateVisibility = debounce(updateVisibility, 100);
            
            // Map model_family (v2 loader) to model_type (Advanced Options node)
            const FAMILY_TO_MODEL_TYPE = {
                "Qwen": "QwenVL",
                "Florence": "Florence2",
                "Mistral": "Mistral",
                "LLaVA": "LLaVA",
                "LLM (Text-Only)": "LLM"
            };
            
            // Function to sync model_type in connected Advanced Options node
            const syncAdvancedOptionsModelType = (modelFamily) => {
                // Find the pipe_opt input
                const pipeOptInput = node.inputs?.find(input => input.name === "pipe_opt");
                if (!pipeOptInput || pipeOptInput.link == null) {
                    return; // No connected Advanced Options node
                }
                
                // Get the link info from the graph
                const link = app.graph.links[pipeOptInput.link];
                if (!link) return;
                
                // Find the connected node (source of the link)
                const sourceNode = app.graph.getNodeById(link.origin_id);
                if (!sourceNode) return;
                
                // Check if it's the Advanced Options node
                if (sourceNode.type !== "Pipe Out LM Advanced Options [Eclipse]") return;
                
                // Find the model_type widget
                const modelTypeWidget = sourceNode.widgets?.find(w => w.name === "model_type");
                if (!modelTypeWidget) return;
                
                // Map family to model_type
                const targetModelType = FAMILY_TO_MODEL_TYPE[modelFamily];
                if (!targetModelType) return;
                
                // Only update if different
                if (modelTypeWidget.value !== targetModelType) {
                    // // // console.log(`[SmartLM] Syncing Advanced Options model_type: ${modelFamily} -> ${targetModelType}`);
                    modelTypeWidget.value = targetModelType;
                    
                    // Trigger the callback to update widget visibility
                    if (modelTypeWidget.callback) {
                        modelTypeWidget.callback(targetModelType);
                    }
                }
            };
            
            // Flag to track if change originated from template selection
            // When true, family/method callbacks won't reset the template
            let isLoadingFromTemplate = false;
            
            // Model family change handler (now SECOND choice - after template)
            const originalFamilyCallback = modelFamilyWidget.callback;
            modelFamilyWidget.callback = async function(value) {
                // // // console.log(`[SmartLM] Model family changed: ${value}`);
                
                // Call original callback if exists
                if (originalFamilyCallback) {
                    originalFamilyCallback.apply(this, arguments);
                }
                
                // Sync model_type in connected Advanced Options node
                syncAdvancedOptionsModelType(value);
                
                // Don't reset fields if change came from template selection
                if (!isLoadingFromTemplate) {
                    // Reset template to None - this ensures clean slate for new family
                    // and prevents stale repo_id/mmproj_url from being used
                    if (templateNameWidget) templateNameWidget.value = "None";
                    
                    // Reset model selection
                    if (modelNameWidget) modelNameWidget.value = "None";
                    
                    // Reset model source and all related fields
                    const modelSourceWidget = getWidget("model_source");
                    if (modelSourceWidget) modelSourceWidget.value = "Local";
                    const repoIdWidget = getWidget("repo_id");
                    if (repoIdWidget) repoIdWidget.value = "";
                    const localPathWidget = getWidget("local_path");
                    if (localPathWidget) localPathWidget.value = "";
                    
                    // Reset mmproj fields completely
                    const mmprojSourceWidget = getWidget("mmproj_source");
                    if (mmprojSourceWidget) mmprojSourceWidget.value = "Local";
                    const mmprojUrlWidget = getWidget("mmproj_url");
                    if (mmprojUrlWidget) mmprojUrlWidget.value = "";
                    const mmprojPathWidget = getWidget("mmproj_path");
                    if (mmprojPathWidget) mmprojPathWidget.value = "";
                    const mmprojLocalWidget = getWidget("mmproj_local");
                    if (mmprojLocalWidget && mmprojLocalWidget.options.values.length > 0) {
                        mmprojLocalWidget.value = mmprojLocalWidget.options.values[0];
                    }
                }
                
                // Update method dropdown (filtered by family)
                await updateMethodDropdown(value, isLoadingFromTemplate);
                
                // Update quantization options (method may have changed)
                updateQuantizationOptions(loadingMethodWidget.value);
                
                // For Florence: multi-task works differently (prompt splitting for detection tasks)
                // Don't force disable here - let visibility handler control it based on task
                // The visibility handler will show/hide based on whether it's a detection task
                
                // Update multi-task dropdown options for new family using presets
                await populateFollowups(value);
                
                // Update visibility
                updateVisibility(loadingMethodWidget.value, value);
            };
            
            // Loading method change handler (now THIRD choice - after template and family)
            const originalLoadingMethodCallback = loadingMethodWidget.callback;
            loadingMethodWidget.callback = async function(value) {
                // // // console.log(`[SmartLM] Loading method changed: ${value}`);
                
                // Call original callback if exists
                if (originalLoadingMethodCallback) {
                    originalLoadingMethodCallback.apply(this, arguments);
                }
                
                // Clear file selections when switching to Ollama Docker
                // Ollama uses its own model registry, not local file paths
                if (value === "Ollama (Docker)") {
                    setWidgetValue("model_name", "None");
                    setWidgetValue("local_path", "");
                    setWidgetValue("mmproj_local", "");
                    setWidgetValue("mmproj_path", "");
                }
                
                // Update quantization options (vLLM doesn't support 8-bit)
                updateQuantizationOptions(value);
                
                // Update visibility (shows/hides relevant widgets for the method)
                updateVisibility(value, modelFamilyWidget.value);
            };
            
            // Model source change handler (affects repo_id/local_path visibility)
            const modelSourceWidget = getWidget("model_source");
            if (modelSourceWidget) {
                const originalModelSourceCallback = modelSourceWidget.callback;
                modelSourceWidget.callback = async function(value) {
                    // // // console.log(`[SmartLM] Model source changed: ${value}`);
                    
                    if (originalModelSourceCallback) {
                        originalModelSourceCallback.apply(this, arguments);
                    }
                    
                    // When switching to Local, refresh model list from discovery
                    if (value === "Local") {
                        await updateModelDropdown(loadingMethodWidget.value, modelFamilyWidget.value);
                    }
                    
                    updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value);
                };
            }
            
            // MMProj source change handler (affects mmproj_url/mmproj_local visibility)
            const mmprojSourceWidget = getWidget("mmproj_source");
            if (mmprojSourceWidget) {
                const originalMMProjSourceCallback = mmprojSourceWidget.callback;
                mmprojSourceWidget.callback = function(value) {
                    // // // console.log(`[SmartLM] MMProj source changed: ${value}`);
                    
                    if (originalMMProjSourceCallback) {
                        originalMMProjSourceCallback.apply(this, arguments);
                    }
                    
                    // When switching to HuggingFace, auto-populate mmproj_url from template if available
                    if (value === "HuggingFace" && templateNameWidget?.value && templateNameWidget.value !== "None") {
                        const templateConfig = allTemplates[templateNameWidget.value];
                        if (templateConfig?.mmproj_url) {
                            const mmprojUrlWidget = getWidget("mmproj_url");
                            if (mmprojUrlWidget && !mmprojUrlWidget.value) {
                                setWidgetValue("mmproj_url", templateConfig.mmproj_url);
                                // // // console.log(`[SmartLM] Auto-populated mmproj_url from template: ${templateConfig.mmproj_url}`);
                            }
                        }
                    }
                    
                    updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value);
                };
            }
            
            // Template name change handler (FIRST choice in template-first workflow)
            // When a template is selected, load family, loading_method, and paths from it
            if (templateNameWidget) {
                const originalTemplateCallback = templateNameWidget.callback;
                
                templateNameWidget.callback = async function(value) {
                    // // // console.log(`[SmartLM] Template changed: ${value}`);
                    
                    // Call original callback
                    if (originalTemplateCallback) {
                        originalTemplateCallback.apply(this, arguments);
                    }
                    
                    // Don't load if None or already loading from template
                    if (!value || value === "None" || isLoadingFromTemplate) {
                        // Keep user_prompt value when template is deselected
                        // User may have customized the prompt and doesn't want to lose it
                        return;
                    }
                    
                    isLoadingFromTemplate = true;
                    try {
                        const config = await loadTemplate(value);
                        if (!config) {
                            return;
                        }
                        
                        // // // console.log(`[SmartLM] Loading from template:`, config);
                        
                        // TEMPLATE-FIRST WORKFLOW:
                        // 1. Load model_family from template (required field)
                        // 2. Load loading_method if saved in template
                        // 3. Load paths and other settings
                        
                        // Step 1: Load model_family if present in template
                        if (config.model_family) {
                            const templateFamily = config.model_family;
                            // // // console.log(`[SmartLM] Setting family from template: ${templateFamily}`);
                            
                            // Update family dropdown value (this will trigger its callback)
                            setWidgetValue("model_family", templateFamily);
                        }
                        
                        // Step 2: Load loading_method if present in template
                        if (config.loading_method) {
                            const templateMethod = config.loading_method;
                            // Set method directly from template (no family filtering)
                            // // // console.log(`[SmartLM] Setting method from template: ${templateMethod}`);
                            setWidgetValue("loading_method", templateMethod);
                        }
                        
                        // Step 2.5: Refresh model dropdown after setting family and method
                        // This ensures the dropdown is populated before we try to select local_path
                        await updateModelDropdown(loadingMethodWidget.value, modelFamilyWidget.value);
                        
                        // Step 3: Update model source and paths
                        // Check if this is an Ollama registry model (uses ollama_model field instead of repo_id)
                        const isOllamaTemplate = config.model_source === "ollama";
                        // Check if current loading method is Ollama Docker (ignores local file paths)
                        const isOllamaDockerMethod = loadingMethodWidget.value === "Ollama (Docker)";
                        
                        // // // console.log(`[SmartLM] Template paths - local_path: "${config.local_path}", repo_id: "${config.repo_id}", isOllama: ${isOllamaTemplate}, isOllamaDockerMethod: ${isOllamaDockerMethod}`);
                        
                        if (isOllamaTemplate || isOllamaDockerMethod) {
                            // Ollama templates/method use their own model registry, don't set model_name from file paths
                            // Clear any file selection from previous template
                            setWidgetValue("model_name", "None");
                            setWidgetValue("local_path", "");
                            // Keep model_source as Local (Ollama handles model download internally)
                            setWidgetValue("model_source", "Local");
                            // Set repo_id for reference if available
                            if (config.repo_id && config.repo_id.trim() !== "") {
                                setWidgetValue("repo_id", config.repo_id);
                            }
                        } else if (config.local_path && config.local_path.trim() !== "") {
                            // Downloaded model: prioritize local_path
                            setWidgetValue("model_source", "Local");
                            // Check if local_path exists in model_name dropdown options
                            const modelNameWidget = getWidget("model_name");
                            const modelOptions = modelNameWidget?.options?.values || [];
                            let matchedModelName = null;
                            
                            // Try direct match first
                            if (modelOptions.includes(config.local_path)) {
                                matchedModelName = config.local_path;
                            } else {
                                // Try matching with common prefixes (for models in alternative folders like florence2/)
                                const prefixes = ["florence2/", ""];
                                for (const prefix of prefixes) {
                                    const prefixedPath = prefix + config.local_path;
                                    if (modelOptions.includes(prefixedPath)) {
                                        matchedModelName = prefixedPath;
                                        break;
                                    }
                                }
                                // Also try finding by suffix match (in case template has old path format)
                                if (!matchedModelName) {
                                    // Normalize path and extract model name (last non-empty segment)
                                    const localPathNormalized = config.local_path.replace(/\\/g, '/').replace(/\/+$/, '');
                                    const pathParts = localPathNormalized.split('/').filter(p => p);
                                    const modelName = pathParts[pathParts.length - 1];
                                    if (modelName) {
                                        // Try to find option ending with this model name
                                        matchedModelName = modelOptions.find(opt => {
                                            const optNormalized = opt.replace(/\/+$/, '');
                                            return optNormalized.endsWith('/' + modelName) || optNormalized === modelName;
                                        });
                                    }
                                }
                            }
                            
                            if (matchedModelName) {
                                setWidgetValue("model_name", matchedModelName);
                            }
                            setWidgetValue("local_path", config.local_path);
                            // Always set repo_id if available (for switching to HuggingFace later)
                            setWidgetValue("repo_id", config.repo_id || "");
                        } else if (config.repo_id && config.repo_id.trim() !== "") {
                            // HuggingFace/URL model: show repo_id
                            setWidgetValue("model_source", "HuggingFace");
                            setWidgetValue("repo_id", config.repo_id);
                            setWidgetValue("local_path", "");
                        } else {
                            // No local_path or repo_id - default to Local mode with empty values
                            setWidgetValue("model_source", "Local");
                            setWidgetValue("repo_id", config.repo_id || "");
                            setWidgetValue("local_path", "");
                        }
                        
                        // Step 4: Set all mmproj values from template (empty string if not in template)
                        setWidgetValue("mmproj_url", config.mmproj_url || "");
                        setWidgetValue("mmproj_path", config.mmproj_path || "");
                        // Check if mmproj_path exists in mmproj_local dropdown options
                        const mmprojLocalWidget = getWidget("mmproj_local");
                        if (config.mmproj_path && config.mmproj_path.trim() && 
                            mmprojLocalWidget?.options?.values?.includes(config.mmproj_path)) {
                            setWidgetValue("mmproj_local", config.mmproj_path);
                            setWidgetValue("mmproj_source", "Local");
                        } else if (config.mmproj_url && config.mmproj_url.trim()) {
                            setWidgetValue("mmproj_local", "");
                            setWidgetValue("mmproj_source", "HuggingFace");
                        } else {
                            setWidgetValue("mmproj_local", "");
                            setWidgetValue("mmproj_source", "Local");
                        }
                        
                        // Step 5: Load generation parameters (always set, use template value or keep current)
                        // Convert quantization from internal format (e.g., "4bit") to display format (e.g., "4-bit (Lowest VRAM)")
                        if (config.quantization) {
                            const quantDisplay = quantToDisplay(config.quantization);
                            setWidgetValue("quantization", quantDisplay);
                        }
                        if (config.attention_mode) setWidgetValue("attention_mode", config.attention_mode);
                        if (config.context_size !== undefined) setWidgetValue("context_size", config.context_size);
                        if (config.max_tokens !== undefined) setWidgetValue("max_tokens", config.max_tokens);
                        
                        // Step 6: Load default task if saved (after task dropdown is updated for family)
                        if (config.default_task && taskWidget) {
                            // Common tasks have no prefix (e.g., "Detailed Description")
                            // Family-specific tasks are prefixed (e.g., "Qwen: Object Detection")
                            // Task dropdown shows stripped names after filtering
                            const taskValue = config.default_task;
                            const taskOptions = taskWidget.options?.values || [];
                            
                            if (taskOptions.includes(taskValue)) {
                                setWidgetValue("task", taskValue);
                            } else {
                                // Special handling for Florence: templates may store machine keys
                                if (modelFamilyWidget.value === "Florence") {
                                    // Direct match by machine key
                                    const bare = taskValue.includes(": ") ? taskValue.split(": ")[1] : taskValue;
                                    if (florenceKeyToDisplay[bare]) {
                                        setWidgetValue("task", florenceKeyToDisplay[bare]);
                                    } else if (florenceKeyToDisplay[bare.toLowerCase()]) {
                                        setWidgetValue("task", florenceKeyToDisplay[bare.toLowerCase()]);
                                    } else {
                                        // Try matching prettified key or normalized display name
                                        const prettified = bare.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                                        const matched = taskOptions.find(t => normalizeString(t) === normalizeString(prettified) || normalizeString(t) === normalizeString(bare));
                                        if (matched) setWidgetValue("task", matched);
                                        else console.warn(`[SmartLM] Could not map Florence default_task '${taskValue}' to a display task`);
                                    }
                                } else {
                                    // Try to find matching task (strip prefix if present)
                                    const strippedTask = taskValue.includes(": ") ? taskValue.split(": ")[1] : taskValue;
                                    const matchingTask = taskOptions.find(t => t === strippedTask || t.endsWith(taskValue));
                                    if (matchingTask) {
                                        setWidgetValue("task", matchingTask);
                                    } else {
                                        console.warn(`[SmartLM] Could not map default_task '${taskValue}' to a display task`);
                                    }
                                }
                            }

                            // Step 6.5: If template provided a default text input, set the user_prompt widget
                            if (config.default_text_input !== undefined && getWidget("user_prompt")) {
                                const dt = config.default_text_input || "";
                                // For Florence, only apply default_text_input when the selected task is a Florence detection task
                                // AND presets are loaded (to correctly determine detection tasks)
                                let applyDefault = true;
                                const presetsLoaded = presetSections.detection && presetSections.detection.length > 0;
                                if (modelFamilyWidget.value === "Florence" && presetsLoaded) {
                                    const currentTask = taskWidget?.value || "";
                                    const meta = presetTaskMap[normalizeString(currentTask)];
                                    const id = meta && meta.id ? meta.id : null;
                                    const detectionIds = (presetSections.detection || []).map(name => {
                                        const m = presetTaskMap[normalizeString(name)];
                                        return m && m.id ? m.id : null;
                                    }).filter(Boolean);
                                    applyDefault = detectionIds.includes(id);
                                } else if (modelFamilyWidget.value === "Florence" && !presetsLoaded) {
                                    // Presets not loaded yet for Florence - skip applying default to avoid incorrect behavior
                                    applyDefault = false;
                                }
                                if (applyDefault) {
                                    // Apply raw value - allow empty strings to clear previous values
                                    setWidgetValue("user_prompt", dt);
                                }
                            }
                        }
                        
                        // Update quantization options for the selected method
                        updateQuantizationOptions(loadingMethodWidget.value);
                        
                        // Update visibility for the loaded family/method
                        updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value);
                        
                        // Step 5.5: Apply any remaining template values to matching widgets (safe, non-destructive)
                        try {
                            const SKIP_KEYS = new Set([
                                'model_family','loading_method','local_path','repo_id','model_source',
                                'mmproj_url','mmproj_path','mmproj_local','quantization','attention_mode',
                                'context_size','max_tokens','default_task','default_text_input'
                            ]);
                            for (const [tkey, tval] of Object.entries(config)) {
                                if (tval === undefined || tval === null) continue;
                                if (SKIP_KEYS.has(tkey)) continue; // already handled above
                                const widget = getWidget(tkey);
                                if (!widget) continue;

                                // If widget has predefined options, try to safely match an option
                                if (widget.options?.values && Array.isArray(widget.options.values)) {
                                    let desired = tval;
                                    if (tkey === 'quantization') desired = quantToDisplay(tval);

                                    // Exact match
                                    if (widget.options.values.includes(desired)) {
                                        setWidgetValue(tkey, desired);
                                        // // // console.log(`[SmartLM] Applied template value to ${tkey}: ${desired}`);
                                        continue;
                                    }

                                    // Try normalized match or partial matches
                                    const normDesired = normalizeString(String(desired));
                                    const match = widget.options.values.find(o => {
                                        const on = normalizeString(String(o));
                                        return on === normDesired || on.endsWith(normDesired) || on.includes(normDesired);
                                    });
                                    if (match) {
                                        setWidgetValue(tkey, match);
                                        // // // console.log(`[SmartLM] Applied template value to ${tkey}: ${match} (matched ${desired})`);
                                        continue;
                                    }

                                    // For free-text combos, set raw value
                                    if (widget.type === 'text' || widget.type === 'input' || widget.type === 'string') {
                                        setWidgetValue(tkey, tval);
                                        // // // console.log(`[SmartLM] Applied template free value to ${tkey}`);
                                    }
                                } else {
                                    // No options: think boolean, number, or free text - set directly
                                    setWidgetValue(tkey, tval);
                                    // // // console.log(`[SmartLM] Applied template value to ${tkey}: ${tval}`);
                                }
                            }
                        } catch (e) {
                            console.warn('[SmartLM] Failed to apply template widget values:', e);
                        }

                    } finally {
                        isLoadingFromTemplate = false;
                    }
                };
            }
            
            // Task change handler (affects detection widget visibility)
            if (taskWidget) {
                const originalTaskCallback = taskWidget.callback;
                taskWidget.callback = function(value) {
                    // // // console.log(`[SmartLM] Task changed: ${value}`);
                    
                    if (originalTaskCallback) {
                        originalTaskCallback.apply(this, arguments);
                    }
                    
                    // Update visibility to show/hide detection-specific widgets
                    updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value);

                    // If multi-task mode is enabled, refresh follow-up task dropdowns to enforce text-only filtering
                    (async () => {
                        const mt = getWidget("multi_task_mode");
                        if (mt && mt.value === true) {
                            await populateFollowups(modelFamilyWidget.value);
                        }
                    })();
                };
            }
            
            // Multi-task mode change handler
            const multiTaskModeWidget = getWidget("multi_task_mode");
            if (multiTaskModeWidget) {
                const originalMultiTaskModeCallback = multiTaskModeWidget.callback;
                multiTaskModeWidget.callback = async function(value) {
                    // // // console.log(`[SmartLM] Multi-task mode changed: ${value}`);
                    
                    if (originalMultiTaskModeCallback) {
                        originalMultiTaskModeCallback.apply(this, arguments);
                    }
                    
                    // Update visibility to show/hide multi-task widgets
                    updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value);
                    
                    // Populate additional task dropdowns from presets when enabled
                    if (value === true) {
                        await populateFollowups(modelFamilyWidget.value);
                    }
                };
            }
            
            // Task count change handler
            const taskCountWidget = getWidget("task_count");
            if (taskCountWidget) {
                const originalTaskCountCallback = taskCountWidget.callback;
                taskCountWidget.callback = function(value) {
                    // // // console.log(`[SmartLM] Task count changed: ${value}`);
                    
                    if (originalTaskCountCallback) {
                        originalTaskCountCallback.apply(this, arguments);
                    }
                    
                    // Update visibility to show/hide task_2/3/4 based on count
                    updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value);
                };
            }
            
            // ===== SEED HANDLING =====
            // Initialize seed tracking
            node._Eclipse_lastSeed = undefined;
            node._Eclipse_cachedInputSeed = null;
            node._Eclipse_cachedResolvedSeed = null;
            
            // Find the seed widget and remove control_after_generate
            let seedWidget = null;
            let controlAfterGenerateIndex = -1;
            for (const [i, widget] of this.widgets.entries()) {
                const wname = (widget.name || '').toString().toLowerCase();
                const wlabel = (widget.label || widget.options?.label || widget.options?.name || '').toString().toLowerCase();
                const wlocalized = (widget.localized_name || '').toString().toLowerCase();
                if (wname === 'seed' || wlabel === 'seed' || wlocalized === 'seed') {
                    seedWidget = widget;
                } else if (wname === 'control_after_generate') {
                    controlAfterGenerateIndex = i;
                }
            }
            
            // Remove control_after_generate after the loop to avoid index issues
            if (controlAfterGenerateIndex >= 0) {
                this.widgets.splice(controlAfterGenerateIndex, 1);
            }
            
            if (seedWidget) {
                node._Eclipse_seedWidget = seedWidget;
                node._Eclipse_randomMin = 0;
                node._Eclipse_randomMax = 1125899906842624;
                
                // Method to generate random seed (matching eclipse-seed.js)
                node.generateRandomSeed = function() {
                    const step = this._Eclipse_seedWidget?.options?.step || 1;
                    const randomMin = this._Eclipse_randomMin || 0;
                    const randomMax = this._Eclipse_randomMax || 1125899906842624;
                    const randomRange = (randomMax - randomMin) / (step / 10);
                    let seed = Math.floor(Math.random() * randomRange) * (step / 10) + randomMin;
                    
                    // Avoid special seeds
                    if (SPECIAL_SEEDS.includes(seed)) {
                        seed = 0;
                    }
                    return seed;
                };
                
                // Method to determine seed to use (matching eclipse-seed.js)
                node.getSeedToUse = function() {
                    const inputSeed = Number(this._Eclipse_seedWidget.value);
                    
                    // Check if we have a cached resolved seed for this input seed
                    // This prevents generating different random seeds on multiple calls
                    if (this._Eclipse_cachedInputSeed === inputSeed && this._Eclipse_cachedResolvedSeed != null) {
                        return this._Eclipse_cachedResolvedSeed;
                    }
                    
                    let seedToUse = null;
                    
                    // If our input seed was a special seed, then handle it
                    if (SPECIAL_SEEDS.includes(inputSeed)) {
                        // If the last seed was not a special seed and we have increment/decrement, then do that
                        if (typeof this._Eclipse_lastSeed === "number" && !SPECIAL_SEEDS.includes(this._Eclipse_lastSeed)) {
                            if (inputSeed === SPECIAL_SEED_INCREMENT) {
                                seedToUse = this._Eclipse_lastSeed + 1;
                            } else if (inputSeed === SPECIAL_SEED_DECREMENT) {
                                seedToUse = this._Eclipse_lastSeed - 1;
                            }
                        }
                        
                        // If we don't have a seed to use, or it's a special seed, randomize
                        if (seedToUse == null || SPECIAL_SEEDS.includes(seedToUse)) {
                            seedToUse = this.generateRandomSeed();
                        }
                    }
                    
                    const finalSeed = seedToUse != null ? seedToUse : inputSeed;
                    
                    // Cache the resolved seed for this input seed
                    this._Eclipse_cachedInputSeed = inputSeed;
                    this._Eclipse_cachedResolvedSeed = finalSeed;
                    
                    return finalSeed;
                };
                
                // Hook into the seed widget's value setter to clear cache when it changes
                const originalCallback = seedWidget.callback;
                seedWidget.callback = (value) => {
                    // Clear the seed cache when the seed value changes
                    node._Eclipse_cachedInputSeed = null;
                    node._Eclipse_cachedResolvedSeed = null;
                    // Call the original callback if it exists
                    if (originalCallback) {
                        return originalCallback.call(seedWidget, value);
                    }
                };
                
                const seedWidgetIndex = node.widgets.indexOf(seedWidget);
                
                // Button: Randomize Each Time
                const randomizeButton = node.addWidget(
                    "button",
                    "🎲 Randomize Each Time",
                    "",
                    () => {
                        seedWidget.value = SPECIAL_SEED_RANDOM;
                        if (seedWidget.callback) {
                            seedWidget.callback(SPECIAL_SEED_RANDOM);
                        }
                    },
                    { serialize: false }
                );
                
                // Button: New Fixed Random
                const newRandomButton = node.addWidget(
                    "button",
                    "🎲 New Fixed Random",
                    "",
                    () => {
                        const newSeed = node.generateRandomSeed();
                        seedWidget.value = newSeed;
                        if (seedWidget.callback) {
                            seedWidget.callback(newSeed);
                        }
                    },
                    { serialize: false }
                );
                
                // Button: Use Last Queued Seed
                const lastSeedButton = node.addWidget(
                    "button",
                    LAST_SEED_BUTTON_LABEL,
                    "",
                    () => {
                        if (node._Eclipse_lastSeed != null) {
                            seedWidget.value = node._Eclipse_lastSeed;
                            lastSeedButton.name = LAST_SEED_BUTTON_LABEL;
                            lastSeedButton.disabled = true;
                        }
                    },
                    { serialize: false }
                );
                lastSeedButton.disabled = true;
                node._Eclipse_lastSeedButton = lastSeedButton;
                
                // Move buttons to be right after the seed widget
                const buttonsToMove = [randomizeButton, newRandomButton, lastSeedButton];
                for (let i = buttonsToMove.length - 1; i >= 0; i--) {
                    const button = buttonsToMove[i];
                    const currentIndex = node.widgets.indexOf(button);
                    if (currentIndex !== seedWidgetIndex + 1) {
                        node.widgets.splice(currentIndex, 1);
                        node.widgets.splice(seedWidgetIndex + 1, 0, button);
                    }
                }
                
                // Intercept execution to track the seed that was actually used
                const originalOnExecuted = node.onExecuted;
                node.onExecuted = function(message) {
                    const result = originalOnExecuted ? originalOnExecuted.apply(this, arguments) : undefined;
                    
                    // Store the seed that was actually used if available
                    if (message && message.seed !== undefined) {
                        this._Eclipse_lastSeed = message.seed;
                    }
                    
                    return result;
                };
            }
            
            // Initialize on node creation - defer slightly to ensure node has valid ID
            // LiteGraph assigns ID after onNodeCreated returns
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    
                    // Run visibility first
                    if (loadingMethodWidget && modelFamilyWidget) {
                        updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value, true);
                    }
                    
                    // Then run async operations without blocking
                    (async function() {
                        await updateTemplateDropdown();
                        await updateMethodDropdown(modelFamilyWidget.value);
                        updateQuantizationOptions(loadingMethodWidget.value);
                        const family = modelFamilyWidget.value;
                        await populateFollowups(family);
                    })();
                }
            }, 0);
            
            // Lazy init for when node becomes visible - refresh dropdowns only
            // NOTE: Visibility is already configured at load time with skipPerformanceChecks=true
            // This only refreshes dropdown contents when node scrolls into view
            setupLazyInit(node, async function() {
                // Load templates first (unfiltered)
                await updateTemplateDropdown();
                
                // Update method dropdown based on current family
                await updateMethodDropdown(modelFamilyWidget.value);
                
                // Update quantization options
                updateQuantizationOptions(loadingMethodWidget.value);
                
                // Populate multi-task dropdowns from presets
                const family = modelFamilyWidget.value;
                await populateFollowups(family);
            });
            
            // Hook into onConnectionsChange to detect when text input is connected/disconnected
            const onConnectionsChange = node.onConnectionsChange;
            node.onConnectionsChange = function(type, index, connected, link_info) {
                if (onConnectionsChange) {
                    onConnectionsChange.apply(this, arguments);
                }
                
                // Check if the connection change is for an input (type 1 = input)
                if (type === 1) {
                    const input = this.inputs[index];
                    if (input && input.name === "text") {
                        // Text input connection changed, update visibility
                        requestAnimationFrame(() => {
                            updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value);
                        });
                        // Clear user_prompt when text input is connected (external text takes over)
                        // Only clear if presets are loaded (avoids clearing during workflow restore)
                        const presetsLoaded = presetSections.detection && presetSections.detection.length > 0;
                        if (connected && presetsLoaded) {
                            setWidgetValue("user_prompt", "");
                        }
                    }
                    // If pipe_opt input is connected, sync model_type in Advanced Options node
                    if (input && input.name === "pipe_opt" && connected) {
                        requestAnimationFrame(() => {
                            syncAdvancedOptionsModelType(modelFamilyWidget.value);
                        });
                    }
                }
            };
            
            // Hook into onConfigure to reload template when workflow is loaded (page reload / workflow open)
            const onConfigure = node.onConfigure;
            node.onConfigure = function(info) {
                if (onConfigure) {
                    onConfigure.apply(this, arguments);
                }
                
                // After workflow is configured, check if a template is selected and reload it
                setTimeout(async () => {
                    const templateName = templateNameWidget?.value;
                    
                    if (templateName && templateName !== "None") {
                        // // // console.log(`[SmartLM] Workflow loaded, reapplying template: ${templateName}`);
                        
                        // Trigger the template callback to reload all settings from template
                        isLoadingFromTemplate = false; // Reset flag to allow loading
                        if (templateNameWidget.callback) {
                            await templateNameWidget.callback(templateName);
                        }
                    } else {
                        // No template - update visibility and filter task dropdowns
                        // Use skipPerformanceChecks=true to ensure visibility runs even if node is outside viewport
                        updateVisibility(loadingMethodWidget.value, modelFamilyWidget.value, true);

                        // Keep user_prompt value - user may have custom instructions
                        // (prompt is only cleared when text input is connected)

                        // Populate all task dropdowns from presets (no family filtering)
                        const family = modelFamilyWidget.value;
                        await updateTaskDropdown(family, false);
                        await populateFollowups(family);
                    }
                    
                    // Sync model_type in connected Advanced Options node
                    syncAdvancedOptionsModelType(modelFamilyWidget.value);
                }, 150);  // Slight delay to ensure widgets are fully initialized
            };
            
            return r;
        };
    },
    
    async setup() {
        // Check if an Eclipse node is present in the workflow
        const hasEclipseNode = app.graph?.nodes?.some(node => NODE_NAMES.includes(node.type));
        
        // Only reload configs and clear caches if an Eclipse node is present
        if (hasEclipseNode) {
            // Reload prompt configs from disk on page load/refresh
            // This ensures any user edits to config files are picked up
            try {
                const response = await fetch('/eclipse/reload_all');
                if (response.ok) {
                    const result = await response.json();
                    if (result.success) {
                        // // // console.log(`[Eclipse] Reloaded on page load: ${result.reloaded.join(', ')}`);
                    } else {
                        console.warn(`[Eclipse] Reload had errors:`, result);
                    }
                }
            } catch (e) {
                console.warn("[Eclipse] Could not reload configs:", e);
            }
            
            // Clear all caches to force fresh fetch after reload
            // Preset prompts cache (task dropdowns)
            presetPromptsCache = null;
            presetRawPrompts = null;
            presetTaskMap = {};
            presetSections = { custom: [], vision: [], detection: [], text: [], refine: [] };
            
            // Templates cache (template dropdown)
            invalidateTemplatesCache();
            
            // Discovered models cache (model_name dropdown)
            invalidateModelsCache();
            
            // Method support matrix (force refetch)
            METHOD_SUPPORT_V2 = null;
            methodSupportPromise = null;
            
            // // // console.log("[Eclipse] All caches cleared on page load");
            
            // Refresh all existing SmartLM nodes on the canvas
            const existingNodes = app.graph?._nodes || [];
            for (const node of existingNodes) {
                if (NODE_NAMES.includes(node.type)) {
                    // // // console.log(`[SmartLM] Refreshing node ${node.id} after config reload...`);
                    // Force refresh template and model lists
                    await refreshTemplateList(node);
                }
            }
        }
        
        // Listen for execution completion to refresh template list
        // (templates may be auto-created when downloading models via repo_id)
        // Use debouncing to avoid excessive refreshes during workflow execution
        api.addEventListener("executed", async (event) => {
            // Check if any SmartLM nodes exist in the workflow
            const nodes = app.graph?._nodes || [];
            const hasSmartLMNodes = nodes.some(node => NODE_NAMES.includes(node.type));
            
            if (!hasSmartLMNodes) {
                return; // Skip refresh if no SmartLM nodes in workflow
            }
            
            // Debounce multiple rapid executions
            const now = Date.now();
            if (now - lastExecutionRefreshTime < 3000) {
                return; // Skip if refreshed recently (3 second cooldown)
            }
            
            // Clear any pending refresh
            if (executionRefreshTimeout) {
                clearTimeout(executionRefreshTimeout);
            }
            
            // Schedule debounced refresh
            executionRefreshTimeout = setTimeout(async () => {
                lastExecutionRefreshTime = Date.now();
                
                // // // console.log(`[SmartLM] Workflow execution detected, checking for new templates (debounced)...`);
                
                // Only invalidate caches silently - templates will be refreshed automatically
                // when users interact with template widgets due to shared cache invalidation
                invalidateTemplatesCacheSilent();
                invalidateModelsCacheSilent();
                
                // // // console.log(`[SmartLM] Template cache refreshed for future widget interactions`);
            }, 1500); // 1.5 second debounce
        });
        // Hook into the graphToPrompt to handle seed values
        const originalGraphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function() {
            // Call the original graphToPrompt first
            const result = await originalGraphToPrompt.apply(this, arguments);
            
            if (!result || !result.output) return result;
            
            // Process all SmartLM nodes
            const nodes = app.graph._nodes;
            for (const node of nodes) {
                
                if (NODE_NAMES.includes(node.type) && node._Eclipse_seedWidget) {
                    // Skip if node is muted or bypassed
                    if (node.mode === 2 || node.mode === 4) {
                        continue;
                    }
                    
                    // Check if this node is in the prompt
                    const nodeId = String(node.id);
                    if (result.output && result.output[nodeId]) {
                        const seedToUse = node.getSeedToUse();
                        
                        // Update the seed in the prompt output (what gets sent to server)
                        if (result.output[nodeId].inputs && result.output[nodeId].inputs.seed !== undefined) {
                            result.output[nodeId].inputs.seed = seedToUse;
                        }

                        // Update last seed tracking only when it actually changes
                        if (Number(node._Eclipse_lastSeed) !== Number(seedToUse)) {
                            node._Eclipse_lastSeed = seedToUse;
                        }
                        
                        // Clear the seed cache after use so next call generates fresh random seed
                        node._Eclipse_cachedInputSeed = null;
                        node._Eclipse_cachedResolvedSeed = null;
                        
                        // Update the last seed button - but DON'T change the widget value
                        if (node._Eclipse_lastSeedButton) {
                            const currentWidgetValue = Number(node._Eclipse_seedWidget.value);
                            if (SPECIAL_SEEDS.includes(currentWidgetValue)) {
                                // Widget has special seed, show what was actually used
                                node._Eclipse_lastSeedButton.name = `♻️ ${seedToUse}`;
                                node._Eclipse_lastSeedButton.disabled = false;
                            } else {
                                // Widget has regular seed value
                                node._Eclipse_lastSeedButton.name = LAST_SEED_BUTTON_LABEL;
                                node._Eclipse_lastSeedButton.disabled = true;
                            }
                        }
                        
                        // Also update workflow data if present (for saved workflows)
                        if (result.workflow && result.workflow.nodes) {
                            const workflowNode = result.workflow.nodes.find(n => n.id === node.id);
                            if (workflowNode && workflowNode.widgets_values) {
                                const seedWidgetIndex = node.widgets.indexOf(node._Eclipse_seedWidget);
                                if (seedWidgetIndex >= 0) {
                                    // Only update workflow stored value if it differs
                                    if (workflowNode.widgets_values[seedWidgetIndex] !== seedToUse) {
                                        workflowNode.widgets_values[seedWidgetIndex] = seedToUse;
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            return result;
        };
    },
});
