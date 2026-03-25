/* eclipse-smart-sampler-settings-v2.js — Dual-seed (image + prompt) with mode chips */
import { app } from './comfy/index.js';
import {
    createWidgetVisibilityManager,
    smartResize,
    notifyVue,
    isVueMode,
    onVueModeChange,
} from './eclipse-widget-performance-utils.js';
import { injectComboChipCSS, createComboChipWidget as _createComboChipWidget } from './eclipse-combo-chip.js';

const NODE_NAME = 'Smart Sampler Settings v2 [Eclipse]';
const SPECIAL_SEEDS = [-1, -2, -3];

// Feature options (must match Python FEATURE_OPTIONS order)
const FEATURE_OPTIONS = [
    'allow_overwrite', 'sampler', 'scheduler', 'steps', 'cfg',
    'guidance', 'denoise', 'noise_injection', 'upscale',
    'image_seed',
    '🎲 img random', '⏫ img increment', '⏬ img decrement',
    'prompt_seed',
    '🎲 prm random', '⏫ prm increment', '⏬ prm decrement',
];
const DEFAULT_FEATURES = [
    'sampler', 'scheduler', 'steps', 'cfg', 'denoise',
    'image_seed', '🎲 img random',
];

injectComboChipCSS('');

// Map each feature option to the widget(s) it controls
const FEATURE_WIDGETS = {
    allow_overwrite: ['allow_overwrite'],
    sampler: ['sampler_name'],
    scheduler: ['scheduler'],
    steps: ['steps'],
    cfg: ['cfg'],
    guidance: ['guidance'],
    denoise: ['denoise'],
    noise_injection: ['sigmas_denoise', 'noise_strength'],
    upscale: ['upscale_steps', 'upscale_denoise', 'upscale_value'],
    image_seed: ['image_seed'],
    prompt_seed: ['prompt_seed'],
};

// Image seed mode chips
const IMG_MODE_CHIPS = ['🎲 img random', '⏫ img increment', '⏬ img decrement'];
const IMG_MODE_CHIP_TO_VAL = {
    '🎲 img random': -1,
    '⏫ img increment': -2,
    '⏬ img decrement': -3,
};
const IMG_VAL_TO_MODE_CHIP = Object.fromEntries(
    Object.entries(IMG_MODE_CHIP_TO_VAL).map(([k, v]) => [v, k])
);

// Prompt seed mode chips
const PRM_MODE_CHIPS = ['🎲 prm random', '⏫ prm increment', '⏬ prm decrement'];
const PRM_MODE_CHIP_TO_VAL = {
    '🎲 prm random': -1,
    '⏫ prm increment': -2,
    '⏬ prm decrement': -3,
};
const PRM_VAL_TO_MODE_CHIP = Object.fromEntries(
    Object.entries(PRM_MODE_CHIP_TO_VAL).map(([k, v]) => [v, k])
);

// Radio groups: only one mode per seed
const RADIO_GROUPS = [IMG_MODE_CHIPS, PRM_MODE_CHIPS];

// All mode chips (UI-only, stripped from prompt to avoid cache invalidation)
const ALL_MODE_CHIPS = new Set([...IMG_MODE_CHIPS, ...PRM_MODE_CHIPS]);

// Dynamically added buttons tracked for visibility
const IMG_SEED_BUTTONS = ['_btn_last_image_seed'];
const PRM_SEED_BUTTONS = ['_btn_last_prompt_seed'];

// All widget names controlled by features
const ALL_CONTROLLED = Object.values(FEATURE_WIDGETS).flat()
    .concat(IMG_SEED_BUTTONS).concat(PRM_SEED_BUTTONS);

function createComboChipWidget(node, savedValue, origIdx) {
    const w = _createComboChipWidget({
        node,
        options: FEATURE_OPTIONS,
        savedValue,
        origIdx,
        radioGroups: RADIO_GROUPS,
        radioToggle: true,
    });
    // Override serialization so mode chips never reach the server prompt.
    // Mode chips are UI-only state that control seed widget values.
    w.serializeValue = () => {
        const val = Array.isArray(w.value) ? w.value : [];
        return val.filter((f) => !ALL_MODE_CHIPS.has(f));
    };
    return w;
}

