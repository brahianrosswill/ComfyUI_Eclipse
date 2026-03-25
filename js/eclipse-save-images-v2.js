/* eclipse-save-images-v2.js - Combo-chip feature toggles for Save Images v2 [Eclipse] */
import { app } from './comfy/index.js';
import {
    createWidgetVisibilityManager,
} from './eclipse-widget-performance-utils.js';
import { injectComboChipCSS, createComboChipWidget as _createComboChipWidget } from './eclipse-combo-chip.js';

const NODE_NAME = 'Save Images v2 [Eclipse]';

// Feature options for the combo-chip selector
const FEATURE_OPTIONS = [
    'save', 'optimize', 'lossless_webp', 'embed_workflow',
    'save_gen_data', 'remove_prompts', 'save_json', 'loras_to_prompt',
    'show_previews', 'quality', 'dpi', 'output', 'filename',
];

// Default active chips
const DEFAULT_FEATURES = [
    'save', 'embed_workflow', 'save_gen_data', 'output', 'filename',
];

// Chip name → backing widget name
const CHIP_TO_BACKING = {
    'save':        'save_to_disk',
    'optimize':      'optimize_image',
    'lossless_webp': 'lossless_webp',
    'embed_workflow': 'embed_workflow',
    'save_gen_data': 'save_generation_data',
    'remove_prompts': 'remove_prompts',
    'save_json':     'save_workflow_as_json',
    'loras_to_prompt': 'add_loras_to_prompt',
    'show_previews': 'show_previews',
    'quality':       'use_quality',
    'dpi':           'use_dpi',
    'output':        'use_output',
    'filename':      'use_filename',
};

// All backing widget names (always hidden, chips replace them)
const BACKING_WIDGETS = Object.values(CHIP_TO_BACKING);

// Visibility chips → which value widgets they show/hide
const VISIBILITY_MAP = {
    'output':   ['output_path'],
    'filename': ['filename_prefix', 'filename_delimiter', 'filename_number_padding', 'filename_number_start', 'extension'],
    'quality':  ['quality'],
    'dpi':      ['dpi'],
};

injectComboChipCSS('si');

// Sync chip state → hidden backing widgets for serialization
function syncChipsToBacking(selectedSet, node) {
    for (const [chip, backing] of Object.entries(CHIP_TO_BACKING)) {
        const w = node.widgets?.find((w) => w.name === backing);
        if (w && w.value !== selectedSet.has(chip)) w.value = selectedSet.has(chip);
    }
}

// Read chip state from hidden backing widgets (for configure/load)
function readChipsFromBacking(node) {
    const chips = new Set();
    for (const [chip, backing] of Object.entries(CHIP_TO_BACKING)) {
        const w = node.widgets?.find((w) => w.name === backing);
        if (w && w.value) chips.add(chip);
    }
    return chips;
}

function createComboChipWidget(node, initialSet, origIdx) {
    return _createComboChipWidget({
        node, options: FEATURE_OPTIONS, savedValue: initialSet, origIdx,
        widgetName: '_si_features', cssPrefix: 'si', serialize: false,
    });
}

// Visibility update based on chip state
function updateVisibility(node, vis) {
    if (node.id === -1) return;

    const featW = node.widgets?.find((w) => w.name === '_si_features');
    const selected = featW ? new Set(featW.value) : readChipsFromBacking(node);

    // Hide all backing widgets (always hidden, replaced by chips)
    for (const name of BACKING_WIDGETS) vis.setVisible(name, false);

    // Show/hide value widgets based on visibility chips
    for (const [chip, widgetNames] of Object.entries(VISIBILITY_MAP)) {
        const isActive = selected.has(chip);
        for (const wName of widgetNames) {
            vis.setVisible(wName, isActive);
        }
    }
}

app.registerExtension({
    name: 'Eclipse.SaveImagesV2',
    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== NODE_NAME) return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const ret = origOnNodeCreated ? origOnNodeCreated.apply(this, arguments) : void 0;
            const node = this;

            const vis = createWidgetVisibilityManager(node);
            node._Eclipse_vis = vis;

            // Read initial chip state from backing widgets (handles loaded workflows)
            const initialSet = readChipsFromBacking(node);
            const hasAnyBacking = BACKING_WIDGETS.some((name) => {
                const w = node.widgets?.find((w) => w.name === name);
                return w && w.value === true;
            });
            const chipSet = hasAnyBacking ? initialSet : new Set(DEFAULT_FEATURES);

            // Insert chip widget at top of node
            const origIdx = 0;
            const featWidget = createComboChipWidget(node, chipSet, origIdx);

            featWidget.callback = () => {
                const selected = new Set(featWidget.value);
                // Auto-enable save when output or filename is activated
                if ((selected.has('output') || selected.has('filename')) && !selected.has('save')) {
                    selected.add('save');
                    featWidget.value = [...selected];
                }
                syncChipsToBacking(selected, node);
                updateVisibility(node, vis);
            };

            // Sync initial state
            syncChipsToBacking(chipSet, node);

            // Apply visibility after all widgets are created
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    updateVisibility(node, vis);
                }
            }, 0);

            // Restore on configure (loading saved workflows)
            const origConfigure = node.onConfigure;
            node.onConfigure = function (data) {
                origConfigure?.apply(this, arguments);
                vis.clearCache?.();
                const chips = readChipsFromBacking(node);
                featWidget.value = [...chips];
                setTimeout(() => updateVisibility(node, vis), 100);
            };

            return ret;
        };
    },
});
