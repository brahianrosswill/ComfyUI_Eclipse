/**
 * Eclipse — Dynamic Inputs with Auto-Grow / Auto-Shrink
 *
 * Manages dynamic input slots for V1 nodes that use an `inputcount` widget.
 * Slots auto-grow when the last slot is connected (up to max), and auto-shrink
 * when trailing slots are disconnected (down to MIN_SLOTS).
 * The `inputcount` widget is hidden but kept in sync for serialization.
 *
 * Also handles AnyType (*) type propagation: when one slot is connected,
 * all dynamic slots and the output adopt the concrete type.
 */
import { app } from './comfy/index.js';
import { patchNodeCSSSize } from './eclipse-widget-performance-utils.js';

const MIN_SLOTS = 2;
const MAX_SLOTS = 64;

// Shared resize helper
function scheduleResize(node) {
    setTimeout(() => {
        node.setDirtyCanvas(true, false);
        const computed = node.computeSize();
        const cur = node.size;
        const w = Math.max(cur[0], 200);
        const h = Math.max(computed[1] + 5, 50);
        if (h > cur[1] || Math.abs(cur[1] - h) > 10) {
            node.setSize([w, h]);
            patchNodeCSSSize(node);
        }
        node.setDirtyCanvas(true, true);
    }, 50);
}

// Get the highest prefix number from current inputs
function getHighestSlotNum(node, prefix) {
    let max = 0;
    if (!node.inputs) return max;
    const re = new RegExp('^' + prefix + '_(\\d+)$');
    for (const inp of node.inputs) {
        const m = inp.name?.match(re);
        if (m) {
            const num = parseInt(m[1], 10);
            if (num > max) max = num;
        }
    }
    return max;
}

// Determine the concrete type for dynamic slots (AnyType nodes only)
function inferSlotType(node, prefix, defaultType) {
    if (defaultType !== '*') return defaultType;
    if (!node.inputs) return '*';
    // First: check if any slot already has a concrete type
    const typed = node.inputs.find(inp => inp.name?.startsWith(prefix + '_') && inp.type !== '*');
    if (typed) return typed.type;
    // Second: check link data
    const linked = node.inputs.find(inp => inp.name?.startsWith(prefix + '_') && inp.link != null);
    if (linked) {
        const link = app.graph?.links?.[linked.link] ?? app.graph?.links?.get?.(linked.link);
        if (link?.type) return link.type;
    }
    return '*';
}

// Helper: resolve a graph link by ID (handles both Map and plain-object storage)
function getLink(id) {
    if (id == null) return null;
    return app.graph?.links?.[id] ?? app.graph?.links?.get?.(id) ?? null;
}

// Helper: resolve source output type from a connected input slot
function getSourceType(inp) {
    const link = getLink(inp?.link);
    if (!link) return null;
    const srcNode = app.graph?.getNodeById(link.origin_id);
    return srcNode?.outputs?.[link.origin_slot]?.type ?? link.type ?? null;
}

// Node config map: nodeName → { type, prefix, max }
const NODE_CONFIGS = {
    RvConversion_ConcatMulti:                { type: 'PIPE',   prefix: 'pipe',   max: MAX_SLOTS },
    'Concat Pipe Multi [Eclipse]':           { type: 'PIPE',   prefix: 'pipe',   max: MAX_SLOTS },
    RvRouter_Any_MultiSwitch:                { type: '*',      prefix: 'any',    max: MAX_SLOTS },
    'Any Multi-Switch [Eclipse]':            { type: '*',      prefix: 'any',    max: MAX_SLOTS },
    RvRouter_Any_MultiSwitch_purge:          { type: '*',      prefix: 'any',    max: MAX_SLOTS },
    'Any Multi-Switch Purge [Eclipse]':      { type: '*',      prefix: 'any',    max: MAX_SLOTS },
    RvConversion_MergeStrings:               { type: 'STRING', prefix: 'string', max: MAX_SLOTS },
    'Merge Strings [Eclipse]':               { type: 'STRING', prefix: 'string', max: MAX_SLOTS },
    RvConversion_Join:                       { type: '*',      prefix: 'input',  max: MAX_SLOTS },
    'Join [Eclipse]':                        { type: '*',      prefix: 'input',  max: MAX_SLOTS },
};