// Shared visibility update logic
function updateFeatureVisibility(node, vis) {
    if (node.id === -1) return;
    const raw = vis.getValue('features');
    const selected = Array.isArray(raw) ? raw : [];
    const selectedSet = new Set(selected);

    // Hide all controlled widgets first
    for (const name of ALL_CONTROLLED) vis.setVisible(name, false);

    // Show widgets for selected features
    for (const feature of selectedSet) {
        const widgets = FEATURE_WIDGETS[feature];
        if (widgets) for (const name of widgets) vis.setVisible(name, true);
    }

    // Image seed: show widget + button when image_seed or any img mode is selected
    const imgSeedVisible = selectedSet.has('image_seed') || IMG_MODE_CHIPS.some((c) => selectedSet.has(c));
    vis.setVisible('image_seed', imgSeedVisible);
    for (const name of IMG_SEED_BUTTONS) vis.setVisible(name, imgSeedVisible);

    // Prompt seed: show widget + button when prompt_seed or any prm mode is selected
    const prmSeedVisible = selectedSet.has('prompt_seed') || PRM_MODE_CHIPS.some((c) => selectedSet.has(c));
    vis.setVisible('prompt_seed', prmSeedVisible);
    for (const name of PRM_SEED_BUTTONS) vis.setVisible(name, prmSeedVisible);

    smartResize(node);
}

// Generate a random seed value
function generateRandomSeed() {
    const max = Number.MAX_SAFE_INTEGER;
    let seed = Math.floor(Math.random() * max);
    if (SPECIAL_SEEDS.includes(seed)) seed = 0;
    return seed;
}

// Resolve a seed value from its special mode
function resolveSeed(input, lastSeed) {
    if (!SPECIAL_SEEDS.includes(input)) return input;
    let resolved = null;
    if (typeof lastSeed === 'number' && !SPECIAL_SEEDS.includes(lastSeed)) {
        if (input === -2) resolved = lastSeed + 1;
        else if (input === -3) resolved = lastSeed - 1;
    }
    if (resolved == null || SPECIAL_SEEDS.includes(resolved))
        resolved = generateRandomSeed();
    return resolved;
}

// Set up one seed channel (image_seed or prompt_seed)
function setupSeedChannel(node, seedWidgetName, btnName, lastSeedLabel, statePrefix) {
    const seedWidget = node.widgets?.find((w) => w.name === seedWidgetName);
    if (!seedWidget) return;

    const stateKeys = {
        widget: `_Eclipse_${statePrefix}Widget`,
        last: `_Eclipse_last${statePrefix}`,
        button: `_Eclipse_${statePrefix}Button`,
        cachedInput: `_Eclipse_cached${statePrefix}Input`,
        cachedResolved: `_Eclipse_cached${statePrefix}Resolved`,
    };

    node[stateKeys.widget] = seedWidget;
    node[stateKeys.last] = undefined;
    node[stateKeys.cachedInput] = null;
    node[stateKeys.cachedResolved] = null;

    const origCb = seedWidget.callback;
    seedWidget.callback = (v) => {
        node[stateKeys.cachedInput] = null;
        node[stateKeys.cachedResolved] = null;
        if (origCb) origCb.call(seedWidget, v);
    };

    const seedIdx = node.widgets.indexOf(seedWidget);

    // ♻️ Use Last Queued Seed button
    const btnLastSeed = node.addWidget('button', btnName, '', () => {
        const last = node[stateKeys.last];
        if (last != null) {
            seedWidget.value = last;
            btnLastSeed.label = lastSeedLabel;
            btnLastSeed.disabled = true;

            // Deselect mode chips for this seed
            if (node._Eclipse_chipWidget) {
                const modeChips = statePrefix === 'ImageSeed' ? IMG_MODE_CHIPS : PRM_MODE_CHIPS;
                const chips = new Set(node._Eclipse_chipWidget.value);
                for (const m of modeChips) chips.delete(m);
                node._Eclipse_updatingChips = true;
                node._Eclipse_chipWidget.value = [...chips];
                node._Eclipse_updatingChips = false;
                // Trigger visibility update directly (guard prevents callback recursion)
                const vis = node._Eclipse_vis;
                if (vis) updateFeatureVisibility(node, vis);
            }
            notifyVue(node);
        }
    }, { serialize: false });
    btnLastSeed.label = lastSeedLabel;
    btnLastSeed.disabled = true;
    node[stateKeys.button] = btnLastSeed;

    // Move button right after seed widget
    const btnIdx = node.widgets.indexOf(btnLastSeed);
    if (btnIdx !== seedIdx + 1) {
        node.widgets.splice(btnIdx, 1);
        node.widgets.splice(seedIdx + 1, 0, btnLastSeed);
    }

    return { seedWidget, stateKeys };
}

