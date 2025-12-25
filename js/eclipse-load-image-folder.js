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

import { app, api } from './comfy/index.js';

const NODE_NAME = "Load Image From Folder [Eclipse]";

// Track previous folder_path per node to detect changes
const nodeFolderPaths = new Map();

// Track if stop-iteration was triggered - reset when folder changes
const nodeStopTriggered = new Map();

app.registerExtension({
    name: "Eclipse.LoadImageFromFolder",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) return;
        
        console.log("[LoadImageFromFolder] Registering extension");
        
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            const node = this;
            const nodeId = node.id;
            
            // Get widgets
            const getWidget = (name) => node.widgets?.find(w => w.name === name);
            
            const folderPathWidget = getWidget("folder_path");
            const indexWidget = getWidget("index");
            const refreshListWidget = getWidget("refresh_list");
            
            if (!folderPathWidget) {
                console.warn("[LoadImageFromFolder] folder_path widget not found");
                return r;
            }
            
            // Store initial folder path
            nodeFolderPaths.set(nodeId, folderPathWidget.value);
            nodeStopTriggered.set(nodeId, false);
            
            // Folder path change handler
            const originalFolderPathCallback = folderPathWidget.callback;
            folderPathWidget.callback = function(value) {
                const previousPath = nodeFolderPaths.get(nodeId);
                
                // Call original callback if exists
                if (originalFolderPathCallback) {
                    originalFolderPathCallback.apply(this, arguments);
                }
                
                // Check if folder actually changed
                if (value !== previousPath) {
                    console.log(`[LoadImageFromFolder] Folder changed: "${previousPath}" -> "${value}"`);
                    
                    // Update stored path
                    nodeFolderPaths.set(nodeId, value);
                    
                    // Clear stop-triggered flag - user is starting fresh with new folder
                    nodeStopTriggered.set(nodeId, false);
                    
                    // Notify backend to clear cache for old folder
                    if (previousPath) {
                        fetch('/eclipse/load_image_folder/invalidate_cache', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ folder_path: previousPath })
                        }).catch(e => {
                            // Endpoint may not exist yet, that's ok
                            console.log("[LoadImageFromFolder] Cache invalidation endpoint not available");
                        });
                    }
                    
                    // Reset index to 0 when folder changes (user can adjust if needed)
                    if (indexWidget && indexWidget.value !== 0) {
                        console.log(`[LoadImageFromFolder] Resetting index from ${indexWidget.value} to 0`);
                        indexWidget.value = 0;
                        if (indexWidget.callback) {
                            indexWidget.callback(0);
                        }
                    }
                    
                    // Trigger refresh_list to force file rescan on next execution
                    if (refreshListWidget) {
                        refreshListWidget.value = true;
                        console.log("[LoadImageFromFolder] Enabled refresh_list for next execution");
                    }
                    
                    node.setDirtyCanvas(true, true);
                }
            };
            
            // Index change handler - clear stop flag when user manually changes index
            if (indexWidget) {
                const originalIndexCallback = indexWidget.callback;
                indexWidget.callback = function(value) {
                    // Call original callback if exists
                    if (originalIndexCallback) {
                        originalIndexCallback.apply(this, arguments);
                    }
                    
                    // If user manually changes index, clear the stop flag
                    // This allows auto-queue to work again
                    if (nodeStopTriggered.get(nodeId)) {
                        console.log("[LoadImageFromFolder] Index changed, clearing stop flag");
                        nodeStopTriggered.set(nodeId, false);
                    }
                };
            }
            
            // Clean up when node is removed
            const onRemoved = node.onRemoved;
            node.onRemoved = function() {
                nodeFolderPaths.delete(nodeId);
                nodeStopTriggered.delete(nodeId);
                if (onRemoved) {
                    onRemoved.apply(this, arguments);
                }
            };
            
            return r;
        };
    },
    
    async setup() {
        // Listen for stop-iteration to disable auto-queue and track which nodes triggered it
        api.addEventListener("stop-iteration", (event) => {
            console.log("[Eclipse] Received stop-iteration signal, disabling auto-queue...");
            
            // === DISABLE AUTO-QUEUE ===
            // IMPORTANT: We only toggle the ENABLED state, not the MODE.
            // Setting mode to "disabled" breaks re-enabling via UI checkbox.
            
            // Method 1: Try the classic checkbox (older ComfyUI versions)
            const autoQueueCheckbox = document.getElementById("autoQueueCheckbox");
            if (autoQueueCheckbox && autoQueueCheckbox.checked) {
                autoQueueCheckbox.checked = false;
                autoQueueCheckbox.dispatchEvent(new Event('change', { bubbles: true }));
                console.log("[Eclipse] Auto-queue disabled via checkbox");
            }
            
            // Method 2: Try app.ui.autoQueueEnabled (toggle enabled, NOT mode)
            if (app.ui) {
                if (app.ui.autoQueueEnabled !== undefined) {
                    app.ui.autoQueueEnabled = false;
                    console.log("[Eclipse] Auto-queue disabled via app.ui.autoQueueEnabled");
                }
            }
            
            // Method 3: Try to find and click the auto-queue toggle button in newer ComfyUI
            // Look for the queue button area and toggle
            try {
                // Find the auto-queue checkbox/toggle in the menu
                const queueButton = document.querySelector('[id*="queue"]');
                const autoToggle = document.querySelector('input[type="checkbox"][id*="auto"], input[type="checkbox"][class*="auto"]');
                if (autoToggle && autoToggle.checked) {
                    autoToggle.checked = false;
                    autoToggle.dispatchEvent(new Event('change', { bubbles: true }));
                    console.log("[Eclipse] Auto-queue disabled via auto toggle");
                }
            } catch (e) {
                // Toggle not found
            }
            
            console.log("[Eclipse] Stop-iteration handling complete");
            
            // === TRACK NODES AND RESET INDEX ===
            // Mark all LoadImageFromFolder nodes as having triggered stop
            // AND reset their index to 0 so the next run starts fresh
            // This is CRITICAL - without resetting index, IS_CHANGED returns the same value
            // and ComfyUI skips execution (uses cached result)
            const nodes = app.graph?._nodes || [];
            for (const node of nodes) {
                if (node.type === NODE_NAME) {
                    nodeStopTriggered.set(node.id, true);
                    console.log(`[LoadImageFromFolder] Node ${node.id} triggered stop-iteration`);
                    
                    // Reset index to 0 so next execution starts from beginning
                    const indexWidget = node.widgets?.find(w => w.name === "index");
                    if (indexWidget) {
                        console.log(`[LoadImageFromFolder] Resetting index from ${indexWidget.value} to 0 for next run`);
                        indexWidget.value = 0;
                        if (indexWidget.callback) {
                            indexWidget.callback(0);
                        }
                        node.setDirtyCanvas(true, true);
                    }
                }
            }
        });
        
        // Listen for execution start to reset refresh_list back to false
        api.addEventListener("execution_start", () => {
            const nodes = app.graph?._nodes || [];
            for (const node of nodes) {
                if (node.type === NODE_NAME) {
                    const refreshListWidget = node.widgets?.find(w => w.name === "refresh_list");
                    if (refreshListWidget && refreshListWidget.value === true) {
                        // Reset after a short delay to ensure the execution picks up the true value
                        setTimeout(() => {
                            refreshListWidget.value = false;
                            console.log(`[LoadImageFromFolder] Reset refresh_list for node ${node.id}`);
                        }, 500);
                    }
                }
            }
        });
    },
});
