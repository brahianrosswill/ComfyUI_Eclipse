/* eclipse-mode-nodes.js - Minified for ComfyUI Eclipse */
import { app } from './comfy/index.js';
import { smartResize, notifyVue, batchedNotifyVue } from './eclipse-widget-performance-utils.js';
const MODE_ALWAYS = 0,
    MODE_MUTE = 2,
    MODE_BYPASS = 4;
let _collapseStyle = null;
const _collapsedNodeIds = new Set();
function _updateCollapseStyleSheet() {
    if (
        (_collapseStyle ||
            ((_collapseStyle = document.createElement('style')),
            (_collapseStyle.id = 'eclipse-collapse-connections'),
            document.head.appendChild(_collapseStyle)),
        0 === _collapsedNodeIds.size)
    )
        return void (_collapseStyle.textContent = '');
    const e = [..._collapsedNodeIds].map((e) => `[data-node-id="${e}"] .lg-slot--input`).join(',\n');
    _collapseStyle.textContent = `${e} {\n        height: 0 !important;\n        min-height: 0 !important;\n        overflow: hidden !important;\n        margin: 0 !important;\n        padding: 0 !important;\n        pointer-events: none !important;\n    }`;
}
function setCollapseCSS(e, t) {
    if (null == e.id) return;
    const i = String(e.id);
    if (t) {
        if (_collapsedNodeIds.has(i)) return;
        _collapsedNodeIds.add(i);
    } else {
        if (!_collapsedNodeIds.has(i)) return;
        _collapsedNodeIds.delete(i);
    }
    _updateCollapseStyleSheet();
}
const NODE_NAMES = {
        FAST_MUTER: 'Fast Muter [Eclipse]',
        FAST_BYPASSER: 'Fast Bypasser [Eclipse]',
        FAST_GROUPS_MUTER: 'Fast Groups Muter [Eclipse]',
        FAST_GROUPS_BYPASSER: 'Fast Groups Bypasser [Eclipse]',
        NODE_MODE_REPEATER: 'Mute / Bypass Repeater [Eclipse]',
        NODE_COLLECTOR: 'Node Collector [Eclipse]',
    },
    ECLIPSE_MODE_TYPES = Object.values(NODE_NAMES),
    RGTHREE_COMPAT_TYPES = [
        'Fast Muter (rgthree)',
        'Fast Bypasser (rgthree)',
        'Fast Groups Muter (rgthree)',
        'Fast Groups Bypasser (rgthree)',
        'Mute / Bypass Repeater (rgthree)',
        'Node Collector (rgthree)',
        'Node Combiner (rgthree)',
        'Fast Actions Button (rgthree)',
        'Random Unmuter (rgthree)',
    ],
    REROUTE_TYPES = ['Reroute', 'Reroute (rgthree)'],
    COLLECTOR_TYPES = [NODE_NAMES.NODE_COLLECTOR, 'Node Collector (rgthree)', 'Node Combiner (rgthree)'],
    TOGGLER_TYPES = [
        NODE_NAMES.FAST_MUTER,
        NODE_NAMES.FAST_BYPASSER,
        'Fast Muter (rgthree)',
        'Fast Bypasser (rgthree)',
        'Fast Actions Button (rgthree)',
        'Random Unmuter (rgthree)',
    ];
