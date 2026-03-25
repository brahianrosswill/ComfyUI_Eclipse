import { app } from './comfy/index.js';
import { patchNodeCSSSize } from './eclipse-widget-performance-utils.js';
app.registerExtension({
    name: 'Eclipse.DynamicInputs',
    async beforeRegisterNodeDef(t, e, i) {
        if (!e?.name) return;
        const n = {
            RvConversion_ConcatMulti: { type: 'PIPE', prefix: 'pipe' },
            'Concat Pipe Multi [Eclipse]': { type: 'PIPE', prefix: 'pipe' },
            RvRouter_Any_MultiSwitch: { type: '*', prefix: 'any' },
            'Any Multi-Switch [Eclipse]': { type: '*', prefix: 'any' },
            RvRouter_Any_MultiSwitch_purge: { type: '*', prefix: 'any' },
            'Any Multi-Switch Purge [Eclipse]': { type: '*', prefix: 'any' },
            RvConversion_MergeStrings: { type: 'STRING', prefix: 'string' },
            'Merge Strings [Eclipse]': { type: 'STRING', prefix: 'string' },
            RvConversion_Join: { type: '*', prefix: 'input' },
            'Join [Eclipse]': { type: '*', prefix: 'input' },
        }[e.name && e.name.includes('/') ? e.name.split('/').pop() : e.name];
        n &&
            (t.prototype.onNodeCreated = function () {
                const t = this,
                    e = '*' === n.type,
                    s = (t, e) => `${t}_${e}`,
                    p = () => {
                        if (!e) return;
                        const s = n.prefix || 'any',
                            p = t.onConnectionsChange;
                        t.onConnectionsChange = function (t, e, n, a) {
                            if ((p && p.apply(this, arguments), !a || !this.inputs || !this.outputs)) return;
                            const o = this.inputs[e];
                            if (o && o.name && o.name.startsWith(s + '_')) {
                                if (n && t === LiteGraph.INPUT) {
                                    const t = i.graph.getNodeById(a.origin_id);
                                    if (!t || !t.outputs?.[a.origin_slot]) return;
                                    const e = t.outputs[a.origin_slot].type,
                                        n = LGraphCanvas.link_type_colors[e];
                                    ((o.type = e),
                                        a.id && (i.graph.links[a.id].color = n),
                                        this.inputs.forEach((t) => {
                                            t.name && t.name.startsWith(s + '_') && t !== o && (t.type = e);
                                        }),
                                        this.outputs[0] && ((this.outputs[0].type = e), (this.outputs[0].name = e)));
                                } else if (!n && t === LiteGraph.INPUT) {
                                    const t = this.inputs.filter(
                                        (t) => t.name && t.name.startsWith(s + '_') && null !== t.link,
                                    );
                                    if (t.length > 0) {
                                        const e = t[0].type;
                                        (this.inputs.forEach((t) => {
                                            t.name && t.name.startsWith(s + '_') && (t.type = e);
                                        }),
                                            this.outputs[0] &&
                                                ((this.outputs[0].type = e), (this.outputs[0].name = e)));
                                    } else
                                        (this.inputs.forEach((t) => {
                                            t.name && t.name.startsWith(s + '_') && (t.type = '*');
                                        }),
                                            this.outputs[0] &&
                                                ((this.outputs[0].type = '*'), (this.outputs[0].name = '')));
                                }
                                this.computeSize?.();
                            }
                        };
                    };
                e && p();
                const a = () => {
                    t.inputs || (t.inputs = []);
                    const p = t.widgets ? t.widgets.find((t) => 'inputcount' === t.name) : null,
                        a = p ? p.value : 2,
                        o = Math.max(2, a);
                    p && p.value < 2 && (p.value = 2);
                    const r = n.prefix || ('string' == typeof n.type ? n.type.toLowerCase() : 'input'),
                        u = new Set(t.inputs.filter((t) => 'string' == typeof t.name).map((t) => t.name)),
                        c = new Set((t.widgets || []).map((t) => t.name).filter((t) => 'string' == typeof t)),
                        h = new Set([...u, ...c].filter((t) => t.startsWith(r + '_')));
                    if (h.size === o) {
                        let p = n.type;
                        if (e && t.inputs && t.inputs.length > 0) {
                            const e = t.inputs.find((t) => t.name && t.name.startsWith(r + '_') && '*' !== t.type);
                            if (e) p = e.type;
                            else {
                                const e = t.inputs.find((t) => t.name && t.name.startsWith(r + '_') && null !== t.link);
                                if (e) {
                                    const t = i.graph.links[e.link];
                                    t && (p = t.type);
                                }
                            }
                        }
                        for (let e = 1; e <= o; ++e) {
                            const i = s(r, e);
                            c.has(i) && !u.has(i) && t.addInput(i, p, void 0 !== n.shape ? { shape: n.shape } : void 0);
                        }
                        return void setTimeout(() => {
                            t.setDirtyCanvas(!0, !1);
                            const e = t.computeSize(),
                                i = t.size;
                            let n = Math.max(i[0], 200),
                                s = Math.max(e[1] + 5, 50);
                            const p = Math.abs(i[1] - s);
                            ((s > i[1] || p > 10) && (t.setSize([n, s]), patchNodeCSSSize(t)),
                                t.setDirtyCanvas(!0, !0));
                        }, 50);
                    }
                    if (h.size > o) {
                        const e = Array.from(h)
                            .map((t) => {
                                const e = t.match(new RegExp(r + '_(\\d+)$'));
                                return e ? parseInt(e[1], 10) : null;
                            })
                            .filter(Boolean)
                            .sort((t, e) => e - t);
                        for (const i of e) {
                            if (h.size <= o) break;
                            const e = s(r, i),
                                n = t.inputs.findIndex((t) => t.name === e);
                            if ((-1 !== n && t.removeInput(n), t.widgets)) {
                                const i = t.widgets.findIndex((t) => t.name === e);
                                -1 !== i && t.widgets.splice(i, 1);
                            }
                            h.delete(e);
                        }
                        return void setTimeout(() => {
                            t.setDirtyCanvas(!0, !1);
                            const e = t.computeSize(),
                                i = t.size;
                            let n = Math.max(i[0], 200),
                                s = Math.max(e[1] + 5, 50);
                            const p = Math.abs(i[1] - s);
                            ((s > i[1] || p > 10) && (t.setSize([n, s]), patchNodeCSSSize(t)),
                                t.setDirtyCanvas(!0, !0));
                        }, 50);
                    }
                    let l = n.type;
                    if (e && t.inputs && t.inputs.length > 0) {
                        const e = t.inputs.find((t) => t.name && t.name.startsWith(r + '_') && '*' !== t.type);
                        if (e) l = e.type;
                        else {
                            const e = t.inputs.find((t) => t.name && t.name.startsWith(r + '_') && null !== t.link);
                            if (e) {
                                const t = i.graph.links[e.link];
                                t && (l = t.type);
                            }
                        }
                    }
                    for (let e = 1; e <= o; ++e) {
                        const i = s(r, e);
                        h.has(i) || (t.addInput(i, l, void 0 !== n.shape ? { shape: n.shape } : void 0), h.add(i));
                    }
                    setTimeout(() => {
                        t.setDirtyCanvas(!0, !1);
                        const e = t.computeSize(),
                            i = t.size;
                        let n = Math.max(i[0], 200),
                            s = Math.max(e[1] + 5, 50);
                        const p = Math.abs(i[1] - s);
                        ((s > i[1] || p > 10) && (t.setSize([n, s]), patchNodeCSSSize(t)), t.setDirtyCanvas(!0, !0));
                    }, 50);
                };
                setTimeout(() => {
                    try {
                        a();
                    } catch (t) {}
                }, 80);
                const r = t.widgets?.find((t) => 'inputcount' === t.name);
                if (r) {
                    let o = r.value;
                    const u = r.callback;
                    r.callback = function () {
                        u && u.apply(this, arguments);
                        if (r.value !== o) { o = r.value; a(); }
                    };
                }
            });
    },
});
