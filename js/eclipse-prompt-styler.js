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

// Track style count per node (for index max clamping)
const nodeStyleCounts = new Map();

app.registerExtension({
    name: "Eclipse.PromptStyler",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) return;
        
        console.log("[PromptStyler] Registering extension");
        
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
                    widget.hidden = false;
                } else {
                    // Hide widget - save original type first
                    if (widget.type !== "converted-widget" && !widget.origType) {
                        widget.origType = widget.type;
                    }
                    widget.type = "converted-widget";
                    widget.computeSize = () => [0, -4];
                    widget.hidden = true;
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
            node._Eclipse_lastIndex = null;  // Track last executed index for increment/decrement
            
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
                
                // Try to preserve the current selection if it exists in new list
                if (preserveSelection && styles.includes(currentValue)) {
                    styleWidget.value = currentValue;
                    // Update index to match the new position
                    const newIndex = styles.indexOf(currentValue);
                    if (newIndex >= 0 && indexWidget.value !== newIndex) {
                        indexWidget.value = newIndex;
                    }
                } else {
                    // Use index to select from new list (with wrapping)
                    const wrappedIndex = currentIndex % styles.length;
                    styleWidget.value = styles[wrappedIndex];
                    if (indexWidget.value !== wrappedIndex) {
                        indexWidget.value = wrappedIndex;
                    }
                }
                
                console.log(`[PromptStyler] Updated styles: ${styles.length} styles loaded`);
                app.graph.setDirtyCanvas(true);
            };
            
            // Update style dropdown based on index
            const updateStyleFromIndex = (index) => {
                const styles = getStyleOptions();
                if (styles.length === 0) return;
                
                // Only update if index >= 0
                if (index < 0) return;
                
                // Wrap index using modulo
                const wrappedIndex = index % styles.length;
                const selectedStyle = styles[wrappedIndex];
                
                if (selectedStyle && styleWidget.value !== selectedStyle) {
                    styleWidget.value = selectedStyle;
                    console.log(`[PromptStyler] Index ${index} (wrapped: ${wrappedIndex}) -> style: "${selectedStyle}"`);
                    
                    // Trigger widget callback if exists
                    if (styleWidget.callback) {
                        styleWidget.callback(selectedStyle);
                    }
                    
                    // Mark graph as changed
                    app.graph.setDirtyCanvas(true);
                }
            };
            
            // Update index based on style selection
            const updateIndexFromStyle = (styleName) => {
                const styles = getStyleOptions();
                const styleIndex = styles.indexOf(styleName);
                
                if (styleIndex >= 0 && indexWidget.value !== styleIndex) {
                    indexWidget.value = styleIndex;
                    console.log(`[PromptStyler] Style "${styleName}" -> index: ${styleIndex}`);
                    
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
                    
                    // Clear last index when mode changes
                    node._Eclipse_lastIndex = null;
                    
                    // Fetch and update styles for the new mode
                    console.log(`[PromptStyler] Style mode changed to: ${value}`);
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
                
                // Update style dropdown
                updateStyleFromIndex(value);
            };
            
            // Style widget change handler
            const originalStyleCallback = styleWidget.callback;
            styleWidget.callback = function(value) {
                // Call original callback if exists
                if (originalStyleCallback) {
                    originalStyleCallback.apply(this, arguments);
                }
                
                // Update index to match selected style
                updateIndexFromStyle(value);
            };
            
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
        
        // Method to calculate index based on index_control
        nodeType.prototype.getIndexToUse = function() {
            const indexWidget = this._Eclipse_indexWidget;
            const indexControlWidget = this.widgets?.find(w => w.name === "index_control");
            
            if (!indexWidget || !indexControlWidget) {
                return indexWidget?.value ?? 0;
            }
            
            const indexControl = indexControlWidget.value;
            const widgetIndex = indexWidget.value;
            const lastIndex = this._Eclipse_lastIndex;
            const maxIndex = indexWidget.options?.max ?? 999999;
            const styleCount = nodeStyleCounts.get(this.id) || (maxIndex + 1);
            
            let indexToUse = widgetIndex;
            
            switch (indexControl) {
                case "fixed":
                    // Always use widget value
                    indexToUse = widgetIndex;
                    break;
                    
                case "increment":
                    // If we have a last index, increment from it
                    if (lastIndex !== null) {
                        indexToUse = lastIndex + 1;
                        if (indexToUse >= styleCount) {
                            indexToUse = 0;  // Wrap around
                        }
                    } else {
                        // First run, use widget value
                        indexToUse = widgetIndex;
                    }
                    break;
                    
                case "decrement":
                    // If we have a last index, decrement from it
                    if (lastIndex !== null) {
                        indexToUse = lastIndex - 1;
                        if (indexToUse < 0) {
                            indexToUse = Math.max(0, styleCount - 1);  // Wrap to end
                        }
                    } else {
                        // First run, use widget value
                        indexToUse = widgetIndex;
                    }
                    break;
                    
                case "random":
                    // Pick a random index within valid range
                    if (styleCount > 1) {
                        // Try to avoid same index as last time
                        let attempts = 0;
                        do {
                            indexToUse = Math.floor(Math.random() * styleCount);
                            attempts++;
                        } while (indexToUse === lastIndex && attempts < 10);
                    } else {
                        indexToUse = 0;
                    }
                    break;
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
                
                console.log(`[PromptStyler] graphToPrompt: widget=${currentWidgetValue}, calculated=${indexToUse}`);
                
                // Update the index in the prompt output (what gets sent to server)
                if (result.output[nodeId].inputs && result.output[nodeId].inputs.index !== undefined) {
                    result.output[nodeId].inputs.index = indexToUse;
                }
                
                // Update index widget to show what we're sending
                if (indexWidget.value !== indexToUse) {
                    indexWidget.value = indexToUse;
                    if (indexWidget.callback) {
                        indexWidget.callback(indexToUse);
                    }
                }
                
                // Also update style widget to match new index
                const styles = styleWidget.options?.values || [];
                if (styles.length > 0) {
                    const wrappedIndex = indexToUse % styles.length;
                    const selectedStyle = styles[wrappedIndex];
                    if (selectedStyle && styleWidget.value !== selectedStyle) {
                        styleWidget.value = selectedStyle;
                    }
                }
                
                node.setDirtyCanvas(true, true);
                
                // Store as last executed index for next iteration
                node._Eclipse_lastIndex = indexToUse;
                
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
