/** Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*     http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/

import { app } from './comfy/index.js';

const NODE_NAME = "Prompt Styler [Eclipse]";

// Special mode constants
const MODE_RANDOM = -1;
const MODE_INCREMENT = -2;
const MODE_DECREMENT = -3;

// Track style count per node (for index max clamping)
const nodeStyleCounts = new Map();

app.registerExtension({
    name: "Eclipse.PromptStyler",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) return;
        
        // // // console.log("[PromptStyler] Registering extension");
        
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const node = this;
            const nodeId = node.id;
            
            // Helper function to hide/show a widget
            const setWidgetVisible = (widgetName, visible) => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                if (!widget) return;
                
                if (visible) {
                    // Show widget - restore original type
                    if (widget.origType) {
                        widget.type = widget.origType;
                    }
                    delete widget.computeSize;
                } else {
                    // Hide widget - save original type first and make it tiny
                    if (widget.type !== "converted-widget" && !widget.origType) {
                        widget.origType = widget.type;
                    }
                    widget.type = "converted-widget";
                    widget.computeSize = () => [0, -4];
                }
            };
            
            // Get widgets
            const getWidget = (name) => node.widgets?.find(w => w.name === name);
            
            const styleModeWidget = getWidget("style_mode");
            const styleWidget = getWidget("style");
            const indexWidget = getWidget("index");
            const spacesToUnderscoresWidget = getWidget("spaces_to_underscores");
            
            if (!styleWidget || !indexWidget) {
                console.warn("[PromptStyler] Required widgets not found");
                return r;
            }
            
            // Store references for graphToPrompt hook
            node._Eclipse_indexWidget = indexWidget;
            node._Eclipse_styleWidget = styleWidget;
            node._Eclipse_lastResolvedIndex = null;  // Last index resolved in graphToPrompt
            node._Eclipse_manualIndex = null;  // Manually set index (for "Use Last Queued")
            node._Eclipse_updatingIndex = false;  // Flag to track when system is updating index (vs user)
            node._Eclipse_updatingStyle = false;  // Flag to track when system is updating style (vs user)
            
            // Update visibility of max_words_to_combine based on spaces_to_underscores
            const updateMaxWordsVisibility = () => {
                const spacesToUnderscores = spacesToUnderscoresWidget?.value ?? false;
                setWidgetVisible("max_words_to_combine", spacesToUnderscores);
                const newSize = node.computeSize();
                node.setSize([node.size[0], newSize[1]]);
                app.graph.setDirtyCanvas(true);
            };
            
            // Add callback for spaces_to_underscores widget
            if (spacesToUnderscoresWidget) {
                const originalSpacesCallback = spacesToUnderscoresWidget.callback;
                spacesToUnderscoresWidget.callback = function(value) {
                    if (originalSpacesCallback) {
                        originalSpacesCallback.apply(this, arguments);
                    }
                    updateMaxWordsVisibility();
                };
            }
            
            // Get the style options from the combo widget
            const getStyleOptions = () => {
                return styleWidget.options?.values || [];
            };
            
            // Update style count when styles change
            const updateStyleCount = () => {
                const styles = getStyleOptions();
                nodeStyleCounts.set(nodeId, styles.length);
                if (indexWidget.options) {
                    indexWidget.options.max = Math.max(0, styles.length - 1);
                }
            };
            
            // Fetch styles for a specific mode from the server
            const fetchStylesForMode = async (mode) => {
                try {
                    const response = await fetch(`/eclipse/prompt_styler/styles/${mode}`);
                    if (!response.ok) {
                        console.error(`[PromptStyler] Failed to fetch styles for mode ${mode}`);
                        return null;
                    }
                    const data = await response.json();
                    return data.styles || [];
                } catch (error) {
                    console.error(`[PromptStyler] Error fetching styles: ${error}`);
                    return null;
                }
            };
            
            // Update the style dropdown with new options
            const updateStyleDropdown = (styles, preserveSelection = true) => {
                if (!styles || styles.length === 0) return;
                
                const currentValue = styleWidget.value;
                const currentIndex = indexWidget.value;
                
                // Update the options
                styleWidget.options.values = styles;
                
                // Update style count
                updateStyleCount();
                
                // Reset tracking when style list changes (fresh start)
                node._Eclipse_lastResolvedIndex = null;
                node._Eclipse_manualIndex = null;
                
                // Try to preserve the current selection if it exists in new list
                if (preserveSelection && styles.includes(currentValue)) {
                    // Set flags to indicate system updates (not user)
                    node._Eclipse_updatingStyle = true;
                    
                    styleWidget.value = currentValue;
                    
                    // Update index to match the new position
                    const newIndex = styles.indexOf(currentValue);
                    if (newIndex >= 0 && indexWidget.value !== newIndex) {
                        // Set flag to indicate system update (not user)
                        node._Eclipse_updatingIndex = true;
                        
                        indexWidget.value = newIndex;
                        
                        // Clear flag after update
                        node._Eclipse_updatingIndex = false;
                    }
                    
                    // Clear style flag after update
                    node._Eclipse_updatingStyle = false;
                } else {
                    // Use index to select from new list (with wrapping if needed)
                    // Only wrap if current index is non-negative (not a special mode)
                    let targetIndex = currentIndex;
                    if (currentIndex >= 0 && currentIndex >= styles.length) {
                        targetIndex = currentIndex % styles.length;
                    } else if (currentIndex >= styles.length) {
                        // Special mode, don't change it
                        targetIndex = currentIndex;
                    } else if (currentIndex < 0 && currentIndex >= MODE_DECREMENT) {
                        // Special mode, keep it
                        targetIndex = currentIndex;
                    } else if (currentIndex < MODE_DECREMENT) {
                        // Out of range special mode, reset to 0
                        targetIndex = 0;
                    }
                    
                    // Set flags to indicate system updates (not user)
                    if (targetIndex >= 0) {
                        const wrappedIndex = targetIndex % styles.length;
                        
                        node._Eclipse_updatingStyle = true;
                        styleWidget.value = styles[wrappedIndex];
                        node._Eclipse_updatingStyle = false;
                        
                        if (indexWidget.value !== wrappedIndex) {
                            node._Eclipse_updatingIndex = true;
                            indexWidget.value = wrappedIndex;
                            node._Eclipse_updatingIndex = false;
                        }
                    }
                }
                
                // // // console.log(`[PromptStyler] Updated styles: ${styles.length} styles loaded`);
                app.graph.setDirtyCanvas(true);
            };
            
            // Update style dropdown based on index (only for non-negative indices)
            const updateStyleFromIndex = (index) => {
                const styles = getStyleOptions();
                if (styles.length === 0) return;
                
                // Only update if index >= 0 (special modes don't change visible style)
                if (index < 0) {
                    // // // console.log(`[PromptStyler] Index is special mode (${index}), keeping current style visible`);
                    return;
                }
                
                // Wrap index using modulo
                const wrappedIndex = index % styles.length;
                const selectedStyle = styles[wrappedIndex];
                
                if (selectedStyle && styleWidget.value !== selectedStyle) {
                    // // // console.log(`[PromptStyler] Index ${index} (wrapped: ${wrappedIndex}) -> style: "${selectedStyle}"`);
                    
                    // Set flag to indicate system update (not user)
                    node._Eclipse_updatingStyle = true;
                    
                    styleWidget.value = selectedStyle;
                    
                    // Trigger widget callback if exists
                    if (styleWidget.callback) {
                        styleWidget.callback(selectedStyle);
                    }
                    
                    // Clear flag after update
                    node._Eclipse_updatingStyle = false;
                    
                    // Mark graph as changed
                    app.graph.setDirtyCanvas(true);
                }
            };
            
            // Update index based on style selection
            const updateIndexFromStyle = (styleName) => {
                const styles = getStyleOptions();
                const styleIndex = styles.indexOf(styleName);
                
                if (styleIndex >= 0 && indexWidget.value !== styleIndex) {
                    // // // console.log(`[PromptStyler] Style "${styleName}" -> index: ${styleIndex}`);
                    
                    // Set flag to indicate system update (not user)
                    node._Eclipse_updatingIndex = true;
                    
                    indexWidget.value = styleIndex;
                    
                    // Clear flag after update
                    node._Eclipse_updatingIndex = false;
                    
                    // Mark graph as changed
                    app.graph.setDirtyCanvas(true);
                }
            };
            
            // Style mode change handler
            if (styleModeWidget) {
                const originalStyleModeCallback = styleModeWidget.callback;
                styleModeWidget.callback = async function(value) {
                    // Call original callback if exists
                    if (originalStyleModeCallback) {
                        originalStyleModeCallback.apply(this, arguments);
                    }
                    
                    // Clear tracking when mode changes
                    node._Eclipse_lastResolvedIndex = null;
                    node._Eclipse_manualIndex = null;
                    
                    // Fetch and update styles for the new mode
                    // // // console.log(`[PromptStyler] Style mode changed to: ${value}`);
                    const styles = await fetchStylesForMode(value);
                    if (styles) {
                        updateStyleDropdown(styles, true);
                    }
                };
            }
            
            // Index widget change handler
            const originalIndexCallback = indexWidget.callback;
            indexWidget.callback = function(value) {
                // Call original callback if exists
                if (originalIndexCallback) {
                    originalIndexCallback.apply(this, arguments);
                }
                
                // If user manually changes index (not system update)
                if (!node._Eclipse_updatingIndex) {
                    // // // console.log(`[PromptStyler] Manual index change: ${value}`);
                    
                    // Update button state based on mode
                    if (node._Eclipse_lastIndexButton) {
                        if (value >= 0) {
                            // Fixed index mode - disable button and reset tracking
                            node._Eclipse_lastIndexButton.name = "♻️ (Use Last Queued Index)";
                            node._Eclipse_lastIndexButton.disabled = true;
                            // Reset tracking when entering fixed mode
                            node._Eclipse_lastResolvedIndex = null;
                            node._Eclipse_manualIndex = null;
                        } else {
                            // Special mode - keep button enabled if we have history
                            if (node._Eclipse_lastResolvedIndex !== null && node._Eclipse_lastResolvedIndex !== undefined) {
                                // Keep showing last resolved index when switching between special modes
                                node._Eclipse_lastIndexButton.name = `♻️ ${node._Eclipse_lastResolvedIndex}`;
                                node._Eclipse_lastIndexButton.disabled = false;
                            } else {
                                // No history yet
                                node._Eclipse_lastIndexButton.name = "♻️ (Use Last Queued Index)";
                                node._Eclipse_lastIndexButton.disabled = true;
                            }
                        }
                    }
                    
                    // Update style to match (only if non-negative index)
                    updateStyleFromIndex(value);
                }
            };
            
            // Style widget change handler
            const originalStyleCallback = styleWidget.callback;
            styleWidget.callback = function(value) {
                // Call original callback if exists
                if (originalStyleCallback) {
                    originalStyleCallback.apply(this, arguments);
                }
                
                // If user manually changes style (not system update)
                if (!node._Eclipse_updatingStyle) {
                    // // // console.log(`[PromptStyler] Manual style change: "${value}"`);
                    
                    // Reset tracking (fresh start)
                    node._Eclipse_lastResolvedIndex = null;
                    node._Eclipse_manualIndex = null;
                    
                    // Only update index to match selected style if NOT in special mode
                    // In special modes (-1, -2, -3), just update the visual style display
                    const currentIndex = indexWidget.value;
                    if (currentIndex >= 0) {
                        // Fixed index mode - update index to match style
                        updateIndexFromStyle(value);
                    } else {
                        // Special mode - keep mode intact, but show the style's index in button
                        const styles = getStyleOptions();
                        const styleIndex = styles.indexOf(value);
                        if (styleIndex >= 0 && node._Eclipse_lastIndexButton) {
                            node._Eclipse_lastIndexButton.name = `♻️ ${styleIndex}`;
                            node._Eclipse_lastIndexButton.disabled = false;
                        }
                        // // // console.log(`[PromptStyler] In special mode (${currentIndex}), showing style index ${styleIndex} in button`);
                    }
                }
            };
            
            // Add navigation buttons at the bottom of the node
            const addButton = (label, tooltip, onClick) => {
                const button = node.addWidget("button", label, null, onClick);
                button.tooltip = tooltip;
                button.serialize = false;  // Don't save button state
                return button;
            };
            
            // Add buttons (they'll be added at the end automatically)
            addButton(
                "🎲 Randomize Each Time",
                "Set index to -1 (random style on each queue)",
                () => {
                    // Set index to random mode
                    node._Eclipse_updatingIndex = true;
                    indexWidget.value = MODE_RANDOM;
                    node._Eclipse_updatingIndex = false;
                    
                    // Reset tracking
                    node._Eclipse_lastResolvedIndex = null;
                    node._Eclipse_manualIndex = null;
                    
                    // // // console.log("[PromptStyler] Set to random mode (-1)");
                    app.graph.setDirtyCanvas(true);
                }
            );
            
            const lastIndexButton = addButton(
                "♻️ (Use Last Queued Index)",
                "Lock to the index from last queue (disables increment/decrement/random)",
                () => {
                    // If we have a last resolved index, use it
                    if (node._Eclipse_lastResolvedIndex !== null) {
                        node._Eclipse_updatingIndex = true;
                        indexWidget.value = node._Eclipse_lastResolvedIndex;
                        node._Eclipse_updatingIndex = false;
                        
                        // Update style to match
                        updateStyleFromIndex(node._Eclipse_lastResolvedIndex);
                        
                        // Reset tracking
                        node._Eclipse_lastResolvedIndex = null;
                        node._Eclipse_manualIndex = null;
                        
                        // // // console.log(`[PromptStyler] Locked to last queued index: ${indexWidget.value}`);
                    } else {
                        // // // console.log("[PromptStyler] No last queued index available");
                    }
                    app.graph.setDirtyCanvas(true);
                }
            );
            
            // Store reference to button for updating its label
            lastIndexButton.disabled = true; // Start disabled until we have history
            node._Eclipse_lastIndexButton = lastIndexButton;
            
            // Clean up when node is removed
            const onRemoved = node.onRemoved;
            node.onRemoved = function() {
                nodeStyleCounts.delete(nodeId);
                if (onRemoved) {
                    onRemoved.apply(this, arguments);
                }
            };
            
            // Initialize: sync style with index, update widget visibility, and store style count
            setTimeout(() => {
                updateStyleFromIndex(indexWidget.value);
                updateMaxWordsVisibility();
                updateStyleCount();
            }, 100);
            
            return r;
        };
        
        // Method to calculate index based on special modes
        nodeType.prototype.getIndexToUse = function() {
            const indexWidget = this._Eclipse_indexWidget;
            
            if (!indexWidget) {
                return 0;
            }
            
            const currentIndex = indexWidget.value;
            const lastResolvedIndex = this._Eclipse_lastResolvedIndex;
            const maxIndex = indexWidget.options?.max ?? 999999;
            const styleCount = nodeStyleCounts.get(this.id) || (maxIndex + 1);
            
            let indexToUse = currentIndex;
            
            // Handle special modes
            if (currentIndex === MODE_RANDOM) {
                // Random mode: pick random index
                if (styleCount > 1) {
                    // Try to avoid same index as last time
                    let attempts = 0;
                    do {
                        indexToUse = Math.floor(Math.random() * styleCount);
                        attempts++;
                    } while (indexToUse === lastResolvedIndex && attempts < 10);
                } else {
                    indexToUse = 0;
                }
            } else if (currentIndex === MODE_INCREMENT) {
                // Increment mode: increment from last resolved, wrap around at max
                if (lastResolvedIndex !== null) {
                    indexToUse = lastResolvedIndex + 1;
                    if (indexToUse >= styleCount) {
                        indexToUse = 0;  // Wrap to start
                    }
                } else {
                    // First run, start from style widget's current index
                    const styles = this._Eclipse_styleWidget?.options?.values || [];
                    const currentStyle = this._Eclipse_styleWidget?.value;
                    const styleIdx = styles.indexOf(currentStyle);
                    indexToUse = styleIdx >= 0 ? styleIdx : 0;
                }
            } else if (currentIndex === MODE_DECREMENT) {
                // Decrement mode: decrement from last resolved, wrap around at 0
                if (lastResolvedIndex !== null) {
                    indexToUse = lastResolvedIndex - 1;
                    if (indexToUse < 0) {
                        indexToUse = Math.max(0, styleCount - 1);  // Wrap to end
                    }
                } else {
                    // First run, start from style widget's current index
                    const styles = this._Eclipse_styleWidget?.options?.values || [];
                    const currentStyle = this._Eclipse_styleWidget?.value;
                    const styleIdx = styles.indexOf(currentStyle);
                    indexToUse = styleIdx >= 0 ? styleIdx : 0;
                }
            } else if (currentIndex >= 0) {
                // Fixed index mode: use current index with wrapping
                indexToUse = currentIndex % styleCount;
            } else {
                // Unknown special mode, default to 0
                indexToUse = 0;
            }
            
            return indexToUse;
        };
    },
    
    async setup() {
        // Hook into graphToPrompt to calculate and apply index before sending to server
        // This is the same pattern used by eclipse-seed.js and eclipse-load-image-folder.js
        const originalGraphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function() {
            // Call the original graphToPrompt first
            const result = await originalGraphToPrompt.apply(this, arguments);
            
            if (!result || !result.output) {
                return result;
            }
            
            // Process all PromptStyler nodes
            const nodes = app.graph._nodes;
            for (const node of nodes) {
                if (node.type !== NODE_NAME || !node._Eclipse_indexWidget) {
                    continue;
                }
                
                // Skip if node is muted or bypassed
                if (node.mode === 2 || node.mode === 4) {
                    continue;
                }
                
                // Check if this node is in the prompt
                const nodeId = String(node.id);
                if (!result.output[nodeId]) {
                    continue;
                }
                
                // Calculate the index to use based on index_control
                const indexToUse = node.getIndexToUse();
                const indexWidget = node._Eclipse_indexWidget;
                const styleWidget = node._Eclipse_styleWidget;
                const currentWidgetValue = indexWidget.value;
                
                // // // console.log(`[PromptStyler] graphToPrompt: widget=${currentWidgetValue}, calculated=${indexToUse}`);
                
                // Update the index in the prompt output (what gets sent to server)
                if (result.output[nodeId].inputs && result.output[nodeId].inputs.index !== undefined) {
                    result.output[nodeId].inputs.index = indexToUse;
                }
                
                // DON'T update index widget if in special mode - keep showing the mode (-1, -2, -3)
                // Only update style widget to show what will be selected
                // User can click "Use Last Queued Index" button if they want to lock the resolved position
                const isSpecialMode = currentWidgetValue < 0;
                
                if (!isSpecialMode) {
                    // Fixed index mode - update index widget if different
                    if (indexWidget.value !== indexToUse) {
                        // Set flag to indicate system is updating (not user)
                        node._Eclipse_updatingIndex = true;
                        
                        indexWidget.value = indexToUse;
                        if (indexWidget.callback) {
                            indexWidget.callback(indexToUse);
                        }
                        
                        // Clear flag after update
                        node._Eclipse_updatingIndex = false;
                    }
                }
                
                // Always update style widget to match the resolved index (system update, not user)
                const styles = styleWidget.options?.values || [];
                if (styles.length > 0) {
                    const wrappedIndex = indexToUse % styles.length;
                    const selectedStyle = styles[wrappedIndex];
                    if (selectedStyle && styleWidget.value !== selectedStyle) {
                        // Set flag to indicate system update (not user)
                        node._Eclipse_updatingStyle = true;
                        
                        styleWidget.value = selectedStyle;
                        
                        // Clear flag after update
                        node._Eclipse_updatingStyle = false;
                    }
                }
                
                node.setDirtyCanvas(true, true);
                
                // Store as last resolved index for next iteration
                node._Eclipse_lastResolvedIndex = indexToUse;
                
                // Update the "Use Last Queued Index" button label and state
                if (node._Eclipse_lastIndexButton) {
                    if (isSpecialMode) {
                        // In special mode, show the resolved index in button label
                        if (node._Eclipse_lastResolvedIndex !== null && node._Eclipse_lastResolvedIndex !== undefined) {
                            node._Eclipse_lastIndexButton.name = `♻️ ${node._Eclipse_lastResolvedIndex}`;
                            node._Eclipse_lastIndexButton.disabled = false; // Enable button
                        } else {
                            // No history yet in special mode
                            node._Eclipse_lastIndexButton.name = "♻️ (Use Last Queued Index)";
                            node._Eclipse_lastIndexButton.disabled = true; // Disabled until we have history
                        }
                    } else {
                        // Fixed mode - always disable button
                        node._Eclipse_lastIndexButton.name = "♻️ (Use Last Queued Index)";
                        node._Eclipse_lastIndexButton.disabled = true;
                    }
                }
                
                // Also update workflow data if present
                if (result.workflow && result.workflow.nodes) {
                    const workflowNode = result.workflow.nodes.find(n => n.id === node.id);
                    if (workflowNode && workflowNode.widgets_values) {
                        const indexWidgetIndex = node.widgets.indexOf(indexWidget);
                        if (indexWidgetIndex >= 0) {
                            workflowNode.widgets_values[indexWidgetIndex] = indexToUse;
                        }
                    }
                }
            }

           
            return result;
        };
    },
});
