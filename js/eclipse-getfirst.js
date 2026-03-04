/**
 * eclipse-getfirst.js - GetFirst virtual node for ComfyUI Eclipse
 *
 * A virtual node that resolves to the first available (active, connected) SetNode
 * from a user-defined priority list. Replaces N GetNodes + 1 Multi-Switch with
 * a single node.
 *
 * Works with KJNodes SetNode (diffus3 pattern). Purely frontend — no backend
 * execution, no VRAM cost. Link resolution happens at graph serialization time.
 *
 * Copyright (c) 2026 r-vage. MIT License.
 */
import { app } from './comfy/index.js';

const LGraphNode = LiteGraph.LGraphNode;

const TYPE_FILTERS = [
    "*", "MODEL", "CLIP", "VAE", "CONDITIONING", "LATENT",
    "IMAGE", "MASK", "FLOAT", "INT", "STRING",
    "CONTROL_NET", "NOISE", "GUIDER", "SAMPLER", "SIGMAS"
];

// Color map matching KJNodes SetNode colors
const COLOR_MAP = {
    "DEFAULT": LGraphCanvas.node_colors?.gray,
    "MODEL": LGraphCanvas.node_colors?.blue,
    "LATENT": LGraphCanvas.node_colors?.purple,
    "VAE": LGraphCanvas.node_colors?.red,
    "CONDITIONING": LGraphCanvas.node_colors?.brown,
    "IMAGE": LGraphCanvas.node_colors?.pale_blue,
    "CLIP": LGraphCanvas.node_colors?.yellow,
    "FLOAT": LGraphCanvas.node_colors?.green,
    "MASK": { color: "#1c5715", bgcolor: "#1f401b" },
    "INT": { color: "#1b4669", bgcolor: "#29699c" },
    "CONTROL_NET": { color: "#156653", bgcolor: "#1c453b" },
    "NOISE": { color: "#2e2e2e", bgcolor: "#242121" },
    "GUIDER": { color: "#3c7878", bgcolor: "#1c453b" },
    "SAMPLER": { color: "#614a4a", bgcolor: "#3b2c2c" },
    "SIGMAS": { color: "#485248", bgcolor: "#272e27" },
};

function showAlert(message) {
    app.extensionManager.toast.add({
        severity: 'warn',
        summary: "Eclipse GetFirst",
        detail: message,
        life: 5000,
    });
}

// Get all SetNode variable names, optionally filtered by type
function getSetterVars(graph, typeFilter) {
    if (!graph || !graph._nodes) return [];
    const setters = graph._nodes.filter(n => n.type === 'SetNode');
    const vars = [];
    for (const setter of setters) {
        const name = setter.widgets?.[0]?.value;
        if (!name || name === '') continue;
        if (typeFilter && typeFilter !== '*') {
            const setterType = setter.inputs?.[0]?.type;
            if (setterType !== typeFilter && setterType !== '*') continue;
        }
        vars.push(name);
    }
    return vars.sort();
}

// Find a SetNode by variable name
function findSetter(graph, varName) {
    if (!graph || !graph._nodes || !varName || varName === '') return null;
    return graph._nodes.find(n =>
        n.type === 'SetNode' && n.widgets?.[0]?.value === varName
    ) || null;
}

// Check if a SetNode's source chain is active (not muted)
function isSetterActive(graph, setter) {
    if (!setter) return false;
    // SetNode itself is in a muted group
    if (setter.mode === 2) return false;
    // SetNode has no input connection
    if (!setter.inputs?.[0]?.link) return false;
    const link = graph.links?.[setter.inputs[0].link];
    if (!link) return false;
    const sourceNode = graph._nodes_by_id?.[link.origin_id];
    if (!sourceNode) return false;
    // Source node is muted (mode 2 = muted)
    // Bypassed (mode 4) is OK — ComfyUI handles pass-through
    if (sourceNode.mode === 2) return false;
    return true;
}

// Apply type-based coloring
function applyColor(node, type) {
    const colors = COLOR_MAP[type];
    if (colors) {
        node.color = colors.color;
        node.bgcolor = colors.bgcolor;
    } else {
        const defaults = LGraphCanvas.node_colors?.gray;
        if (defaults) {
            node.color = defaults.color;
            node.bgcolor = defaults.bgcolor;
        }
    }
}


