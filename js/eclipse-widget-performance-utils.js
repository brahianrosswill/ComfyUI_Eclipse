export function debounce(e, t) {
    let i;
    return function (...n) {
        (clearTimeout(i), (i = setTimeout(() => e(...n), t)));
    };
}
export const canvasDirtyBatcher = {
    markDirty(e, t = !0, i = !1) {
        e?.setDirtyCanvas && e.setDirtyCanvas(t, i);
    },
};
export function notifyVue(e) {
    const t = e.widgets;
    if (t?.length) {
        const e = t.pop();
        t.push(e);
    }
}
const _pendingNotify = new Set();
let _notifyScheduled = !1;
export function batchedNotifyVue(e) {
    _pendingNotify.add(e);
    if (!_notifyScheduled) {
        _notifyScheduled = !0;
        queueMicrotask(() => {
            _notifyScheduled = !1;
            for (const e of _pendingNotify) notifyVue(e);
            _pendingNotify.clear();
        });
    }
}
export function createWidgetVisibilityManager(e) {
    const t = new Map();
    let i = null,
        n = !1;
    function s(t) {
        if (!i || i.size !== (e.widgets?.length || 0)) {
            i = new Map();
            for (const t of e.widgets || []) i.set(t.name, t);
        }
        return i.get(t);
    }
    return {
        setVisible(i, o) {
            if (t.get(i) === o) return;
            const r = s(i);
            r &&
                (t.set(i, o),
                (r.hidden = !o),
                r.options && (r.options.hidden = !o),
                n ||
                    ((n = !0),
                    queueMicrotask(() => {
                        ((n = !1), notifyVue(e));
                    })));
        },
        getValue(e) {
            const t = s(e);
            return t ? t.value : null;
        },
        clearCache() {
            (t.clear(), (i = null));
        },
    };
}
function _getNodeElement(e) {
    return e._eclipse_el?.isConnected
        ? e._eclipse_el
        : null == e.id
          ? null
          : ((e._eclipse_el = document.querySelector(`[data-node-id="${e.id}"]`)), e._eclipse_el);
}
function _applyResize(e, t, i, n) {
    if (e.flags?.collapsed) return;
    const s = e.size[0],
        o = e.size[1];
    e.size[1] = 0;
    const r = e.computeSize(),
        a = Math.max(s, t),
        c = Math.max(r[1], i) + n;
    if (a === s && c === o) return void (e.size[1] = o);
    e.setSize?.([a, c]);
    const l = _getNodeElement(e);
    (l && (l.style.setProperty('--node-height', `${c}px`), l.style.setProperty('--node-width', `${a}px`)),
        e.graph?.setDirtyCanvas?.(!0, !1));
}
export function patchNodeCSSSize(e) {
    if (e.flags?.collapsed) return;
    const t = _getNodeElement(e);
    t &&
        (t.style.setProperty('--node-height', `${e.size[1]}px`), t.style.setProperty('--node-width', `${e.size[0]}px`));
}
export function smartResize(e, { minWidth: t = 259, minHeight: i = 100, padding: n = 5 } = {}) {
    (_applyResize(e, t, i, n),
        e._smartResizePending ||
            ((e._smartResizePending = !0),
            requestAnimationFrame(() => {
                ((e._smartResizePending = !1), _applyResize(e, t, i, n));
            })));
}
// --- Vue / Nodes 2.0 mode-change detection (zero-polling) ---
// Intercepts LiteGraph.vueNodesMode via property descriptor so extensions
// can react when the user toggles between Classic and Nodes 2.0.
const _vmcCallbacks = new Set();
let _vmcInstalled = false;
let _vmcValue = false;
function _installVueModeWatcher() {
    if (_vmcInstalled) return;
    _vmcInstalled = true;
    try {
        _vmcValue = !!LiteGraph.vueNodesMode;
        Object.defineProperty(LiteGraph, 'vueNodesMode', {
            get() { return _vmcValue; },
            set(v) {
                const prev = _vmcValue;
                _vmcValue = !!v;
                if (prev !== _vmcValue) {
                    for (const cb of _vmcCallbacks) {
                        try { cb(_vmcValue, prev); } catch (e) { console.error('[Eclipse] vueModeChange error', e); }
                    }
                }
            },
            configurable: true,
            enumerable: true,
        });
    } catch { /* frozen object — ignore */ }
}
export function isVueMode() {
    try { return !!LiteGraph.vueNodesMode; } catch { return false; }
}
export function onVueModeChange(callback) {
    _installVueModeWatcher();
    _vmcCallbacks.add(callback);
    return () => _vmcCallbacks.delete(callback);
}
export default {
    debounce: debounce,
    canvasDirtyBatcher: canvasDirtyBatcher,
    notifyVue: notifyVue,
    batchedNotifyVue: batchedNotifyVue,
    createWidgetVisibilityManager: createWidgetVisibilityManager,
    patchNodeCSSSize: patchNodeCSSSize,
    smartResize: smartResize,
    isVueMode: isVueMode,
    onVueModeChange: onVueModeChange,
};