// Sync seed widget value ↔ mode chips for one seed channel
function syncSeedToChips(node, seedValue, modeChips, valToChip) {
    if (!node._Eclipse_chipWidget) return;
    const chips = new Set(node._Eclipse_chipWidget.value);
    for (const m of modeChips) chips.delete(m);
    if (SPECIAL_SEEDS.includes(seedValue)) {
        const chip = valToChip[seedValue];
        if (chip) chips.add(chip);
    }
    node._Eclipse_updatingChips = true;
    node._Eclipse_chipWidget.value = [...chips];
    node._Eclipse_updatingChips = false;
}

// Sync mode chips → seed widget value for one seed channel
function syncChipsToSeed(node, selectedSet, modeChips, chipToVal, seedWidget, parentChip) {
    const activeMode = modeChips.find((m) => selectedSet.has(m));
    if (activeMode) {
        // Mode chip selected → ensure parent chip is also selected
        if (!selectedSet.has(parentChip)) {
            selectedSet.add(parentChip);
        }
        const modeVal = chipToVal[activeMode];
        if (seedWidget.value !== modeVal) {
            seedWidget.value = modeVal;
            seedWidget.callback?.(modeVal);
        }
    } else if (selectedSet.has(parentChip) && SPECIAL_SEEDS.includes(seedWidget.value)) {
        // Parent chip selected but no mode → pin to 0 (user can type a value)
        // Don't change if already a fixed value
    }
    // If parent chip deselected, also deselect all mode chips
    if (!selectedSet.has(parentChip) && !modeChips.some((m) => selectedSet.has(m))) {
        // Nothing to do — already clean
    }
}

