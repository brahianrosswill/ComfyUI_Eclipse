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
function _getConnectedSeedSignature(e, t, s) {
    const i = e.inputs?.[t]?.link;
    if (null == i) return;
    const n = app.graph.links[i];
    if (!n) return;
    const l = String(n.origin_id),
        a = s.output[l]?.inputs;
    return a ? JSON.stringify(a) : void 0;
}
app.registerExtension({
    name: 'Eclipse.ReadPromptFiles',
    async beforeRegisterNodeDef(e, t, s) {
        if (t.name !== NODE_NAME) return;
        const i = s.graphToPrompt;
        s.graphToPrompt = async function () {
            const t = await i.apply(this, arguments),
                n = s.graph;
            for (const s in t.output) {
                const i = n.getNodeById(Number(s));
                if (i && i.constructor === e) {
                    if (void 0 !== i._Eclipse_manualIndex) {
                        ((t.output[s].inputs.index = i._Eclipse_manualIndex),
                            (i._Eclipse_lastResolvedIndex = i._Eclipse_manualIndex));
                        continue;
                    }
                    const e = i.inputs?.findIndex((e) => 'seed_input' === e.name),
                        n = e >= 0 && null != i.inputs[e]?.link,
                        l = SPECIAL_SEEDS.includes(Number(i._Eclipse_indexWidget?.value));
                    if (n && l) {
                        const n = _getConnectedSeedSignature(i, e, t);
                        if (
                            !(void 0 === n || void 0 === i._Eclipse_lastSeedInput || n !== i._Eclipse_lastSeedInput) &&
                            void 0 !== i._Eclipse_lastResolvedIndex
                        ) {
                            ((t.output[s].inputs.index = i._Eclipse_lastResolvedIndex),
                                i._Eclipse_lastIndexButton &&
                                    ((i._Eclipse_lastIndexButton.name = `♻️ ${i._Eclipse_lastResolvedIndex}`),
                                    (i._Eclipse_lastIndexButton.disabled = !1),
                                    notifyVue(i)));
                            continue;
                        }
                        i._Eclipse_lastSeedInput = n;
                    }
                    let a = null,
                        d = !1;
                    if (i._Eclipse_indexWidget) {
                        const e = Number(i._Eclipse_indexWidget.value);
                        if (SPECIAL_SEEDS.includes(e))
                            switch (e) {
                                case -1:
                                    const e = await i.getMaxIndex();
                                    a = e >= 0 ? Math.floor(Math.random() * (e + 1)) : 0;
                                    break;
                                case -2:
                                    const n = await i.getMaxIndex();
                                    if (n >= 0) {
                                        const e = !1 !== t.output[s].inputs.stop_at_end;
                                        if (
                                            void 0 === i._Eclipse_baseIndexForNavigation ||
                                            SPECIAL_SEEDS.includes(i._Eclipse_baseIndexForNavigation)
                                        )
                                            if (
                                                void 0 === i._Eclipse_lastResolvedIndex ||
                                                SPECIAL_SEEDS.includes(i._Eclipse_lastResolvedIndex)
                                            )
                                                a = 0;
                                            else {
                                                const t = i._Eclipse_lastResolvedIndex;
                                                a = !e && t + 1 > n ? 0 : (t + 1) % (n + 1);
                                            }
                                        else {
                                            const t = i._Eclipse_baseIndexForNavigation;
                                            ((i._Eclipse_baseIndexForNavigation = void 0),
                                                (a = !e && t + 1 > n ? 0 : (t + 1) % (n + 1)));
                                        }
                                    } else a = 0;
                                    break;
                                case -4: {
                                    const e = await i.getMaxIndex();
                                    if (e >= 0) {
                                        const n = e + 1,
                                            l = i._Eclipse_usedIndices || new Set(),
                                            d = [];
                                        for (let t = 0; t <= e; t++) l.has(t) || d.push(t);
                                        if (d.length > 0) {
                                            ((a = d[Math.floor(Math.random() * d.length)]),
                                                l.add(a),
                                                (i._Eclipse_usedIndices = l));
                                        } else {
                                            !1 !== t.output[s].inputs.stop_at_end
                                                ? (a = e + 1)
                                                : ((i._Eclipse_usedIndices = new Set()),
                                                  (a = Math.floor(Math.random() * n)),
                                                  i._Eclipse_usedIndices.add(a));
                                        }
                                    } else a = 0;
                                    break;
                                }
                                case -3:
                                    const l = await i.getMaxIndex();
                                    if (l >= 0) {
                                        const e = !1 !== t.output[s].inputs.stop_at_end;
                                        if (
                                            void 0 === i._Eclipse_baseIndexForNavigation ||
                                            SPECIAL_SEEDS.includes(i._Eclipse_baseIndexForNavigation)
                                        )
                                            if (
                                                void 0 === i._Eclipse_lastResolvedIndex ||
                                                SPECIAL_SEEDS.includes(i._Eclipse_lastResolvedIndex)
                                            )
                                                a = l;
                                            else {
                                                const t = i._Eclipse_lastResolvedIndex;
                                                a = !e && t - 1 < 0 ? l : t > 0 ? t - 1 : l;
                                            }
                                        else {
                                            const t = i._Eclipse_baseIndexForNavigation;
                                            ((i._Eclipse_baseIndexForNavigation = void 0),
                                                (a = !e && t - 1 < 0 ? l : t > 0 ? t - 1 : l));
                                        }
                                    } else a = 0;
                            }
                        else a = i.getIndexToUse();
                        null !== a &&
                            ((t.output[s].inputs.index = a),
                            (d =
                                void 0 === i._Eclipse_lastResolvedIndex ||
                                String(i._Eclipse_lastResolvedIndex) !== String(a)));
                    }
                    if ((d && null !== a && (i._Eclipse_lastResolvedIndex = a), i._Eclipse_lastIndexButton)) {
                        const e = i._Eclipse_indexWidget?.value;
                        if (SPECIAL_SEEDS.includes(Number(e)))
                            if (void 0 !== i._Eclipse_lastResolvedIndex) {
                                if (-4 === Number(e)) {
                                    const e = nodePromptCounts.get(Number(s)) || 0,
                                        t = i._Eclipse_usedIndices?.size || 0;
                                    i._Eclipse_lastIndexButton.name = `♻️ ${i._Eclipse_lastResolvedIndex} (${t}/${e})`;
                                } else i._Eclipse_lastIndexButton.name = `♻️ ${i._Eclipse_lastResolvedIndex}`;
                                i._Eclipse_lastIndexButton.disabled = !1;
                            } else
                                ((i._Eclipse_lastIndexButton.name = '♻️ (Use Last Queued Index)'),
                                    (i._Eclipse_lastIndexButton.disabled = !0));
                        else
                            ((i._Eclipse_lastIndexButton.name = '♻️ (Use Last Queued Index)'),
                                (i._Eclipse_lastIndexButton.disabled = !0));
                        notifyVue(i);
                    }
                }
            }
            return t;
        };
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
});
