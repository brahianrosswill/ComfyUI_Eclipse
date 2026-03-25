/* eclipse-lora-stack.js - Inline mode-bar + widget visibility for Lora Stack [Eclipse] */
import { app } from './comfy/index.js';
import {
    smartResize,
    createWidgetVisibilityManager,
} from './eclipse-widget-performance-utils.js';

const NODE_NAME = 'Lora Stack [Eclipse]';

const MODE_OPTIONS = ['standard', 'model_only', 'simple'];
const DEFAULT_MODE = 'standard';

// --- Inject inline mode-bar CSS once ---
let _cssInjected = false;
function injectModeBarCSS() {
    if (_cssInjected) return;
    _cssInjected = true;
    const style = document.createElement('style');
    style.textContent = `
.eclipse-ls-mode-bar {
    display: flex; align-items: center; gap: 4px;
    width: 100%; height: 100%; padding: 0 6px; box-sizing: border-box;
}
.eclipse-ls-mode-chip {
    cursor: pointer; padding: 2px 10px; border-radius: 4px;
    font-size: 0.75rem; font-family: sans-serif; user-select: none;
    background: #2a2a2a; color: #888; border: 1px solid #444;
    flex: 1; text-align: center;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.eclipse-ls-mode-chip.selected {
    background: #2a5a3a; color: #ddd; border-color: #4a8a5a;
}`;
    document.head.appendChild(style);
}
injectModeBarCSS();

app.registerExtension({
    name: 'Eclipse.LoraStack',
    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== NODE_NAME) return;

        const origCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const ret = origCreated?.apply(this, arguments);
            const node = this;

            const vis = createWidgetVisibilityManager(node);
            const d = (name, show) => vis.setVisible(name, show);
            const gv = (name) => vis.getValue(name);

            // --- Read current mode from backing widget ---
            const modeW = node.widgets?.find((w) => w.name === 'mode');
            const origIdx = modeW ? node.widgets.indexOf(modeW) : 0;

            // Hide backing combo (it still serializes)
            if (modeW) {
                modeW.hidden = true;
                if (modeW.options) modeW.options.hidden = true;
            }

            let currentMode = (modeW && MODE_OPTIONS.includes(modeW.value)) ? modeW.value : DEFAULT_MODE;

            // --- Build inline mode-bar (chips directly visible on node) ---
            const bar = document.createElement('div');
            bar.className = 'eclipse-ls-mode-bar';

            const chipEls = [];
            for (const opt of MODE_OPTIONS) {
                const chip = document.createElement('span');
                chip.className = 'eclipse-ls-mode-chip' + (opt === currentMode ? ' selected' : '');
                chip.textContent = opt;
                chip.addEventListener('pointerdown', (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (opt === currentMode) return;
                    currentMode = opt;
                    for (const c of chipEls) c.classList.toggle('selected', c.textContent === currentMode);
                    if (modeW) modeW.value = currentMode;
                    updateVisibility();
                });
                chipEls.push(chip);
                bar.appendChild(chip);
            }

            const modeBarWidget = node.addDOMWidget('_ls_mode', 'custom', bar, {
                getValue: () => currentMode,
                setValue: (v) => {
                    if (MODE_OPTIONS.includes(v)) {
                        currentMode = v;
                        for (const c of chipEls) c.classList.toggle('selected', c.textContent === currentMode);
                    }
                },
                getMinHeight: () => 26,
                getMaxHeight: () => 26,
                serialize: false,
            });

            // Reposition to where backing mode widget was
            const newIdx = node.widgets.indexOf(modeBarWidget);
            if (newIdx >= 0 && newIdx !== origIdx) {
                node.widgets.splice(newIdx, 1);
                node.widgets.splice(origIdx, 0, modeBarWidget);
            }

            // --- Visibility logic ---
            const updateVisibility = () => {
                if (node.id === -1) return;

                const hideClip = currentMode === 'model_only' || currentMode === 'simple';
                const count = gv('lora_count') || 5;

                for (let i = 1; i <= 10; i++) {
                    const show = i <= count;
                    d(`switch_${i}`, show);
                    d(`lora_name_${i}`, show);
                    d(`model_weight_${i}`, show);
                    d(`clip_weight_${i}`, show && !hideClip);
                }
                smartResize(node);
            };

            // lora_count callback
            const lcW = node.widgets?.find((w) => w.name === 'lora_count');
            if (lcW) {
                const origCb = lcW.callback;
                lcW.callback = function () {
                    origCb?.apply(this, arguments);
                    updateVisibility();
                };
            }

            // Initial visibility
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    updateVisibility();
                }
            }, 0);

            // Configure handler (load workflow)
            const origConfigure = node.onConfigure;
            node.onConfigure = function (data) {
                origConfigure?.apply(this, arguments);
                setTimeout(() => {
                    // Backward compat: migrate old model_only_lora/simple booleans to mode
                    if (data?.widgets_values) {
                        const wv = data.widgets_values;
                        if (typeof wv[0] === 'boolean') {
                            const modelOnly = wv[0];
                            const simple = wv[1];
                            currentMode = modelOnly ? 'model_only' : simple ? 'simple' : 'standard';
                            if (modeW) modeW.value = currentMode;
                        }
                    }
                    // Restore from backing widget after workflow load
                    if (modeW && MODE_OPTIONS.includes(modeW.value)) {
                        currentMode = modeW.value;
                    }
                    for (const c of chipEls) c.classList.toggle('selected', c.textContent === currentMode);
                    updateVisibility();
                }, 100);
            };

            return ret;
        };
    },
});