app.registerExtension({
    name: 'Eclipse.SmartSamplerSettings_v2',
    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== NODE_NAME) return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const ret = origOnNodeCreated ? origOnNodeCreated.apply(this, arguments) : void 0;

            const node = this;
            const vis = createWidgetVisibilityManager(node);
            node._Eclipse_vis = vis;

            // --- Features chip widget setup ---
            const autoFeaturesW = node.widgets?.find((w) => w.name === 'features');
            let featWidget;

            if (isVueMode()) {
                const origIdx = autoFeaturesW ? node.widgets.indexOf(autoFeaturesW) : 0;
                let savedValue = DEFAULT_FEATURES.slice();
                if (autoFeaturesW) {
                    if (Array.isArray(autoFeaturesW.value) && autoFeaturesW.value.length > 0) {
                        savedValue = autoFeaturesW.value.slice();
                    }
                    autoFeaturesW.onRemove?.();
                    node.widgets.splice(origIdx, 1);
                }
                featWidget = createComboChipWidget(node, savedValue, origIdx);
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
                featWidget = createComboChipWidget(node, savedValue, origIdx + 1);
                node._Eclipse_backingFeaturesW = autoFeaturesW;
            }
            node._Eclipse_chipWidget = featWidget;

            // Remove auto-generated control_after_generate widgets
            for (let i = node.widgets.length - 1; i >= 0; i--) {
                const wName = (node.widgets[i].name || '').toLowerCase();
                if (wName === 'control_after_generate') {
                    node.widgets.splice(i, 1);
                }
            }

            // --- Dual seed setup ---
            setupSeedChannel(node, 'image_seed', '_btn_last_image_seed',
                '♻️ (Use Last Queued Image Seed)', 'ImageSeed');
            setupSeedChannel(node, 'prompt_seed', '_btn_last_prompt_seed',
                '♻️ (Use Last Queued Prompt Seed)', 'PromptSeed');

            // --- Features callback: visibility + seed sync ---
            const origFeatCallback = featWidget.callback;
            featWidget.callback = function (value) {
                if (node._Eclipse_updatingChips) return;
                origFeatCallback?.call(this, value);
                // Sync to backing widget WITHOUT mode chips (mode chips are UI-only state)
                if (node._Eclipse_backingFeaturesW) {
                    const clean = (Array.isArray(featWidget.value) ? featWidget.value : []).filter((f) => !ALL_MODE_CHIPS.has(f));
                    node._Eclipse_backingFeaturesW.value = clean;
                }
                const selectedSet = new Set(Array.isArray(featWidget.value) ? featWidget.value : []);

                // Sync mode chips → seed widget values
                let chipsChanged = false;
                if (node._Eclipse_ImageSeedWidget) {
                    const before = selectedSet.size;
                    syncChipsToSeed(node, selectedSet, IMG_MODE_CHIPS, IMG_MODE_CHIP_TO_VAL,
                        node._Eclipse_ImageSeedWidget, 'image_seed');
                    if (selectedSet.size !== before) chipsChanged = true;
                }
                if (node._Eclipse_PromptSeedWidget) {
                    const before = selectedSet.size;
                    syncChipsToSeed(node, selectedSet, PRM_MODE_CHIPS, PRM_MODE_CHIP_TO_VAL,
                        node._Eclipse_PromptSeedWidget, 'prompt_seed');
                    if (selectedSet.size !== before) chipsChanged = true;
                }

                // Write back chip changes only if syncChipsToSeed modified the set
                if (chipsChanged) {
                    node._Eclipse_updatingChips = true;
                    featWidget.value = [...selectedSet];
                    node._Eclipse_updatingChips = false;
                }

                updateFeatureVisibility(node, vis);
            };

            // Initial visibility
            requestAnimationFrame(() => updateFeatureVisibility(node, vis));

            return ret;
        };

        // Seed resolution helpers on the prototype
        nodeType.prototype._resolveSeed = function (statePrefix) {
            const widget = this[`_Eclipse_${statePrefix}Widget`];
            if (!widget) return 0;
            const input = Number(widget.value);
            const cachedInputKey = `_Eclipse_cached${statePrefix}Input`;
            const cachedResolvedKey = `_Eclipse_cached${statePrefix}Resolved`;
            const lastKey = `_Eclipse_last${statePrefix}`;
            if (this[cachedInputKey] === input && this[cachedResolvedKey] != null)
                return this[cachedResolvedKey];
            const resolved = resolveSeed(input, this[lastKey]);
            this[cachedInputKey] = input;
            this[cachedResolvedKey] = resolved;
            return resolved;
        };

        // Store last seeds from execution results
        const origOnExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (data) {
            const ret = origOnExecuted ? origOnExecuted.apply(this, arguments) : void 0;
            if (data) {
                if (data.image_seed !== undefined) this._Eclipse_lastImageSeed = data.image_seed;
                if (data.prompt_seed !== undefined) this._Eclipse_lastPromptSeed = data.prompt_seed;
            }
            return ret;
        };

        // Visibility on configure (loading saved workflows)
        const origOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (data) {
            const ret = origOnConfigure ? origOnConfigure.call(this, data) : void 0;
            const node = this;
            const vis = node._Eclipse_vis || createWidgetVisibilityManager(node);
            vis.clearCache();
            requestAnimationFrame(() => updateFeatureVisibility(node, vis));
            return ret;
        };
    },

    // Seed resolution at queue time
    async setup() {
        // Mode switch (Classic ↔ Nodes 2.0): fully recreate affected nodes
        onVueModeChange(() => {
            const graph = app.graph;
            if (!graph?._nodes) return;
            for (let i = 0; i < graph._nodes.length; i++) {
                const oldNode = graph._nodes[i];
                if (oldNode.type !== NODE_NAME) continue;
                const serialized = oldNode.serialize();
                for (const w of oldNode.widgets || []) w.onRemove?.();
                const newNode = LiteGraph.createNode(oldNode.type);
                if (!newNode) continue;
                graph._nodes[i] = newNode;
                newNode.configure(serialized);
                newNode.graph = graph;
                graph._nodes_by_id[newNode.id] = newNode;
                if (oldNode.inputs) newNode.inputs = [...oldNode.inputs];
                if (oldNode.outputs) newNode.outputs = [...oldNode.outputs];
            }
            graph.setDirtyCanvas?.(true, true);
        });

        const origGraphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const result = await origGraphToPrompt.apply(this, arguments);
            const nodes = app.graph._nodes;
            for (const node of nodes) {
                if (node.type !== NODE_NAME) continue;
                if (node.mode === 2 || node.mode === 4) continue;

                const nodeId = String(node.id);
                if (!result.output?.[nodeId]) continue;

                // Strip mode chips from features — they're UI-only and must not
                // affect ComfyUI's input hash, otherwise toggling random↔fixed
                // with the same resolved seed causes unnecessary re-execution.
                // Handles both plain array and V3 __value__ wrapper formats.
                const rawFeatures = result.output[nodeId].inputs?.features;
                if (rawFeatures != null) {
                    if (Array.isArray(rawFeatures)) {
                        result.output[nodeId].inputs.features =
                            rawFeatures.filter((f) => !ALL_MODE_CHIPS.has(f));
                    } else if (typeof rawFeatures === 'object' && '__value__' in rawFeatures && Array.isArray(rawFeatures.__value__)) {
                        rawFeatures.__value__ = rawFeatures.__value__.filter((f) => !ALL_MODE_CHIPS.has(f));
                    }
                }

                // Resolve both seeds
                const seeds = [
                    { prefix: 'ImageSeed', inputKey: 'image_seed', label: '♻️ (Use Last Queued Image Seed)' },
                    { prefix: 'PromptSeed', inputKey: 'prompt_seed', label: '♻️ (Use Last Queued Prompt Seed)' },
                ];

                for (const { prefix, inputKey, label } of seeds) {
                    const widget = node[`_Eclipse_${prefix}Widget`];
                    if (!widget) continue;

                    const resolved = node._resolveSeed(prefix);

                    // Update prompt output
                    if (result.output[nodeId].inputs?.[inputKey] !== undefined) {
                        const current = result.output[nodeId].inputs[inputKey];
                        if (Number(current) !== Number(resolved))
                            result.output[nodeId].inputs[inputKey] = resolved;
                    }

                    // Backward compat: also set "seed" to image_seed value
                    if (inputKey === 'image_seed' && result.output[nodeId].inputs?.seed !== undefined) {
                        result.output[nodeId].inputs.seed = resolved;
                    }

                    // Track last seed
                    const lastKey = `_Eclipse_last${prefix}`;
                    if (Number(node[lastKey]) !== Number(resolved)) {
                        node[lastKey] = resolved;
                    }

                    // Clear cache
                    node[`_Eclipse_cached${prefix}Input`] = null;
                    node[`_Eclipse_cached${prefix}Resolved`] = null;

                    // Update ♻️ button
                    const btn = node[`_Eclipse_${prefix}Button`];
                    if (btn) {
                        const seedVal = widget.value;
                        if (SPECIAL_SEEDS.includes(seedVal)) {
                            btn.label = `♻️ ${resolved}`;
                            btn.disabled = false;
                        } else {
                            btn.label = label;
                            btn.disabled = true;
                        }
                        notifyVue(node);
                    }

                    // Update workflow values
                    if (result.workflow?.nodes) {
                        const wfNode = result.workflow.nodes.find((n) => n.id === node.id);
                        if (wfNode?.widgets_values) {
                            const idx = node.widgets.indexOf(widget);
                            if (idx >= 0 && wfNode.widgets_values[idx] !== resolved)
                                wfNode.widgets_values[idx] = resolved;
                        }
                    }
                }
            }
            return result;
        };
    },
});