function changeModeOfNodes(e, t) {
    const i = Array.isArray(e) ? e : [e];
    for (const e of i) e && void 0 !== e.mode && e.mode !== t && ((e.mode = t), notifyDownstreamModeChange(e));
}
function isReroute(e) {
    if (!e) return !1;
    const t = e.type || '';
    return REROUTE_TYPES.includes(t);
}
function isCollector(e) {
    if (!e) return !1;
    const t = e.type || '';
    return COLLECTOR_TYPES.includes(t);
}
function isPassThrough(e, t) {
    return !!isReroute(e) || (!t && isCollector(e));
}
function getLink(e, t) {
    return e && null != t
        ? e.links && 'function' == typeof e.links.get
            ? e.links.get(t) || null
            : e.links?.[t] || null
        : null;
}
function getConnectedInputNodes(e, t) {
    const i = [];
    if (!e || !e.inputs || !e.graph) return i;
    const o = t >= 0 ? [e.inputs[t]] : e.inputs;
    for (const t of o) {
        if (!t || null == t.link) continue;
        const o = getLink(e.graph, t.link);
        if (!o) continue;
        const s = e.graph.getNodeById(o.origin_id);
        s && i.push(s);
    }
    return i;
}
function getConnectedInputNodesFiltered(e, t, i) {
    const o = [];
    if (!e || !e.inputs || !e.graph) return o;
    const s = t >= 0 ? [e.inputs[t]] : e.inputs;
    for (const t of s) {
        if (!t || null == t.link) continue;
        const s = getLink(e.graph, t.link);
        if (!s) continue;
        const n = e.graph.getNodeById(s.origin_id);
        if (n)
            if (isPassThrough(n, i)) {
                const e = getConnectedInputNodesFiltered(n, -1, i);
                o.push(...e);
            } else o.push(n);
    }
    return o;
}
function getConnectedOutputNodes(e, t, i) {
    const o = [];
    if (!e || !e.graph) return o;
    const s = e.outputs || [];
    for (const n of s)
        if (n.links)
            for (const s of n.links) {
                const n = getLink(e.graph, s);
                if (!n) continue;
                const l = e.graph.getNodeById(n.target_id);
                if (l && (!i || l === i))
                    if (t && isPassThrough(l, !1)) {
                        const e = getConnectedOutputNodes(l, !0);
                        o.push(...e);
                    } else o.push(l);
            }
    return o;
}
function getGroupNodes(e, t) {
    if (!e) return [];
    !1 !== t && 'function' == typeof e.recomputeInsideNodes && e.recomputeInsideNodes();
    const i = e._nodes || [];
    return Array.from(i).filter((e) => e && void 0 !== e.mode);
}
function syncModeWidgets(e) {
    if (!e.graph || void 0 === e._eclipse_modeOn) return;
    const t = e._eclipse_modeOn,
        i = getConnectedInputNodesFiltered(e, -1, !1);
    let o = !1;
    for (let s = 0; s < i.length; s++) {
        const n = e.widgets?.[s];
        if (!n) continue;
        const l = i[s].mode === t;
        n.value !== l && ((n.value = l), (o = !0));
    }
    o && (notifyVue(e), e.setDirtyCanvas(!0, !1));
}
function requestSync(e) {
    e._eclipse_syncQueued ||
        ((e._eclipse_syncQueued = !0),
        requestAnimationFrame(() => {
            ((e._eclipse_syncQueued = !1), syncModeWidgets(e));
        }));
}
function notifyDownstreamModeChange(e) {
    if (!e?.graph) return;
    const t = e.outputs || [];
    for (const i of t)
        if (i.links)
            for (const t of i.links) {
                const i = getLink(e.graph, t);
                if (!i) continue;
                const o = e.graph.getNodeById(i.target_id);
                o && o._eclipse_onUpstreamModeChange && o._eclipse_onUpstreamModeChange();
            }
}
function hookModeProperty(e, t) {
    if (!e) return () => {};
    if (e._eclipse_modeHooks)
        return (
            e._eclipse_modeHooks.push(t),
            () => {
                const i = e._eclipse_modeHooks?.indexOf(t);
                i >= 0 && e._eclipse_modeHooks.splice(i, 1);
            }
        );
    e._eclipse_modeHooks = [t];
    const i = (e, t, i) => {
            const o = e._eclipse_modeHooks?.slice() || [];
            for (const s of o) s(e, t, i);
        },
        o = Object.getOwnPropertyDescriptor(e, 'mode');
    if (o && (o.get || o.set)) {
        const t = o.set,
            s = o.get;
        Object.defineProperty(e, 'mode', {
            get() {
                return s ? s.call(this) : o.value;
            },
            set(e) {
                const n = s ? s.call(this) : o.value;
                (t ? t.call(this, e) : (o.value = e), e !== n && i(this, n, e));
            },
            configurable: !0,
            enumerable: !1 !== o.enumerable,
        });
    } else {
        let t = o ? o.value : e.mode;
        Object.defineProperty(e, 'mode', {
            get: () => t,
            set(e) {
                const o = t;
                ((t = e), e !== o && i(this, o, e));
            },
            configurable: !0,
            enumerable: !0,
        });
    }
    return () => {
        const i = e._eclipse_modeHooks?.indexOf(t);
        i >= 0 && e._eclipse_modeHooks.splice(i, 1);
    };
}
function hookTitleProperty(e, t) {
    if (!e) return () => {};
    if (e._eclipse_titleHooks)
        return (
            e._eclipse_titleHooks.push(t),
            () => {
                const i = e._eclipse_titleHooks?.indexOf(t);
                i >= 0 && e._eclipse_titleHooks.splice(i, 1);
            }
        );
    e._eclipse_titleHooks = [t];
    const i = (e) => {
            const t = e._eclipse_titleHooks?.slice() || [];
            for (const i of t) i(e);
        },
        o = Object.getOwnPropertyDescriptor(e, 'title');
    if (o && (o.get || o.set)) {
        const t = o.set,
            s = o.get;
        Object.defineProperty(e, 'title', {
            get() {
                return s ? s.call(this) : o.value;
            },
            set(e) {
                const n = s ? s.call(this) : o.value;
                (t ? t.call(this, e) : (o.value = e), e !== n && i(this));
            },
            configurable: !0,
            enumerable: !1 !== o.enumerable,
        });
    } else {
        let t = o ? o.value : e.title;
        Object.defineProperty(e, 'title', {
            get: () => t,
            set(e) {
                const o = t;
                ((t = e), e !== o && i(this));
            },
            configurable: !0,
            enumerable: !0,
        });
    }
    return () => {
        const i = e._eclipse_titleHooks?.indexOf(t);
        i >= 0 && e._eclipse_titleHooks.splice(i, 1);
    };
}
function syncTitleHooks(e, t, i) {
    const o = e._eclipse_hookedTitles || (e._eclipse_hookedTitles = new Map()),
        s = new Set(t.map((e) => e.id));
    for (const [e, t] of o) s.has(e) || (t(), o.delete(e));
    for (const e of t)
        if (!o.has(e.id)) {
            const t = hookTitleProperty(e, i);
            o.set(e.id, t);
        }
}
function stabilizeInputs(e, t, i) {
    let o = !1;
    e.inputs || (e.inputs = []);
    for (const t of e.inputs) t && /^input_\d+$/i.test(t.name) && ((t.name = ' '), (o = !0));
    const s = !!e.properties?.collapse_connections,
        n = e.inputs[e.inputs.length - 1];
    n
        ? null != n.link
            ? s || (e.addInput(' ', '*'), (o = !0))
            : s && e.inputs.length > 1 && e.inputs.slice(0, -1).some((e) => null != e?.link)
              ? (e.removeInput(e.inputs.length - 1), (o = !0))
              : ' ' !== n.name && ((n.name = ' '), (o = !0))
        : (e.addInput(' ', '*'), (o = !0));
    for (let n = s ? e.inputs.length - 1 : e.inputs.length - 2; n >= 0; n--) {
        const s = e.inputs[n];
        if (s)
            if (null == s.link)
                e.inputs.length > 1 ? (e.removeInput(n), (o = !0)) : ' ' !== s.name && ((s.name = ' '), (o = !0));
            else if ('hide' === i) ' ' !== s.name && ((s.name = ' '), (o = !0));
            else if (t) {
                const t = getConnectedInputNodesFiltered(e, n, !1),
                    i = t[0]?.title || ' ';
                s.name !== i && ((s.name = i), (o = !0));
            } else {
                const t = getConnectedInputNodes(e, n),
                    i = t[0]?.title || ' ';
                s.name !== i && ((s.name = i), (o = !0));
            }
    }
    if ((setCollapseCSS(e, s), s)) {
        const t = 0.7 * (LiteGraph.NODE_SLOT_HEIGHT ?? 20);
        for (const i of e.inputs) (i.pos && i.pos[1] === t) || ((i.pos = [10, t]), (o = !0));
    } else for (const t of e.inputs) t.pos && (delete t.pos, (o = !0));
    for (const t of e.inputs) '_eclipseHide' === t.widget?.name && (delete t.widget, (o = !0));
    return o;
}
function scheduleStabilize(e, t, i, o) {
    (o && e._eclipse_stabilizeTimer && (clearTimeout(e._eclipse_stabilizeTimer), (e._eclipse_stabilizeTimer = null)),
        e._eclipse_stabilizeTimer ||
            (e._eclipse_stabilizeTimer = setTimeout(() => {
                ((e._eclipse_stabilizeTimer = null), e.graph && t.call(e));
            }, i || 100)));
}
function preserveWidth(e) {
    e._eclipse_tempWidth = e.size[0];
}
function blankInputNames(e) {
    if (e.inputs) for (const t of e.inputs) t && (/^input_\d+$/i.test(t.name) || '' === t.name) && (t.name = ' ');
}
function setupModeChanger(e, t, i, o) {
    ((e.prototype.isVirtualNode = !0),
        (e['@toggleRestriction'] = { type: 'combo', values: ['default', 'max one', 'always one'] }));
    const s = e.prototype.onNodeCreated;
    e.prototype.onNodeCreated = function () {
        const e = s?.apply(this, arguments);
        ((this.serialize_widgets = !0),
            (this.properties = this.properties || {}),
            void 0 === this.properties.toggleRestriction && (this.properties.toggleRestriction = 'default'),
            void 0 === this.properties.collapse_connections && (this.properties.collapse_connections = !1),
            this.outputs?.length || this.addOutput('oc', '*'),
            blankInputNames(this),
            (this._eclipse_modeOn = t),
            (this._eclipse_modeOff = i));
        const o = this;
        return (
            (this._eclipse_onUpstreamModeChange = function () {
                requestSync(o);
            }),
            (this._eclipse_hookedNodes = new Map()),
            scheduleStabilize(this, modeChangerStabilize, 100),
            e
        );
    };
    const n = e.prototype.configure;
    ((e.prototype.configure = function (e) {
        this._eclipse_configuring = !0;
        const o = n?.apply(this, arguments);
        return (
            (this._eclipse_configuring = !1),
            (this._eclipse_modeOn = t),
            (this._eclipse_modeOff = i),
            scheduleStabilize(this, modeChangerStabilize, 300, !0),
            o
        );
    }),
        (e.prototype.onConnectionsChange = function (e, t, i, o) {
            if (!o) return;
            const s = getConnectedOutputNodes(this, !0);
            for (const e of s) e._eclipse_onChainChange && e._eclipse_onChainChange();
            i
                ? (this._eclipse_stabilizeTimer &&
                      (clearTimeout(this._eclipse_stabilizeTimer), (this._eclipse_stabilizeTimer = null)),
                  modeChangerStabilize.call(this),
                  scheduleStabilize(this, modeChangerStabilize, 200, !0))
                : scheduleStabilize(this, modeChangerStabilize, 500, !0);
        }),
        (e.prototype._eclipse_onChainChange = function () {
            (this._eclipse_stabilizeTimer &&
                (clearTimeout(this._eclipse_stabilizeTimer), (this._eclipse_stabilizeTimer = null)),
                modeChangerStabilize.call(this));
        }),
        (e.prototype.onConnectOutput = function (e, t, i, o, s) {
            return !getConnectedInputNodes(this).includes(o);
        }),
        (e.prototype.onConnectInput = function (e, t, i, o, s) {
            return !getConnectedOutputNodes(this, !1).includes(o);
        }));
    const l = e.prototype.onRemoved;
    e.prototype.onRemoved = function () {
        if ((l?.apply(this, arguments), this._eclipse_hookedNodes)) {
            for (const e of this._eclipse_hookedNodes.values()) e();
            this._eclipse_hookedNodes.clear();
        }
        if (this._eclipse_hookedTitles) {
            for (const e of this._eclipse_hookedTitles.values()) e();
            this._eclipse_hookedTitles.clear();
        }
        (this._eclipse_stabilizeTimer &&
            (clearTimeout(this._eclipse_stabilizeTimer), (this._eclipse_stabilizeTimer = null)),
            setCollapseCSS(this, !1));
    };
    const r = e.prototype.onSerialize;
    ((e.prototype.onSerialize = function (e) {
        if ((r?.call(this, e), e?.inputs))
            for (const t of e.inputs) ('_eclipseHide' === t?.widget?.name && delete t.widget, delete t.pos);
    }),
        (e.prototype.computeSize = function (e) {
            let t = LGraphNode.prototype.computeSize.call(this, e);
            if (
                (this._eclipse_tempWidth &&
                    ((t[0] = Math.max(this._eclipse_tempWidth, t[0])),
                    clearTimeout(this._eclipse_widthTimer),
                    (this._eclipse_widthTimer = setTimeout(() => {
                        this._eclipse_tempWidth = null;
                    }, 32))),
                this.properties?.collapse_connections)
            ) {
                const e = LiteGraph.NODE_SLOT_HEIGHT ?? 20,
                    i = Math.max((this.inputs?.length || 0) - 1, 0);
                i > 0 && (t[1] = t[1] - i * e);
            }
            return t;
        }),
        (e.prototype.getExtraMenuOptions = function (e, t) {
            (t.push(null),
                t.push({
                    content: this.properties?.collapse_connections ? 'Show Connections' : 'Collapse Connections',
                    callback: () => {
                        ((this.properties.collapse_connections = !this.properties.collapse_connections),
                            scheduleStabilize(this, modeChangerStabilize, 0, !0));
                    },
                }),
                t.push(null));
            for (const e of o) t.push({ content: e, callback: () => this._eclipse_handleAction(e) });
            t.push(null);
            const i = this.properties?.toggleRestriction || 'default';
            for (const e of ['default', 'max one', 'always one'])
                t.push({
                    content: `${e === i ? '✓ ' : '  '}Restriction: ${e}`,
                    callback: () => {
                        ((this.properties.toggleRestriction = e), this.setDirtyCanvas(!0, !1));
                    },
                });
            return t;
        }),
        (e.prototype._eclipse_handleAction = function (e) {
            const t = 'always one' === this.properties?.toggleRestriction,
                i = this.widgets || [];
            if (e.startsWith('Enable')) {
                const e = (this.properties?.toggleRestriction || '').includes(' one');
                for (let t = 0; t < i.length; t++) i[t]._eclipse_doMode?.(!(e && t > 0), !0);
            } else if (e.startsWith('Mute') || e.startsWith('Bypass'))
                for (let e = 0; e < i.length; e++) i[e]._eclipse_doMode?.(t && 0 === e, !0);
            else if (e.startsWith('Toggle')) {
                const e = (this.properties?.toggleRestriction || '').includes(' one');
                let o = !1;
                for (const t of i) {
                    let i = (!e || !o) && !t.value;
                    ((o = o || i), t._eclipse_doMode?.(i, !0));
                }
                !o && t && i.length && i[i.length - 1]._eclipse_doMode?.(!0, !0);
            }
            (notifyVue(this), this.setDirtyCanvas(!0, !1));
        }));
}
function modeChangerStabilize() {
    if (!this.graph) return;
    preserveWidth(this);
    let e = stabilizeInputs(this, !0, 'hide');
    const t = getConnectedInputNodesFiltered(this, -1, !1),
        i = this._eclipse_modeOn,
        o = this._eclipse_modeOff;
    for (let s = 0; s < t.length; s++) {
        const n = t[s];
        if (!n) continue;
        let l = this.widgets?.[s];
        const r = n.title;
        let c = !1;
        if (
            (l
                ? l.name !== r &&
                  ((l.name = r),
                  (l.options = { on: 'yes', off: 'no' }),
                  l._state && (l._state.name = r),
                  'function' == typeof l.setNodeId && l.setNodeId(this.id),
                  (c = !0),
                  (e = !0))
                : (preserveWidth(this),
                  (l = this.addWidget('toggle', r, n.mode === i, () => {}, { on: 'yes', off: 'no' })),
                  (c = !0),
                  (e = !0)),
            c)
        ) {
            const e = this,
                t = n,
                s = l;
            ((s._eclipse_doMode = function (n, l) {
                let r = null != n ? n : t.mode === o;
                if (!0 !== l) {
                    const t = e.properties?.toggleRestriction || 'default';
                    if (r && t.includes(' one'))
                        for (const t of e.widgets || []) t._eclipse_doMode && t._eclipse_doMode(!1, !0);
                    else r || 'always one' !== t || (r = (e.widgets || []).every((e) => !e.value || e === s));
                }
                (changeModeOfNodes(t, r ? i : o), (s.value = r));
            }),
                (s.callback = () => s._eclipse_doMode()));
        }
        const p = n.mode === i;
        l.value !== p && ((l.value = p), (e = !0));
    }
    for (; this.widgets && this.widgets.length > t.length; ) (this.widgets.pop(), (e = !0));
    const s = this._eclipse_hookedNodes || (this._eclipse_hookedNodes = new Map()),
        n = new Set(t.map((e) => e.id));
    for (const [e, t] of s) n.has(e) || (t(), s.delete(e));
    const l = this;
    for (const e of t)
        if (!s.has(e.id)) {
            const t = hookModeProperty(e, () => {
                requestSync(l);
            });
            s.set(e.id, t);
        }
    (syncTitleHooks(this, t, () => {
        scheduleStabilize(l, modeChangerStabilize, 50, !0);
    }),
        e && (notifyVue(this), smartResize(this, { minWidth: 0, minHeight: 0, padding: 0 })));
}
function setupGroupsModeChanger(e, t, i, o) {
    ((e.prototype.isVirtualNode = !0),
        (e['@matchColors'] = { type: 'string' }),
        (e['@matchTitle'] = { type: 'string' }),
        (e['@showNav'] = { type: 'boolean' }),
        (e['@showAllGraphs'] = { type: 'boolean' }),
        (e['@sort'] = { type: 'combo', values: ['position', 'alphanumeric', 'custom alphabet'] }),
        (e['@customSortAlphabet'] = { type: 'string' }),
        (e['@toggleRestriction'] = { type: 'combo', values: ['default', 'max one', 'always one'] }));
    const s = e.prototype.onNodeCreated;
    e.prototype.onNodeCreated = function () {
        const e = s?.apply(this, arguments);
        ((this.serialize_widgets = !1), (this.properties = this.properties || {}));
        const o = this.properties;
        (void 0 === o.matchColors && (o.matchColors = ''),
            void 0 === o.matchTitle && (o.matchTitle = ''),
            void 0 === o.showNav && (o.showNav = !0),
            void 0 === o.showAllGraphs && (o.showAllGraphs = !0),
            void 0 === o.sort && (o.sort = 'position'),
            void 0 === o.customSortAlphabet && (o.customSortAlphabet = ''),
            void 0 === o.toggleRestriction && (o.toggleRestriction = 'default'),
            this.outputs?.length || this.addOutput('oc', '*'),
            (this._eclipse_modeOn = t),
            (this._eclipse_modeOff = i),
            (this._eclipse_tempSize = null));
        const n = this;
        return (
            (this._eclipse_refreshInterval = setInterval(() => {
                n.graph && groupsRefreshWidgets.call(n);
            }, 500)),
            e
        );
    };
    const n = e.prototype.configure;
    e.prototype.configure = function (e) {
        const o = n?.apply(this, arguments);
        return ((this._eclipse_modeOn = t), (this._eclipse_modeOff = i), o);
    };
    const l = e.prototype.onRemoved;
    ((e.prototype.onRemoved = function () {
        (l?.apply(this, arguments),
            this._eclipse_refreshInterval &&
                (clearInterval(this._eclipse_refreshInterval), (this._eclipse_refreshInterval = null)));
    }),
        (e.prototype.computeSize = function (e) {
            let t = LGraphNode.prototype.computeSize.call(this, e);
            return (
                this._eclipse_tempSize &&
                    ((t[0] = Math.max(this._eclipse_tempSize[0], t[0])),
                    (t[1] = Math.max(this._eclipse_tempSize[1], t[1])),
                    clearTimeout(this._eclipse_sizeTimer),
                    (this._eclipse_sizeTimer = setTimeout(() => {
                        this._eclipse_tempSize = null;
                    }, 32))),
                t
            );
        }),
        (e.prototype.getExtraMenuOptions = function (e, t) {
            t.push(null);
            for (const e of o) t.push({ content: e, callback: () => this._eclipse_handleAction(e) });
            t.push(null);
            const i = this.properties?.toggleRestriction || 'default';
            for (const e of ['default', 'max one', 'always one'])
                t.push({
                    content: `${e === i ? '✓ ' : '  '}Restriction: ${e}`,
                    callback: () => {
                        ((this.properties.toggleRestriction = e), this.setDirtyCanvas(!0, !1));
                    },
                });
            return t;
        }),
        (e.prototype._eclipse_handleAction = function (e) {
            const t = 'always one' === this.properties?.toggleRestriction,
                i = this.widgets || [];
            if (e.startsWith('Enable')) {
                const e = (this.properties?.toggleRestriction || '').includes(' one');
                for (let t = 0; t < i.length; t++) i[t]._eclipse_doMode?.(!(e && t > 0), !0);
            } else if (e.startsWith('Mute') || e.startsWith('Bypass'))
                for (let e = 0; e < i.length; e++) i[e]._eclipse_doMode?.(t && 0 === e, !0);
            else if (e.startsWith('Toggle')) {
                const e = (this.properties?.toggleRestriction || '').includes(' one');
                let o = !1;
                for (const t of i) {
                    let i = (!e || !o) && !t.value;
                    ((o = o || i), t._eclipse_doMode?.(i, !0));
                }
                !o && t && i.length && i[i.length - 1]._eclipse_doMode?.(!0, !0);
            }
            for (const e of i) e.triggerDraw?.();
            batchedNotifyVue(this);
            this.setDirtyCanvas(!0, !1);
        }));
}
function groupsRefreshWidgets() {
    if (!this.graph) return;
    const e = this._eclipse_modeOn,
        t = this._eclipse_modeOff;
    let i = getSortedGroups(this);
    if (
        ((i = filterGroupsByColor(i, this.properties?.matchColors)),
        (i = filterGroupsByTitle(i, this.properties?.matchTitle)),
        !this.properties?.showAllGraphs && app.canvas)
    ) {
        const e = app.canvas.getCurrentGraph?.() || app.graph;
        i = i.filter((t) => t.graph === e);
    }
    let o = 0,
        s = !1;
    for (const n of i) {
        const i = `Enable ${n.title}`;
        let l = (this.widgets || []).find((e) => e._eclipse_groupTitle === n.title && e._eclipse_groupId === n.id);
        (l ||
            ((this._eclipse_tempSize = this.size ? [...this.size] : null),
            (l = this.addCustomWidget(createGroupToggleWidget(n, this, e, t))),
            smartResize(this, { minWidth: 0, minHeight: 0, padding: 0 }),
            (s = !0)),
            l.name !== i && ((l.name = i), (s = !0)));
        const r = getGroupNodes(n).some((e) => 0 === e.mode);
        l.value !== r && ((l.value = r), (s = !0));
        const c = (this.widgets || []).indexOf(l);
        (c !== o && c >= 0 && (this.widgets.splice(o, 0, this.widgets.splice(c, 1)[0]), (s = !0)), o++);
    }
    for (; (this.widgets || []).length > o; ) {
        const e = this.widgets.pop();
        (e && e.onRemove && e.onRemove(), (s = !0));
    }
    if (s) {
        for (const e of this.widgets || []) e.triggerDraw?.();
        notifyVue(this);
        this.setDirtyCanvas(!0, !1);
    }
}
function createGroupToggleWidget(e, t, i, o) {
    const s = {
        type: 'custom',
        name: `Enable ${e.title}`,
        value: !1,
        options: { on: 'yes', off: 'no' },
        _eclipse_groupTitle: e.title,
        _eclipse_groupId: e.id,
        _eclipse_group: e,
        _eclipse_doMode(e, n) {
            const l = s._eclipse_group;
            if (!l) return;
            const r = getGroupNodes(l),
                c = r.some((e) => 0 === e.mode);
            let p = null != e ? e : !c;
            if (!0 !== n) {
                const e = t.properties?.toggleRestriction || 'default';
                if (p && e.includes(' one'))
                    for (const e of t.widgets || []) e._eclipse_doMode && e !== s && e._eclipse_doMode(!1, !0);
                else p || 'always one' !== e || (p = (t.widgets || []).every((e) => !e.value || e === s));
            }
            (changeModeOfNodes(r, p ? i : o), (s.value = p));
            for (const e of t.widgets || []) e.triggerDraw?.();
            batchedNotifyVue(t);
            t.graph?.setDirtyCanvas(!0, !1);
        },
        callback() {
            s._eclipse_doMode();
        },
        draw(e, i, o, n, l) {
            const r = !1 !== t.properties?.showNav;
            ((e.fillStyle = '#2a2a2a'),
                e.beginPath(),
                e.roundRect(15, n, o - 30, l, 4),
                e.fill(),
                (e.strokeStyle = '#444'),
                e.stroke());
            let c = o - 15;
            if (r) {
                c -= 7;
                const t = n + 0.5 * l;
                ((e.fillStyle = e.strokeStyle = '#89A'),
                    (e.lineJoin = 'round'),
                    (e.lineCap = 'round'),
                    e.beginPath(),
                    e.moveTo(c, t),
                    e.lineTo(c - 7, t + 6),
                    e.lineTo(c - 7, t + 3),
                    e.lineTo(c - 14, t + 3),
                    e.lineTo(c - 14, t - 3),
                    e.lineTo(c - 7, t - 3),
                    e.lineTo(c - 7, t - 6),
                    e.closePath(),
                    e.fill(),
                    e.stroke(),
                    (c -= 21),
                    (c -= 4),
                    (e.strokeStyle = '#444'),
                    e.beginPath(),
                    e.moveTo(c, n + 2),
                    e.lineTo(c, n + l - 2),
                    e.stroke());
            }
            c -= 7;
            const p = 0.32 * l;
            ((e.fillStyle = s.value ? '#89A' : '#444'),
                e.beginPath(),
                e.arc(c - p, n + 0.5 * l, p, 0, 2 * Math.PI),
                e.fill(),
                (c -= 2 * p),
                (c -= 4),
                (e.textAlign = 'right'),
                (e.fillStyle = s.value ? '#ccc' : '#666'),
                (e.font = `${Math.max(10, 0.55 * l)}px Arial`));
            const a = s.value ? 'yes' : 'no';
            (e.fillText(a, c, n + 0.7 * l),
                (c -= Math.max(e.measureText('yes').width, e.measureText('no').width)),
                (c -= 7),
                (e.textAlign = 'left'),
                (e.fillStyle = s.value ? '#ddd' : '#999'));
            const u = c - 15 - 10,
                h = (s.name || '').replace(/^Enable /, '');
            u > 0 && e.fillText(fitString(e, h, u), 25, n + 0.7 * l);
        },
        mouse(e, i, o) {
            if ('pointerdown' !== e.type) return !0;
            if (!1 !== t.properties?.showNav && i[0] >= o.size[0] - 15 - 32) {
                const e = app.canvas;
                if (e && s._eclipse_group) {
                    const t = s._eclipse_group;
                    e.centerOnNode?.(t);
                    const i = e.ds?.scale || 1;
                    if (t._size) {
                        const o = e.canvas.width / t._size[0] - 0.02,
                            s = e.canvas.height / t._size[1] - 0.02;
                        e.setZoom?.(Math.min(i, o, s), [e.canvas.width / 2, e.canvas.height / 2]);
                    }
                    e.setDirty?.(!0, !0);
                }
            } else s._eclipse_doMode();
            return !0;
        },
        computeSize: (e) => [e, LiteGraph.NODE_WIDGET_HEIGHT || 20],
        serializeValue: () => s.value,
    };
    return s;
}
function fitString(e, t, i) {
    if (!t) return '';
    let o = e.measureText(t).width;
    if (o <= i) return t;
    const s = e.measureText('…').width;
    let n = t.length;
    for (; n > 0; ) if ((n--, (o = e.measureText(t.substring(0, n)).width), o + s <= i)) return t.substring(0, n) + '…';
    return '…';
}
function getSortedGroups(e) {
    const t = e.graph?._groups || [];
    if (!t.length) return [];
    const i = e.properties?.sort || 'position';
    let o = [...t];
    if ('alphanumeric' === i) o.sort((e, t) => (e.title || '').localeCompare(t.title || ''));
    else if ('position' === i)
        o.sort((e, t) => {
            const i = e._pos?.[1] ?? e.pos?.[1] ?? 0,
                o = t._pos?.[1] ?? t.pos?.[1] ?? 0;
            if (Math.abs(i - o) > 50) return i - o;
            return (e._pos?.[0] ?? e.pos?.[0] ?? 0) - (t._pos?.[0] ?? t.pos?.[0] ?? 0);
        });
    else if ('custom alphabet' === i) {
        const t = (e.properties?.customSortAlphabet || '').replace(/\n/g, '');
        if (t.trim()) {
            const e = t.includes(',')
                ? t
                      .toLowerCase()
                      .split(',')
                      .map((e) => e.trim())
                : t.toLowerCase().trim().split('');
            o.sort((t, i) => {
                const o = (t.title || '').toLowerCase(),
                    s = (i.title || '').toLowerCase();
                let n = -1,
                    l = -1;
                for (
                    let t = 0;
                    t < e.length &&
                    (n < 0 && o.startsWith(e[t]) && (n = t),
                    l < 0 && s.startsWith(e[t]) && (l = t),
                    !(n >= 0 && l >= 0));
                    t++
                );
                return n >= 0 && l >= 0
                    ? n !== l
                        ? n - l
                        : o.localeCompare(s)
                    : n >= 0
                      ? -1
                      : l >= 0
                        ? 1
                        : o.localeCompare(s);
            });
        } else o.sort((e, t) => (e.title || '').localeCompare(t.title || ''));
    }
    return o;
}
function filterGroupsByColor(e, t) {
    if (!t?.trim()) return e;
    let i = t
        .split(',')
        .map((e) => e.trim())
        .filter((e) => e);
    return i.length
        ? ((i = i.map(
              (e) => (
                  (e = e.toLowerCase()),
                  'undefined' != typeof LGraphCanvas &&
                      LGraphCanvas.node_colors?.[e] &&
                      (e = LGraphCanvas.node_colors[e].groupcolor || e),
                  3 === (e = e.replace('#', '')).length && (e = e.replace(/(.)(.)(.)/, '$1$1$2$2$3$3')),
                  `#${e}`
              ),
          )),
          e.filter((e) => {
              let t = (e.color || '').replace('#', '').trim().toLowerCase();
              return !!t && (3 === t.length && (t = t.replace(/(.)(.)(.)/, '$1$1$2$2$3$3')), i.includes(`#${t}`));
          }))
        : e;
}
function filterGroupsByTitle(e, t) {
    if (!t?.trim()) return e;
    try {
        const i = new RegExp(t, 'i');
        return e.filter((e) => i.test(e.title || ''));
    } catch (t) {
        return e;
    }
}
function setupNodeModeRepeater(e) {
    e.prototype.isVirtualNode = !0;
    const t = e.prototype.onNodeCreated;
    e.prototype.onNodeCreated = function () {
        const e = t?.apply(this, arguments);
        ((this.properties = this.properties || {}),
            this.outputs?.length
                ? this.outputs[0] && ((this.outputs[0].color_on = '#Fc0'), (this.outputs[0].color_off = '#a80'))
                : this.addOutput('oc', '*', { color_on: '#Fc0', color_off: '#a80' }),
            blankInputNames(this));
        const i = this;
        return (
            (this._eclipse_unhookMode = hookModeProperty(this, (e, t, o) => {
                i._eclipse_configuring || repeaterOnModeChange.call(i, t, o);
            })),
            scheduleStabilize(this, repeaterStabilize, 100),
            e
        );
    };
    const i = e.prototype.configure;
    e.prototype.configure = function (e) {
        this._eclipse_configuring = !0;
        const t = i?.apply(this, arguments);
        return ((this._eclipse_configuring = !1), scheduleStabilize(this, repeaterStabilize, 300, !0), t);
    };
    const o = e.prototype.onRemoved;
    ((e.prototype.onRemoved = function () {
        if (
            (o?.apply(this, arguments),
            this._eclipse_unhookMode && (this._eclipse_unhookMode(), (this._eclipse_unhookMode = null)),
            this._eclipse_hookedNodes)
        ) {
            for (const e of this._eclipse_hookedNodes.values()) e();
            this._eclipse_hookedNodes.clear();
        }
        if (this._eclipse_hookedTitles) {
            for (const e of this._eclipse_hookedTitles.values()) e();
            this._eclipse_hookedTitles.clear();
        }
        this._eclipse_stabilizeTimer &&
            (clearTimeout(this._eclipse_stabilizeTimer), (this._eclipse_stabilizeTimer = null));
    }),
        (e.prototype.onConnectionsChange = function (e, t, i, o) {
            o &&
                (i
                    ? (this._eclipse_stabilizeTimer &&
                          (clearTimeout(this._eclipse_stabilizeTimer), (this._eclipse_stabilizeTimer = null)),
                      repeaterStabilize.call(this),
                      scheduleStabilize(this, repeaterStabilize, 200, !0))
                    : scheduleStabilize(this, repeaterStabilize, 500, !0));
        }),
        (e.prototype.onConnectOutput = function (e, t, i, o, s) {
            if (!o) return !1;
            const n = (getConnectedOutputNodes(this, !0, o)[0] || o).type || '';
            return TOGGLER_TYPES.includes(n) || COLLECTOR_TYPES.includes(n) || REROUTE_TYPES.includes(n);
        }),
        (e.prototype.onConnectInput = function (e, t, i, o, s) {
            if (!o) return !1;
            if (getConnectedOutputNodes(this, !1).includes(o)) return !1;
            if (getConnectedInputNodes(this).includes(o)) {
                if (!getConnectedInputNodes(this, e).includes(o)) return !1;
            }
            return !0;
        }),
        (e.prototype.computeSize = function (e) {
            let t = LGraphNode.prototype.computeSize.call(this, e);
            return (
                this._eclipse_tempWidth &&
                    ((t[0] = Math.max(this._eclipse_tempWidth, t[0])),
                    clearTimeout(this._eclipse_widthTimer),
                    (this._eclipse_widthTimer = setTimeout(() => {
                        this._eclipse_tempWidth = null;
                    }, 32))),
                t
            );
        }));
}
function repeaterStabilize() {
    if (!this.graph) return;
    preserveWidth(this);
    let e = stabilizeInputs(this, !1);
    const t = getConnectedInputNodes(this),
        i = this;
    syncTitleHooks(this, t, () => {
        scheduleStabilize(i, repeaterStabilize, 50, !0);
    });
    const o = getConnectedInputNodesFiltered(this, -1, !1),
        s = this._eclipse_hookedNodes || (this._eclipse_hookedNodes = new Map()),
        n = new Set(o.map((e) => e.id));
    for (const [e, t] of s) n.has(e) || (t(), s.delete(e));
    for (const e of o)
        if (!s.has(e.id)) {
            const t = hookModeProperty(e, (e, t, o) => {
                if (i._eclipse_propagating) return;
                getConnectedInputNodesFiltered(i, -1, !1).length > 1 ||
                    (i.mode !== o && ((i._eclipse_propagating = !0), (i.mode = o), (i._eclipse_propagating = !1)));
            });
            s.set(e.id, t);
        }
    e &&
        ((this.inputs = this.inputs.map((e) => ({ ...e, boundingRect: e.boundingRect || [0, 0, 0, 0] }))),
        smartResize(this, { minWidth: 0, minHeight: 0, padding: 0 }));
}
function repeaterOnModeChange(e, t) {
    if (!this.graph) return;
    if (this._eclipse_propagating) return;
    this._eclipse_propagating = !0;
    const i = getConnectedInputNodesFiltered(this, -1, !1);
    if (i.length) for (const e of i) changeModeOfNodes(e, t);
    else if (this.graph._groups?.length)
        for (const e of this.graph._groups) {
            const i = getGroupNodes(e);
            if (i.includes(this)) for (const e of i) e !== this && changeModeOfNodes(e, t);
        }
    (notifyDownstreamModeChange(this), (this._eclipse_propagating = !1));
}
function setupNodeCollector(e) {
    e.prototype.isVirtualNode = !0;
    const t = e.prototype.onNodeCreated;
    e.prototype.onNodeCreated = function () {
        const e = t?.apply(this, arguments);
        ((this.properties = this.properties || {}),
            this.outputs?.length || this.addOutput('Output', '*'),
            blankInputNames(this));
        const i = this;
        return (
            (this._eclipse_unhookMode = hookModeProperty(this, (e, t, o) => {
                i._eclipse_configuring || collectorOnModeChange.call(i, t, o);
            })),
            (this._eclipse_onUpstreamModeChange = function () {
                i._eclipse_upstreamChangeQueued ||
                    ((i._eclipse_upstreamChangeQueued = !0),
                    requestAnimationFrame(() => {
                        ((i._eclipse_upstreamChangeQueued = !1), i.graph && notifyDownstreamModeChange(i));
                    }));
            }),
            scheduleStabilize(this, collectorStabilize, 100),
            e
        );
    };
    const i = e.prototype.configure;
    ((e.prototype.configure = function (e) {
        this._eclipse_configuring = !0;
        const t = i?.apply(this, arguments);
        return ((this._eclipse_configuring = !1), scheduleStabilize(this, collectorStabilize, 300, !0), t);
    }),
        (e.prototype.onConnectionsChange = function (e, t, i, o) {
            if (!o) return;
            const s = getConnectedOutputNodes(this, !0);
            for (const e of s) e._eclipse_onChainChange && e._eclipse_onChainChange();
            i
                ? (this._eclipse_stabilizeTimer &&
                      (clearTimeout(this._eclipse_stabilizeTimer), (this._eclipse_stabilizeTimer = null)),
                  collectorStabilize.call(this),
                  scheduleStabilize(this, collectorStabilize, 200, !0))
                : scheduleStabilize(this, collectorStabilize, 500, !0);
        }),
        (e.prototype.onConnectInput = function (e, t, i, o, s) {
            if (!o) return !1;
            if (getConnectedOutputNodes(this, !1).includes(o)) return !1;
            const n = getConnectedInputNodes(this);
            if (n.includes(o)) {
                if (!getConnectedInputNodes(this, e).includes(o)) return !1;
            }
            if (isReroute(o)) {
                const t = getConnectedInputNodesFiltered(o, -1, !0)[0];
                if (t && n.includes(t)) {
                    if (!getConnectedInputNodes(this, e).some((e) => e === o)) return !1;
                }
            }
            return !0;
        }),
        (e.prototype.onConnectOutput = function (e, t, i, o, s) {
            if (!o) return !1;
            return !getConnectedInputNodes(this).includes(o);
        }));
    const o = e.prototype.onRemoved;
    ((e.prototype.onRemoved = function () {
        if (
            (o?.apply(this, arguments),
            this._eclipse_unhookMode && (this._eclipse_unhookMode(), (this._eclipse_unhookMode = null)),
            this._eclipse_hookedTitles)
        ) {
            for (const e of this._eclipse_hookedTitles.values()) e();
            this._eclipse_hookedTitles.clear();
        }
        this._eclipse_stabilizeTimer &&
            (clearTimeout(this._eclipse_stabilizeTimer), (this._eclipse_stabilizeTimer = null));
    }),
        (e.prototype._eclipse_onChainChange = function () {
            (this._eclipse_stabilizeTimer &&
                (clearTimeout(this._eclipse_stabilizeTimer), (this._eclipse_stabilizeTimer = null)),
                collectorStabilize.call(this));
        }),
        (e.prototype.computeSize = function (e) {
            let t = LGraphNode.prototype.computeSize.call(this, e);
            return (
                this._eclipse_tempWidth &&
                    ((t[0] = Math.max(this._eclipse_tempWidth, t[0])),
                    clearTimeout(this._eclipse_widthTimer),
                    (this._eclipse_widthTimer = setTimeout(() => {
                        this._eclipse_tempWidth = null;
                    }, 32))),
                t
            );
        }));
}
function collectorOnModeChange(e, t) {
    if (!this.graph) return;
    const i = getConnectedInputNodesFiltered(this, -1, !1);
    for (const e of i) changeModeOfNodes(e, t);
    notifyDownstreamModeChange(this);
}
function collectorStabilize() {
    if (!this.graph) return;
    preserveWidth(this);
    let e = stabilizeInputs(this, !0);
    const t = getConnectedInputNodesFiltered(this, -1, !1),
        i = this;
    (syncTitleHooks(this, t, () => {
        scheduleStabilize(i, collectorStabilize, 50, !0);
    }),
        e &&
            ((this.inputs = this.inputs.map((e) => ({ ...e, boundingRect: e.boundingRect || [0, 0, 0, 0] }))),
            smartResize(this, { minWidth: 0, minHeight: 0, padding: 0 }),
            this.setDirtyCanvas(!0, !0)));
}
app.registerExtension({
    name: 'Eclipse.ModeNodes',
    async nodeCreated(e) {
        const t = e.comfyClass || e.type || '';
        ECLIPSE_MODE_TYPES.includes(t) &&
            (blankInputNames(e),
            t === NODE_NAMES.FAST_MUTER || t === NODE_NAMES.FAST_BYPASSER
                ? (e.outputs?.length || e.addOutput('oc', '*'),
                  e._eclipse_modeOn ||
                      ((e._eclipse_modeOn = 0), (e._eclipse_modeOff = t === NODE_NAMES.FAST_MUTER ? 2 : 4)),
                  scheduleStabilize(e, modeChangerStabilize, 100, !0))
                : t === NODE_NAMES.NODE_MODE_REPEATER
                  ? (e.outputs?.length
                        ? e.outputs[0] && ((e.outputs[0].color_on = '#Fc0'), (e.outputs[0].color_off = '#a80'))
                        : e.addOutput('oc', '*', { color_on: '#Fc0', color_off: '#a80' }),
                    scheduleStabilize(e, repeaterStabilize, 100, !0))
                  : t === NODE_NAMES.NODE_COLLECTOR
                    ? (e.outputs?.length || e.addOutput('Output', '*'),
                      scheduleStabilize(e, collectorStabilize, 100, !0))
                    : (t !== NODE_NAMES.FAST_GROUPS_MUTER && t !== NODE_NAMES.FAST_GROUPS_BYPASSER) ||
                      e.outputs?.length ||
                      e.addOutput('oc', '*'));
    },
    async beforeRegisterNodeDef(e, t, i) {
        if (t?.name)
            switch (t.name) {
                case NODE_NAMES.FAST_MUTER:
                    setupModeChanger(e, 0, 2, ['Mute all', 'Enable all', 'Toggle all']);
                    break;
                case NODE_NAMES.FAST_BYPASSER:
                    setupModeChanger(e, 0, 4, ['Bypass all', 'Enable all', 'Toggle all']);
                    break;
                case NODE_NAMES.FAST_GROUPS_MUTER:
                    setupGroupsModeChanger(e, 0, 2, ['Mute all', 'Enable all', 'Toggle all']);
                    break;
                case NODE_NAMES.FAST_GROUPS_BYPASSER:
                    setupGroupsModeChanger(e, 0, 4, ['Bypass all', 'Enable all', 'Toggle all']);
                    break;
                case NODE_NAMES.NODE_MODE_REPEATER:
                    setupNodeModeRepeater(e);
                    break;
                case NODE_NAMES.NODE_COLLECTOR:
                    setupNodeCollector(e);
            }
    },
});
