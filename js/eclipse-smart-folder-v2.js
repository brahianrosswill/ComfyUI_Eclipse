/* eclipse-smart-folder-v2.js - Widget visibility + combo-chip features for Smart Folder v2 [Eclipse] */
import { app } from './comfy/index.js';
import {
    debounce,
    smartResize,
    createWidgetVisibilityManager,
    isVueMode,
    onVueModeChange,
    notifyVue,
} from './eclipse-widget-performance-utils.js';
import { injectComboChipCSS, createComboChipWidget as _createComboChipWidget } from './eclipse-combo-chip.js';

const NODE_NAME = 'Smart Folder v2 [Eclipse]';
const SPECIAL_SEEDS = [-1, -2, -3];
const LAST_SEED_BUTTON_LABEL = '♻️ (Use Last Queued Seed)';

// Feature options for the combo-chip selector
const FEATURE_OPTIONS = ['image', 'video', 'date_time', 'batch', 'image_size', 'seed'];
const DEFAULT_FEATURES = ['image', 'date_time'];

// Radio groups: mutually exclusive (selecting one deselects siblings)
const RADIO_GROUPS = [['image', 'video']];

// Backing widgets: hidden originals that handle serialization
const BACKING_WIDGETS = ['generation_mode', 'create_date_time_folder', 'create_batch_folder', 'use_image_size', 'use_seed'];

injectComboChipCSS('sf2');

// Sync chip state → hidden backing widgets for serialization
function syncChipsToBacking(selectedSet, node) {
    const setW = (name, val) => {
        const w = node.widgets?.find((w) => w.name === name);
        if (w && w.value !== val) w.value = val;
    };
    setW('generation_mode', selectedSet.has('video') ? 'Video Mode' : 'Image Mode');
    setW('create_date_time_folder', selectedSet.has('date_time'));
    setW('create_batch_folder', selectedSet.has('batch'));
    setW('use_image_size', selectedSet.has('image_size'));
    setW('use_seed', selectedSet.has('seed'));
}

// Read chip state from hidden backing widgets (for configure/load)
function readChipsFromBacking(node) {
    const gv = (name) => {
        const w = node.widgets?.find((w) => w.name === name);
        return w ? w.value : undefined;
    };
    const chips = new Set();
    if (gv('generation_mode') === 'Video Mode') chips.add('video');
    else chips.add('image');
    if (gv('create_date_time_folder')) chips.add('date_time');
    if (gv('create_batch_folder')) chips.add('batch');
    if (gv('use_image_size')) chips.add('image_size');
    if (gv('use_seed')) chips.add('seed');
    return chips;
}

function createComboChipWidget(node, initialSet, origIdx) {
    return _createComboChipWidget({
        node, options: FEATURE_OPTIONS, savedValue: initialSet, origIdx,
        widgetName: '_sf_features', cssPrefix: 'sf2', radioGroups: RADIO_GROUPS, serialize: false,
    });
}

// Visibility update based on chip state
function updateVisibility(node, vis) {
    if (node.id === -1) return;

    const featW = node.widgets?.find((w) => w.name === '_sf_features');
    const selected = featW ? new Set(featW.value) : readChipsFromBacking(node);

    const isImage = selected.has('image');
    const isVideo = selected.has('video');
    const hasDateTime = selected.has('date_time');
    const hasBatch = selected.has('batch');
    const hasImageSize = selected.has('image_size');
    const customImage = vis.getValue('image_size') === 'Custom';
    const customVideo = vis.getValue('video_size') === 'Custom';

    // Hide backing widgets (always hidden, replaced by chips)
    for (const name of BACKING_WIDGETS) vis.setVisible(name, false);

    // Date/time
    vis.setVisible('date_time_format', hasDateTime);
    vis.setVisible('date_time_position', hasDateTime);

    // Batch
    vis.setVisible('batch_folder_name', hasBatch);
    vis.setVisible('batch_number', hasBatch);
    vis.setVisible('batch_number_control', hasBatch);

    // Image
    vis.setVisible('root_folder_image', isImage);
    vis.setVisible('image_size', isImage && hasImageSize);
    vis.setVisible('width', isImage && hasImageSize && customImage);
    vis.setVisible('height', isImage && hasImageSize && customImage);
    vis.setVisible('latent_type', isImage && hasImageSize);
    vis.setVisible('batch_size', isImage);

    // Video
    vis.setVisible('root_folder_video', isVideo);
    vis.setVisible('video_size', isVideo);
    vis.setVisible('video_width', isVideo && customVideo);
    vis.setVisible('video_height', isVideo && customVideo);
    vis.setVisible('frame_rate', isVideo);
    vis.setVisible('frame_load_cap', isVideo);
    vis.setVisible('context_length', isVideo);
    vis.setVisible('loop_count', isVideo);
    vis.setVisible('overlap', isVideo);
    vis.setVisible('skip_first_frames', isVideo);
    vis.setVisible('skip_calculation', isVideo);
    vis.setVisible('skip_calculation_control', isVideo);
    vis.setVisible('select_every_nth', isVideo);

    // Seed + seed buttons
    const hasSeed = selected.has('seed');
    vis.setVisible('seed', hasSeed);
    vis.setVisible('_btn_randomize', hasSeed);
    vis.setVisible('_btn_new_fixed', hasSeed);
    vis.setVisible('_btn_last_seed', hasSeed);

    smartResize(node);
}

