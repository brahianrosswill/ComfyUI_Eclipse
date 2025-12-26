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

app.registerExtension({
    name: "Eclipse.PromptStyler",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) return;
        
        console.log("[PromptStyler] Registering extension");
        
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const node = this;
            
            // Get widgets
            const getWidget = (name) => node.widgets?.find(w => w.name === name);
            
            const styleModeWidget = getWidget("style_mode");
            const styleWidget = getWidget("style");
            const indexWidget = getWidget("index");
            
            if (!styleWidget || !indexWidget) {
                console.warn("[PromptStyler] Required widgets not found");
                return r;
            }
            
            // Get the style options from the combo widget
            const getStyleOptions = () => {
                return styleWidget.options?.values || [];
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
            
            // Initialize: sync style with index
            setTimeout(() => {
                updateStyleFromIndex(indexWidget.value);
            }, 100);
            
            return r;
        };
    }
});
