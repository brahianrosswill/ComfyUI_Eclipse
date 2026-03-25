/* eclipse-combo-chip.js - Shared combo-chip dropdown widget factory for Eclipse nodes.
 *
 * Provides a reusable multi-select chip widget that renders as a compact single row
 * ("N items selected ▼") and opens a floating chip panel on click.
 * Supports pure toggle mode and optional radio groups (mutually exclusive selections,
 * with toggle-off support via radioToggle config option).
 *
 * Usage:
 *   import { injectComboChipCSS, createComboChipWidget } from './eclipse-combo-chip.js';
 *   injectComboChipCSS('sml');
 *   const widget = createComboChipWidget({ node, options, savedValue, origIdx, ... });
 */

import { isVueMode } from './eclipse-widget-performance-utils.js';

// DOM widget margin (px). DomWidgets.vue subtracts 2*margin from computedHeight
// to get the element container height. Keeping this small avoids overflow.
const WIDGET_MARGIN = 2;
// Extra bottom spacing to visually separate from the widget below
const WIDGET_BOTTOM_PAD = 4;
// Visible trigger element height (px) — matches CSS .eclipse-*-combo-trigger
const TRIGGER_HEIGHT = 24;
// Total widget slot height including margins + bottom padding
const WIDGET_TOTAL_HEIGHT = TRIGGER_HEIGHT + 2 * WIDGET_MARGIN + WIDGET_BOTTOM_PAD; // 32