app.registerExtension({
    name: 'Eclipse.SmartFolderV2',
    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== NODE_NAME) return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const ret = origOnNodeCreated ? origOnNodeCreated.apply(this, arguments) : void 0;
            const node = this;
            const vis = createWidgetVisibilityManager(node);
            node._Eclipse_vis = vis;
            node._Eclipse_lastBatchNumber = null;
            node._Eclipse_lastSkipFirstFramesCalc = null;

            // Read initial chip state from backing widgets
            const initialSet = readChipsFromBacking(node);

            // Insert combo-chip at generation_mode's position
            const modeW = node.widgets?.find((w) => w.name === 'generation_mode');
            const origIdx = modeW ? node.widgets.indexOf(modeW) : 0;

            // Hide all backing widgets (they still serialize, chips are cosmetic overlay)
            for (const name of BACKING_WIDGETS) {
                const w = node.widgets?.find((w) => w.name === name);
                if (w) {
                    w.hidden = true;
                    if (w.options) w.options.hidden = true;
                }
            }

            // Create combo-chip dropdown
            const featWidget = createComboChipWidget(node, initialSet, origIdx);

            // Hook chip callback → sync backing widgets + update visibility
            const origFeatCb = featWidget.callback;
            featWidget.callback = function (value) {
                origFeatCb?.call(this, value);
                syncChipsToBacking(new Set(featWidget.value), node);
                updateVisibility(node, vis);
            };

            // --- Remove control_after_generate widget ---
            for (let i = node.widgets.length - 1; i >= 0; i--) {
                const wName = (node.widgets[i].name || '').toString().toLowerCase();
                if (wName === 'control_after_generate') {
                    node.widgets.splice(i, 1);
                }
            }

            // --- Seed button setup ---
            const seedWidget = node.widgets?.find((w) => w.name === 'seed');
            if (seedWidget) {
                node._Eclipse_seedWidget = seedWidget;
                node._Eclipse_lastSeed = undefined;
                node._Eclipse_randomMin = 0;
                node._Eclipse_randomMax = Number.MAX_SAFE_INTEGER;
                node._Eclipse_cachedInputSeed = null;
                node._Eclipse_cachedResolvedSeed = null;

                const origSeedCb = seedWidget.callback;
                seedWidget.callback = (v) => {
                    node._Eclipse_cachedInputSeed = null;
                    node._Eclipse_cachedResolvedSeed = null;
                    if (origSeedCb) origSeedCb.call(seedWidget, v);
                };

                const seedIdx = node.widgets.indexOf(seedWidget);

                const btnRandomize = node.addWidget('button', '_btn_randomize', '', () => {
                    seedWidget.value = -1;
                    seedWidget.callback && seedWidget.callback(-1);
                }, { serialize: false });
                btnRandomize.label = '🎲 Randomize Each Time';

                const btnNewFixed = node.addWidget('button', '_btn_new_fixed', '', () => {
                    const s = node.generateRandomSeed();
                    seedWidget.value = s;
                    seedWidget.callback && seedWidget.callback(s);
                }, { serialize: false });
                btnNewFixed.label = '🎲 New Fixed Random';

                const btnLastSeed = node.addWidget('button', '_btn_last_seed', '', () => {
                    if (node._Eclipse_lastSeed != null) {
                        seedWidget.value = node._Eclipse_lastSeed;
                        btnLastSeed.label = LAST_SEED_BUTTON_LABEL;
                        btnLastSeed.disabled = true;
                        notifyVue(node);
                    }
                }, { serialize: false });
                btnLastSeed.label = LAST_SEED_BUTTON_LABEL;
                btnLastSeed.disabled = true;
                node._Eclipse_lastSeedButton = btnLastSeed;

                // Move buttons right after seed widget
                const buttons = [btnRandomize, btnNewFixed, btnLastSeed];
                for (let i = buttons.length - 1; i >= 0; i--) {
                    const btn = buttons[i];
                    const idx = node.widgets.indexOf(btn);
                    if (idx !== seedIdx + 1) {
                        node.widgets.splice(idx, 1);
                        node.widgets.splice(seedIdx + 1, 0, btn);
                    }
                }
            }

            const debouncedUpdate = debounce(() => updateVisibility(node, vis), 100);

            // Hook conditional-visibility trigger widgets (image_size/video_size combos)
            for (const name of ['image_size', 'video_size']) {
                const w = node.widgets?.find((w) => w.name === name);
                if (w) {
                    const origCb = w.callback;
                    w.callback = function (v) {
                        debouncedUpdate();
                        origCb?.call(this, v);
                    };
                }
            }

            // Initial visibility
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    syncChipsToBacking(initialSet, node);
                    updateVisibility(node, vis);
                }
            }, 0);

            // Restore on configure (loading saved workflows)
            const origConfigure = node.onConfigure;
            node.onConfigure = function (data) {
                origConfigure?.apply(this, arguments);
                node._Eclipse_initialized = true; // prevent deferred init from overwriting restored values
                vis.clearCache?.();
                // Read backing widget values → set chip state
                const chips = readChipsFromBacking(node);
                featWidget.value = [...chips];
                syncChipsToBacking(chips, node); // ensure backing matches chip state
                setTimeout(() => updateVisibility(node, vis), 100);
            };

            return ret;
        };

        // Seed helper methods
        nodeType.prototype.generateRandomSeed = function () {
            const step = this._Eclipse_seedWidget?.options?.step || 1;
            const min = this._Eclipse_randomMin || 0;
            const range = ((this._Eclipse_randomMax || 0xFFFFFFFF) - min) / (step / 10);
            let seed = Math.floor(Math.random() * range) * (step / 10) + min;
            if (SPECIAL_SEEDS.includes(seed)) seed = 0;
            return seed;
        };

        nodeType.prototype.getSeedToUse = function () {
            const input = Number(this._Eclipse_seedWidget.value);
            if (this._Eclipse_cachedInputSeed === input && this._Eclipse_cachedResolvedSeed != null)
                return this._Eclipse_cachedResolvedSeed;
            let resolved = null;
            if (SPECIAL_SEEDS.includes(input)) {
                if (typeof this._Eclipse_lastSeed === 'number' && !SPECIAL_SEEDS.includes(this._Eclipse_lastSeed)) {
                    if (input === -2) resolved = this._Eclipse_lastSeed + 1;
                    else if (input === -3) resolved = this._Eclipse_lastSeed - 1;
                }
                if (resolved == null || SPECIAL_SEEDS.includes(resolved))
                    resolved = this.generateRandomSeed();
            }
            const final = resolved != null ? resolved : input;
            this._Eclipse_cachedInputSeed = input;
            this._Eclipse_cachedResolvedSeed = final;
            return final;
        };

        // Store last seed from execution results
        const origOnExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (data) {
            const ret = origOnExecuted ? origOnExecuted.apply(this, arguments) : void 0;
            if (data && data.seed !== undefined) {
                this._Eclipse_lastSeed = data.seed;
            }
            return ret;
        };
    },

    async setup() {
        // Mode switch (Classic ↔ Nodes 2.0): recreate nodes
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

        // graphToPrompt hook: batch_number + skip_calculation increment + seed resolution
        const origGraphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const result = await origGraphToPrompt.apply(this, arguments);
            const nodes = app.graph._nodes;

            for (const node of nodes) {
                if (node.type !== NODE_NAME) continue;
                if (node.mode === 2 || node.mode === 4) continue;

                const nodeId = String(node.id);
                if (!result.output?.[nodeId]) continue;
                const inputs = result.output[nodeId].inputs;

                // --- batch_number increment ---
                const batchW = node.widgets?.find((w) => w.name === 'batch_number');
                const batchCtrl = node.widgets?.find((w) => w.name === 'batch_number_control');
                if (batchW && batchCtrl && inputs) {
                    if (batchCtrl.value === 'increment') {
                        if (node._Eclipse_lastBatchNumber != null) {
                            const next = node._Eclipse_lastBatchNumber + 1;
                            inputs.batch_number = next;
                            node._Eclipse_lastBatchNumber = next;
                            if (Number(batchW.value) !== next) batchW.value = next;
                            if (result.workflow?.nodes) {
                                const wfNode = result.workflow.nodes.find((n) => n.id === node.id);
                                if (wfNode?.widgets_values) {
                                    const idx = node.widgets.indexOf(batchW);
                                    if (idx >= 0) wfNode.widgets_values[idx] = next;
                                }
                            }
                        } else {
                            node._Eclipse_lastBatchNumber = batchW.value;
                        }
                    } else {
                        node._Eclipse_lastBatchNumber = batchW.value;
                    }
                }

                // --- skip_calculation increment ---
                const skipW = node.widgets?.find((w) => w.name === 'skip_calculation');
                const skipCtrl = node.widgets?.find((w) => w.name === 'skip_calculation_control');
                if (skipW && skipCtrl && inputs) {
                    if (skipCtrl.value === 'increment') {
                        if (node._Eclipse_lastSkipFirstFramesCalc != null) {
                            const next = node._Eclipse_lastSkipFirstFramesCalc + 1;
                            inputs.skip_calculation = next;
                            node._Eclipse_lastSkipFirstFramesCalc = next;
                            if (Number(skipW.value) !== next) skipW.value = next;
                            if (result.workflow?.nodes) {
                                const wfNode = result.workflow.nodes.find((n) => n.id === node.id);
                                if (wfNode?.widgets_values) {
                                    const idx = node.widgets.indexOf(skipW);
                                    if (idx >= 0) wfNode.widgets_values[idx] = next;
                                }
                            }
                        } else {
                            node._Eclipse_lastSkipFirstFramesCalc = skipW.value;
                        }
                    } else {
                        node._Eclipse_lastSkipFirstFramesCalc = skipW.value;
                    }
                }

                // --- Seed resolution ---
                if (node._Eclipse_seedWidget) {
                    const resolved = node.getSeedToUse();

                    if (inputs?.seed !== undefined) {
                        const current = inputs.seed;
                        if (Number(current) !== Number(resolved))
                            inputs.seed = resolved;
                    }

                    if (Number(node._Eclipse_lastSeed) !== Number(resolved)) {
                        node._Eclipse_lastSeed = resolved;
                    }
                    node._Eclipse_cachedInputSeed = null;
                    node._Eclipse_cachedResolvedSeed = null;

                    if (node._Eclipse_lastSeedButton) {
                        const seedVal = node._Eclipse_seedWidget.value;
                        if (SPECIAL_SEEDS.includes(seedVal)) {
                            node._Eclipse_lastSeedButton.label = `♻️ ${resolved}`;
                            node._Eclipse_lastSeedButton.disabled = false;
                        } else {
                            node._Eclipse_lastSeedButton.label = LAST_SEED_BUTTON_LABEL;
                            node._Eclipse_lastSeedButton.disabled = true;
                        }
                        notifyVue(node);
                    }

                    if (result.workflow?.nodes) {
                        const wfNode = result.workflow.nodes.find((n) => n.id === node.id);
                        if (wfNode?.widgets_values) {
                            const idx = node.widgets.indexOf(node._Eclipse_seedWidget);
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
