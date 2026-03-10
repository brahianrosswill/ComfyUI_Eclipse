/* eclipse-load-image-folder.js - Minified for ComfyUI Eclipse */
import { app, api } from './comfy/index.js';
import { notifyVue } from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Load Image From Folder [Eclipse]',
    MODE_RANDOM = -1,
    MODE_INCREMENT = -2,
    MODE_DECREMENT = -3,
    MODE_RANDOM_NO_REPEAT = -4,
    SPECIAL_MODES = [-1, -2, -3, -4],
    nodeFolderPaths = new Map(),
    nodeStopTriggered = new Map(),
    nodeImageCounts = new Map(),
    fetchDebounceTimers = new Map();
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
async function updateImageCount(e) {
    const t = e.id,
        n = e.widgets?.find((e) => 'folder_path' === e.name),
        s = e.widgets?.find((e) => 'include_subfolders' === e.name),
        i = e.widgets?.find((e) => 'index' === e.name);
    if (!n || !i) return;
    const o = n.value,
        a = s?.value ?? !1;
    if (!o || !o.trim()) return ((i.options.max = 999999), void nodeImageCounts.set(t, 0));
    try {
        const n = await fetch('/eclipse/load_image_folder/count', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_path: o, include_subfolders: a }),
        });
        if (n.ok) {
            const s = (await n.json()).total_count || 0;
            (nodeImageCounts.set(t, s),
                s > 0
                    ? ((i.options.max = Math.max(0, s - 1)),
                      i.value > i.options.max && ((i.value = i.options.max), i.callback && i.callback(i.value)))
                    : (i.options.max = 0));
            const o = e._Eclipse_lastIndexButton;
            if (o && -4 === i.value && null !== e._Eclipse_lastResolvedIndex) {
                const t = e._Eclipse_usedIndices?.size || 0;
                ((o.name = `♻️ ${e._Eclipse_lastResolvedIndex} (${t}/${s})`), notifyVue(e));
            }
            e.setDirtyCanvas(!0, !0);
        }
    } catch (e) {
        console.warn('[LoadImageFromFolder] Failed to fetch image count:', e);
    }
}
function updateImageCountDebounced(e, t = 300) {
    const n = e.id;
    fetchDebounceTimers.has(n) && clearTimeout(fetchDebounceTimers.get(n));
    const s = setTimeout(() => {
        (updateImageCount(e), fetchDebounceTimers.delete(n));
    }, t);
    fetchDebounceTimers.set(n, s);
}
app.registerExtension({
    name: 'Eclipse.LoadImageFromFolder',
    async beforeRegisterNodeDef(e, t, n) {
        if (t.name !== NODE_NAME) return;
        const s = e.prototype.onNodeCreated;
        ((e.prototype.onNodeCreated = function () {
            const e = s ? s.apply(this, arguments) : void 0,
                t = this,
                n = t.id,
                i = (e) => t.widgets?.find((t) => t.name === e),
                o = i('folder_path'),
                a = i('index'),
                d = i('refresh_list');
            if (!o) return (console.warn('[LoadImageFromFolder] folder_path widget not found'), e);
            ((t._Eclipse_indexWidget = a),
                (t._Eclipse_lastIndex = null),
                (t._Eclipse_updatingIndex = !1),
                (t._Eclipse_lastResolvedIndex = null),
                (t._Eclipse_lastIndexButton = null),
                (t._Eclipse_lastSeedInput = void 0),
                (t._Eclipse_usedIndices = new Set()));
            const l = (e) =>
                (e || '')
                    .split('\n')
                    .map((e) => e.trim())
                    .filter((e) => e.length > 0);
            (nodeFolderPaths.set(n, l(o.value)), nodeStopTriggered.set(n, !1));
            const c = o.callback;
            o.callback = function (e) {
                const s = nodeFolderPaths.get(n) || [],
                    i = l(e);
                c && c.apply(this, arguments);
                const o = s[0] !== i[0],
                    u = s.filter((e) => !i.includes(e)),
                    p = i.filter((e) => !s.includes(e)),
                    r = u.length > 0 || o;
                if (o || u.length > 0 || p.length > 0) {
                    (nodeFolderPaths.set(n, i),
                        r && nodeStopTriggered.set(n, !1),
                        o && ((t._Eclipse_lastIndex = null), (t._Eclipse_usedIndices = new Set())));
                    for (const e of u)
                        fetch('/eclipse/load_image_folder/invalidate_cache', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ folder_path: e }),
                        }).catch((e) => {});
                    (o &&
                        a &&
                        0 !== a.value &&
                        ((t._Eclipse_updatingIndex = !0),
                        (a.value = 0),
                        a.callback && a.callback(0),
                        (t._Eclipse_updatingIndex = !1)),
                        u.length > 0 && d && (d.value = !0),
                        updateImageCountDebounced(t),
                        t.setDirtyCanvas(!0, !0));
                }
            };
            const u = i('include_subfolders');
            if (u) {
                const e = u.callback;
                u.callback = function (n) {
                    (e && e.apply(this, arguments), updateImageCountDebounced(t));
                };
            }
            if (a) {
                const e = a.callback;
                a.callback = function (s) {
                    if ((e && e.apply(this, arguments), !t._Eclipse_updatingIndex)) {
                        const e = -1 === s || -2 === s || -3 === s || -4 === s,
                            i = t._Eclipse_indexWidget && -4 === t._Eclipse_lastIndex;
                        if (e) {
                            const e = t._Eclipse_lastIndexButton;
                            if (e && null !== t._Eclipse_lastResolvedIndex) {
                                e.disabled = !1;
                                const i = nodeImageCounts.get(n) || 0;
                                if (-4 === s && i > 0) {
                                    t._Eclipse_usedIndices;
                                    e.name = `♻️ ${t._Eclipse_lastResolvedIndex}/${i}`;
                                } else e.name = `♻️ ${t._Eclipse_lastResolvedIndex}`;
                                notifyVue(t);
                            }
                            -4 !== s || i || (t._Eclipse_usedIndices = new Set());
                        } else {
                            ((t._Eclipse_lastResolvedIndex = null), (t._Eclipse_lastIndex = null));
                            const e = t._Eclipse_lastIndexButton;
                            e && ((e.disabled = !0), (e.name = '♻️ (Use Last Queued Index)'), notifyVue(t));
                        }
                        nodeStopTriggered.get(n) && nodeStopTriggered.set(n, !1);
                    }
                };
            }
            if (a) {
                t.addWidget('button', '🎲 Randomize Each Time', null, () => {
                    ((t._Eclipse_updatingIndex = !0),
                        (a.value = -1),
                        a.callback && a.callback(-1),
                        (t._Eclipse_updatingIndex = !1),
                        t.setDirtyCanvas(!0, !0));
                }).serialize = !1;
            }
            if (a) {
                const e = t.addWidget('button', '♻️ (Use Last Queued Index)', null, () => {
                    if (null !== t._Eclipse_lastResolvedIndex) {
                        const e = t._Eclipse_lastResolvedIndex;
                        ((a.value = e), a.callback && a.callback(e), t.setDirtyCanvas(!0, !0));
                    }
                });
                ((e.serialize = !1), (e.disabled = !0), (t._Eclipse_lastIndexButton = e));
            }
            const p = t.onRemoved;
            return (
                (t.onRemoved = function () {
                    (nodeFolderPaths.delete(n),
                        nodeStopTriggered.delete(n),
                        nodeImageCounts.delete(n),
                        fetchDebounceTimers.has(n) &&
                            (clearTimeout(fetchDebounceTimers.get(n)), fetchDebounceTimers.delete(n)),
                        p && p.apply(this, arguments));
                }),
                o.value &&
                    o.value.trim() &&
                    setTimeout(() => {
                        updateImageCount(t);
                    }, 100),
                e
            );
        }),
            (e.prototype.getIndexToUse = function (e = !0) {
                const t = this._Eclipse_indexWidget;
                if (!t) return 0;
                const n = t.value,
                    s = this._Eclipse_lastIndex,
                    i = t.options?.max ?? 999999,
                    o = nodeImageCounts.get(this.id) || i + 1;
                let a = n;
                if (-1 === n)
                    if (o > 1) {
                        let e = 0;
                        do {
                            ((a = Math.floor(Math.random() * o)), e++);
                        } while (a === s && e < 10);
                    } else a = 0;
                else if (-2 === n) null === s ? (a = 0) : ((a = s + 1), !e && a > i ? (a = 0) : a > i && (a = i));
                else if (-3 === n) null === s ? (a = i) : ((a = s - 1), !e && a < 0 ? (a = i) : a < 0 && (a = 0));
                else if (-4 === n) {
                    const t = this._Eclipse_usedIndices || new Set(),
                        n = [];
                    for (let e = 0; e <= i; e++) t.has(e) || n.push(e);
                    if (n.length > 0) {
                        ((a = n[Math.floor(Math.random() * n.length)]), t.add(a), (this._Eclipse_usedIndices = t));
                    } else
                        e
                            ? (a = i + 1)
                            : ((this._Eclipse_usedIndices = new Set()),
                              (a = Math.floor(Math.random() * o)),
                              this._Eclipse_usedIndices.add(a));
                } else a = n;
                return a;
            }));
    },
    async setup() {
        (api.addEventListener('stop-iteration', (e) => {
            const t = document.getElementById('autoQueueCheckbox');
            (t && t.checked && ((t.checked = !1), t.dispatchEvent(new Event('change', { bubbles: !0 }))),
                app.ui && void 0 !== app.ui.autoQueueEnabled && (app.ui.autoQueueEnabled = !1));
            try {
                document.querySelector('[id*="queue"]');
                const e = document.querySelector(
                    'input[type="checkbox"][id*="auto"], input[type="checkbox"][class*="auto"]',
                );
                e && e.checked && ((e.checked = !1), e.dispatchEvent(new Event('change', { bubbles: !0 })));
            } catch (e) {}
            const n = app.graph?._nodes || [];
            for (const e of n)
                if (e.type === NODE_NAME) {
                    nodeStopTriggered.set(e.id, !0);
                    const t = e.widgets?.find((e) => 'index' === e.name);
                    (t &&
                        ((e._Eclipse_updatingIndex = !0),
                        (t.value = 0),
                        t.callback && t.callback(0),
                        (e._Eclipse_updatingIndex = !1),
                        e.setDirtyCanvas(!0, !0)),
                        (e._Eclipse_lastIndex = null));
                }
        }),
            api.addEventListener('execution_start', () => {
                const e = app.graph?._nodes || [];
                for (const t of e)
                    if (t.type === NODE_NAME) {
                        const e = t.widgets?.find((e) => 'refresh_list' === e.name);
                        e &&
                            !0 === e.value &&
                            ((t._Eclipse_refreshPending = !0),
                            setTimeout(() => {
                                ((e.value = !1), notifyVue(t), t.setDirtyCanvas(!0, !0));
                            }, 500));
                    }
            }),
            api.addEventListener('executed', (e) => {
                const t = e.detail;
                if (!t) return;
                const n = t.node || t.display_node;
                if (!n) return;
                const s = app.graph?.getNodeById(Number(n));
                s &&
                    s.type === NODE_NAME &&
                    (s._Eclipse_refreshPending
                        ? ((s._Eclipse_refreshPending = !1), (s._Eclipse_usedIndices = new Set()), updateImageCount(s))
                        : updateImageCountDebounced(s, 500));
            }));
        const e = app.graph?.configure?.bind(app.graph);
        app.graph &&
            e &&
            (app.graph.configure = function (t) {
                const n = e(t);
                return (
                    setTimeout(() => {
                        const e = app.graph?._nodes || [];
                        for (const t of e)
                            if (t.type === NODE_NAME) {
                                const e = t.widgets?.find((e) => 'folder_path' === e.name);
                                e && e.value && e.value.trim() && updateImageCount(t);
                            }
                    }, 200),
                    n
                );
            });
        const t = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const e = await t.apply(this, arguments);
            if (!e || !e.output) return e;
            const n = app.graph._nodes;
            for (const t of n) {
                if (t.type !== NODE_NAME || !t._Eclipse_indexWidget) continue;
                if (2 === t.mode || 4 === t.mode) continue;
                const n = String(t.id);
                if (!e.output[n]) continue;
                // Remove button widgets from prompt data — their names change and invalidate cache
                if (e.output[n].inputs) {
                    for (const w of t.widgets || []) {
                        if (w.type === 'button' && w.name in e.output[n].inputs) {
                            delete e.output[n].inputs[w.name];
                        }
                    }
                }
                const s = !1 !== e.output[n].inputs?.stop_at_end,
                    seedInputIdx = t.inputs?.findIndex((e) => 'seed_input' === e.name),
                    hasSeedLink = seedInputIdx >= 0 && null != t.inputs[seedInputIdx]?.link,
                    indexVal = Number(t._Eclipse_indexWidget?.value),
                    indexIsSpecial = SPECIAL_MODES.includes(indexVal);
                // Seed freeze: follow prompt-data references to get actual seed value.
                // No connection → work normally. First run → record seed, advance.
                // Same seed → freeze index. Changed seed → advance, record new seed.
                if (hasSeedLink && indexIsSpecial) {
                    const currentSeed = _getResolvedSeedValue(e.output, n, 'seed_input');
                    if (
                        void 0 !== currentSeed &&
                        null !== currentSeed &&
                        void 0 !== t._Eclipse_lastResolvedIndex &&
                        null !== t._Eclipse_lastResolvedIndex &&
                        void 0 !== t._Eclipse_lastSeedInput &&
                        String(currentSeed) === String(t._Eclipse_lastSeedInput)
                    ) {
                        // Same seed — freeze
                        e.output[n].inputs && void 0 !== e.output[n].inputs.index && (e.output[n].inputs.index = t._Eclipse_lastResolvedIndex);
                        const btn = t._Eclipse_lastIndexButton;
                        if (btn) {
                            const ic = nodeImageCounts.get(t.id) || 0;
                            btn.disabled = !1;
                            btn.name = -4 === indexVal
                                ? `♻️ ${t._Eclipse_lastResolvedIndex} (${t._Eclipse_usedIndices?.size || 0}/${ic})`
                                : `♻️ ${t._Eclipse_lastResolvedIndex}`;
                            notifyVue(t);
                        }
                        if (e.workflow && e.workflow.nodes) {
                            const wn = e.workflow.nodes.find((x) => x.id === t.id);
                            if (wn && wn.widgets_values) {
                                const wi = t.widgets.indexOf(t._Eclipse_indexWidget);
                                wi >= 0 && (wn.widgets_values[wi] = indexVal);
                            }
                        }
                        t._Eclipse_lastIndex = t._Eclipse_lastResolvedIndex;
                        // Remove seed_input from prompt — JS-only, prevent upstream cache invalidation
                        if (e.output[n]?.inputs?.seed_input !== void 0) delete e.output[n].inputs.seed_input;
                        continue;
                    }
                    // First run or seed changed — record and advance normally
                    t._Eclipse_lastSeedInput = void 0 !== currentSeed && null !== currentSeed ? String(currentSeed) : void 0;
                }
                // Remove seed_input from prompt — JS-only, prevent upstream cache invalidation
                if (e.output[n]?.inputs?.seed_input !== void 0) delete e.output[n].inputs.seed_input;
                const i = t.getIndexToUse(s),
                    o = t._Eclipse_indexWidget,
                    a = o.value,
                    d = -1 === a || -2 === a || -3 === a || -4 === a,
                    l = -4 === a;
                if (
                    (e.output[n].inputs && void 0 !== e.output[n].inputs.index && (e.output[n].inputs.index = i),
                    d ||
                        o.value === i ||
                        ((t._Eclipse_updatingIndex = !0),
                        (o.value = i),
                        o.callback && o.callback(i),
                        (t._Eclipse_updatingIndex = !1),
                        t.setDirtyCanvas(!0, !0)),
                    d)
                ) {
                    t._Eclipse_lastResolvedIndex = i;
                    const e = t._Eclipse_lastIndexButton;
                    if (e) {
                        if (((e.disabled = !1), l)) {
                            const n = nodeImageCounts.get(t.id) || 0,
                                s = t._Eclipse_usedIndices?.size || 0;
                            e.name = `♻️ ${i} (${s}/${n})`;
                        } else e.name = `♻️ ${i}`;
                        notifyVue(t);
                    }
                } else {
                    const e = t._Eclipse_lastIndexButton;
                    e && ((e.disabled = !0), (e.name = '♻️ (Use Last Queued Index)'), notifyVue(t));
                }
                if (((t._Eclipse_lastIndex = i), e.workflow && e.workflow.nodes)) {
                    const n = e.workflow.nodes.find((e) => e.id === t.id);
                    if (n && n.widgets_values) {
                        const e = t.widgets.indexOf(o);
                        e >= 0 && (n.widgets_values[e] = d ? a : i);
                    }
                }
            }
            return e;
        };
    },
});