// Inject CSS for a given prefix. Safe to call multiple times — checks the DOM, not just memory.
export function injectComboChipCSS(prefix) {
    const styleId = `eclipse-combo-chip-css-${prefix || 'default'}`;
    if (document.getElementById(styleId)) return;

    const p = prefix ? `${prefix}-` : '';
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
.eclipse-${p}chip {
    cursor: pointer;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 0.95rem;
    font-family: sans-serif;
    user-select: none;
    white-space: nowrap;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
    background: #2a2a2a;
    color: #888;
    border: 1px solid #444;
}
.eclipse-${p}chip:hover {
    background: #363636;
    border-color: #666;
}
.eclipse-${p}chip.selected {
    background: #2a5a3a;
    color: #ddd;
    border-color: #4a8a5a;
}
.eclipse-${p}chip.selected:hover {
    background: #356b46;
}
.eclipse-${p}chip.disabled {
    opacity: 0.35;
    cursor: not-allowed;
    border-style: dashed;
}
.eclipse-${p}combo-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: calc(100% - 26px);
    height: 24px;
    margin: 0 auto 4px auto;
    padding: 0 10px;
    background: #1a3324;
    border: 1px solid #2a5a3a;
    border-radius: 4px;
    color: #aaa;
    font-size: 0.75rem;
    font-family: sans-serif;
    cursor: pointer;
    box-sizing: border-box;
    user-select: none;
}
.eclipse-${p}combo-trigger:hover {
    border-color: #3a6a4a;
    background: #213d2c;
}
.eclipse-${p}combo-trigger .arrow {
    font-size: 0.65rem;
    margin-left: 6px;
    color: #888;
}
.eclipse-${p}chip-panel {
    position: fixed;
    z-index: 100000;
    background: #1e1e1e;
    border: 1px solid #555;
    border-radius: 6px;
    padding: 6px;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    max-width: 320px;
}
`;
    document.head.appendChild(style);
}

// Find the radio group a feature belongs to, or null
function findRadioGroup(feature, radioGroups) {
    if (!radioGroups) return null;
    for (const group of radioGroups) {
        if (group.includes(feature)) return group;
    }
    return null;
}

// Create a combo-chip multi-select widget.
//
// config:
//   node           - LiteGraph node instance
//   options        - string[] of available chip options
//   savedValue     - initial selection (Array or Set)
//   origIdx        - widget insertion index
//   widgetName     - widget name (default: 'features')
//   cssPrefix      - CSS class prefix, e.g. 'sml' → 'eclipse-sml-chip' (default: '' → 'eclipse-chip')
//   radioGroups    - optional array of arrays for mutually exclusive selections, e.g. [['image','video']]
//   radioToggle    - if true, clicking a selected radio chip deselects it (default: false)
//   serialize      - whether widget serializes (default: true, set false for cosmetic overlay widgets)
//   onSelectionChange - optional callback(selectedSet) called after any chip toggle
//
// Returns the created DOMWidget.
export function createComboChipWidget(config) {
    const {
        node,
        options: featureOptions,
        savedValue,
        origIdx,
        widgetName = 'features',
        cssPrefix = '',
        radioGroups = null,
        radioToggle = false,
        serialize = true,
        onSelectionChange = null,
        disabledChips = null,
    } = config;

    const p = cssPrefix ? `${cssPrefix}-` : '';
    let selectedSet = new Set(savedValue);
    let disabledSet = new Set(disabledChips);
    let panel = null;

    // Remove any disabled chips from initial selection
    for (const d of disabledSet) selectedSet.delete(d);

    // Trigger bar (always visible, single row)
    // Critical styles applied inline to avoid CSS cascade race conditions
    // with Vue's DOMWidgetImpl. Class styles handle hover only.
    const trigger = document.createElement('div');
    trigger.className = `eclipse-${p}combo-trigger`;
    Object.assign(trigger.style, {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        width: 'calc(100% - 26px)',
        height: '24px',
        margin: '0 auto 4px auto',
        padding: '0 10px',
        background: '#1a3324',
        border: '1px solid #2a5a3a',
        borderRadius: '4px',
        color: '#aaa',
        fontSize: '0.75rem',
        fontFamily: 'sans-serif',
        cursor: 'pointer',
        boxSizing: 'border-box',
        userSelect: 'none',
    });
    function updateLabel() {
        const n = selectedSet.size;
        trigger.innerHTML = `<span>${n} item${n !== 1 ? 's' : ''} selected</span><span class="arrow">▼</span>`;
    }
    updateLabel();

    let featWidget;

    function closePanel() {
        if (panel) {
            panel.remove();
            panel = null;
        }
    }

    function openPanel() {
        if (panel) { closePanel(); return; }
        panel = document.createElement('div');
        panel.className = `eclipse-${p}chip-panel`;

        for (const opt of featureOptions) {
            const chip = document.createElement('span');
            const isDisabled = disabledSet.has(opt);
            chip.className = `eclipse-${p}chip`
                + (selectedSet.has(opt) ? ' selected' : '')
                + (isDisabled ? ' disabled' : '');
            chip.textContent = opt;
            chip.addEventListener('pointerdown', (e) => {
                e.stopPropagation();
                e.preventDefault();
                if (disabledSet.has(opt)) return;

                const radioGroup = findRadioGroup(opt, radioGroups);
                if (radioGroup) {
                    if (selectedSet.has(opt)) {
                        // Already selected: toggle off only if radioToggle is enabled
                        if (radioToggle) selectedSet.delete(opt);
                        else return;
                    } else {
                        for (const sibling of radioGroup) selectedSet.delete(sibling);
                        selectedSet.add(opt);
                    }
                } else {
                    // Toggle
                    if (selectedSet.has(opt)) selectedSet.delete(opt);
                    else selectedSet.add(opt);
                }

                // Update all chip visuals
                for (const c of panel.children) {
                    c.classList.toggle('selected', selectedSet.has(c.textContent));
                    c.classList.toggle('disabled', disabledSet.has(c.textContent));
                }
                updateLabel();
                featWidget.callback?.(featWidget.value);
            });
            panel.appendChild(chip);
        }

        // Position below trigger
        const rect = trigger.getBoundingClientRect();
        panel.style.left = `${rect.left}px`;
        panel.style.top = `${rect.bottom + 2}px`;
        panel.style.minWidth = `${rect.width}px`;
        document.body.appendChild(panel);

        // Close on outside click
        const onOutside = (e) => {
            if (panel && !panel.contains(e.target) && !trigger.contains(e.target)) {
                closePanel();
                document.removeEventListener('pointerdown', onOutside, true);
            }
        };
        requestAnimationFrame(() => {
            document.addEventListener('pointerdown', onOutside, true);
        });
    }

    trigger.addEventListener('pointerdown', (e) => {
        e.stopPropagation();
        e.preventDefault();
        openPanel();
    });

    const widgetOpts = {
        getValue: () => [...selectedSet],
        setValue: (v) => {
            const arr = Array.isArray(v) ? v : [];
            selectedSet = new Set(arr.filter((x) => featureOptions.includes(x) && !disabledSet.has(x)));
            updateLabel();
            if (panel) {
                for (const c of panel.children) {
                    c.classList.toggle('selected', selectedSet.has(c.textContent));
                    c.classList.toggle('disabled', disabledSet.has(c.textContent));
                }
            }
        },
        getMinHeight: () => WIDGET_TOTAL_HEIGHT,
        getMaxHeight: () => WIDGET_TOTAL_HEIGHT,
        margin: WIDGET_MARGIN,
    };
    if (!serialize) widgetOpts.serialize = false;

    featWidget = node.addDOMWidget(widgetName, 'custom', trigger, widgetOpts);
    featWidget.computedHeight = WIDGET_TOTAL_HEIGHT;

    // In Vue Nodes 2.0, DOMWidgetImpl.computeLayoutSize makes hasLayoutSize=true,
    // which gives this widget an 'auto' grid row that absorbs extra node height.
    // Override to undefined so the row becomes 'min-content' (exactly 24px).
    // In classic mode, keep computeLayoutSize so _arrangeWidgets allocates the
    // correct height (WIDGET_TOTAL_HEIGHT) for the DOM container.
    if (isVueMode()) {
        featWidget.computeLayoutSize = undefined;
    }

    // Clean up panel when widget is removed
    const origOnRemove = featWidget.onRemove;
    featWidget.onRemove = function () {
        closePanel();
        origOnRemove?.call(this);
    };

    // Reposition widget to desired index
    const newIdx = node.widgets.indexOf(featWidget);
    if (newIdx >= 0 && newIdx !== origIdx) {
        node.widgets.splice(newIdx, 1);
        node.widgets.splice(origIdx, 0, featWidget);
    }

    // Dynamically update which chips are disabled (grayed out / unclickable).
    // Disabled chips are automatically deselected.
    featWidget.setDisabledChips = (chips) => {
        disabledSet = new Set(chips);
        let changed = false;
        for (const d of disabledSet) {
            if (selectedSet.has(d)) { selectedSet.delete(d); changed = true; }
        }
        if (changed) {
            updateLabel();
            featWidget.callback?.(featWidget.value);
        }
        if (panel) {
            for (const c of panel.children) {
                c.classList.toggle('disabled', disabledSet.has(c.textContent));
                c.classList.toggle('selected', selectedSet.has(c.textContent));
            }
        }
    };

    return featWidget;
}
