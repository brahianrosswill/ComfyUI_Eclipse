/* eclipse-load-image-folder-pipe.js - Combo-chip toggles for Load Image From Folder (Pipe) [Eclipse] */
import { app, api } from './comfy/index.js';
import { notifyVue, createWidgetVisibilityManager } from './eclipse-widget-performance-utils.js';
import { injectComboChipCSS, createComboChipWidget as _createComboChipWidget } from './eclipse-combo-chip.js';

const NODE_NAME = 'Load Image From Folder (Pipe) [Eclipse]';
const MODE_RANDOM = -1, MODE_INCREMENT = -2, MODE_DECREMENT = -3, MODE_RANDOM_NO_REPEAT = -4;
const SPECIAL_MODES = [MODE_RANDOM, MODE_INCREMENT, MODE_DECREMENT, MODE_RANDOM_NO_REPEAT];

// Chip options — booleans exposed as chips + mode radio chips
const CHIP_OPTIONS = [
    'read_subfolders', 'stop_at_end', 'extract_metadata', 'refresh_list',
    '🎲 random', '⏫ increment', '⏬ decrement', '🔀 shuffle',
];
const DEFAULT_CHIPS = ['read_subfolders', 'stop_at_end'];

// Mode chips — radio group (mutually exclusive, toggle-off allowed)
const MODE_CHIPS = ['🎲 random', '⏫ increment', '⏬ decrement', '🔀 shuffle'];
const MODE_CHIP_TO_INDEX = {
    '🎲 random': MODE_RANDOM,
    '⏫ increment': MODE_INCREMENT,
    '⏬ decrement': MODE_DECREMENT,
    '🔀 shuffle': MODE_RANDOM_NO_REPEAT,
};
const INDEX_TO_MODE_CHIP = Object.fromEntries(
    Object.entries(MODE_CHIP_TO_INDEX).map(([k, v]) => [v, k])
);

// Chip label → backing widget name (boolean toggles only)
const CHIP_TO_BACKING = {
    'read_subfolders':        'include_subfolders',
    'stop_at_end':       'stop_at_end',
    'extract_metadata':  'extract_metadata',
    'refresh_list':           'refresh_list',
};
const BACKING_WIDGETS = Object.values(CHIP_TO_BACKING);

injectComboChipCSS('liff');

// --- State maps (shared across instances) ---
const nodeFolderPaths = new Map();
const nodeStopTriggered = new Map();
const nodeImageCounts = new Map();
const fetchDebounceTimers = new Map();

// --- Seed resolution (same as eclipse-load-image-folder.js) ---
function _getResolvedSeedFromGraph(node) {
    const seedInputIdx = node.inputs?.findIndex(e => 'seed_input' === e.name);
    if (seedInputIdx < 0 || null == node.inputs[seedInputIdx]?.link) return;
    let curNode = node, curIdx = seedInputIdx, depth = 10;
    while (depth-- > 0) {
        let linkInfo;
        const linkId = curNode.inputs?.[curIdx]?.link;
        if (null != linkId) linkInfo = app.graph.links[linkId];
        else if (curNode.getInputLink) linkInfo = curNode.getInputLink(curIdx);
        if (!linkInfo) return;
        const src = app.graph.getNodeById(linkInfo.origin_id);
        if (!src) return;
        if (src.getSeedToUse) return src.getSeedToUse();
        if (src._Eclipse_seedWidget) return Number(src._Eclipse_seedWidget.value);
        if (src.getInputLink) { curNode = src; curIdx = 0; continue; }
        if (src.inputs?.length === 1 && src.outputs?.length >= 1) { curNode = src; curIdx = 0; continue; }
        for (const w of src.widgets || []) {
            const wn = (w.name || '').toLowerCase();
            if (wn === 'seed' || wn === 'value') return Number(w.value);
        }
        return;
    }
}

