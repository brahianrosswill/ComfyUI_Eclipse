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
* Dynamic widget visibility for Save Prompt node
* Shows/hides CSV and JSON specific widgets based on extension selection
*/

import { app } from './comfy/index.js';

const NODE_NAME = "Save Prompt [Eclipse]";

app.registerExtension({
    name: "Eclipse.SavePrompt",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const node = this;
            
            // CSV-specific widgets
            const csvWidgets = ["csv_positive_name", "csv_negative_prompt"];
            // JSON-specific widgets
            const jsonWidgets = ["nsfw_level"];
            
            const setWidgetVisible = (widgetName, visible) => {
                const widget = node.widgets?.find(w => w.name === widgetName);
                if (!widget) return;
                
                if (visible) {
                    if (widget.origType) {
                        widget.type = widget.origType;
                    } else if (widget.type === "converted-widget") {
                        widget.type = widget.origComboType || "combo";
                        widget.origType = widget.origComboType || "combo";
                    }
                    delete widget.computeSize;
                    widget.hidden = false;
                } else {
                    if (widget.type !== "converted-widget" && !widget.origType) {
                        widget.origType = widget.type;
                        if (widget.type === "combo") {
                            widget.origComboType = "combo";
                        }
                    }
                    widget.type = "converted-widget";
                    widget.computeSize = () => [0, -4];
                    widget.hidden = true;
                }
            };
            
            const getWidgetValue = (name) => {
                const widget = node.widgets?.find(w => w.name === name);
                return widget ? widget.value : null;
            };
            
            const updateVisibility = () => {
                const extension = getWidgetValue("extension");
                
                // CSV widgets - visible when extension is 'csv'
                const isCsv = extension === "csv";
                csvWidgets.forEach(widgetName => {
                    setWidgetVisible(widgetName, isCsv);
                });
                
                // JSON widgets - only visible when extension is 'json'
                jsonWidgets.forEach(widgetName => {
                    setWidgetVisible(widgetName, extension === "json");
                });
                
                // Smart resize - only adjust height, preserve width
                setTimeout(() => {
                    node.setDirtyCanvas(true, false);
                    
                    const computedSize = node.computeSize();
                    const currentSize = node.size;
                    
                    const minHeight = 100;
                    
                    let newHeight = Math.max(computedSize[1], minHeight);
                    newHeight += 5;
                    
                    const heightDiff = Math.abs(currentSize[1] - newHeight);
                    const isGrowing = newHeight > currentSize[1];
                    
                    if (isGrowing || heightDiff > 10) {
                        node.setSize([currentSize[0], newHeight]);
                    }
                    
                    node.setDirtyCanvas(true, true);
                }, 50);
            };
            
            // Hook into extension widget
            const extensionWidget = node.widgets?.find(w => w.name === "extension");
            if (extensionWidget) {
                const originalCallback = extensionWidget.callback;
                extensionWidget.callback = function() {
                    if (originalCallback) {
                        originalCallback.apply(this, arguments);
                    }
                    updateVisibility();
                };
            }
            
            // Initial visibility update
            setTimeout(() => {
                updateVisibility();
            }, 10);
            
            // Hook into onConfigure to update visibility when workflow is loaded
            const onConfigure = node.onConfigure;
            node.onConfigure = function(info) {
                if (onConfigure) {
                    onConfigure.apply(this, arguments);
                }
                
                setTimeout(() => {
                    updateVisibility();
                }, 50);
            };
            
            return r;
        };
    }
});
