/**
 * eclipse-getallactive.js - GetAllActive virtual node for ComfyUI Eclipse
 *
 * A virtual node that resolves ALL active (not muted, connected) SetNode
 * vars from a user-defined list. Each var gets its own output slot.
 * Connect the outputs to a Join String node for concatenation.
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
        summary: "Eclipse GetAll",
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
    if (setter.mode === 2) return false;
    if (!setter.inputs?.[0]?.link) return false;
    const link = graph.links?.[setter.inputs[0].link];
    if (!link) return false;
    const sourceNode = graph._nodes_by_id?.[link.origin_id];
    if (!sourceNode) return false;
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
    name: "Eclipse.GetAllActiveNode",
    registerCustomNodes() {
        class GetAllActiveNode extends LGraphNode {
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
                const VAR_WIDGET_START = 2; // after type_filter and var_count

                // Get filtered var names for combo options
                this.getFilteredVars = function () {
                    const typeFilter = this.widgets?.[0]?.value || '*';
                    return getSetterVars(this.graph, typeFilter);
                };

                // Create a var combo widget with proper callback
                this.createVarWidget = function (index) {
                    this.addWidget("combo", `var_${index}`, "", (value) => {
                        node.updateOutputTypes();
                    }, {
                        values: () => {
                            const vars = node.getFilteredVars();
                            return ["", ...vars];
                        }
                    });
                };

                // Sync var widgets AND outputs to match var_count
                this.syncVarWidgets = function () {
                    const targetCount = Math.max(1, Math.min(10, this.properties.varCount || 2));

                    // Sync widgets
                    const existingVarWidgets = this.widgets.slice(VAR_WIDGET_START);
                    const currentCount = existingVarWidgets.length;

                    if (currentCount < targetCount) {
                        for (let i = currentCount; i < targetCount; i++) {
                            this.createVarWidget(i + 1);
                        }
                    } else if (currentCount > targetCount) {
                        const keepWidgets = this.widgets.slice(0, VAR_WIDGET_START + targetCount);
                        this.widgets.length = 0;
                        for (const w of keepWidgets) {
                            this.widgets.push(w);
                        }
                    }

                    // Sync outputs to match var count
                    this.syncOutputs(targetCount);

                    const computed = this.computeSize();
                    this.setSize([Math.max(this.size[0], computed[0]), computed[1]]);
                };

                // Sync output slots to match var count
                this.syncOutputs = function (targetCount) {
                    const currentOutputs = this.outputs?.length || 0;

                    if (currentOutputs < targetCount) {
                        for (let i = currentOutputs; i < targetCount; i++) {
                            this.addOutput(`out_${i + 1}`, '*');
                        }
                    } else if (currentOutputs > targetCount) {
                        // Remove excess outputs from end
                        while (this.outputs.length > targetCount) {
                            this.removeOutput(this.outputs.length - 1);
                        }
                    }

                    // Update output names/types from var widgets
                    this.updateOutputTypes();
                };

                // Refresh all var widget options (when type filter changes)
                this.refreshVarWidgets = function () {
                    this.setDirtyCanvas(true, true);
                };

                // Update ALL output types based on their respective setter types
                this.updateOutputTypes = function () {
                    if (!this.outputs || this.outputs.length === 0) return;
                    const typeFilter = this.widgets?.[0]?.value || '*';
                    const varWidgets = this.widgets.slice(VAR_WIDGET_START);

                    for (let i = 0; i < this.outputs.length; i++) {
                        const varName = varWidgets[i]?.value || '';
                        let type = '*';

                        if (typeFilter !== '*') {
                            type = typeFilter;
                        } else if (varName) {
                            const setter = findSetter(this.graph, varName);
                            if (setter?.inputs?.[0]?.type && setter.inputs[0].type !== '*') {
                                type = setter.inputs[0].type;
                            }
                        }

                        this.outputs[i].type = type;
                        this.outputs[i].name = varName || `out_${i + 1}`;
                    }

                    // Color by resolved type (use first valid)
                    if (app.ui.settings.getSettingValue("KJNodes.nodeAutoColor")) {
                        const resolvedType = typeFilter !== '*' ? typeFilter
                            : this.outputs.find(o => o.type !== '*')?.type;
                        if (resolvedType) applyColor(this, resolvedType);
                    }
                };

                this.clone = function () {
                    const cloned = GetAllActiveNode.prototype.clone.apply(this);
                    cloned.setSize(cloned.computeSize());
                    return cloned;
                };

                // Called by SetNode patch when a setter is renamed
                this.renameVar = function (oldName, newName) {
                    if (!oldName || oldName === '') return;
                    const varWidgets = this.widgets.slice(VAR_WIDGET_START);
                    let changed = false;
                    for (const w of varWidgets) {
                        if (w.value === oldName) {
                            w.value = newName;
                            changed = true;
                        }
                    }
                    if (changed) {
                        this.updateOutputTypes();
                        this.setDirtyCanvas(true, true);
                    }
                };

                // Widget 0: type filter
                this.addWidget("combo", "type_filter", "*", (value) => {
                    node.refreshVarWidgets();
                    node.updateOutputTypes();
                }, { values: TYPE_FILTERS });

                // Widget 1: var count
                const VAR_COUNT_OPTIONS = ["1","2","3","4","5","6","7","8","9","10"];
                this.addWidget("combo", "var_count", "2", (value) => {
                    const count = parseInt(value) || 2;
                    node.properties.varCount = count;
                    node.syncVarWidgets();
                    node.setDirtyCanvas(true, true);
                }, { values: VAR_COUNT_OPTIONS });

                // Create initial outputs and var widgets
                this.syncVarWidgets();

                this.isVirtualNode = true;
            }

            // Core: resolve each output slot to its var's setter link
            getInputLink(slot) {
                if (!this.graph) return null;
                const VAR_WIDGET_START = 2;
                const varWidget = this.widgets?.[VAR_WIDGET_START + slot];
                if (!varWidget) return null;

                const varName = varWidget.value;
                if (!varName || varName === '') return null;

                const setter = findSetter(this.graph, varName);
                if (!setter) return null;
                if (!isSetterActive(this.graph, setter)) return null;

                const link = this.graph.links?.[setter.inputs[0].link];
                return link || null;
            }

            onAdded(graph) {
                this.updateOutputTypes();
            }

            onResize() {
                if (this.outputs?.length > 0) this.updateOutputTypes();
            }

            onConfigure(data) {
                if (data.properties?.varCount) {
                    this.properties.varCount = data.properties.varCount;
                    this.widgets[1].value = String(data.properties.varCount);
                }
                const savedWidgets = data.widgets_values;
                if (savedWidgets && savedWidgets.length > 2) {
                    const varCount = savedWidgets.length - 2;
                    this.properties.varCount = varCount;
                    this.widgets[1].value = String(varCount);
                    this.syncVarWidgets();
                    for (let i = 0; i < varCount; i++) {
                        if (this.widgets[i + 2]) {
                            this.widgets[i + 2].value = savedWidgets[i + 2] || "";
                        }
                    }
                }
                this.updateOutputTypes();
            }

            getExtraMenuOptions(_, options) {
                const node = this;
                const menuEntry = this.drawConnection ? "Hide connections" : "Show connections";

                options.unshift(
                    {
                        content: menuEntry,
                        callback: () => {
                            node.drawConnection = !node.drawConnection;
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
                            title: "Var List",
                            options: setterItems,
                        },
                    });
                }
            }

            onDrawForeground(ctx, lGraphCanvas) {
                if (this.flags?.collapsed) return;

                if (this.drawConnection) {
                    this._drawVirtualLinks(lGraphCanvas, ctx);
                }

                this._drawActiveIndicators(ctx);
            }

            // Green dots on ALL active vars (not just first)
            _drawActiveIndicators(ctx) {
                if (!this.graph) return;
                const varWidgets = this.widgets.slice(2);
                for (let i = 0; i < varWidgets.length; i++) {
                    const varName = varWidgets[i].value;
                    if (!varName || varName === '') continue;
                    const setter = findSetter(this.graph, varName);
                    if (setter && isSetterActive(this.graph, setter)) {
                        const w = varWidgets[i];
                        if (w.last_y !== undefined) {
                            ctx.fillStyle = "#4CAF50";
                            ctx.beginPath();
                            ctx.arc(10, w.last_y + LiteGraph.NODE_WIDGET_HEIGHT * 0.5, 4, 0, Math.PI * 2);
                            ctx.fill();
                        }
                    }
                }
            }

            // Draw virtual links to ALL active setters
            _drawVirtualLinks(lGraphCanvas, ctx) {
                if (!this.graph) return;
                const varWidgets = this.widgets.slice(2);
                for (let i = 0; i < varWidgets.length; i++) {
                    const varName = varWidgets[i].value;
                    if (!varName || varName === '') continue;
                    const setter = findSetter(this.graph, varName);
                    if (setter && isSetterActive(this.graph, setter)) {
                        const defaultLink = { type: 'default', color: this.slotColor };
                        let start_node_slotpos = setter.getConnectionPos(false, 0);
                        start_node_slotpos = [
                            start_node_slotpos[0] - this.pos[0],
                            start_node_slotpos[1] - this.pos[1],
                        ];
                        // Target the corresponding output slot
                        const outPos = this.getConnectionPos(false, i);
                        let end_node_slotpos = [
                            outPos[0] - this.pos[0],
                            outPos[1] - this.pos[1],
                        ];
                        lGraphCanvas.renderLink(
                            ctx,
                            start_node_slotpos,
                            end_node_slotpos,
                            defaultLink,
                            false,
                            null,
                            this.slotColor
                        );
                    }
                }
            }
        }

        LiteGraph.registerNodeType(
            "GetAllActiveNode",
            Object.assign(GetAllActiveNode, {
                title: "Get All Active",
            })
        );

        GetAllActiveNode.category = "🌒 Eclipse";
    },
});