// --- Image count fetch ---
async function updateImageCount(node) {
    const id = node.id;
    const folderW = node.widgets?.find(w => w.name === 'folder_path');
    const indexW = node.widgets?.find(w => w.name === 'index');
    if (!folderW || !indexW) return;
    const folderPath = folderW.value;
    const includeSubW = node.widgets?.find(w => w.name === 'include_subfolders');
    const includeSub = includeSubW?.value ?? false;
    if (!folderPath || !folderPath.trim()) { indexW.options.max = 999999; nodeImageCounts.set(id, 0); return; }
    try {
        const resp = await fetch('/eclipse/load_image_folder/count', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_path: folderPath, include_subfolders: includeSub }),
        });
        if (resp.ok) {
            const count = (await resp.json()).total_count || 0;
            nodeImageCounts.set(id, count);
            if (count > 0) {
                indexW.options.max = Math.max(0, count - 1);
                if (indexW.value > indexW.options.max) {
                    indexW.value = indexW.options.max;
                    indexW.callback?.(indexW.value);
                }
            } else {
                indexW.options.max = 0;
            }
            // Update last-index button label for shuffle mode
            const btn = node._Eclipse_lastIndexButton;
            if (btn && indexW.value === -4 && node._Eclipse_lastResolvedIndex !== null) {
                const used = node._Eclipse_usedIndices?.size || 0;
                btn.name = `♻️ ${node._Eclipse_lastResolvedIndex} (${used}/${count})`;
                notifyVue(node);
            }
            node.setDirtyCanvas(true, true);
        }
    } catch (e) {
        console.warn('[LoadImageFromFolder Pipe] Failed to fetch image count:', e);
    }
}

function updateImageCountDebounced(node, delay = 300) {
    const id = node.id;
    if (fetchDebounceTimers.has(id)) clearTimeout(fetchDebounceTimers.get(id));
    fetchDebounceTimers.set(id, setTimeout(() => {
        updateImageCount(node);
        fetchDebounceTimers.delete(id);
    }, delay));
}

// --- Chip sync helpers ---
function syncChipsToBacking(selectedSet, node) {
    for (const [chip, backing] of Object.entries(CHIP_TO_BACKING)) {
        const w = node.widgets?.find(w => w.name === backing);
        if (w && w.value !== selectedSet.has(chip)) w.value = selectedSet.has(chip);
    }
}

function readChipsFromBacking(node) {
    const chips = new Set();
    for (const [chip, backing] of Object.entries(CHIP_TO_BACKING)) {
        const w = node.widgets?.find(w => w.name === backing);
        if (w && w.value) chips.add(chip);
    }
    return chips;
}

