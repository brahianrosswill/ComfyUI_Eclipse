/* eclipse-replace-string-v3.js - Multi-select chip widget + visibility for Replace String v3 [Eclipse] */
import { app } from './comfy/index.js';
import {
    debounce,
    smartResize,
    createWidgetVisibilityManager,
    isVueMode,
    onVueModeChange,
} from './eclipse-widget-performance-utils.js';
import { injectComboChipCSS, createComboChipWidget as _createComboChipWidget } from './eclipse-combo-chip.js';

const NODE_NAME = 'Replace String v3 [Eclipse]';

// Must match Python FEATURE_OPTIONS order
const FEATURE_OPTIONS = [
    'instructions', 'list_first', 'list_to_string',
    'image_style', 'shot_style', 'subject', 'background', 'mood', 'lighting',
    'age', 'watermark', 'cleanup',
];
const DEFAULT_FEATURES = [];

injectComboChipCSS('rsv3');

// Widgets controlled by features
const FEATURE_WIDGETS = {
    age: ['age'],
};

function createComboChipWidget(node, savedValue, origIdx) {
    return _createComboChipWidget({ node, options: FEATURE_OPTIONS, savedValue, origIdx, cssPrefix: 'rsv3' });
}

app.registerExtension({
    name: 'Eclipse.ReplaceStringV3',
    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== NODE_NAME) return;
        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const ret = origOnNodeCreated ? origOnNodeCreated.apply(this, arguments) : void 0;
            const node = this;
            const vis = createWidgetVisibilityManager(node);
            node._Eclipse_vis = vis;
            const d = (name, show) => vis.setVisible(name, show);

            // --- Features multi-select setup (dual-path) ---
            const autoFeaturesW = node.widgets?.find(w => w.name === 'features');
            let featWidget;

            if (isVueMode()) {
                // Nodes 2.0: replace ComponentWidgetImpl with combo-chip dropdown
                const origIdx = autoFeaturesW ? node.widgets.indexOf(autoFeaturesW) : 0;
                let savedValue = DEFAULT_FEATURES.slice();
                if (autoFeaturesW) {
                    if (Array.isArray(autoFeaturesW.value) && autoFeaturesW.value.length > 0) {
                        savedValue = autoFeaturesW.value.slice();
                    }
                    autoFeaturesW.onRemove?.();
                    node.widgets.splice(origIdx, 1);
                }
                featWidget = createComboChipWidget(node, savedValue, 0);
            } else {
                // Classic mode: hide native multi-select, use combo-chip dropdown
                let savedValue = DEFAULT_FEATURES.slice();
                if (autoFeaturesW) {
                    if (Array.isArray(autoFeaturesW.value) && autoFeaturesW.value.length > 0) {
                        savedValue = autoFeaturesW.value.slice();
                    }
                    autoFeaturesW.hidden = true;
                    if (autoFeaturesW.options) autoFeaturesW.options.hidden = true;
                    if (Array.isArray(autoFeaturesW.value) && autoFeaturesW.value.length === 0) {
                        autoFeaturesW.value = savedValue.slice();
                    }
                }
                featWidget = createComboChipWidget(node, savedValue, 0);
                node._Eclipse_backingFeaturesW = autoFeaturesW;
            }

            const updateVisibility = () => {
                if (node.id === -1) return;
                const raw = vis.getValue('features');
                const feats = new Set(Array.isArray(raw) ? raw : []);

                // age widget only visible when age feature is selected
                d('age', feats.has('age'));

                smartResize(node);
            };

            const debouncedUpdate = debounce(updateVisibility, 100);

            // --- Features callback ---
            const origFeatCallback = featWidget?.callback;
            if (featWidget) {
                featWidget.callback = function (value) {
                    origFeatCallback?.call(this, value);
                    if (node._Eclipse_backingFeaturesW) {
                        node._Eclipse_backingFeaturesW.value = featWidget.value;
                    }
                    updateVisibility();
                };
            }

            // Initialize
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    updateVisibility();
                }
            }, 0);

            const origOnConfigure = node.onConfigure;
            node.onConfigure = function (config) {
                origOnConfigure && origOnConfigure.apply(this, arguments);
                setTimeout(() => { updateVisibility(); }, 100);
            };

            return ret;
        };
    },

    async setup() {
        onVueModeChange(() => {
            const graph = app.graph;
            if (!graph?._nodes) return;
            for (let i = 0; i < graph._nodes.length; i++) {
                const n = graph._nodes[i];
                if (n.comfyClass === NODE_NAME) {
                    try {
                        const savedWidgets = {};
                        n.widgets?.forEach(w => { savedWidgets[w.name] = w.value; });
                        n.onNodeCreated?.call(n);
                        n.widgets?.forEach(w => { if (savedWidgets[w.name] !== undefined) w.value = savedWidgets[w.name]; });
                    } catch (e) { console.warn('[Replace String v3] mode switch recreate error:', e); }
                }
            }
            graph.setDirtyCanvas?.(true, true);
        });
    },
});
