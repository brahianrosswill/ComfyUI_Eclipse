/* eclipse-wildcard-processor.js - Minified for ComfyUI Eclipse */
import { app } from './comfy/index.js';
import { notifyVue } from './eclipse-widget-performance-utils.js';
const LAST_SEED_BUTTON_LABEL = '♻️ (Use Last Queued Seed)',
    SPECIAL_SEED_RANDOM = -1,
    SPECIAL_SEED_INCREMENT = -2,
    SPECIAL_SEED_DECREMENT = -3,
    SPECIAL_SEEDS = [-1, -2, -3];
let wildcardList = [],
    wildcardListLoading = !1;
async function loadWildcardList() {
    if (!wildcardListLoading) {
        wildcardListLoading = !0;
        try {
            const e = await fetch('/eclipse/wildcards/list');
            e.ok && (wildcardList = await e.json());
        } catch (e) {
            (console.warn('[Eclipse Wildcard] Failed to load wildcard list:', e), (wildcardList = []));
        } finally {
            wildcardListLoading = !1;
        }
    }
}
function updateWildcardCombo(e) {
    if (!e) return;
    const t = ['Select a Wildcard', ...wildcardList];
    (e.options
        ? 'object' != typeof e.options || Array.isArray(e.options)
            ? Array.isArray(e.options) && Object.defineProperty(e, 'options', { value: t, writable: !0 })
            : (e.options.values = t)
        : Object.defineProperty(e, 'options', { value: t, writable: !0 }),
        e.element && e.element.style.setProperty('--changed', 'true', 'important'));
}
function cleanProcessedText(e) {
    return e
        ? (e = (e = (e = (e = (e = (e = (e = (e = e.replace(/__[\w.\-+/*\\]+?__/g, '')).replace(
              /[,\s]*,[,\s]*,/g,
              ',',
          )).replace(/\.,\s*/g, ', ')).replace(/,\s*\./g, '.')).replace(/\s*,\s*,/g, ',')).replace(
              /^\s*,\s*/g,
              '',
          )).replace(/\s*,\s*$/g, ''))
              .replace(/\s+/g, ' ')
              .trim())
        : e;
}
async function updatePopulatedText(e, t, i) {
    if (e && t)
        try {
            const s = await fetch('/eclipse/wildcards/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: t, seed: i }),
            });
            if (s.ok) {
                const t = await s.json();
                if (t.success) {
                    const i = cleanProcessedText(t.output);
                    ((e.value = i), e.callback && e.callback(i));
                } else console.warn('[Eclipse Wildcard] Server error - success=false');
            } else console.warn('[Eclipse Wildcard] Server returned status:', s.status);
        } catch (e) {
            console.error('[Eclipse Wildcard] Error updating preview:', e);
        }
}
function updateUIForMode(e, t) {
    const i = e.widgets?.find((e) => 'seed' === e.name);
    if (i)
        switch (t) {
            case 'populate':
                i.element &&
                    ((i.element.style.opacity = '1.0'),
                    (i.element.title = 'Change seed to generate new output, fix seed to keep same output'));
                break;
            case 'fixed':
                i.element && ((i.element.style.opacity = '0.5'), (i.element.title = "Seed is ignored in 'fixed' mode"));
        }
}
(app.registerExtension({
    name: 'Eclipse.WildcardProcessor',
    async setup() {
        await loadWildcardList();
        const e = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const t = app.graph._nodes;
            for (const e of t)
                if ('Wildcard Processor [Eclipse]' === e.type) {
                    const t = e.widgets?.find((e) => 'wildcard_text' === e.name),
                        i = e.widgets?.find((e) => 'populated_text' === e.name),
                        s = e.widgets?.find((e) => 'mode' === e.name);
                    if (!s || !t || !i) continue;
                    const d = s.value,
                        n = t.value;
                    if ('fixed' === d) continue;
                    if ('populate' === d && n) {
                        const t = e.widgets?.find((e) => 'seed' === e.name),
                            s =
                                e.getSeedToUse && 'function' == typeof e.getSeedToUse
                                    ? e.getSeedToUse()
                                    : (t?.value ?? 0);
                        try {
                            const e = await fetch('/eclipse/wildcards/process', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ text: n, seed: s }),
                            });
                            if (e.ok) {
                                const t = await e.json();
                                t.success && (i.value = t.output);
                            }
                        } catch (e) {
                            console.error('[Eclipse Wildcard] graphToPrompt wildcard processing error:', e);
                        }
                    }
                }
            const i = await e.apply(this, arguments);
            for (const e of t)
                if ('Wildcard Processor [Eclipse]' === e.type && e._Eclipse_seedWidget) {
                    if (2 === e.mode || 4 === e.mode) continue;
                    const t = String(e.id);
                    if (i.output && i.output[t]) {
                        const s = e._Eclipse_seedWidget,
                            d = e.inputs?.find((e) => 'seed' === e.widget?.name);
                        let n;
                        if (d && null != d.link) n = s.value;
                        else if (
                            ((n =
                                e.getSeedToUse && 'function' == typeof e.getSeedToUse
                                    ? e.getSeedToUse()
                                    : e._Eclipse_seedWidget.value),
                            i.output[t].inputs && void 0 !== i.output[t].inputs.seed && (i.output[t].inputs.seed = n),
                            (e._Eclipse_lastSeed = n),
                            (e._Eclipse_cachedInputSeed = null),
                            (e._Eclipse_cachedResolvedSeed = null),
                            e._Eclipse_lastSeedButton)
                        ) {
                            const t = e._Eclipse_seedWidget.value;
                            (SPECIAL_SEEDS.includes(t)
                                ? ((e._Eclipse_lastSeedButton.name = `♻️ ${n}`),
                                  (e._Eclipse_lastSeedButton.disabled = !1))
                                : ((e._Eclipse_lastSeedButton.name = LAST_SEED_BUTTON_LABEL),
                                  (e._Eclipse_lastSeedButton.disabled = !0)),
                                notifyVue(e));
                        }
                        if (i.workflow && i.workflow.nodes) {
                            const t = i.workflow.nodes.find((t) => t.id === e.id);
                            if (t && t.widgets_values) {
                                e.widgets?.find((e) => 'mode' === e.name);
                                const i = e.widgets?.find((e) => 'seed' === e.name),
                                    s = e.widgets?.find((e) => 'populated_text' === e.name),
                                    d = e.widgets.indexOf(i),
                                    a = e.widgets.indexOf(s);
                                (d >= 0 && (t.widgets_values[d] = n), a >= 0 && s && (t.widgets_values[a] = s.value));
                            }
                        }
                    }
                }
            return i;
        };
    },
    async beforeRegisterNodeDef(e, t, i) {
        if ('Wildcard Processor [Eclipse]' !== t.name && 'Wildcard Processor [Eclipse]' !== t.class_type) return;
        ((e.prototype.generateRandomSeed = function () {
            const e = this._Eclipse_seedWidget?.options?.step || 1,
                t = this._Eclipse_randomMin || 0,
                i = ((this._Eclipse_randomMax || 0x4000000000000) - t) / (e / 10);
            let s = Math.floor(Math.random() * i) * (e / 10) + t;
            return (SPECIAL_SEEDS.includes(s) && (s = 0), s);
        }),
            (e.prototype.getSeedToUse = function () {
                const e = Number(this._Eclipse_seedWidget.value);
                if (this._Eclipse_cachedInputSeed === e && null != this._Eclipse_cachedResolvedSeed)
                    return this._Eclipse_cachedResolvedSeed;
                let t = null;
                SPECIAL_SEEDS.includes(e) &&
                    ('number' != typeof this._Eclipse_lastSeed ||
                        SPECIAL_SEEDS.includes(this._Eclipse_lastSeed) ||
                        (-2 === e ? (t = this._Eclipse_lastSeed + 1) : -3 === e && (t = this._Eclipse_lastSeed - 1)),
                    (null == t || SPECIAL_SEEDS.includes(t)) && (t = this.generateRandomSeed()));
                const i = null != t ? t : e;
                return ((this._Eclipse_cachedInputSeed = e), (this._Eclipse_cachedResolvedSeed = i), i);
            }));
        const s = e.prototype.onExecuted;
        ((e.prototype.onExecuted = function (e) {
            const t = s ? s.apply(this, arguments) : void 0;
            if (e && e.text && e.text.length > 0) {
                const t = this.widgets?.find((e) => 'mode' === e.name),
                    i = t?.value || 'populate',
                    s = this.widgets?.find((e) => 'populated_text' === e.name);
                s && 'populate' === i && (s.value = e.text[0]);
            }
            return (e && void 0 !== e.seed && (this._Eclipse_lastSeed = Array.isArray(e.seed) ? e.seed[0] : e.seed), t);
        }),
            (e.prototype.isSeedConnected = function () {
                const e = this.inputs?.find((e) => 'seed' === e.widget?.name);
                return e && null != e.link;
            }),
            (e.prototype.updateSeedButtonStates = function () {
                const e = this.widgets?.find((e) => 'mode' === e.name),
                    t = e?.value || 'populate',
                    i = this.isSeedConnected();
                if ('populate' !== t || i)
                    (this._Eclipse_randomizeButton && (this._Eclipse_randomizeButton.disabled = !0),
                        this._Eclipse_newRandomButton && (this._Eclipse_newRandomButton.disabled = !0),
                        this._Eclipse_lastSeedButton && (this._Eclipse_lastSeedButton.disabled = !0));
                else if (
                    (this._Eclipse_randomizeButton && (this._Eclipse_randomizeButton.disabled = !1),
                    this._Eclipse_newRandomButton && (this._Eclipse_newRandomButton.disabled = !1),
                    this._Eclipse_lastSeedButton && null != this._Eclipse_lastSeed)
                ) {
                    const e = this._Eclipse_seedWidget?.value;
                    this._Eclipse_lastSeedButton.disabled = !SPECIAL_SEEDS.includes(e);
                }
                notifyVue(this);
            }));
        const d = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            ((this._isInitializing = !0), d && d.call(this));
            const e = this;
            let t = null,
                i = -1;
            for (let e = 0; e < this.widgets.length; e++) {
                const s = this.widgets[e],
                    d = (s.name || '').toString().toLowerCase();
                'seed' === d ? (t = s) : 'control_after_generate' === d && (i = e);
            }
            if (
                (i >= 0 && this.widgets.splice(i, 1),
                t ||
                    console.warn(
                        '[Eclipse Wildcard] Seed widget not found! Available widgets:',
                        this.widgets.map((e) => e.name),
                    ),
                t)
            ) {
                ((this._Eclipse_seedWidget = t),
                    (this._Eclipse_lastSeed = void 0),
                    (this._Eclipse_randomMin = 0),
                    (this._Eclipse_randomMax = 0x4000000000000),
                    (this._Eclipse_cachedInputSeed = null),
                    (this._Eclipse_cachedResolvedSeed = null),
                    t.type && (t.type = 'number'),
                    (t.hidden = !1),
                    t.options && (t.options.hidden = !1));
                (t.callback, this.widgets.indexOf(t));
                const e = this.addWidget(
                        'button',
                        '🎲 Randomize Each Time',
                        '',
                        () => {
                            ((t.value = -1), t.callback && t.callback(-1));
                        },
                        { serialize: !1 },
                    ),
                    i = this.addWidget(
                        'button',
                        '🎲 New Fixed Random',
                        '',
                        () => {
                            const e = this.generateRandomSeed();
                            ((t.value = e), t.callback && t.callback(e));
                        },
                        { serialize: !1 },
                    ),
                    s = this.addWidget(
                        'button',
                        LAST_SEED_BUTTON_LABEL,
                        '',
                        () => {
                            null != this._Eclipse_lastSeed &&
                                ((t.value = this._Eclipse_lastSeed),
                                (s.name = LAST_SEED_BUTTON_LABEL),
                                (s.disabled = !0),
                                notifyVue(this));
                        },
                        { serialize: !1 },
                    );
                ((s.disabled = !0),
                    (this._Eclipse_lastSeedButton = s),
                    (this._Eclipse_randomizeButton = e),
                    (this._Eclipse_newRandomButton = i));
                const d = this.widgets?.find((e) => 'wildcards' === e.name),
                    n = this.widgets?.find((e) => 'mode' === e.name),
                    a = n ? this.widgets.indexOf(n) : -1;
                if (d && a >= 0) {
                    const e = this.widgets.indexOf(d);
                    e !== a + 1 && (this.widgets.splice(e, 1), this.widgets.splice(a + 1, 0, d));
                }
                const l = [e, i, s];
                for (let e = l.length - 1; e >= 0; e--) {
                    const i = l[e],
                        s = this.widgets.indexOf(i),
                        d = this.widgets.indexOf(t);
                    s !== d + 1 && (this.widgets.splice(s, 1), this.widgets.splice(d + 1, 0, i));
                }
                const o = {
                    type: 'SPACER',
                    name: 'spacer',
                    computeSize: () => [0, 8],
                    draw: () => {},
                    mouse: () => {},
                    serialize: !1,
                };
                this.widgets.push(o);
            }
            const s = this.onResize;
            this.onResize = function (e) {
                if (((e[0] = Math.max(e[0], 200)), (e[1] = Math.max(e[1], 100)), s)) return s.apply(this, [e]);
            };
            const n = this.size;
            n[0] >= 259 && (this.size = [200, n[1]]);
            const a = this.widgets?.find((e) => 'wildcard_text' === e.name),
                l = this.widgets?.find((e) => 'populated_text' === e.name),
                o = this.widgets?.find((e) => 'mode' === e.name),
                c = this.widgets?.find((e) => 'wildcards' === e.name);
            if (t) {
                const i = t.callback;
                t.callback = (s) => {
                    if (
                        ((e._Eclipse_cachedInputSeed = null),
                        (e._Eclipse_cachedResolvedSeed = null),
                        i && i.call(t, s),
                        !e._isInitializing && 'populate' === o?.value && a?.value && l)
                    ) {
                        const t = e.getSeedToUse();
                        updatePopulatedText(l, a.value, t);
                    }
                };
            }
            if (a && l) {
                const i = a.callback;
                a.callback = function (s) {
                    try {
                        if ((i && i.call(this, s), e._isInitializing)) return;
                        const d = new Error().stack;
                        if (d && d.includes('serializeValue')) return;
                        if ('populate' === o?.value && s && t) {
                            const t = e.getSeedToUse();
                            updatePopulatedText(l, s, t);
                        }
                    } catch (e) {
                        console.error('[Eclipse Wildcard] Error in wildcard_text callback:', e);
                    }
                };
            }
            if (o) {
                const i = o.callback;
                o.callback = function (s) {
                    try {
                        if ((i && i.call(this, s), e._isInitializing)) return;
                        ('populate' === s
                            ? (a &&
                                  l &&
                                  t &&
                                  ((l.disabled = !0),
                                  l.element &&
                                      ((l.element.style.opacity = '0.85'),
                                      (l.element.style.cursor = 'not-allowed'),
                                      (l.element.title =
                                          'Auto-generated in populate mode. Change seed to generate new output, fix seed to keep same output.'))),
                              e.updateSeedButtonStates())
                            : 'fixed' === s &&
                              (l &&
                                  ((e._Eclipse_cachedInputSeed = void 0),
                                  (e._Eclipse_cachedResolvedSeed = void 0),
                                  (l.disabled = !1),
                                  l.element &&
                                      ((l.element.style.opacity = '1.0'),
                                      (l.element.style.cursor = 'text'),
                                      (l.element.title = 'Edit to customize the output'))),
                              e.updateSeedButtonStates()),
                            updateUIForMode(e, s));
                    } catch (e) {
                        console.error('[Eclipse Wildcard] Error in mode callback:', e);
                    }
                };
            }
            if (c) {
                const t = c.draw;
                t &&
                    (c.draw = function (e, i, s, d, n) {
                        return (updateWildcardCombo(this), t.call(this, e, i, s, d, n));
                    });
                const i = c.callback;
                ((c.callback = function (t) {
                    if ((i && i.call(this, t), t && 'Select a Wildcard' !== t)) {
                        const i = e.widgets?.find((e) => 'wildcard_text' === e.name);
                        if (i) {
                            let e = i.value || '',
                                s = '';
                            if (e) {
                                const t = e.trimEnd();
                                t && !t.endsWith(',') ? (s = ', ') : t.endsWith(',') && (s = ' ');
                            }
                            ((i.value = e + s + t),
                                (i.value = i.value.replace(/\.,\s+/g, ', ')),
                                (i.value = i.value.replace(/\s+/g, ' ').trim()),
                                i.callback && i.callback(i.value));
                        }
                        setTimeout(() => {
                            c.value = 'Select a Wildcard';
                        }, 10);
                    }
                }),
                    updateWildcardCombo(c));
            }
            setTimeout(() => {
                if (((this._isInitializing = !1), o && l)) {
                    const t = o.value;
                    ('populate' === t &&
                        ((l.disabled = !0),
                        l.element &&
                            ((l.element.style.opacity = '0.85'),
                            (l.element.style.cursor = 'not-allowed'),
                            (l.element.title =
                                'Auto-generated in populate mode. Change seed to generate new output, fix seed to keep same output.')),
                        e.updateSeedButtonStates()),
                        updateUIForMode(e, t));
                }
            }, 0);
            const r = this.onConnectionsChange;
            this.onConnectionsChange = function (e, t, i, s) {
                if ((r && r.apply(this, arguments), 1 === e)) {
                    const e = this.inputs?.[t];
                    e && e.widget && 'seed' === e.widget.name && this.updateSeedButtonStates();
                }
            };
        };
    },
    async nodeCreated(e, t) {
        if ('Wildcard Processor [Eclipse]' !== e.type) return;
        (e.widgets?.find((e) => 'mode' === e.name),
            e.widgets?.find((e) => 'populated_text' === e.name),
            e.widgets?.find((e) => 'wildcard_text' === e.name));
        const i = e.widgets?.find((e) => 'wildcards' === e.name);
        i && updateWildcardCombo(i);
    },
    async loadedGraphNode(e, t) {
        if ('Wildcard Processor [Eclipse]' !== e.type) return;
        e.widgets?.find((e) => 'mode' === e.name);
        const i = e.widgets?.find((e) => 'populated_text' === e.name),
            s = (e.widgets?.find((e) => 'wildcard_text' === e.name), e.widgets?.find((e) => 'wildcards' === e.name));
        (s && updateWildcardCombo(s),
            setTimeout(() => {
                if (((e._isInitializing = !1), i)) {
                    const t = i.value;
                    (i.callback && i.callback(t),
                        i.element ? (i.element.value = t) : e.onResize && e.onResize(e.size),
                        i.options && (i.options.property = 'populated_text'));
                }
                (e.updateSeedButtonStates && e.updateSeedButtonStates(), e.setDirtyCanvas && e.setDirtyCanvas(!0, !0));
            }, 100));
    },
}),
    setInterval(async () => {
        try {
            const e = await fetch('/eclipse/wildcards/list');
            if (e.ok) {
                const t = await e.json();
                if (JSON.stringify(t) !== JSON.stringify(wildcardList)) {
                    wildcardList = t;
                    for (const e in app.graph._nodes) {
                        const t = app.graph._nodes[e];
                        if ('Wildcard Processor [Eclipse]' === t.type) {
                            const e = t.widgets?.find((e) => 'wildcards' === e.name);
                            e && updateWildcardCombo(e);
                        }
                    }
                }
            }
        } catch (e) {}
    }, 5e3));