app.registerExtension({
    name: 'Eclipse.LoadImageFromFolderPipe',
    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== NODE_NAME) return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const ret = origOnNodeCreated ? origOnNodeCreated.apply(this, arguments) : void 0;
            const node = this;
            const id = node.id;

            const vis = createWidgetVisibilityManager(node);
            const findW = (name) => node.widgets?.find(w => w.name === name);

            const folderW = findW('folder_path');
            const indexW = findW('index');

            if (!folderW) { console.warn('[LoadImageFromFolder Pipe] folder_path widget not found'); return ret; }

            // --- Internal state ---
            node._Eclipse_indexWidget = indexW;
            node._Eclipse_lastIndex = null;
            node._Eclipse_updatingIndex = false;
            node._Eclipse_lastResolvedIndex = null;
            node._Eclipse_lastIndexButton = null;
            node._Eclipse_lastSeedInput = undefined;
            node._Eclipse_usedIndices = new Set();
            node._Eclipse_pausedShuffle = false;

            const parseFolders = (v) => (v || '').split('\n').map(s => s.trim()).filter(s => s.length > 0);
            nodeFolderPaths.set(id, parseFolders(folderW.value));
            nodeStopTriggered.set(id, false);

            // --- Read initial chip state from backing widgets + index mode ---
            const initialSet = readChipsFromBacking(node);
            const hasAnyBacking = BACKING_WIDGETS.some(name => {
                const w = findW(name);
                return w && w.value === true;
            });
            const chipSet = hasAnyBacking ? initialSet : new Set(DEFAULT_CHIPS);
            // Add mode chip based on current index value
            if (indexW && SPECIAL_MODES.includes(indexW.value)) {
                const modeChip = INDEX_TO_MODE_CHIP[indexW.value];
                if (modeChip) chipSet.add(modeChip);
            }

            // Hide all backing boolean widgets (chips replace them)
            for (const name of BACKING_WIDGETS) vis.setVisible(name, false);

            // --- Create chip widget after folder_path ---
            const origIdx = folderW ? node.widgets.indexOf(folderW) + 1 : 0;
            const featWidget = _createComboChipWidget({
                node, options: CHIP_OPTIONS, savedValue: chipSet, origIdx,
                widgetName: '_liff_features', cssPrefix: 'liff', serialize: false,
                radioGroups: [MODE_CHIPS], radioToggle: true,
            });

            node._Eclipse_chipWidget = featWidget;

            featWidget.callback = () => {
                const selected = new Set(featWidget.value);
                syncChipsToBacking(selected, node);

                // Sync mode chip → index widget
                if (indexW) {
                    const activeMode = MODE_CHIPS.find(m => selected.has(m));
                    if (activeMode) {
                        const modeVal = MODE_CHIP_TO_INDEX[activeMode];
                        if (indexW.value !== modeVal) {
                            // Preserve shuffle state when switching back
                            if (modeVal === MODE_RANDOM_NO_REPEAT && node._Eclipse_pausedShuffle) {
                                node._Eclipse_pausedShuffle = false;
                            } else if (modeVal === MODE_RANDOM_NO_REPEAT && indexW.value !== MODE_RANDOM_NO_REPEAT) {
                                node._Eclipse_usedIndices = new Set();
                            }
                            node._Eclipse_updatingIndex = true;
                            indexW.value = modeVal;
                            indexW.callback?.(modeVal);
                            node._Eclipse_updatingIndex = false;
                        }
                    } else if (SPECIAL_MODES.includes(indexW.value)) {
                        // All mode chips deselected → revert to last resolved or 0
                        const pinVal = node._Eclipse_lastResolvedIndex ?? 0;
                        node._Eclipse_updatingIndex = true;
                        indexW.value = pinVal;
                        indexW.callback?.(pinVal);
                        node._Eclipse_updatingIndex = false;
                    }
                    node.setDirtyCanvas(true, true);
                }

                updateImageCountDebounced(node);
            };

            // Sync initial state
            syncChipsToBacking(chipSet, node);

            // --- Folder path change handler ---
            const origFolderCb = folderW.callback;
            folderW.callback = function (val) {
                const oldPaths = nodeFolderPaths.get(id) || [];
                const newPaths = parseFolders(val);
                origFolderCb?.apply(this, arguments);

                const firstChanged = oldPaths[0] !== newPaths[0];
                const removed = oldPaths.filter(p => !newPaths.includes(p));
                const added = newPaths.filter(p => !oldPaths.includes(p));
                const needReset = removed.length > 0 || firstChanged;

                if (firstChanged || removed.length > 0 || added.length > 0) {
                    nodeFolderPaths.set(id, newPaths);
                    if (needReset) nodeStopTriggered.set(id, false);
                    if (firstChanged) { node._Eclipse_lastIndex = null; node._Eclipse_usedIndices = new Set(); }
                    // Invalidate cache for removed folders
                    for (const p of removed) {
                        fetch('/eclipse/load_image_folder/invalidate_cache', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ folder_path: p }),
                        }).catch(() => {});
                    }
                    if (firstChanged && indexW && indexW.value !== 0) {
                        node._Eclipse_updatingIndex = true;
                        indexW.value = 0;
                        indexW.callback?.(0);
                        node._Eclipse_updatingIndex = false;
                    }
                    if (removed.length > 0) {
                        const refreshW = findW('refresh_list');
                        if (refreshW) refreshW.value = true;
                    }
                    updateImageCountDebounced(node);
                    node.setDirtyCanvas(true, true);
                }
            };

            // --- Index change handler ---
            if (indexW) {
                const origIndexCb = indexW.callback;
                indexW.callback = function (val) {
                    origIndexCb?.apply(this, arguments);
                    if (node._Eclipse_updatingIndex) return;

                    const isSpecial = SPECIAL_MODES.includes(val);
                    const wasShuffle = node._Eclipse_indexWidget && node._Eclipse_lastIndex === -4;

                    // Sync mode chips to match index value
                    if (node._Eclipse_chipWidget) {
                        const chips = new Set(node._Eclipse_chipWidget.value);
                        for (const m of MODE_CHIPS) chips.delete(m);
                        if (isSpecial) {
                            const modeChip = INDEX_TO_MODE_CHIP[val];
                            if (modeChip) chips.add(modeChip);
                        }
                        node._Eclipse_chipWidget.value = [...chips];
                    }

                    if (isSpecial) {
                        const btn = node._Eclipse_lastIndexButton;
                        if (btn && node._Eclipse_lastResolvedIndex !== null) {
                            btn.disabled = false;
                            const ic = nodeImageCounts.get(id) || 0;
                            btn.name = val === -4 && ic > 0
                                ? `♻️ ${node._Eclipse_lastResolvedIndex} (${node._Eclipse_usedIndices?.size || 0}/${ic})`
                                : `♻️ ${node._Eclipse_lastResolvedIndex}`;
                            notifyVue(node);
                        }
                        if (val === -4 && !wasShuffle) {
                            if (node._Eclipse_pausedShuffle) node._Eclipse_pausedShuffle = false;
                            else node._Eclipse_usedIndices = new Set();
                        }
                    } else {
                        node._Eclipse_lastResolvedIndex = null;
                        node._Eclipse_lastIndex = null;
                        const btn = node._Eclipse_lastIndexButton;
                        if (btn) { btn.disabled = true; btn.name = '♻️ (Use Last Queued Index)'; notifyVue(node); }
                    }
                    if (nodeStopTriggered.get(id)) nodeStopTriggered.set(id, false);
                };
            }

            // --- Last Index button ---
            if (indexW) {
                const lastBtn = node.addWidget('button', '♻️ (Use Last Queued Index)', null, () => {
                    if (node._Eclipse_lastResolvedIndex !== null) {
                        if (indexW.value === -4) node._Eclipse_pausedShuffle = true;
                        node._Eclipse_updatingIndex = true;
                        indexW.value = node._Eclipse_lastResolvedIndex;
                        indexW.callback?.(indexW.value);
                        node._Eclipse_updatingIndex = false;
                        // Deselect mode chips
                        if (node._Eclipse_chipWidget) {
                            const chips = new Set(node._Eclipse_chipWidget.value);
                            for (const m of MODE_CHIPS) chips.delete(m);
                            node._Eclipse_chipWidget.value = [...chips];
                        }
                        node.setDirtyCanvas(true, true);
                    }
                });
                lastBtn.serialize = false;
                lastBtn.disabled = true;
                node._Eclipse_lastIndexButton = lastBtn;
            }

            // --- Cleanup on remove ---
            const origOnRemoved = node.onRemoved;
            node.onRemoved = function () {
                nodeFolderPaths.delete(id);
                nodeStopTriggered.delete(id);
                nodeImageCounts.delete(id);
                if (fetchDebounceTimers.has(id)) { clearTimeout(fetchDebounceTimers.get(id)); fetchDebounceTimers.delete(id); }
                origOnRemoved?.apply(this, arguments);
            };

            // Initial count fetch
            if (folderW.value && folderW.value.trim()) {
                setTimeout(() => updateImageCount(node), 100);
            }

            return ret;
        };

        // --- getIndexToUse method (same logic as original) ---
        nodeType.prototype.getIndexToUse = function (stopAtEnd = true) {
            const indexW = this._Eclipse_indexWidget;
            if (!indexW) return 0;
            const val = indexW.value;
            const lastIdx = this._Eclipse_lastIndex;
            const maxIdx = indexW.options?.max ?? 999999;
            const totalCount = nodeImageCounts.get(this.id) || maxIdx + 1;
            let resolved = val;

            if (val === MODE_RANDOM) {
                if (totalCount > 1) {
                    let attempts = 0;
                    do { resolved = Math.floor(Math.random() * totalCount); attempts++; }
                    while (resolved === lastIdx && attempts < 10);
                } else resolved = 0;
            } else if (val === MODE_INCREMENT) {
                if (lastIdx === null) resolved = 0;
                else { resolved = lastIdx + 1; if (!stopAtEnd && resolved > maxIdx) resolved = 0; else if (resolved > maxIdx) resolved = maxIdx; }
            } else if (val === MODE_DECREMENT) {
                if (lastIdx === null) resolved = maxIdx;
                else { resolved = lastIdx - 1; if (!stopAtEnd && resolved < 0) resolved = maxIdx; else if (resolved < 0) resolved = 0; }
            } else if (val === MODE_RANDOM_NO_REPEAT) {
                const used = this._Eclipse_usedIndices || new Set();
                const available = [];
                for (let i = 0; i <= maxIdx; i++) { if (!used.has(i)) available.push(i); }
                if (available.length > 0) {
                    resolved = available[Math.floor(Math.random() * available.length)];
                    used.add(resolved);
                    this._Eclipse_usedIndices = used;
                } else if (stopAtEnd) {
                    resolved = maxIdx + 1;
                } else {
                    this._Eclipse_usedIndices = new Set();
                    resolved = Math.floor(Math.random() * totalCount);
                    this._Eclipse_usedIndices.add(resolved);
                }
            }
            return resolved;
        };
    },

    async setup() {
        // --- Stop iteration handler ---
        api.addEventListener('stop-iteration', () => {
            // Disable auto-queue
            const cb = document.getElementById('autoQueueCheckbox');
            if (cb?.checked) { cb.checked = false; cb.dispatchEvent(new Event('change', { bubbles: true })); }
            if (app.ui?.autoQueueEnabled !== undefined) app.ui.autoQueueEnabled = false;
            try {
                const autoCb = document.querySelector('input[type="checkbox"][id*="auto"], input[type="checkbox"][class*="auto"]');
                if (autoCb?.checked) { autoCb.checked = false; autoCb.dispatchEvent(new Event('change', { bubbles: true })); }
            } catch (_) {}

            for (const node of app.graph?._nodes || []) {
                if (node.type !== NODE_NAME) continue;
                nodeStopTriggered.set(node.id, true);
                const indexW = node.widgets?.find(w => w.name === 'index');
                if (indexW) {
                    node._Eclipse_updatingIndex = true;
                    indexW.value = 0;
                    indexW.callback?.(0);
                    node._Eclipse_updatingIndex = false;
                    node.setDirtyCanvas(true, true);
                }
                node._Eclipse_lastIndex = null;
            }
        });

        // --- Execution start: auto-clear refresh flag ---
        api.addEventListener('execution_start', () => {
            for (const node of app.graph?._nodes || []) {
                if (node.type !== NODE_NAME) continue;
                const refreshW = node.widgets?.find(w => w.name === 'refresh_list');
                if (refreshW?.value === true) {
                    node._Eclipse_refreshPending = true;
                    setTimeout(() => {
                        refreshW.value = false;
                        // Also deselect 'refresh' chip visually
                        const chipW = node.widgets?.find(w => w.name === '_liff_features');
                        if (chipW) {
                            const sel = new Set(chipW.value);
                            sel.delete('refresh');
                            chipW.value = [...sel];
                        }
                        notifyVue(node);
                        node.setDirtyCanvas(true, true);
                    }, 500);
                }
            }
        });

        // --- Execution complete: update counts ---
        api.addEventListener('executed', (e) => {
            const detail = e.detail;
            if (!detail) return;
            const nodeId = detail.node || detail.display_node;
            if (!nodeId) return;
            const node = app.graph?.getNodeById(Number(nodeId));
            if (!node || node.type !== NODE_NAME) return;
            if (node._Eclipse_refreshPending) {
                node._Eclipse_refreshPending = false;
                node._Eclipse_usedIndices = new Set();
                updateImageCount(node);
            } else {
                updateImageCountDebounced(node, 500);
            }
        });

        // --- Graph configure: fetch counts after workflow load ---
        const origConfigure = app.graph?.configure?.bind(app.graph);
        if (app.graph && origConfigure) {
            app.graph.configure = function (data) {
                const result = origConfigure(data);
                setTimeout(() => {
                    for (const node of app.graph?._nodes || []) {
                        if (node.type !== NODE_NAME) continue;
                        const folderW = node.widgets?.find(w => w.name === 'folder_path');
                        if (folderW?.value?.trim()) updateImageCount(node);
                    }
                }, 200);
                return result;
            };
        }

        // --- graphToPrompt: resolve special index modes ---
        const origGraphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const result = await origGraphToPrompt.apply(this, arguments);
            if (!result?.output) return result;

            for (const node of app.graph._nodes) {
                if (node.type !== NODE_NAME || !node._Eclipse_indexWidget) continue;
                if (node.mode === 2 || node.mode === 4) continue;  // muted/bypassed

                const nodeId = String(node.id);
                if (!result.output[nodeId]) continue;

                // Remove button widgets from prompt data
                if (result.output[nodeId].inputs) {
                    for (const w of node.widgets || []) {
                        if (w.type === 'button' && w.name in result.output[nodeId].inputs) {
                            delete result.output[nodeId].inputs[w.name];
                        }
                    }
                    // Remove non-serializing chip widget
                    delete result.output[nodeId].inputs._liff_features;
                }

                const stopAtEnd = result.output[nodeId].inputs?.stop_at_end !== false;
                const seedInputIdx = node.inputs?.findIndex(e => 'seed_input' === e.name);
                const hasSeedLink = seedInputIdx >= 0 && node.inputs[seedInputIdx]?.link != null;
                const indexVal = Number(node._Eclipse_indexWidget?.value);
                const isSpecial = SPECIAL_MODES.includes(indexVal);

                // Seed freeze logic
                if (hasSeedLink && isSpecial) {
                    const currentSeed = _getResolvedSeedFromGraph(node);
                    if (currentSeed != null && node._Eclipse_lastResolvedIndex != null
                        && node._Eclipse_lastSeedInput !== undefined
                        && String(currentSeed) === String(node._Eclipse_lastSeedInput)) {
                        // Same seed — freeze index
                        if (result.output[nodeId].inputs?.index !== undefined) {
                            result.output[nodeId].inputs.index = node._Eclipse_lastResolvedIndex;
                        }
                        const btn = node._Eclipse_lastIndexButton;
                        if (btn) {
                            const ic = nodeImageCounts.get(node.id) || 0;
                            btn.disabled = false;
                            btn.name = indexVal === -4
                                ? `♻️ ${node._Eclipse_lastResolvedIndex} (${node._Eclipse_usedIndices?.size || 0}/${ic})`
                                : `♻️ ${node._Eclipse_lastResolvedIndex}`;
                            notifyVue(node);
                        }
                        if (result.workflow?.nodes) {
                            const wn = result.workflow.nodes.find(x => x.id === node.id);
                            if (wn?.widgets_values) {
                                const wi = node.widgets.indexOf(node._Eclipse_indexWidget);
                                if (wi >= 0) wn.widgets_values[wi] = indexVal;
                            }
                        }
                        node._Eclipse_lastIndex = node._Eclipse_lastResolvedIndex;
                        if (result.output[nodeId]?.inputs?.seed_input !== undefined) delete result.output[nodeId].inputs.seed_input;
                        continue;
                    }
                    node._Eclipse_lastSeedInput = currentSeed != null ? String(currentSeed) : undefined;
                }

                // Remove seed_input from prompt
                if (result.output[nodeId]?.inputs?.seed_input !== undefined) delete result.output[nodeId].inputs.seed_input;

                // Resolve index
                const resolved = node.getIndexToUse(stopAtEnd);
                const indexW = node._Eclipse_indexWidget;
                const rawVal = indexW.value;
                const rawIsSpecial = SPECIAL_MODES.includes(rawVal);

                if (result.output[nodeId].inputs?.index !== undefined) result.output[nodeId].inputs.index = resolved;

                if (rawIsSpecial) {
                    node._Eclipse_lastResolvedIndex = resolved;
                    const btn = node._Eclipse_lastIndexButton;
                    if (btn) {
                        btn.disabled = false;
                        if (rawVal === -4) {
                            const ic = nodeImageCounts.get(node.id) || 0;
                            btn.name = `♻️ ${resolved} (${node._Eclipse_usedIndices?.size || 0}/${ic})`;
                        } else {
                            btn.name = `♻️ ${resolved}`;
                        }
                        notifyVue(node);
                    }
                } else {
                    if (rawVal !== resolved) {
                        node._Eclipse_updatingIndex = true;
                        indexW.value = resolved;
                        indexW.callback?.(resolved);
                        node._Eclipse_updatingIndex = false;
                        node.setDirtyCanvas(true, true);
                    }
                    const btn = node._Eclipse_lastIndexButton;
                    if (btn) { btn.disabled = true; btn.name = '♻️ (Use Last Queued Index)'; notifyVue(node); }
                }

                node._Eclipse_lastIndex = resolved;
                if (result.workflow?.nodes) {
                    const wn = result.workflow.nodes.find(x => x.id === node.id);
                    if (wn?.widgets_values) {
                        const wi = node.widgets.indexOf(indexW);
                        if (wi >= 0) wn.widgets_values[wi] = rawIsSpecial ? rawVal : resolved;
                    }
                }
            }
            return result;
        };
    },
    async refreshComboInNodes() {
        for (const node of app.graph?._nodes || []) {
            if (node.type !== NODE_NAME) continue;
            const folderW = node.widgets?.find(w => w.name === 'folder_path');
            if (folderW?.value?.trim()) {
                await fetch('/eclipse/load_image_folder/invalidate_cache', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder_path: folderW.value }),
                }).catch(() => {});
                updateImageCount(node);
            }
        }
    },
});
