/* eclipse-read-prompt-files.js - Minified for ComfyUI Eclipse */
import { app, api } from './comfy/index.js';
import { notifyVue } from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Read Prompt Files [Eclipse]',
    SPECIAL_SEED_RANDOM = -1,
    SPECIAL_SEED_INCREMENT = -2,
    SPECIAL_SEED_DECREMENT = -3,
    SPECIAL_SEED_SHUFFLE = -4,
    SPECIAL_SEEDS = [-1, -2, -3, -4],
    nodePromptCounts = new Map(),
    nodeFilePaths = new Map();
// Follow prompt-data link references to get the resolved seed value.
// In prompt data, linked inputs are stored as ["sourceNodeId", slotIndex].
// Virtual nodes (Get/Set) are already resolved, so we follow the chain.
function _resolvePromptValue(promptOutput, ref, depth) {
    if (depth > 4) return;
    if (!Array.isArray(ref)) return ref;
    const sourceId = String(ref[0]),
        sourceInputs = promptOutput[sourceId]?.inputs;
    if (!sourceInputs) return;
    for (const k in sourceInputs) {
        const kl = k.toLowerCase();
        if (kl === 'seed' || kl === 'value') {
            return _resolvePromptValue(promptOutput, sourceInputs[k], depth + 1);
        }
    }
}
function _getResolvedSeedValue(promptOutput, nodeId, inputName) {
    const ref = promptOutput[nodeId]?.inputs?.[inputName];
    if (ref == null) return;
    return _resolvePromptValue(promptOutput, ref, 0);
}
app.registerExtension({
    name: 'Eclipse.ReadPromptFiles',
    async beforeRegisterNodeDef(e, t, s) {
        if (t.name !== NODE_NAME) return;
        const n = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = n ? n.apply(this, arguments) : void 0;
            ((this._Eclipse_lastIndex = void 0),
                (this._Eclipse_lastResolvedIndex = void 0),
                (this._Eclipse_manualIndex = void 0),
                (this._Eclipse_baseIndexForNavigation = void 0),
                (this._Eclipse_cachedInputIndex = null),
                (this._Eclipse_cachedResolvedIndex = null),
                (this._Eclipse_lastSeedInput = void 0),
                (this._Eclipse_usedIndices = new Set()));
            let t = null;
            for (const [e, s] of this.widgets.entries()) {
                const i = (s.name || '').toString().toLowerCase(),
                    n = (s.label || s.options?.label || s.options?.name || '').toString().toLowerCase();
                'index' === i || 'index' === n ? (t = s) : 'control_after_generate' === i && this.widgets.splice(e, 1);
            }
            if (!t) return (console.warn('[Eclipse-ReadPromptFiles] Could not find Index widget'), e);
            this._Eclipse_indexWidget = t;
            const s = this.id,
                i = this.widgets?.find(
                    (e) =>
                        (e.name || '').toLowerCase().includes('file_paths') ||
                        (e.name || '').toLowerCase().includes('filepaths'),
                );
            if (i) {
                nodeFilePaths.set(s, i.value);
                const e = this,
                    n = i.callback;
                i.callback = function (i) {
                    const l = nodeFilePaths.get(s);
                    (n && n.apply(this, arguments),
                        !s || s < 0
                            ? nodeFilePaths.set(s, i)
                            : i === l ||
                              ('' === l && '' === i) ||
                              (nodeFilePaths.set(s, i),
                              (e._Eclipse_lastResolvedIndex = void 0),
                              (e._Eclipse_cachedInputIndex = null),
                              (e._Eclipse_cachedResolvedIndex = null),
                              l &&
                                  l.trim() &&
                                  fetch('/eclipse/read_prompt_files/invalidate_cache', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ file_paths: l }),
                                  }).catch((e) => {}),
                              i &&
                                  i.trim() &&
                                  e
                                      .getMaxIndex()
                                      .then((e) => {
                                          if (t.options) {
                                              t.options.max;
                                              const s = t.value || 0;
                                              ((t.options.max = Math.max(0, e)),
                                                  s > t.options.max
                                                      ? ((t.value = 0), t.callback && t.callback(0))
                                                      : t.options.max);
                                          }
                                      })
                                      .catch((e) => {
                                          (console.warn('[ReadPromptFiles] Error updating max index:', e),
                                              (t.value = 0),
                                              t.callback && t.callback(0));
                                      }),
                              e._Eclipse_lastIndexButton &&
                                  ((e._Eclipse_lastIndexButton.disabled = !0), notifyVue(e))));
                };
            }
            const l = t.callback;
            t.callback = (e) => {
                if (
                    ((this._Eclipse_cachedInputIndex = null),
                    (this._Eclipse_cachedResolvedIndex = null),
                    SPECIAL_SEEDS.includes(Number(e))
                        ? ((this._Eclipse_manualIndex = void 0),
                          -4 === Number(e) && (this._Eclipse_usedIndices = new Set()),
                          this._Eclipse_lastIndexButton &&
                              void 0 !== this._Eclipse_lastResolvedIndex &&
                              ((this._Eclipse_lastIndexButton.name = `♻️ ${this._Eclipse_lastResolvedIndex}`),
                              (this._Eclipse_lastIndexButton.disabled = !1),
                              notifyVue(this)))
                        : ((this._Eclipse_manualIndex = e),
                          (this._Eclipse_baseIndexForNavigation = e),
                          this._Eclipse_lastIndexButton &&
                              ((this._Eclipse_lastIndexButton.name = '♻️ (Use Last Queued Index)'),
                              (this._Eclipse_lastIndexButton.disabled = !0),
                              notifyVue(this))),
                    l)
                )
                    return l.call(t, e);
            };
            const a = this.addWidget(
                    'button',
                    '🎲 Randomize Each Time',
                    '',
                    () => {
                        ((t.value = -1), (this._Eclipse_manualIndex = void 0), t.callback && t.callback(-1));
                    },
                    { serialize: !1 },
                ),
                d = this.addWidget(
                    'button',
                    '♻️ (Use Last Queued Index)',
                    '',
                    () => {
                        null != this._Eclipse_lastResolvedIndex &&
                            ((t.value = this._Eclipse_lastResolvedIndex),
                            (this._Eclipse_manualIndex = this._Eclipse_lastResolvedIndex),
                            (d.name = '♻️ (Use Last Queued Index)'),
                            (d.disabled = !0),
                            notifyVue(this),
                            t.callback && t.callback(this._Eclipse_lastResolvedIndex));
                    },
                    { serialize: !1 },
                );
            return (
                (d.disabled = !0),
                (this._Eclipse_lastIndexButton = d),
                (this.generateRandomIndex = async function () {
                    const e = await this.getMaxIndex();
                    if (e >= 0) {
                        let t = Math.floor(Math.random() * (e + 1));
                        return (SPECIAL_SEEDS.includes(t) && (t = 0), t);
                    }
                    return 0;
                }),
                (this.getIndexToUse = function () {
                    const e = Number(this._Eclipse_indexWidget.value);
                    if (this._Eclipse_cachedInputIndex === e && null != this._Eclipse_cachedResolvedIndex)
                        return this._Eclipse_cachedResolvedIndex;
                    let t = null;
                    SPECIAL_SEEDS.includes(e) && (t = 0);
                    const s = null != t ? t : e;
                    return ((this._Eclipse_cachedInputIndex = e), (this._Eclipse_cachedResolvedIndex = s), s);
                }),
                (this.createSeededRNG = function (e) {
                    let t = e;
                    return function () {
                        return ((t = (9301 * t + 49297) % 233280), t / 233280);
                    };
                }),
                (this.getMaxIndex = async function () {
                    try {
                        const e = this._Eclipse_getFilePathsValue();
                        if (!e || !e.trim()) return 0;
                        const t = await api.fetchApi('/eclipse/read_prompt_files_count', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ file_paths: e }),
                        });
                        if (t.ok) {
                            const e = (await t.json()).count || 0,
                                s = Math.max(0, e - 1);
                            return (nodePromptCounts.set(this.id, e), s);
                        }
                        console.warn(`[ReadPromptFiles] Server error getting count: ${t.status} ${t.statusText}`);
                    } catch (e) {
                        console.warn('[ReadPromptFiles] Error getting max index:', e);
                    }
                    return 0;
                }),
                (this._Eclipse_getFilePathsValue = function () {
                    const e = this.widgets?.find(
                        (e) =>
                            (e.name || '').toLowerCase().includes('file_paths') ||
                            (e.name || '').toLowerCase().includes('filepaths'),
                    );
                    return e?.value || '';
                }),
                (this._Eclipse_navigationButtons = [a, d]),
                e
            );
        };
    },
    async setup() {
        // Patch graphToPrompt in setup() so it runs AFTER the Seed node's setup() patch.
        // This ensures connected seed values are already resolved (e.g., -1 → 42) when we read them.
        const prevGraphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const t = await prevGraphToPrompt.apply(this, arguments),
                allNodes = app.graph._nodes;
            for (const node of allNodes) {
                if (node.type !== NODE_NAME || !node._Eclipse_indexWidget) continue;
                if (2 === node.mode || 4 === node.mode) continue;
                const nodeId = String(node.id);
                if (!t.output || !t.output[nodeId]) continue;

                if (void 0 !== node._Eclipse_manualIndex) {
                    ((t.output[nodeId].inputs.index = node._Eclipse_manualIndex),
                        (node._Eclipse_lastResolvedIndex = node._Eclipse_manualIndex));
                    continue;
                }
                const seedInputIdx = node.inputs?.findIndex((e) => 'seed_input' === e.name),
                    hasSeedLink = seedInputIdx >= 0 && null != node.inputs[seedInputIdx]?.link,
                    indexIsSpecial = SPECIAL_SEEDS.includes(Number(node._Eclipse_indexWidget?.value));
                // Seed freeze: follow prompt-data references to get resolved seed value.
                // No connection → work normally. First run → record seed, advance.
                // Same seed → freeze index. Changed seed → advance, record new seed.
                if (hasSeedLink && indexIsSpecial) {
                    const currentSeed = _getResolvedSeedValue(t.output, nodeId, 'seed_input');
                    if (
                        void 0 !== currentSeed &&
                        null !== currentSeed &&
                        void 0 !== node._Eclipse_lastResolvedIndex &&
                        void 0 !== node._Eclipse_lastSeedInput &&
                        String(currentSeed) === String(node._Eclipse_lastSeedInput)
                    ) {
                        // Same seed — freeze
                        t.output[nodeId].inputs.index = node._Eclipse_lastResolvedIndex;
                        node._Eclipse_lastIndexButton &&
                            ((node._Eclipse_lastIndexButton.name = `♻️ ${node._Eclipse_lastResolvedIndex}`),
                            (node._Eclipse_lastIndexButton.disabled = !1),
                            notifyVue(node));
                        // Remove seed_input from prompt — JS-only, prevent upstream cache invalidation
                        if (t.output[nodeId]?.inputs?.seed_input !== void 0) delete t.output[nodeId].inputs.seed_input;
                        continue;
                    }
                    // First run or seed changed — record and advance normally
                    node._Eclipse_lastSeedInput = void 0 !== currentSeed && null !== currentSeed ? String(currentSeed) : void 0;
                }
                // Remove seed_input from prompt — JS-only, prevent upstream cache invalidation
                if (t.output[nodeId]?.inputs?.seed_input !== void 0) delete t.output[nodeId].inputs.seed_input;
                let resolvedIndex = null,
                    indexChanged = !1;
                if (node._Eclipse_indexWidget) {
                    const mode = Number(node._Eclipse_indexWidget.value);
                    if (SPECIAL_SEEDS.includes(mode))
                        switch (mode) {
                            case -1: {
                                const maxIdx = await node.getMaxIndex();
                                resolvedIndex = maxIdx >= 0 ? Math.floor(Math.random() * (maxIdx + 1)) : 0;
                                break;
                            }
                            case -2: {
                                const maxIdx = await node.getMaxIndex();
                                if (maxIdx >= 0) {
                                    const stopAtEnd = !1 !== t.output[nodeId].inputs.stop_at_end;
                                    if (
                                        void 0 === node._Eclipse_baseIndexForNavigation ||
                                        SPECIAL_SEEDS.includes(node._Eclipse_baseIndexForNavigation)
                                    )
                                        if (
                                            void 0 === node._Eclipse_lastResolvedIndex ||
                                            SPECIAL_SEEDS.includes(node._Eclipse_lastResolvedIndex)
                                        )
                                            resolvedIndex = 0;
                                        else {
                                            const prev = node._Eclipse_lastResolvedIndex;
                                            resolvedIndex = !stopAtEnd && prev + 1 > maxIdx ? 0 : (prev + 1) % (maxIdx + 1);
                                        }
                                    else {
                                        const base = node._Eclipse_baseIndexForNavigation;
                                        ((node._Eclipse_baseIndexForNavigation = void 0),
                                            (resolvedIndex = !stopAtEnd && base + 1 > maxIdx ? 0 : (base + 1) % (maxIdx + 1)));
                                    }
                                } else resolvedIndex = 0;
                                break;
                            }
                            case -4: {
                                const maxIdx = await node.getMaxIndex();
                                if (maxIdx >= 0) {
                                    const total = maxIdx + 1,
                                        used = node._Eclipse_usedIndices || new Set(),
                                        available = [];
                                    for (let j = 0; j <= maxIdx; j++) used.has(j) || available.push(j);
                                    if (available.length > 0) {
                                        ((resolvedIndex = available[Math.floor(Math.random() * available.length)]),
                                            used.add(resolvedIndex),
                                            (node._Eclipse_usedIndices = used));
                                    } else {
                                        !1 !== t.output[nodeId].inputs.stop_at_end
                                            ? (resolvedIndex = maxIdx + 1)
                                            : ((node._Eclipse_usedIndices = new Set()),
                                              (resolvedIndex = Math.floor(Math.random() * total)),
                                              node._Eclipse_usedIndices.add(resolvedIndex));
                                    }
                                } else resolvedIndex = 0;
                                break;
                            }
                            case -3: {
                                const maxIdx = await node.getMaxIndex();
                                if (maxIdx >= 0) {
                                    const stopAtEnd = !1 !== t.output[nodeId].inputs.stop_at_end;
                                    if (
                                        void 0 === node._Eclipse_baseIndexForNavigation ||
                                        SPECIAL_SEEDS.includes(node._Eclipse_baseIndexForNavigation)
                                    )
                                        if (
                                            void 0 === node._Eclipse_lastResolvedIndex ||
                                            SPECIAL_SEEDS.includes(node._Eclipse_lastResolvedIndex)
                                        )
                                            resolvedIndex = maxIdx;
                                        else {
                                            const prev = node._Eclipse_lastResolvedIndex;
                                            resolvedIndex = !stopAtEnd && prev - 1 < 0 ? maxIdx : prev > 0 ? prev - 1 : maxIdx;
                                        }
                                    else {
                                        const base = node._Eclipse_baseIndexForNavigation;
                                        ((node._Eclipse_baseIndexForNavigation = void 0),
                                            (resolvedIndex = !stopAtEnd && base - 1 < 0 ? maxIdx : base > 0 ? base - 1 : maxIdx));
                                    }
                                } else resolvedIndex = 0;
                                break;
                            }
                        }
                    else resolvedIndex = node.getIndexToUse();
                    null !== resolvedIndex &&
                        ((t.output[nodeId].inputs.index = resolvedIndex),
                        (indexChanged =
                            void 0 === node._Eclipse_lastResolvedIndex ||
                            String(node._Eclipse_lastResolvedIndex) !== String(resolvedIndex)));
                }
                if ((indexChanged && null !== resolvedIndex && (node._Eclipse_lastResolvedIndex = resolvedIndex), node._Eclipse_lastIndexButton)) {
                    const mode = node._Eclipse_indexWidget?.value;
                    if (SPECIAL_SEEDS.includes(Number(mode)))
                        if (void 0 !== node._Eclipse_lastResolvedIndex) {
                            if (-4 === Number(mode)) {
                                const count = nodePromptCounts.get(node.id) || 0,
                                    usedCount = node._Eclipse_usedIndices?.size || 0;
                                node._Eclipse_lastIndexButton.name = `♻️ ${node._Eclipse_lastResolvedIndex} (${usedCount}/${count})`;
                            } else node._Eclipse_lastIndexButton.name = `♻️ ${node._Eclipse_lastResolvedIndex}`;
                            node._Eclipse_lastIndexButton.disabled = !1;
                        } else
                            ((node._Eclipse_lastIndexButton.name = '♻️ (Use Last Queued Index)'),
                                (node._Eclipse_lastIndexButton.disabled = !0));
                    else
                        ((node._Eclipse_lastIndexButton.name = '♻️ (Use Last Queued Index)'),
                            (node._Eclipse_lastIndexButton.disabled = !0));
                    notifyVue(node);
                }
            }
            return t;
        };
    },
});
