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
*
* Dynamic widget visibility for Lora Stack
* Shows/hides clip_weight widgets based on simple mode toggle
*/

import { app } from './comfy/index.js';
import { debounce, isNodeVisible, canvasDirtyBatcher } from './eclipse-widget-performance-utils.js';

const NODE_NAME = "Lora Stack [Eclipse]";

app.registerExtension({
    name: "Eclipse.LoraStack",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const node = this;
            
            // Helper function to hide/show a widget
            const setWidgetVisible = (widgetName, visible) => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                if (!widget) return;
                
                if (visible) {
                    // Show widget - restore original type
                    if (widget.origType) {
                        widget.type = widget.origType;
                        // Don't delete origType - keep it in case we hide again later
                    } else if (widget.type === "converted-widget") {
                        // Widget is hidden but origType wasn't saved - this shouldn't happen
                        // Default to "number" as that's what weight widgets are
                        widget.type = "number";
                        widget.origType = "number"; // Save it for future hide/show cycles
                    }
                    delete widget.computeSize;
                    widget.hidden = false; // Make sure widget is visible
                } else {
                    // Hide widget - save original type first
                    if (widget.type !== "converted-widget" && !widget.origType) {
                        widget.origType = widget.type;
                    }
                    widget.type = "converted-widget";
                    widget.computeSize = () => [0, -4];
                    widget.hidden = true; // Hide widget from rendering
                }
            };
            
            // Get widget value safely
            const getWidgetValue = (name) => {
                const widget = node.widgets?.find(w => w.name === name);
                return widget ? widget.value : null;
            };
            
            // Main visibility update function
            const updateVisibility = (skipPerformanceChecks = false) => {
                // Skip if node doesn't have ID yet (during initial creation)
                if (node.id === -1) return;
                
                // Performance: Skip if node is not visible
                if (!skipPerformanceChecks && !isNodeVisible(node)) {
                    return;
                }
                
                const simpleMode = getWidgetValue("simple");
                const loraCount = getWidgetValue("lora_count") || 8;
                
                // Hide/show widgets based on lora_count
                for (let i = 1; i <= 10; i++) {
                    const visible = (i <= loraCount);
                    setWidgetVisible(`switch_${i}`, visible);
                    setWidgetVisible(`lora_name_${i}`, visible);
                    setWidgetVisible(`model_weight_${i}`, visible);
                    // Only show clip_weight if not in simple mode AND within lora_count
                    setWidgetVisible(`clip_weight_${i}`, visible && !simpleMode);
                }
                
                // Smart resize using requestAnimationFrame for better performance
                requestAnimationFrame(() => {
                    const computedSize = node.computeSize();
                    const currentSize = node.size;
                    
                    // Set minimum size
                    const minWidth = 259;
                    const minHeight = 100;
                    
                    // Preserve current width (only enforce minimum), adjust height to computed size
                    let newWidth = Math.max(currentSize[0], minWidth);
                    // Always add padding as computeSize doesn't account for all spacing
                    let padding = 5;
                    let newHeight = Math.max(computedSize[1] + padding, minHeight);
                    
                    // Always resize to match computed size to ensure proper widget display
                    node.setSize([newWidth, newHeight]);
                    
                    canvasDirtyBatcher.markDirty(node);
                });
            };
            
            // Create debounced version to prevent rapid-fire updates
            const debouncedUpdateVisibility = debounce(updateVisibility, 100);
            
            // Override onResize to enforce minimum size based on computed size
            const originalOnResize = node.onResize;
            node.onResize = function(size) {
                // Compute minimum size needed for all widgets
                const simpleMode = getWidgetValue("simple");
                const computedSize = this.computeSize();
                const minWidth = 259;
                // Always add padding as computeSize doesn't account for all spacing
                const padding = 5;
                const minHeight = Math.max(computedSize[1] + padding, 100);
                
                // Enforce minimum dimensions
                size[0] = Math.max(size[0], minWidth);
                size[1] = Math.max(size[1], minHeight);
                
                if (originalOnResize) {
                    return originalOnResize.apply(this, [size]);
                }
            };
            
            // Hook into the relevant toggle widgets
            const relevantWidgets = ["simple", "lora_count"];
            
            relevantWidgets.forEach(widgetName => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                if (widget) {
                    const originalCallback = widget.callback;
                    widget.callback = function() {
                        if (originalCallback) {
                            originalCallback.apply(this, arguments);
                        }
                        debouncedUpdateVisibility();
                    };
                }
            });
            
            // Initial visibility update - defer slightly to ensure node has valid ID
            // LiteGraph assigns ID after onNodeCreated returns
            setTimeout(() => {
                if (!node._Eclipse_initialized) {
                    node._Eclipse_initialized = true;
                    updateVisibility(true);
                }
            }, 0);
            
            // Hook into onConfigure to update visibility when workflow is loaded
            const onConfigure = node.onConfigure;
            node.onConfigure = function(info) {
                if (onConfigure) {
                    onConfigure.apply(this, arguments);
                }
                
                // Defer update until after LiteGraph finishes establishing widget values
                setTimeout(() => {
                    updateVisibility(true);
                }, 100);
            };
            
            return r;
        };
    },
});
