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

// Special index modes (match ReadPromptFiles and PromptStyler)
const MODE_RANDOM = -1;
const MODE_INCREMENT = -2;
const MODE_DECREMENT = -3;

// Track previous folder_path per node to detect changes
const nodeFolderPaths = new Map();

// Track if stop-iteration was triggered - reset when folder changes
const nodeStopTriggered = new Map();

// Track last known image count per node (for index max clamping)
const nodeImageCounts = new Map();

// Debounce timer for image count fetches
const fetchDebounceTimers = new Map();

/**
 * Fetch image count from backend and update index widget max value.
 * This constrains the random range for special modes.
 */
async function updateImageCount(node) {
    const nodeId = node.id;
    const folderPathWidget = node.widgets?.find(w => w.name === "folder_path");
    const includeSubfoldersWidget = node.widgets?.find(w => w.name === "include_subfolders");
    const indexWidget = node.widgets?.find(w => w.name === "index");
    
    if (!folderPathWidget || !indexWidget) return;
    
    const folderPath = folderPathWidget.value;
    const includeSubfolders = includeSubfoldersWidget?.value ?? false;
    
    if (!folderPath || !folderPath.trim()) {
        // No folder, reset to default max
        indexWidget.options.max = 999999;
        nodeImageCounts.set(nodeId, 0);
        return;
    }
    
    try {
        const response = await fetch('/eclipse/load_image_folder/count', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_path: folderPath,
                include_subfolders: includeSubfolders
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            const totalCount = data.total_count || 0;
            
            // Store count for reference
            nodeImageCounts.set(nodeId, totalCount);
            
            if (totalCount > 0) {
                // Set max to totalCount - 1 (0-indexed) so random stays in valid range
                // But minimum of 0 (single image case)
                indexWidget.options.max = Math.max(0, totalCount - 1);
                // // // console.log(`[LoadImageFromFolder] Updated index max to ${totalCount - 1} (${totalCount} images)`);
                
                // If current index exceeds new max, clamp it
                if (indexWidget.value > indexWidget.options.max) {
                    // // // console.log(`[LoadImageFromFolder] Clamping index from ${indexWidget.value} to ${indexWidget.options.max}`);
                    indexWidget.value = indexWidget.options.max;
                    if (indexWidget.callback) {
                        indexWidget.callback(indexWidget.value);
                    }
                }
            } else {
                // No images found, set max to 0
                indexWidget.options.max = 0;
                // // // console.log(`[LoadImageFromFolder] No images found, set index max to 0`);
            }
            
            node.setDirtyCanvas(true, true);
        }
    } catch (e) {
        console.warn("[LoadImageFromFolder] Failed to fetch image count:", e);
        // On error, leave max unchanged (fallback to large value)
    }
}

/**
 * Debounced version of updateImageCount to avoid spamming API.
 */
function updateImageCountDebounced(node, delay = 300) {
    const nodeId = node.id;
    
    // Clear existing timer
    if (fetchDebounceTimers.has(nodeId)) {
        clearTimeout(fetchDebounceTimers.get(nodeId));
    }
    
    // Set new timer
    const timerId = setTimeout(() => {
        updateImageCount(node);
        fetchDebounceTimers.delete(nodeId);
    }, delay);
    
    fetchDebounceTimers.set(nodeId, timerId);
}