app.registerExtension({
    name: 'Eclipse.DynamicInputs',
    async beforeRegisterNodeDef(nodeType, nodeData, appRef) {
        if (!nodeData?.name) return;
        const name = nodeData.name?.includes('/') ? nodeData.name.split('/').pop() : nodeData.name;
        const cfg = NODE_CONFIGS[name];
        if (!cfg) return;

        const origOnCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origOnCreated?.apply(this, arguments);

            const node = this;
            const isAnyType = cfg.type === '*';
            const prefix = cfg.prefix;
            const maxSlots = cfg.max || MAX_SLOTS;
            const slotName = (num) => `${prefix}_${num}`;

            // ── Find and hide the inputcount widget ──────────────────────
            const countWidget = node.widgets?.find(w => w.name === 'inputcount');
            if (countWidget) {
                countWidget.type = 'converted-widget';
                countWidget.hidden = true;
                countWidget.options = countWidget.options || {};
                countWidget.options.hidden = true;
                countWidget.computeSize = () => [0, -4];
            }

            function getInputCount() {
                return countWidget ? Math.max(MIN_SLOTS, countWidget.value) : MIN_SLOTS;
            }

            function setInputCount(val) {
                val = Math.max(MIN_SLOTS, Math.min(maxSlots, val));
                if (countWidget) countWidget.value = val;
            }

            // ── Sync inputs to match inputcount ──────────────────────────
            function syncInputs() {
                node.inputs || (node.inputs = []);
                const desired = getInputCount();
                const slotType = inferSlotType(node, prefix, cfg.type);

                // Collect existing prefix_N input names
                const existing = new Set();
                const widgetNames = new Set();
                for (const inp of node.inputs) {
                    if (inp.name?.startsWith(prefix + '_')) existing.add(inp.name);
                }
                for (const w of (node.widgets || [])) {
                    if (w.name?.startsWith(prefix + '_')) widgetNames.add(w.name);
                }

                // Convert widgets-as-inputs into real inputs if needed
                for (let i = 1; i <= desired; i++) {
                    const name = slotName(i);
                    if (widgetNames.has(name) && !existing.has(name)) {
                        node.addInput(name, slotType, cfg.shape != null ? { shape: cfg.shape } : undefined);
                        existing.add(name);
                    }
                }

                // Add missing inputs
                for (let i = 1; i <= desired; i++) {
                    const name = slotName(i);
                    if (!existing.has(name)) {
                        node.addInput(name, slotType, cfg.shape != null ? { shape: cfg.shape } : undefined);
                        existing.add(name);
                    }
                }

                // Remove excess inputs (highest numbers first)
                const nums = [];
                const re = new RegExp('^' + prefix + '_(\\d+)$');
                for (const name of existing) {
                    const m = name.match(re);
                    if (m) nums.push(parseInt(m[1], 10));
                }
                nums.sort((a, b) => b - a);
                for (const num of nums) {
                    if (existing.size <= desired) break;
                    const name = slotName(num);
                    const idx = node.inputs.findIndex(inp => inp.name === name);
                    if (idx !== -1) node.removeInput(idx);
                    if (node.widgets) {
                        const wIdx = node.widgets.findIndex(w => w.name === name);
                        if (wIdx !== -1) node.widgets.splice(wIdx, 1);
                    }
                    existing.delete(name);
                }

                scheduleResize(node);
            }

            // ── Auto-grow: add a slot when the last one is connected ─────
            function autoGrow() {
                const highestNum = getHighestSlotNum(node, prefix);
                if (highestNum <= 0 || highestNum >= maxSlots) return;

                // Check if the last slot is connected
                const lastSlot = node.inputs?.find(inp => inp.name === slotName(highestNum));
                if (!lastSlot || lastSlot.link == null) return;

                // Add one more
                const newCount = highestNum + 1;
                setInputCount(newCount);
                syncInputs();
            }

            // ── Auto-shrink: remove trailing empty slots on disconnect ───
            function autoShrink() {
                const highestNum = getHighestSlotNum(node, prefix);
                if (highestNum <= MIN_SLOTS) return;

                // Find last connected slot
                let lastConnected = 0;
                for (let i = 1; i <= highestNum; i++) {
                    const inp = node.inputs?.find(inp => inp.name === slotName(i));
                    if (inp?.link != null) lastConnected = i;
                }

                // Keep: lastConnected + 1 empty slot for growth, minimum MIN_SLOTS
                const keep = Math.max(MIN_SLOTS, lastConnected + 1);
                if (keep < highestNum) {
                    setInputCount(keep);
                    syncInputs();
                }
            }

            // ── AnyType propagation ──────────────────────────────────────
            function propagateType(connectedType) {
                if (!isAnyType || !connectedType || connectedType === '*') return;

                // Set concrete type on all dynamic input slots
                for (const inp of node.inputs || []) {
                    if (!inp.name?.startsWith(prefix + '_')) continue;
                    inp.type = connectedType;
                    // Clear explicit color overrides so LiteGraph resolves from type defaults
                    delete inp.color_on;
                    delete inp.color_off;
                }

                // Set output type
                if (node.outputs?.[0]) {
                    node.outputs[0].type = connectedType;
                    node.outputs[0].name = connectedType;
                    delete node.outputs[0].color_on;
                    delete node.outputs[0].color_off;
                }

                // Sync link type and color for all connected input links
                const color = LGraphCanvas.link_type_colors?.[connectedType];
                for (const inp of node.inputs || []) {
                    if (!inp.name?.startsWith(prefix + '_') || inp.link == null) continue;
                    const lnk = getLink(inp.link);
                    if (lnk) {
                        lnk.type = connectedType;
                        if (color) lnk.color = color;
                    }
                }

                // Sync output link type and color
                for (const linkId of node.outputs?.[0]?.links || []) {
                    const lnk = getLink(linkId);
                    if (lnk) {
                        lnk.type = connectedType;
                        if (color) lnk.color = color;
                    }
                }

                node.setDirtyCanvas(true, true);
            }

            function resetType() {
                if (!isAnyType) return;

                // Check for remaining connections to derive type
                const connected = (node.inputs || []).filter(
                    inp => inp.name?.startsWith(prefix + '_') && inp.link != null
                );

                if (connected.length > 0) {
                    // Re-derive type from first remaining connection's source
                    const srcType = getSourceType(connected[0]);
                    if (srcType && srcType !== '*') {
                        propagateType(srcType);
                        return;
                    }
                }

                // No connections remain: revert to wildcard
                for (const inp of node.inputs || []) {
                    if (!inp.name?.startsWith(prefix + '_')) continue;
                    inp.type = '*';
                    delete inp.color_on;
                    delete inp.color_off;
                }

                if (node.outputs?.[0]) {
                    node.outputs[0].type = '*';
                    node.outputs[0].name = '';
                    delete node.outputs[0].color_on;
                    delete node.outputs[0].color_off;
                }

                node.setDirtyCanvas(true, true);
            }

            // ── Validate all connections after paste/load ────────────────
            function validateAllConnections() {
                if (!node.inputs) return;

                // Find concrete type from first valid connection
                let concreteType = null;
                for (const inp of node.inputs) {
                    if (!inp.name?.startsWith(prefix + '_') || inp.link == null) continue;
                    const srcType = getSourceType(inp);
                    if (srcType && srcType !== '*') { concreteType = srcType; break; }
                }

                if (!concreteType) { resetType(); return; }

                propagateType(concreteType);
            }

            // ── Unified onConnectionsChange ──────────────────────────────
            const origOnConns = node.onConnectionsChange;
            node.onConnectionsChange = function (direction, slotIdx, connected, linkData) {
                origOnConns?.apply(this, arguments);

                if (direction !== LiteGraph.INPUT || !this.inputs) return;
                const inp = this.inputs[slotIdx];
                if (!inp?.name?.startsWith(prefix + '_')) return;

                if (connected && linkData) {
                    if (isAnyType) {
                        const srcNode = app.graph?.getNodeById(linkData.origin_id);
                        const srcType = srcNode?.outputs?.[linkData.origin_slot]?.type;
                        if (srcType && srcType !== '*') {
                            // Enforce same-type: reject if existing concrete type differs
                            const existingType = inferSlotType(node, prefix, '*');
                            if (existingType !== '*' && existingType !== srcType) {
                                setTimeout(() => node.disconnectInput(slotIdx), 0);
                                return;
                            }
                            propagateType(srcType);
                        }
                    }
                    // Auto-grow
                    autoGrow();
                } else if (!connected) {
                    // Type reset for AnyType
                    resetType();
                    // Auto-shrink (deferred to let LiteGraph finish cleanup)
                    requestAnimationFrame(() => autoShrink());
                }

                this.setDirtyCanvas?.(true, true);
            };

            // ── Paste / load validation (onConfigure) ────────────────────
            const origOnConfigure = node.onConfigure;
            node.onConfigure = function (data) {
                origOnConfigure?.apply(this, arguments);
                // Delay to let LiteGraph finalize link restoration after paste/load
                setTimeout(() => {
                    try {
                        if (isAnyType) validateAllConnections();
                        autoShrink();
                    } catch (_) {}
                }, 150);
            };

            // ── Initial sync ─────────────────────────────────────────────
            setTimeout(() => {
                try {
                    syncInputs();
                    if (isAnyType) validateAllConnections();
                } catch (_) {}
            }, 80);

            // ── Widget callback (manual override still works) ────────────
            if (countWidget) {
                let lastVal = countWidget.value;
                const origCb = countWidget.callback;
                countWidget.callback = function () {
                    origCb?.apply(this, arguments);
                    if (countWidget.value !== lastVal) {
                        lastVal = countWidget.value;
                        syncInputs();
                    }
                };
            }
        };
    },
});
