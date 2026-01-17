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
* Dynamic widget behavior for Image Resolution node
* Updates width/height widgets based on selected resolution preset
*/

import { app } from './comfy/index.js';

const NODE_NAME = "Image Resolution [Eclipse]";

app.registerExtension({
    name: "Eclipse.ImageResolution",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

            const node = this;
            
            // Find widgets
            const resolutionWidget = node.widgets?.find(w => w.name === "resolution");
            const widthWidget = node.widgets?.find(w => w.name === "width");
            const heightWidget = node.widgets?.find(w => w.name === "height");
            
            if (!resolutionWidget || !widthWidget || !heightWidget) {
                console.warn("[Eclipse.ImageResolution] Required widgets not found");
                return r;
            }
            
            // Helper to show/hide widgets (pattern from eclipse-save-prompt.js)
            const setWidgetVisible = (widget, visible) => {
                if (!widget) return;
                
                if (visible) {
                    if (widget.origType) {
                        widget.type = widget.origType;
                    }
                    delete widget.computeSize;
                    widget.hidden = false;
                } else {
                    if (widget.type !== "converted-widget" && !widget.origType) {
                        widget.origType = widget.type;
                    }
                    widget.type = "converted-widget";
                    widget.computeSize = () => [0, -4];
                    widget.hidden = true;
                }
            };
            
            // Update visibility based on resolution selection
            const updateVisibility = (resolution) => {
                const isCustom = resolution === "Custom";
                
                // Show width/height only when Custom is selected
                setWidgetVisible(widthWidget, isCustom);
                setWidgetVisible(heightWidget, isCustom);
                
                // Smart resize - only adjust height, preserve width
                setTimeout(() => {
                    node.setDirtyCanvas?.(true, false);
                    
                    const computedSize = node.computeSize();
                    const currentSize = node.size;
                    
                    const minHeight = 50;
                    let newHeight = Math.max(computedSize[1], minHeight);
                    
                    node.setSize([currentSize[0], newHeight]);
                    
                    app.graph.setDirtyCanvas(true, true);
                }, 50);
            };
            
            // Hook resolution widget callback
            const originalResolutionCallback = resolutionWidget.callback;
            resolutionWidget.callback = function(value) {
                if (originalResolutionCallback) {
                    originalResolutionCallback.apply(this, arguments);
                }
                updateVisibility(value);
            };
            
            // Initial update based on current resolution value
            setTimeout(() => {
                updateVisibility(resolutionWidget.value);
            }, 10);

            return r;
        };
        
        // Handle workflow load - update visibility after configure
        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function(info) {
            if (onConfigure) {
                onConfigure.apply(this, arguments);
            }
            
            const node = this;
            const resolutionWidget = node.widgets?.find(w => w.name === "resolution");
            
            if (!resolutionWidget) return;
            
            // After workflow load, update visibility based on saved resolution
            setTimeout(() => {
                const resolution = resolutionWidget.value;
                const isCustom = resolution === "Custom";
                
                const widthWidget = node.widgets?.find(w => w.name === "width");
                const heightWidget = node.widgets?.find(w => w.name === "height");
                
                // Helper to show/hide widgets
                const setWidgetVisible = (widget, visible) => {
                    if (!widget) return;
                    
                    if (visible) {
                        if (widget.origType) {
                            widget.type = widget.origType;
                        }
                        delete widget.computeSize;
                        widget.hidden = false;
                    } else {
                        if (widget.type !== "converted-widget" && !widget.origType) {
                            widget.origType = widget.type;
                        }
                        widget.type = "converted-widget";
                        widget.computeSize = () => [0, -4];
                        widget.hidden = true;
                    }
                };
                
                setWidgetVisible(widthWidget, isCustom);
                setWidgetVisible(heightWidget, isCustom);
                
                // Resize node
                const computedSize = node.computeSize();
                node.setSize([node.size[0], Math.max(computedSize[1], 50)]);
                app.graph.setDirtyCanvas(true, true);
            }, 50);
        };
    },
});