app.registerExtension({
    name: "Eclipse.LoadImageFromFolder",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) return;
        
        // // // console.log("[LoadImageFromFolder] Registering extension");
        
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
            
            // Store references for graphToPrompt hook
            node._Eclipse_indexWidget = indexWidget;
            node._Eclipse_lastIndex = null;  // Track last executed index for increment/decrement
            node._Eclipse_updatingIndex = false;  // Flag to track when system is updating index (vs user)
            node._Eclipse_lastResolvedIndex = null;  // Track resolved index from last queue (for button state)
            node._Eclipse_manualIndex = false;  // Flag to track manual vs button-driven index changes
            node._Eclipse_lastIndexButton = null;  // Reference to the "Use Last Queued Index" button
            
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
                    // // // console.log(`[LoadImageFromFolder] Folder changed: "${previousPath}" -> "${value}"`);
                    
                    // Update stored path
                    nodeFolderPaths.set(nodeId, value);
                    
                    // Clear stop-triggered flag - user is starting fresh with new folder
                    nodeStopTriggered.set(nodeId, false);
                    
                    // Clear last executed index - new folder means fresh start
                    node._Eclipse_lastIndex = null;
                    
                    // Notify backend to clear cache for old folder
                    if (previousPath) {
                        fetch('/eclipse/load_image_folder/invalidate_cache', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ folder_path: previousPath })
                        }).catch(e => {
                            // Endpoint may not exist yet, that's ok
                            // // // console.log("[LoadImageFromFolder] Cache invalidation endpoint not available");
                        });
                    }
                    
                    // Reset index to 0 when folder changes (user can adjust if needed)
                    if (indexWidget && indexWidget.value !== 0) {
                        // // // console.log(`[LoadImageFromFolder] Resetting index from ${indexWidget.value} to 0`);
                        
                        // Set flag to indicate system update (not user)
                        node._Eclipse_updatingIndex = true;
                        
                        indexWidget.value = 0;
                        if (indexWidget.callback) {
                            indexWidget.callback(0);
                        }
                        
                        // Clear flag after update
                        node._Eclipse_updatingIndex = false;
                    }
                    
                    // Trigger refresh_list to force file rescan on next execution
                    if (refreshListWidget) {
                        refreshListWidget.value = true;
                        // // // console.log("[LoadImageFromFolder] Enabled refresh_list for next execution");
                    }
                    
                    // Update image count for new folder (constrains random index range)
                    updateImageCountDebounced(node);
                    
                    node.setDirtyCanvas(true, true);
                }
            };
            
            // Include subfolders change handler - update image count
            const includeSubfoldersWidget = getWidget("include_subfolders");
            if (includeSubfoldersWidget) {
                const originalIncludeSubfoldersCallback = includeSubfoldersWidget.callback;
                includeSubfoldersWidget.callback = function(value) {
                    // Call original callback if exists
                    if (originalIncludeSubfoldersCallback) {
                        originalIncludeSubfoldersCallback.apply(this, arguments);
                    }
                    
                    // Update image count when subfolder setting changes
                    // // // console.log(`[LoadImageFromFolder] include_subfolders changed to ${value}`);
                    updateImageCountDebounced(node);
                };
            }
            
            // Index change handler - detect manual changes and clear stop flag
            if (indexWidget) {
                const originalIndexCallback = indexWidget.callback;
                indexWidget.callback = function(value) {
                    // Call original callback if exists
                    if (originalIndexCallback) {
                        originalIndexCallback.apply(this, arguments);
                    }
                    
                    // If user manually changes index (not system update), handle state
                    if (!node._Eclipse_updatingIndex) {
                        // // // console.log(`[LoadImageFromFolder] Manual index change detected: ${node._Eclipse_lastIndex} -> ${value}`);
                        
                        const isSpecialMode = value === MODE_RANDOM || value === MODE_INCREMENT || value === MODE_DECREMENT;
                        
                        if (isSpecialMode) {
                            // Preserve lastResolvedIndex when switching between special modes
                            // Only reset when entering fixed mode
                            const lastIndexButton = node._Eclipse_lastIndexButton;
                            if (lastIndexButton && node._Eclipse_lastResolvedIndex !== null) {
                                // Update button state based on mode and history
                                lastIndexButton.disabled = false;
                                lastIndexButton.name = `♻️ ${node._Eclipse_lastResolvedIndex}`;
                            }
                        } else {
                            // Entering fixed mode - reset tracking
                            node._Eclipse_lastResolvedIndex = null;
                            node._Eclipse_lastIndex = null;
                            
                            const lastIndexButton = node._Eclipse_lastIndexButton;
                            if (lastIndexButton) {
                                lastIndexButton.disabled = true;
                                lastIndexButton.name = "♻️ (Use Last Queued Index)";
                            }
                        }
                        
                        // Clear stop flag - user is manually navigating
                        if (nodeStopTriggered.get(nodeId)) {
                            // // // console.log("[LoadImageFromFolder] Manual index change, clearing stop flag");
                            nodeStopTriggered.set(nodeId, false);
                        }
                    }
                };
            }
            
            // Add "🎲 Randomize Each Time" button
            if (indexWidget) {
                const randomizeButton = node.addWidget("button", "🎲 Randomize Each Time", null, () => {
                    // // // console.log("[LoadImageFromFolder] Randomize button clicked");
                    node._Eclipse_updatingIndex = true;
                    indexWidget.value = MODE_RANDOM;
                    if (indexWidget.callback) {
                        indexWidget.callback(MODE_RANDOM);
                    }
                    node._Eclipse_updatingIndex = false;
                    node.setDirtyCanvas(true, true);
                });
                randomizeButton.serialize = false;
            }
            
            // Add "♻️ Use Last Queued Index" button (starts disabled)
            if (indexWidget) {
                const lastIndexButton = node.addWidget("button", "♻️ (Use Last Queued Index)", null, () => {
                    if (node._Eclipse_lastResolvedIndex !== null) {
                        // // // console.log(`[LoadImageFromFolder] Use last queued index: ${node._Eclipse_lastResolvedIndex}`);
                        node._Eclipse_manualIndex = true;
                        node._Eclipse_updatingIndex = true;
                        indexWidget.value = node._Eclipse_lastResolvedIndex;
                        if (indexWidget.callback) {
                            indexWidget.callback(node._Eclipse_lastResolvedIndex);
                        }
                        node._Eclipse_updatingIndex = false;
                        node._Eclipse_manualIndex = false;
                        node.setDirtyCanvas(true, true);
                    }
                });
                lastIndexButton.serialize = false;
                lastIndexButton.disabled = true;  // Start disabled until first queue with history
                
                // Store reference for later access
                node._Eclipse_lastIndexButton = lastIndexButton;
            }
            
            // Clean up when node is removed
            const onRemoved = node.onRemoved;
            node.onRemoved = function() {
                nodeFolderPaths.delete(nodeId);
                nodeStopTriggered.delete(nodeId);
                nodeImageCounts.delete(nodeId);
                // Clear any pending debounce timer
                if (fetchDebounceTimers.has(nodeId)) {
                    clearTimeout(fetchDebounceTimers.get(nodeId));
                    fetchDebounceTimers.delete(nodeId);
                }
                if (onRemoved) {
                    onRemoved.apply(this, arguments);
                }
            };
            
            // Initial image count fetch (if folder is already set)
            if (folderPathWidget.value && folderPathWidget.value.trim()) {
                // Delay initial fetch to allow node to fully initialize
                setTimeout(() => {
                    updateImageCount(node);
                }, 100);
            }
            
            return r;
        };
        
        // Method to calculate index based on special modes (-1, -2, -3)
        nodeType.prototype.getIndexToUse = function(stopAtEnd = true) {
            const indexWidget = this._Eclipse_indexWidget;
            
            if (!indexWidget) {
                return 0;
            }
            
            const widgetIndex = indexWidget.value;
            const lastIndex = this._Eclipse_lastIndex;
            const maxIndex = indexWidget.options?.max ?? 999999;
            const imageCount = nodeImageCounts.get(this.id) || (maxIndex + 1);
            
            let indexToUse = widgetIndex;
            
            // Handle special modes
            if (widgetIndex === MODE_RANDOM) {
                // -1: Random
                if (imageCount > 1) {
                    // Try to avoid same index as last time
                    let attempts = 0;
                    do {
                        indexToUse = Math.floor(Math.random() * imageCount);
                        attempts++;
                    } while (indexToUse === lastIndex && attempts < 10);
                } else {
                    indexToUse = 0;
                }
            } else if (widgetIndex === MODE_INCREMENT) {
                // -2: Increment
                const baseIndex = lastIndex !== null ? lastIndex : 0;
                indexToUse = baseIndex + 1;
                
                // Check stop_at_end setting
                if (!stopAtEnd && indexToUse > maxIndex) {
                    // Wrap to start when stop_at_end=false
                    indexToUse = 0;
                } else if (indexToUse > maxIndex) {
                    // Clamp at max when stop_at_end=true (Python will handle stop)
                    indexToUse = maxIndex;
                }
            } else if (widgetIndex === MODE_DECREMENT) {
                // -3: Decrement
                const baseIndex = lastIndex !== null ? lastIndex : maxIndex;
                indexToUse = baseIndex - 1;
                
                // Check stop_at_end setting
                if (!stopAtEnd && indexToUse < 0) {
                    // Wrap to end when stop_at_end=false
                    indexToUse = maxIndex;
                } else if (indexToUse < 0) {
                    // Clamp at 0 when stop_at_end=true (Python will handle stop)
                    indexToUse = 0;
                }
            } else {
                // Fixed mode: use widget value as-is
                indexToUse = widgetIndex;
            }
            
            return indexToUse;
        };
    },
    
    async setup() {
        // Listen for stop-iteration to disable auto-queue and track which nodes triggered it
        api.addEventListener("stop-iteration", (event) => {
            // // // console.log("[Eclipse] Received stop-iteration signal, disabling auto-queue...");
            
            // === DISABLE AUTO-QUEUE ===
            // IMPORTANT: We only toggle the ENABLED state, not the MODE.
            // Setting mode to "disabled" breaks re-enabling via UI checkbox.
            
            // Method 1: Try the classic checkbox (older ComfyUI versions)
            const autoQueueCheckbox = document.getElementById("autoQueueCheckbox");
            if (autoQueueCheckbox && autoQueueCheckbox.checked) {
                autoQueueCheckbox.checked = false;
                autoQueueCheckbox.dispatchEvent(new Event('change', { bubbles: true }));
                // // // console.log("[Eclipse] Auto-queue disabled via checkbox");
            }
            
            // Method 2: Try app.ui.autoQueueEnabled (toggle enabled, NOT mode)
            if (app.ui) {
                if (app.ui.autoQueueEnabled !== undefined) {
                    app.ui.autoQueueEnabled = false;
                    // // // console.log("[Eclipse] Auto-queue disabled via app.ui.autoQueueEnabled");
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
                    // // // console.log("[Eclipse] Auto-queue disabled via auto toggle");
                }
            } catch (e) {
                // Toggle not found
            }
            
            // // // console.log("[Eclipse] Stop-iteration handling complete");
            
            // === TRACK NODES AND RESET INDEX ===
            // Mark all LoadImageFromFolder nodes as having triggered stop
            // AND reset their index to 0 so the next run starts fresh
            // This is CRITICAL - without resetting index, IS_CHANGED returns the same value
            // and ComfyUI skips execution (uses cached result)
            const nodes = app.graph?._nodes || [];
            for (const node of nodes) {
                if (node.type === NODE_NAME) {
                    nodeStopTriggered.set(node.id, true);
                    // // // console.log(`[LoadImageFromFolder] Node ${node.id} triggered stop-iteration`);
                    
                    // Reset index to 0 so next execution starts from beginning
                    const indexWidget = node.widgets?.find(w => w.name === "index");
                    if (indexWidget) {
                        // // // console.log(`[LoadImageFromFolder] Resetting index from ${indexWidget.value} to 0 for next run`);
                        
                        // Set flag to indicate system update (not user)
                        node._Eclipse_updatingIndex = true;
                        
                        indexWidget.value = 0;
                        if (indexWidget.callback) {
                            indexWidget.callback(0);
                        }
                        
                        // Clear flag after update
                        node._Eclipse_updatingIndex = false;
                        
                        node.setDirtyCanvas(true, true);
                    }
                    
                    // Clear last executed index since we're resetting
                    node._Eclipse_lastIndex = null;
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
                            // // // console.log(`[LoadImageFromFolder] Reset refresh_list for node ${node.id}`);
                        }, 500);
                    }
                }
            }
        });
        
        // Update image counts for all nodes when graph is configured (workflow load)
        // This ensures index max is correct after loading a workflow
        const originalConfigure = app.graph?.configure?.bind(app.graph);
        if (app.graph && originalConfigure) {
            app.graph.configure = function(data) {
                const result = originalConfigure(data);
                
                // Delay to allow nodes to fully initialize after workflow load
                setTimeout(() => {
                    const nodes = app.graph?._nodes || [];
                    for (const node of nodes) {
                        if (node.type === NODE_NAME) {
                            const folderPathWidget = node.widgets?.find(w => w.name === "folder_path");
                            if (folderPathWidget && folderPathWidget.value && folderPathWidget.value.trim()) {
                                updateImageCount(node);
                            }
                        }
                    }
                }, 200);
                
                return result;
            };
        }
        
        // Hook into graphToPrompt to calculate and apply index before sending to server
        // This is the same pattern used by eclipse-seed.js
        const originalGraphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function() {
            // Call the original graphToPrompt first
            const result = await originalGraphToPrompt.apply(this, arguments);
            
            if (!result || !result.output) {
                return result;
            }
            
            // Process all LoadImageFromFolder nodes
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
                
                // Get stop_at_end setting from inputs
                const stopAtEnd = result.output[nodeId].inputs?.stop_at_end !== false;
                
                // Calculate the index to use based on special mode
                const indexToUse = node.getIndexToUse(stopAtEnd);
                const indexWidget = node._Eclipse_indexWidget;
                const currentWidgetValue = indexWidget.value;
                const isSpecialMode = currentWidgetValue === MODE_RANDOM || currentWidgetValue === MODE_INCREMENT || currentWidgetValue === MODE_DECREMENT;
                
                // // // console.log(`[LoadImageFromFolder] graphToPrompt: widget=${currentWidgetValue}, calculated=${indexToUse}, stopAtEnd=${stopAtEnd}`);
                
                // Update the index in the prompt output (what gets sent to server)
                if (result.output[nodeId].inputs && result.output[nodeId].inputs.index !== undefined) {
                    result.output[nodeId].inputs.index = indexToUse;
                }
                
                // In special mode: keep index widget at -1/-2/-3, don't update to resolved value
                // In fixed mode: update widget to show actual value
                if (!isSpecialMode && indexWidget.value !== indexToUse) {
                    // Set flag to indicate system is updating (not user)
                    node._Eclipse_updatingIndex = true;
                    
                    indexWidget.value = indexToUse;
                    if (indexWidget.callback) {
                        indexWidget.callback(indexToUse);
                    }
                    
                    // Clear flag after update
                    node._Eclipse_updatingIndex = false;
                    
                    node.setDirtyCanvas(true, true);
                }
                
                // Store resolved index and update button state
                if (isSpecialMode) {
                    node._Eclipse_lastResolvedIndex = indexToUse;
                    
                    const lastIndexButton = node._Eclipse_lastIndexButton;
                    if (lastIndexButton) {
                        lastIndexButton.disabled = false;
                        lastIndexButton.name = `♻️ ${indexToUse}`;
                    }
                } else {
                    // Fixed mode - disable button
                    const lastIndexButton = node._Eclipse_lastIndexButton;
                    if (lastIndexButton) {
                        lastIndexButton.disabled = true;
                        lastIndexButton.name = "♻️ (Use Last Queued Index)";
                    }
                }
                
                // Store as last executed index for next iteration
                node._Eclipse_lastIndex = indexToUse;
                
                // Also update workflow data if present
                if (result.workflow && result.workflow.nodes) {
                    const workflowNode = result.workflow.nodes.find(n => n.id === node.id);
                    if (workflowNode && workflowNode.widgets_values) {
                        const indexWidgetIndex = node.widgets.indexOf(indexWidget);
                        if (indexWidgetIndex >= 0) {
                            workflowNode.widgets_values[indexWidgetIndex] = isSpecialMode ? currentWidgetValue : indexToUse;
                        }
                    }
                }
            }
            
            return result;
        };
    },
});
