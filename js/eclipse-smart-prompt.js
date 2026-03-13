/* eclipse-smart-prompt.js - Minified for ComfyUI Eclipse */
import { app } from './comfy/index.js';
import {
    debounce,
    canvasDirtyBatcher,
    notifyVue,
    createWidgetVisibilityManager,
    smartResize,
} from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'Smart Prompt [Eclipse]',
    LAST_SEED_BUTTON_LABEL = '♻️ (Use Last Queued Seed)',
    SPECIAL_SEED_RANDOM = -1,
    SPECIAL_SEED_INCREMENT = -2,
    SPECIAL_SEED_DECREMENT = -3,
    SPECIAL_SEEDS = [-1, -2, -3];
app.registerExtension({
    name: 'Eclipse.SmartPrompt',
    async setup() {
        const e = app.graphToPrompt;
        app.graphToPrompt = async function () {
            const t = await e.apply(this, arguments),
                i = app.graph._nodes;
            for (const e of i)
                if (e.type === NODE_NAME && e._Eclipse_seedWidget) {
                    if (2 === e.mode || 4 === e.mode) continue;
                    const i = String(e.id);
                    if (t.output && t.output[i]) {
                        const s = e.getSeedToUse();
                        if (null === s) continue;
                        if (t.output[i].inputs && void 0 !== t.output[i].inputs.seed) {
                            const e = t.output[i].inputs.seed;
                            Number(e) !== Number(s) && (t.output[i].inputs.seed = s);
                        }
                        if (
                            (Number(e._Eclipse_lastSeed) !== Number(s) && (e._Eclipse_lastSeed = s),
                            (e._Eclipse_cachedInputSeed = null),
                            (e._Eclipse_cachedResolvedSeed = null),
                            e._Eclipse_lastSeedButton)
                        ) {
                            const t = e._Eclipse_seedWidget.value;
                            (SPECIAL_SEEDS.includes(t)
                                ? ((e._Eclipse_lastSeedButton.name = `♻️ ${s}`),
                                  (e._Eclipse_lastSeedButton.disabled = !1))
                                : ((e._Eclipse_lastSeedButton.name = LAST_SEED_BUTTON_LABEL),
                                  (e._Eclipse_lastSeedButton.disabled = !0)),
                                notifyVue(e));
                        }
                        if (t.workflow && t.workflow.nodes) {
                            const i = t.workflow.nodes.find((t) => t.id === e.id);
                            if (i && i.widgets_values) {
                                const t = e.widgets.indexOf(e._Eclipse_seedWidget);
                                t >= 0 && i.widgets_values[t] !== s && (i.widgets_values[t] = s);
                            }
                        }
                    }
                }
            return t;
        };
    },
    async beforeRegisterNodeDef(e, t, i) {
        if (t.name !== NODE_NAME) return;
        ((e.prototype.generateRandomSeed = function () {
            const e = this._Eclipse_seedWidget?.options?.step || 1,
                t = this._Eclipse_randomMin || 0,
                i = ((this._Eclipse_randomMax || 0xFFFFFFFF) - t) / (e / 10);
            let s = Math.floor(Math.random() * i) * (e / 10) + t;
            return (SPECIAL_SEEDS.includes(s) && (s = 0), s);
        }),
            (e.prototype.getSeedToUse = function () {
                const e = this.inputs?.find((e) => 'seed_input' === e.name);
                if (e && null != e.link) return null;
                const t = Number(this._Eclipse_seedWidget.value);
                if (this._Eclipse_cachedInputSeed === t && null != this._Eclipse_cachedResolvedSeed)
                    return this._Eclipse_cachedResolvedSeed;
                let i = null;
                SPECIAL_SEEDS.includes(t) &&
                    ('number' != typeof this._Eclipse_lastSeed ||
                        SPECIAL_SEEDS.includes(this._Eclipse_lastSeed) ||
                        (-2 === t ? (i = this._Eclipse_lastSeed + 1) : -3 === t && (i = this._Eclipse_lastSeed - 1)),
                    (null == i || SPECIAL_SEEDS.includes(i)) && (i = this.generateRandomSeed()));
                const s = null != i ? i : t;
                return ((this._Eclipse_cachedInputSeed = t), (this._Eclipse_cachedResolvedSeed = s), s);
            }));
        const s = e.prototype.onExecuted;
        e.prototype.onExecuted = function (e) {
            const t = s ? s.apply(this, arguments) : void 0;
            return (e && void 0 !== e.seed && (this._Eclipse_lastSeed = e.seed), t);
        };
        const n = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = n ? n.apply(this, arguments) : void 0,
                t = this;
            let s = null;
            for (const [e, t] of this.widgets.entries()) {
                const i = (t.name || '').toString().toLowerCase(),
                    n = (t.label || t.options?.label || t.options?.name || '').toString().toLowerCase(),
                    d = (t.localized_name || '').toString().toLowerCase();
                'seed' === i || 'seed' === n || 'seed' === d
                    ? (s = t)
                    : 'control_after_generate' === i && this.widgets.splice(e, 1);
            }
            if (s) {
                ((this._Eclipse_seedWidget = s),
                    (this._Eclipse_lastSeed = void 0),
                    (this._Eclipse_randomMin = 0),
                    (this._Eclipse_randomMax = Number.MAX_SAFE_INTEGER),
                    (this._Eclipse_cachedInputSeed = null),
                    (this._Eclipse_cachedResolvedSeed = null));
                const e = s.callback;
                s.callback = (t) => {
                    if (((this._Eclipse_cachedInputSeed = null), (this._Eclipse_cachedResolvedSeed = null), e))
                        return e.call(s, t);
                };
                const i = this.widgets.indexOf(s),
                    n = this.addWidget(
                        'button',
                        '🎲 Randomize Each Time',
                        '',
                        () => {
                            ((s.value = -1), s.callback && s.callback(-1));
                        },
                        { serialize: !1 },
                    ),
                    d = this.addWidget(
                        'button',
                        '🎲 New Fixed Random',
                        '',
                        () => {
                            const e = this.generateRandomSeed();
                            ((s.value = e), s.callback && s.callback(e));
                        },
                        { serialize: !1 },
                    ),
                    o = this.addWidget(
                        'button',
                        LAST_SEED_BUTTON_LABEL,
                        '',
                        () => {
                            null != this._Eclipse_lastSeed &&
                                ((s.value = this._Eclipse_lastSeed),
                                (o.name = LAST_SEED_BUTTON_LABEL),
                                (o.disabled = !0),
                                notifyVue(this));
                        },
                        { serialize: !1 },
                    );
                ((o.disabled = !0),
                    (this._Eclipse_lastSeedButton = o),
                    (this._Eclipse_randomizeButton = n),
                    (this._Eclipse_newRandomButton = d));
                const l = [n, d, o];
                for (let e = l.length - 1; e >= 0; e--) {
                    const t = l[e],
                        s = this.widgets.indexOf(t);
                    s !== i + 1 && (this.widgets.splice(s, 1), this.widgets.splice(i + 1, 0, t));
                }
                const a = () => {
                    if (-1 === t.id) return;
                    const e = t.inputs?.find((e) => 'seed_input' === e.name),
                        i = e && null != e.link;
                    t._Eclipse_lastSeedInputConnected !== i &&
                        ((t._Eclipse_lastSeedInputConnected = i),
                        i
                            ? ((s.hidden = !0),
                              s.options && (s.options.hidden = !0),
                              (n.hidden = !0),
                              n.options && (n.options.hidden = !0),
                              (d.hidden = !0),
                              d.options && (d.options.hidden = !0),
                              (o.hidden = !0),
                              o.options && (o.options.hidden = !0))
                            : ((s.hidden = !1),
                              s.options && (s.options.hidden = !1),
                              (n.hidden = !1),
                              n.options && (n.options.hidden = !1),
                              (d.hidden = !1),
                              d.options && (d.options.hidden = !1),
                              (o.hidden = !1),
                              o.options && (o.options.hidden = !1)),
                        notifyVue(t),
                        canvasDirtyBatcher.markDirty(t, !0, !0));
                };
                (a(), (t._Eclipse_updateSeedInputState = a));
            } else
                console.warn(
                    '[Eclipse-SmartPrompt] Could not find Seed widget. Widgets:',
                    this.widgets.map((e) => ({ name: e.name, label: e.label })),
                );
            const d = createWidgetVisibilityManager(t),
                o = async () => {
                    if (-1 === t.id) return;
                    const e = d.getValue('folder');
                    t._Eclipse_lastSelectedFolder !== e &&
                        ((t._Eclipse_lastSelectedFolder = e),
                        d.setVisible('folder', !0),
                        t.widgets?.forEach((i) => {
                            if ('folder' === i.name || 'seed' === i.name) return;
                            if ('button' === i.type) return;
                            if (
                                i === t._Eclipse_randomizeButton ||
                                i === t._Eclipse_newRandomButton ||
                                i === t._Eclipse_lastSeedButton
                            )
                                return;
                            const s = i.name.split(' ')[0],
                                n = 'All' === e || s === e;
                            d.setVisible(i.name, n);
                        }),
                        smartResize(t, { minWidth: 0, minHeight: 50, padding: 0 }));
                },
                l = debounce(o, 200);
            if (t._Eclipse_updateSeedInputState) {
                const e = t._Eclipse_updateSeedInputState,
                    i = debounce(() => {
                        (e(), o());
                    }, 150),
                    s = t.onConnectionsChange;
                t.onConnectionsChange = function (e, t, n, d) {
                    s && s.apply(this, arguments);
                    const o = this.inputs?.find((e) => 'seed_input' === e.name);
                    o && i();
                };
            }
            const a = t.widgets?.find((e) => 'folder' === e.name);
            if (a) {
                const e = a.callback;
                a.callback = async function () {
                    (e && e.apply(this, arguments), await l());
                };
            }
            if (
                (t.widgets?.forEach((e) => {
                    if ('folder' !== e.name && 'seed' !== e.name && 'button' !== e.type) {
                        const t = e.name.split(' ');
                        t.length > 1 && (e.label = t.slice(1).join(' '));
                    }
                }),
                i.canvas)
            ) {
                const e = 250,
                    i = t.computeSize.bind(t);
                t.computeSize = function () {
                    const t = i();
                    return (t[0] > e && (t[0] = e), t);
                };
            }
            setTimeout(() => {
                t._Eclipse_initialized ||
                    t._Eclipse_initialized ||
                    ((t._Eclipse_initialized = !0),
                    t._Eclipse_updateSeedInputState && t._Eclipse_updateSeedInputState(),
                    o());
            }, 50);
            const c = t.onConfigure;
            return (
                (t.onConfigure = function (e) {
                    (c && c.apply(this, arguments),
                        (t._Eclipse_initialized = !0),
                        setTimeout(() => {
                            ((t._Eclipse_lastSeedInputConnected = void 0),
                                t._Eclipse_updateSeedInputState && t._Eclipse_updateSeedInputState(),
                                o());
                        }, 100));
                }),
                e
            );
        };
    },
});