app.registerExtension({
    name: "Eclipse.GetFirstNode",
    registerCustomNodes() {
        class GetFirstNode extends LGraphNode {
            serialize_widgets = true;
            drawConnection = false;
            slotColor = "#FFF";
            canvas = app.canvas;

            constructor(title) {
                super(title);
                if (!this.properties) {
                    this.properties = {};
                }
                this.properties.showOutputText = true;
                this.properties.varCount = 2;

                const node = this;

                // Setter resolution cache — avoids per-frame graph scans
                // Each entry: { setter, active } or null
                this._resolvedSetters = null;

                // Invalidate cache (called when vars/type/graph change)
                this.invalidateCache = function () {
                    this._resolvedSetters = null;
                };

                // Rebuild cache from current var widgets
                this.rebuildCache = function () {
                    if (!this.graph) { this._resolvedSetters = []; return; }
                    const varWidgets = this.widgets.slice(2);
                    this._resolvedSetters = varWidgets.map(w => {
                        const name = w.value;
                        if (!name || name === '') return null;
                        const setter = findSetter(this.graph, name);
                        if (!setter) return null;
                        return { setter, active: isSetterActive(this.graph, setter) };
                    });
                };

                // Get cached setters (lazy rebuild)
                this.getCachedSetters = function () {
                    if (!this._resolvedSetters) this.rebuildCache();
                    return this._resolvedSetters;
                };

                // Get filtered var names for combo options
                this.getFilteredVars = function () {
                    const typeFilter = this.widgets?.[0]?.value || '*';
                    return getSetterVars(this.graph, typeFilter);
                };

                // Create a var combo widget with proper callback
                this.createVarWidget = function (index) {
                    this.addWidget("combo", `var_${index}`, "", (value) => {
                        node.invalidateCache();
                        node.updateOutputType();
                    }, {
                        values: () => {
                            const vars = node.getFilteredVars();
                            return ["", ...vars];
                        }
                    });
                };

                // Sync var widgets to match var_count
                this.syncVarWidgets = function () {
                    const targetCount = Math.max(1, Math.min(20, this.properties.varCount || 2));
                    const varWidgetStartIdx = 2; // after type_filter and var_count

                    // Count existing var widgets
                    const existingVarWidgets = this.widgets.slice(varWidgetStartIdx);
                    const currentCount = existingVarWidgets.length;

                    if (currentCount < targetCount) {
                        // Add more var widgets
                        for (let i = currentCount; i < targetCount; i++) {
                            this.createVarWidget(i + 1);
                        }
                    } else if (currentCount > targetCount) {
                        // Remove excess var widgets (remove from end)
                        const keepWidgets = this.widgets.slice(0, varWidgetStartIdx + targetCount);
                        this.widgets.length = 0;
                        for (const w of keepWidgets) {
                            this.widgets.push(w);
                        }
                    }
                    const computed = this.computeSize();
                    this.setSize([Math.max(this.size[0], computed[0]), computed[1]]);
                };

                // Refresh all var widget options (when type filter changes)
                this.refreshVarWidgets = function () {
                    this.invalidateCache();
                    this.setDirtyCanvas(true, true);
                };

                // Update output type based on resolved setter type
                this.updateOutputType = function () {
                    this.invalidateCache();
                    const typeFilter = this.widgets[0].value;
                    if (typeFilter !== '*') {
                        this.outputs[0].type = typeFilter;
                        this.outputs[0].name = typeFilter;
                        if (app.ui.settings.getSettingValue("KJNodes.nodeAutoColor")) {
                            applyColor(this, typeFilter);
                        }
                    } else {
                        // Try to infer type from first valid setter
                        const resolvedType = this.resolveOutputType();
                        this.outputs[0].type = resolvedType || '*';
                        this.outputs[0].name = resolvedType || '*';
                        if (resolvedType && app.ui.settings.getSettingValue("KJNodes.nodeAutoColor")) {
                            applyColor(this, resolvedType);
                        }
                    }
                };

                // Resolve actual output type from first available setter
                this.resolveOutputType = function () {
                    if (!this.graph) return null;
                    const varWidgets = this.widgets.slice(2);
                    for (const w of varWidgets) {
                        const varName = w.value;
                        if (!varName || varName === '') continue;
                        const setter = findSetter(this.graph, varName);
                        if (setter && setter.inputs?.[0]?.type && setter.inputs[0].type !== '*') {
                            return setter.inputs[0].type;
                        }
                    }
                    return null;
                };

                this.clone = function () {
                    const cloned = GetFirstNode.prototype.clone.apply(this);
                    cloned.setSize(cloned.computeSize());
                    return cloned;
                };

                // Called by patched SetNode.update() when a setter is renamed
                // oldName comes from SetNode.properties.previousName
                this.renameVar = function (oldName, newName) {
                    if (!oldName || oldName === '') return;
                    const varWidgets = this.widgets.slice(2);
                    let changed = false;
                    for (const w of varWidgets) {
                        if (w.value === oldName) {
                            w.value = newName;
                            changed = true;
                        }
                    }
                    if (changed) {
                        this.updateOutputType();
                        this.setDirtyCanvas(true, true);
                    }
                };

                // Swap two var widgets by index (0-based, relative to var widgets)
                this.swapVars = function (idxA, idxB) {
                    const varWidgets = this.widgets.slice(2);
                    if (idxA < 0 || idxB < 0 || idxA >= varWidgets.length || idxB >= varWidgets.length) return;
                    const tmp = varWidgets[idxA].value;
                    varWidgets[idxA].value = varWidgets[idxB].value;
                    varWidgets[idxB].value = tmp;
                    // Rename widget labels to match positions
                    varWidgets[idxA].name = `var_${idxA + 1}`;
                    varWidgets[idxB].name = `var_${idxB + 1}`;
                    this.updateOutputType();
                    this.setDirtyCanvas(true, true);
                };

                // Move a var widget up (0-based index relative to var widgets)
                this.moveVarUp = function (idx) {
                    if (idx <= 0) return;
                    this.swapVars(idx, idx - 1);
                };

                // Move a var widget down (0-based index relative to var widgets)
                this.moveVarDown = function (idx) {
                    const varWidgets = this.widgets.slice(2);
                    if (idx >= varWidgets.length - 1) return;
                    this.swapVars(idx, idx + 1);
                };

                // Move a var to position 0 (top of priority list)
                this.moveVarToTop = function (idx) {
                    for (let i = idx; i > 0; i--) {
                        this.swapVars(i, i - 1);
                    }
                };

                // Move a var to last position (bottom of priority list)
                this.moveVarToBottom = function (idx) {
                    const varWidgets = this.widgets.slice(2);
                    for (let i = idx; i < varWidgets.length - 1; i++) {
                        this.swapVars(i, i + 1);
                    }
                };

                // Insert an empty var at position (0-based), shift others down
                this.insertVarAt = function (idx) {
                    const varWidgets = this.widgets.slice(2);
                    const maxCount = 20;
                    if (varWidgets.length >= maxCount) {
                        showAlert("Maximum 20 vars reached.");
                        return;
                    }
                    // Increase count
                    const newCount = varWidgets.length + 1;
                    this.properties.varCount = newCount;
                    this.widgets[1].value = String(newCount);
                    this.syncVarWidgets();
                    // Shift values down from end to insertion point
                    const updatedVarWidgets = this.widgets.slice(2);
                    for (let i = updatedVarWidgets.length - 1; i > idx; i--) {
                        updatedVarWidgets[i].value = updatedVarWidgets[i - 1].value;
                    }
                    updatedVarWidgets[idx].value = "";
                    this.updateOutputType();
                    this.setDirtyCanvas(true, true);
                };

                // Widget 0: type filter
                this.addWidget("combo", "type_filter", "*", (value) => {
                    node.refreshVarWidgets();
                    node.updateOutputType();
                }, { values: TYPE_FILTERS });

                // Widget 1: var count (combo for reliable integer selection)
                const VAR_COUNT_OPTIONS = ["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20"];
                this.addWidget("combo", "var_count", "2", (value) => {
                    const count = parseInt(value) || 2;
                    node.properties.varCount = count;
                    node.syncVarWidgets();
                    node.setDirtyCanvas(true, true);
                }, { values: VAR_COUNT_OPTIONS });

                // Output
                this.addOutput("*", "*");

                // Create initial var widgets
                this.syncVarWidgets();

                // Virtual node — does not appear in the execution graph
                this.isVirtualNode = true;
            }

            // Core method: resolve to the first active setter's input link
            getInputLink(slot) {
                if (!this.graph) return null;
                const varWidgets = this.widgets.slice(2);

                for (const w of varWidgets) {
                    const varName = w.value;
                    if (!varName || varName === '') continue;

                    const setter = findSetter(this.graph, varName);
                    if (!setter) continue;
                    if (!isSetterActive(this.graph, setter)) continue;

                    const link = this.graph.links?.[setter.inputs[0].link];
                    if (!link) continue;

                    return link;
                }

                return null;
            }

            onAdded(graph) {
                this.updateOutputType();
            }

            onResize() {
                if (this.outputs?.[0]) this.updateOutputType();
            }

            // Restore var_count on configure (loading from saved workflow)
            onConfigure(data) {
                if (data.properties?.varCount) {
                    this.properties.varCount = data.properties.varCount;
                    this.widgets[1].value = String(data.properties.varCount);
                }
                // Reconstruct var widgets from saved widget values
                const savedWidgets = data.widgets_values;
                if (savedWidgets && savedWidgets.length > 2) {
                    const varCount = savedWidgets.length - 2;
                    this.properties.varCount = varCount;
                    this.widgets[1].value = String(varCount);
                    this.syncVarWidgets();
                    // Restore values
                    for (let i = 0; i < varCount; i++) {
                        if (this.widgets[i + 2]) {
                            this.widgets[i + 2].value = savedWidgets[i + 2] || "";
                        }
                    }
                }
                this.updateOutputType();
            }

            getExtraMenuOptions(_, options) {
                const node = this;
                const menuEntry = this.drawConnection ? "Hide connections" : "Show connections";

                options.unshift(
                    {
                        content: menuEntry,
                        callback: () => {
                            node.drawConnection = !node.drawConnection;
                            // Find the active setter for color
                            const varWidgets = node.widgets.slice(2);
                            for (const w of varWidgets) {
                                const setter = findSetter(node.graph, w.value);
                                if (setter && isSetterActive(node.graph, setter)) {
                                    const linkType = setter.inputs[0].type;
                                    node.slotColor = node.canvas.default_connection_color_byType?.[linkType] || "#FFF";
                                    break;
                                }
                            }
                            node.canvas.setDirty(true, true);
                        },
                    },
                    {
                        content: "Go to active setter",
                        callback: () => {
                            const varWidgets = node.widgets.slice(2);
                            for (const w of varWidgets) {
                                const setter = findSetter(node.graph, w.value);
                                if (setter && isSetterActive(node.graph, setter)) {
                                    node.canvas.centerOnNode(setter);
                                    node.canvas.selectNode(setter, false);
                                    node.canvas.setDirty(true, true);
                                    return;
                                }
                            }
                            showAlert("No active setter found.");
                        },
                    },
                );

                // List all configured setters as submenu
                const varWidgets = this.widgets.slice(2);
                const setterItems = [];
                for (let i = 0; i < varWidgets.length; i++) {
                    const varName = varWidgets[i].value;
                    if (!varName) continue;
                    const setter = findSetter(this.graph, varName);
                    const active = setter && isSetterActive(this.graph, setter);
                    setterItems.push({
                        content: `${i + 1}. ${varName} ${active ? '✓' : '✗'}`,
                        callback: () => {
                            if (setter) {
                                node.canvas.centerOnNode(setter);
                                node.canvas.selectNode(setter, false);
                                node.canvas.setDirty(true, true);
                            }
                        },
                    });
                }
                if (setterItems.length > 0) {
                    options.unshift({
                        content: "Setters",
                        has_submenu: true,
                        submenu: {
                            title: "Priority List",
                            options: setterItems,
                        },
                    });
                }

                // Reorder vars submenu
                const reorderItems = [];
                for (let i = 0; i < varWidgets.length; i++) {
                    const label = varWidgets[i].value || `(empty)`;
                    const subOpts = [];
                    if (i > 0) {
                        subOpts.push({
                            content: "↑ Move to Top",
                            callback: () => { node.moveVarToTop(i); },
                        });
                        subOpts.push({
                            content: "↑ Move Up",
                            callback: () => { node.moveVarUp(i); },
                        });
                    }
                    if (i < varWidgets.length - 1) {
                        subOpts.push({
                            content: "↓ Move Down",
                            callback: () => { node.moveVarDown(i); },
                        });
                        subOpts.push({
                            content: "↓ Move to Bottom",
                            callback: () => { node.moveVarToBottom(i); },
                        });
                    }
                    subOpts.push(null); // separator
                    subOpts.push({
                        content: "＋ Insert Above",
                        callback: () => { node.insertVarAt(i); },
                    });
                    reorderItems.push({
                        content: `${i + 1}. ${label}`,
                        has_submenu: true,
                        submenu: { title: label, options: subOpts },
                    });
                }
                options.unshift({
                    content: "Reorder Vars",
                    has_submenu: true,
                    submenu: { title: "Reorder Vars", options: reorderItems },
                });
            }

            onDrawForeground(ctx, lGraphCanvas) {
                if (this.flags?.collapsed) return;

                // Skip drawing if node is off-screen
                const canvas = lGraphCanvas || this.canvas;
                if (canvas?.visible_area) {
                    const [vx, vy, vw, vh] = canvas.visible_area;
                    const [nx, ny] = this.pos;
                    const [nw, nh] = this.size;
                    if (nx + nw < vx || nx > vx + vw || ny + nh < vy || ny > vy + vh) return;
                }

                if (this.drawConnection) {
                    this._drawVirtualLink(lGraphCanvas, ctx);
                }

                this._drawActiveIndicator(ctx);
            }

            _drawActiveIndicator(ctx) {
                const cached = this.getCachedSetters();
                if (!cached) return;
                for (let i = 0; i < cached.length; i++) {
                    const entry = cached[i];
                    if (!entry || !entry.active) continue;
                    const w = this.widgets[i + 2];
                    if (w?.last_y !== undefined) {
                        ctx.fillStyle = "#4CAF50";
                        ctx.beginPath();
                        ctx.arc(10, w.last_y + LiteGraph.NODE_WIDGET_HEIGHT * 0.5, 4, 0, Math.PI * 2);
                        ctx.fill();
                    }
                    break; // Only first active gets the indicator
                }
            }

            _drawVirtualLink(lGraphCanvas, ctx) {
                const cached = this.getCachedSetters();
                if (!cached) return;
                for (const entry of cached) {
                    if (!entry || !entry.active) continue;
                    const setter = entry.setter;
                    const defaultLink = { type: 'default', color: this.slotColor };
                    let start_node_slotpos = setter.getConnectionPos(false, 0);
                    start_node_slotpos = [
                        start_node_slotpos[0] - this.pos[0],
                        start_node_slotpos[1] - this.pos[1],
                    ];
                    let end_node_slotpos = [0, -LiteGraph.NODE_TITLE_HEIGHT * 0.5];
                    lGraphCanvas.renderLink(
                        ctx,
                        start_node_slotpos,
                        end_node_slotpos,
                        defaultLink,
                        false,
                        null,
                        this.slotColor
                    );
                    break;
                }
            }
        }

        LiteGraph.registerNodeType(
            "GetFirstNode",
            Object.assign(GetFirstNode, {
                title: "Get First",
            })
        );

        GetFirstNode.category = "🌒 Eclipse";
    },

    setup() {
        // Hook into SetNode via LiteGraph prototype patching.
        // Wraps update() on each SetNode instance to detect renames and
        // push them to Eclipse getter nodes (GetFirstNode, GetAllActiveNode).
        const SetNodeType = LiteGraph.registered_node_types?.["SetNode"];
        if (!SetNodeType) return;

        const ECLIPSE_GETTER_TYPES = ['GetFirstNode', 'GetAllActiveNode'];

        function isEclipseGetter(n) {
            return ECLIPSE_GETTER_TYPES.includes(n.type);
        }

        function patchSetNodeInstance(node) {
            if (!node.update || node._eclipsePatched) return;
            node._eclipsePatched = true;
            const origUpdate = node.update;
            node.update = function () {
                const prevName = this.properties?.previousName || '';
                const curName = this.widgets?.[0]?.value || '';

                // Let KJNodes do its normal GetNode refresh
                origUpdate.call(this);

                if (!this.graph) return;

                // Push rename to all Eclipse getter nodes
                if (prevName && curName && prevName !== curName) {
                    for (const n of this.graph._nodes) {
                        if (isEclipseGetter(n) && n.renameVar) {
                            n.renameVar(prevName, curName);
                        }
                    }
                }

                // Refresh combo options on all Eclipse getter nodes
                for (const n of this.graph._nodes) {
                    if (isEclipseGetter(n) && n.refreshVarWidgets) {
                        n.refreshVarWidgets();
                    }
                }
            };
        }

        // Patch instances loaded from saved workflows
        const origOnConfigure = SetNodeType.prototype.onConfigure;
        SetNodeType.prototype.onConfigure = function (...args) {
            origOnConfigure?.apply(this, args);
            patchSetNodeInstance(this);
        };

        // Patch newly created instances (dragged onto canvas)
        const origOnNodeCreated = SetNodeType.prototype.onNodeCreated;
        SetNodeType.prototype.onNodeCreated = function (...args) {
            origOnNodeCreated?.apply(this, args);
            patchSetNodeInstance(this);
        };

        // Patch onRemoved to refresh Eclipse getter combos when a setter is deleted
        const origOnRemoved = SetNodeType.prototype.onRemoved;
        SetNodeType.prototype.onRemoved = function (...args) {
            origOnRemoved?.apply(this, args);
            if (!this.graph) return;
            for (const n of this.graph._nodes) {
                if (isEclipseGetter(n) && n.refreshVarWidgets) {
                    n.refreshVarWidgets();
                }
            }
        };
    },
});
