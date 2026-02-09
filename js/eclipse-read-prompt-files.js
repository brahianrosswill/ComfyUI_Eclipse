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

const NODE_NAME = "Read Prompt Files [Eclipse]";

// Special seeds (same as eclipse-seed.js and smart-prompt)
const SPECIAL_SEED_RANDOM = -1;
const SPECIAL_SEED_INCREMENT = -2;
const SPECIAL_SEED_DECREMENT = -3;
const SPECIAL_SEEDS = [SPECIAL_SEED_RANDOM, SPECIAL_SEED_INCREMENT, SPECIAL_SEED_DECREMENT];

// Node tracking for file path changes
const nodeFilePaths = new Map(); // nodeId -> last file_paths value

app.registerExtension({
    name: "Eclipse.ReadPromptFiles",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        // // // console.log(`[Eclipse-ReadPromptFiles] Registering node: ${NODE_NAME}`);
        
        // Override the graphToPrompt to handle index control based on seed changes
        const origGraphToPrompt = app.graphToPrompt;
        app.graphToPrompt = async function() {
            const result = await origGraphToPrompt.apply(this, arguments);
            
            // Process ReadPromptFiles nodes to handle index control
            const graph = app.graph;
            for (const nodeId in result.output) {
                const node = graph.getNodeById(Number(nodeId));
                if (node && node.constructor === nodeType) {
                    // // // console.log(`[ReadPromptFiles] Processing node ${nodeId}`);
                    
                    // Skip if manual index is set
                    if (node._Eclipse_manualIndex !== undefined) {
                        result.output[nodeId].inputs.index = node._Eclipse_manualIndex;
                        // // // console.log(`[ReadPromptFiles] Manual index ${node._Eclipse_manualIndex} applied`);
                        
                        // Update lastResolvedIndex even for manual indices so button shows correct value
                        node._Eclipse_lastResolvedIndex = node._Eclipse_manualIndex;
                        continue;
                    }
                    
                    // Get current index status (no external connections supported)
                    let actualIndex = null;
                    let indexChanged = false;
                    
                    if (node._Eclipse_indexWidget) {
                        const originalWidgetIndex = Number(node._Eclipse_indexWidget.value);
                        
                        // Handle special index modes BEFORE calling getIndexToUse
                        if (SPECIAL_SEEDS.includes(originalWidgetIndex)) {
                            // // // console.log(`[ReadPromptFiles] Special index mode detected: ${originalWidgetIndex}`);
                            
                            switch (originalWidgetIndex) {
                                case SPECIAL_SEED_RANDOM:
                                    // Random index within proper bounds
                                    const maxForRandom = await node.getMaxIndex();
                                    if (maxForRandom >= 0) {
                                        actualIndex = Math.floor(Math.random() * (maxForRandom + 1));
                                        // // // console.log(`[ReadPromptFiles] Random index: ${actualIndex} (range: 0-${maxForRandom})`);
                                    } else {
                                        actualIndex = 0;
                                        // // // console.log(`[ReadPromptFiles] No prompts available, using index 0`);
                                    }
                                    break;
                                    
                                case SPECIAL_SEED_INCREMENT:
                                    // Increment from the correct base index
                                    const maxForIncrement = await node.getMaxIndex();
                                    if (maxForIncrement >= 0) {
                                        // Get stop_at_end setting from inputs
                                        const stopAtEnd = result.output[nodeId].inputs.stop_at_end !== false;
                                        
                                        // Priority: 1) Manual base index, 2) Last resolved index, 3) First run starts at 0
                                        if (node._Eclipse_baseIndexForNavigation !== undefined && !SPECIAL_SEEDS.includes(node._Eclipse_baseIndexForNavigation)) {
                                            const baseIndex = node._Eclipse_baseIndexForNavigation;
                                            // // // console.log(`[ReadPromptFiles] Using base index from manual setting: ${baseIndex}`);
                                            // Clear the base index after using it once
                                            node._Eclipse_baseIndexForNavigation = undefined;
                                            
                                            if (!stopAtEnd && baseIndex + 1 > maxForIncrement) {
                                                // Wrap around to 0
                                                actualIndex = 0;
                                                // // // console.log(`[ReadPromptFiles] Increment wrapped from ${baseIndex} to 0 (max: ${maxForIncrement})`);
                                            } else {
                                                actualIndex = (baseIndex + 1) % (maxForIncrement + 1);
                                                // // // console.log(`[ReadPromptFiles] Increment from ${baseIndex} to ${actualIndex} (max: ${maxForIncrement})`);
                                            }
                                        } else if (node._Eclipse_lastResolvedIndex !== undefined && !SPECIAL_SEEDS.includes(node._Eclipse_lastResolvedIndex)) {
                                            const baseIndex = node._Eclipse_lastResolvedIndex;
                                            // // // console.log(`[ReadPromptFiles] Using base index from last resolved: ${baseIndex}`);
                                            
                                            if (!stopAtEnd && baseIndex + 1 > maxForIncrement) {
                                                // Wrap around to 0
                                                actualIndex = 0;
                                                // // // console.log(`[ReadPromptFiles] Increment wrapped from ${baseIndex} to 0 (max: ${maxForIncrement})`);
                                            } else {
                                                actualIndex = (baseIndex + 1) % (maxForIncrement + 1);
                                                // // // console.log(`[ReadPromptFiles] Increment from ${baseIndex} to ${actualIndex} (max: ${maxForIncrement})`);
                                            }
                                        } else {
                                            // First run - start at 0, don't increment yet
                                            actualIndex = 0;
                                            // // // console.log(`[ReadPromptFiles] First increment run, starting at 0 (max: ${maxForIncrement})`);
                                        }
                                    } else {
                                        actualIndex = 0;
                                    }
                                    break;
                                    
                                case SPECIAL_SEED_DECREMENT:
                                    // Decrement from the correct base index
                                    const maxForDecrement = await node.getMaxIndex();
                                    if (maxForDecrement >= 0) {
                                        // Get stop_at_end setting from inputs
                                        const stopAtEnd = result.output[nodeId].inputs.stop_at_end !== false;
                                        
                                        // Priority: 1) Manual base index, 2) Last resolved index, 3) First run starts at max
                                        if (node._Eclipse_baseIndexForNavigation !== undefined && !SPECIAL_SEEDS.includes(node._Eclipse_baseIndexForNavigation)) {
                                            const baseIndex = node._Eclipse_baseIndexForNavigation;
                                            // // // console.log(`[ReadPromptFiles] Using base index from manual setting: ${baseIndex}`);
                                            // Clear the base index after using it once
                                            node._Eclipse_baseIndexForNavigation = undefined;
                                            
                                            if (!stopAtEnd && baseIndex - 1 < 0) {
                                                // Wrap around to max
                                                actualIndex = maxForDecrement;
                                                // // // console.log(`[ReadPromptFiles] Decrement wrapped from ${baseIndex} to ${maxForDecrement}`);
                                            } else {
                                                actualIndex = baseIndex > 0 ? baseIndex - 1 : maxForDecrement;
                                                // // // console.log(`[ReadPromptFiles] Decrement from ${baseIndex} to ${actualIndex} (max: ${maxForDecrement})`);
                                            }
                                        } else if (node._Eclipse_lastResolvedIndex !== undefined && !SPECIAL_SEEDS.includes(node._Eclipse_lastResolvedIndex)) {
                                            const baseIndex = node._Eclipse_lastResolvedIndex;
                                            // // // console.log(`[ReadPromptFiles] Using base index from last resolved: ${baseIndex}`);
                                            
                                            if (!stopAtEnd && baseIndex - 1 < 0) {
                                                // Wrap around to max
                                                actualIndex = maxForDecrement;
                                                // // // console.log(`[ReadPromptFiles] Decrement wrapped from ${baseIndex} to ${maxForDecrement}`);
                                            } else {
                                                actualIndex = baseIndex > 0 ? baseIndex - 1 : maxForDecrement;
                                                // // // console.log(`[ReadPromptFiles] Decrement from ${baseIndex} to ${actualIndex} (max: ${maxForDecrement})`);
                                            }
                                        } else {
                                            // First run - start at max index, don't decrement yet
                                            actualIndex = maxForDecrement;
                                            // // // console.log(`[ReadPromptFiles] First decrement run, starting at max index ${maxForDecrement}`);
                                        }
                                    } else {
                                        actualIndex = 0;
                                    }
                                    break;
                            }
                        } else {
                            // Regular index value, use getIndexToUse for processing
                            actualIndex = node.getIndexToUse();
                        }
                        
                        if (actualIndex !== null) {
                            result.output[nodeId].inputs.index = actualIndex;
                            indexChanged = node._Eclipse_lastResolvedIndex === undefined || String(node._Eclipse_lastResolvedIndex) !== String(actualIndex);
                        }
                    }
                    
                    // // // console.log(`[ReadPromptFiles] Index: ${actualIndex}, Changed: ${indexChanged}`);
                    
                    // Update tracking BEFORE button update
                    if (indexChanged && actualIndex !== null) {
                        node._Eclipse_lastResolvedIndex = actualIndex;
                    }
                    
                    // Update button state to show LAST queued index (not the next one)
                    if (node._Eclipse_lastIndexButton) {
                        const currentWidgetIndex = node._Eclipse_indexWidget?.value;
                        if (SPECIAL_SEEDS.includes(Number(currentWidgetIndex))) {
                            // Widget has special index mode, show the LAST queued index
                            if (node._Eclipse_lastResolvedIndex !== undefined) {
                                node._Eclipse_lastIndexButton.name = `♻️ ${node._Eclipse_lastResolvedIndex}`;
                                node._Eclipse_lastIndexButton.disabled = false;
                            } else {
                                // No history yet
                                node._Eclipse_lastIndexButton.name = "♻️ (Use Last Queued Index)";
                                node._Eclipse_lastIndexButton.disabled = true;
                            }
                        } else {
                            // Widget has regular index value
                            node._Eclipse_lastIndexButton.name = "♻️ (Use Last Queued Index)";
                            node._Eclipse_lastIndexButton.disabled = true;
                        }
                    }
                    
                    if (indexChanged && actualIndex !== null) {
                        // // // console.log(`[ReadPromptFiles] *** INDEX CHANGED - Updating tracking ***`);
                        // Tracking already updated above, no need to duplicate
                    }
                }
            }
            
            return result;
        };
        
        // Store original onNodeCreated
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        
        nodeType.prototype.onNodeCreated = function() {
            const result = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            
            // // // console.log(`[Eclipse-ReadPromptFiles] Node created:`, this);
            
            // Initialize state
            this._Eclipse_lastIndex = undefined;
            this._Eclipse_lastResolvedIndex = undefined;
            this._Eclipse_manualIndex = undefined;
            this._Eclipse_baseIndexForNavigation = undefined; // Store manual index for navigation base
            this._Eclipse_cachedInputIndex = null;
            this._Eclipse_cachedResolvedIndex = null;
            
            // Find and setup index widget (replaces both seed and index widgets)
            let indexWidget = null;
            
            for (const [i, widget] of this.widgets.entries()) {
                const wname = (widget.name || '').toString().toLowerCase();
                const wlabel = (widget.label || widget.options?.label || widget.options?.name || '').toString().toLowerCase();
                
                if (wname === 'index' || wlabel === 'index') {
                    indexWidget = widget;
                } else if (wname === 'control_after_generate') {
                    // Remove control_after_generate widget
                    this.widgets.splice(i, 1);
                }
            }
            
            if (!indexWidget) {
                console.warn(`[Eclipse-ReadPromptFiles] Could not find Index widget`);
                return result;
            }
            
            // Store widget and initialize properties
            this._Eclipse_indexWidget = indexWidget;
            
            // Track file paths for cache invalidation
            const nodeId = this.id;
            const filePathsWidget = this.widgets?.find(w => 
                (w.name || '').toLowerCase().includes('file_paths') ||
                (w.name || '').toLowerCase().includes('filepaths')
            );
            
            if (filePathsWidget) {
                // Store initial file paths
                nodeFilePaths.set(nodeId, filePathsWidget.value);
                
                // Capture node reference for use in callback
                const node = this;
                
                // File paths change handler
                const originalFilePathsCallback = filePathsWidget.callback;
                filePathsWidget.callback = function(value) {
                    const previousPaths = nodeFilePaths.get(nodeId);
                    
                    // Call original callback if exists
                    if (originalFilePathsCallback) {
                        originalFilePathsCallback.apply(this, arguments);
                    }
                    
                    // Skip processing if node ID is invalid (during initial setup)
                    if (!nodeId || nodeId < 0) {
                        nodeFilePaths.set(nodeId, value); // Still track the value
                        return;
                    }
                    
                    // Check if file paths actually changed (skip empty -> empty transitions)
                    if (value !== previousPaths && !(previousPaths === "" && value === "")) {
                        // // // console.log(`[ReadPromptFiles] File paths changed for node ${nodeId}`);
                        
                        // Only log details if both values are meaningful
                        if (previousPaths || value) {
                            // // // console.log(`[ReadPromptFiles] Updating from ${previousPaths ? 'existing' : 'empty'} paths to ${value ? 'new' : 'empty'} paths`);
                        }
                        
                        // Update stored paths
                        nodeFilePaths.set(nodeId, value);
                        
                        // Clear cached resolved index - new files means fresh start
                        node._Eclipse_lastResolvedIndex = undefined;
                        node._Eclipse_cachedInputIndex = null;
                        node._Eclipse_cachedResolvedIndex = null;
                        
                        // Notify backend to clear cache for old file paths
                        if (previousPaths && previousPaths.trim()) {
                            fetch('/eclipse/read_prompt_files/invalidate_cache', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ file_paths: previousPaths })
                            }).catch(e => {
                                // Endpoint may not exist yet, that's ok
                                // // // console.log("[ReadPromptFiles] Cache invalidation endpoint not available");
                            });
                        }
                        
                        // Update max index range for new file paths and check if current index is still valid
                        if (value && value.trim()) {
                            node.getMaxIndex().then(newMaxIndex => {
                                if (indexWidget.options) {
                                    const oldMax = indexWidget.options.max || 0;
                                    const currentIndex = indexWidget.value || 0;
                                    indexWidget.options.max = Math.max(0, newMaxIndex);
                                    // // // console.log(`[ReadPromptFiles] Updated index max from ${oldMax} to ${indexWidget.options.max} (${newMaxIndex + 1} total prompts)`);
                                    
                                    // Only reset index if current index is out of range
                                    if (currentIndex > indexWidget.options.max) {
                                        // // // console.log(`[ReadPromptFiles] Current index ${currentIndex} is out of range (max: ${indexWidget.options.max}), resetting to 0`);
                                        indexWidget.value = 0;
                                        if (indexWidget.callback) {
                                            indexWidget.callback(0);
                                        }
                                    } else if (currentIndex <= indexWidget.options.max) {
                                        // // // console.log(`[ReadPromptFiles] Current index ${currentIndex} is still valid (max: ${indexWidget.options.max}), keeping current position`);
                                    }
                                }
                            }).catch(err => {
                                console.warn(`[ReadPromptFiles] Error updating max index:`, err);
                                // Fallback: reset to 0 if we can't determine the new range
                                // // // console.log(`[ReadPromptFiles] Fallback: resetting index to 0 due to error`);
                                indexWidget.value = 0;
                                if (indexWidget.callback) {
                                    indexWidget.callback(0);
                                }
                            });
                        }
                        
                        // Update last index button
                        if (node._Eclipse_lastIndexButton) {
                            node._Eclipse_lastIndexButton.disabled = true;
                        }
                    }
                };
            }
            
            // Hook into widget to clear cache when value changes
            const originalIndexCallback = indexWidget.callback;
            indexWidget.callback = (value) => {
                this._Eclipse_cachedInputIndex = null;
                this._Eclipse_cachedResolvedIndex = null;
                
                // Check if this is a manual change to a fixed index (non-special value)
                if (!SPECIAL_SEEDS.includes(Number(value))) {
                    this._Eclipse_manualIndex = value;
                    this._Eclipse_baseIndexForNavigation = value; // Store as base for navigation
                    // // // console.log(`[ReadPromptFiles] Manual index set: ${value}`);
                    
                    // Disable the "Use Last Queued Index" button when manually setting a fixed index
                    if (this._Eclipse_lastIndexButton) {
                        this._Eclipse_lastIndexButton.name = "♻️ (Use Last Queued Index)";
                        this._Eclipse_lastIndexButton.disabled = true;
                    }
                } else {
                    this._Eclipse_manualIndex = undefined; // Clear manual override for special modes
                    // // // console.log(`[ReadPromptFiles] Navigation mode set: ${value}`);
                    // Don't clear _Eclipse_baseIndexForNavigation here - keep it for increment/decrement
                    
                    // Enable the button for special modes (will show last resolved index after queue)
                    if (this._Eclipse_lastIndexButton && this._Eclipse_lastResolvedIndex !== undefined) {
                        this._Eclipse_lastIndexButton.name = `♻️ ${this._Eclipse_lastResolvedIndex}`;
                        this._Eclipse_lastIndexButton.disabled = false;
                    }
                }
                
                if (originalIndexCallback) {
                    return originalIndexCallback.call(indexWidget, value);
                }
            };
            
            // Add navigation buttons for the index widget
            const randomizeButton = this.addWidget(
                "button",
                "🎲 Randomize Each Time",
                "",
                () => {
                    indexWidget.value = SPECIAL_SEED_RANDOM;
                    this._Eclipse_manualIndex = undefined; // Clear manual index
                    if (indexWidget.callback) {
                        indexWidget.callback(SPECIAL_SEED_RANDOM);
                    }
                },
                { serialize: false }
            );
            
            const lastIndexButton = this.addWidget(
                "button",
                "♻️ (Use Last Queued Index)",
                "",
                () => {
                    if (this._Eclipse_lastResolvedIndex != null) {
                        indexWidget.value = this._Eclipse_lastResolvedIndex;
                        this._Eclipse_manualIndex = this._Eclipse_lastResolvedIndex; // Set as manual index
                        lastIndexButton.name = "♻️ (Use Last Queued Index)";
                        lastIndexButton.disabled = true;
                        // // // console.log(`[ReadPromptFiles] Using last queued index: ${this._Eclipse_lastResolvedIndex}`);
                        if (indexWidget.callback) {
                            indexWidget.callback(this._Eclipse_lastResolvedIndex);
                        }
                    }
                },
                { serialize: false }
            );
            lastIndexButton.disabled = true;
            this._Eclipse_lastIndexButton = lastIndexButton;
            
            // Index control functions (based on SmartPrompt pattern)
            this.generateRandomIndex = async function() {
                // Get actual prompt bounds instead of using hardcoded values
                const maxIndex = await this.getMaxIndex();
                if (maxIndex >= 0) {
                    let index = Math.floor(Math.random() * (maxIndex + 1));
                    
                    // Avoid special index modes
                    if (SPECIAL_SEEDS.includes(index)) {
                        index = 0;
                    }
                    // // // console.log(`[ReadPromptFiles] Generated random fixed index: ${index} (range: 0-${maxIndex})`);
                    return index;
                } else {
                    // // // console.log(`[ReadPromptFiles] No prompts available, using index 0`);
                    return 0;
                }
            };
            
            this.getIndexToUse = function() {
                const inputIndex = Number(this._Eclipse_indexWidget.value);
                
                // Check cache
                if (this._Eclipse_cachedInputIndex === inputIndex && this._Eclipse_cachedResolvedIndex != null) {
                    return this._Eclipse_cachedResolvedIndex;
                }
                
                let indexToUse = null;
                
                // Handle special index modes - but these should be handled in graphToPrompt now
                if (SPECIAL_SEEDS.includes(inputIndex)) {
                    // For special modes, return a safe default - actual logic is in graphToPrompt
                    // // // console.log(`[ReadPromptFiles] getIndexToUse: Special mode ${inputIndex}, returning 0 as placeholder`);
                    indexToUse = 0;
                }
                
                const finalIndex = indexToUse != null ? indexToUse : inputIndex;
                
                // Cache the result
                this._Eclipse_cachedInputIndex = inputIndex;
                this._Eclipse_cachedResolvedIndex = finalIndex;
                
                return finalIndex;
            };
            
            // Create seeded RNG function
            this.createSeededRNG = function(indexSeed) {
                // Simple seeded random number generator
                let state = indexSeed;
                return function() {
                    state = (state * 9301 + 49297) % 233280;
                    return state / 233280;
                };
            };
            
            // Get max index from server
            this.getMaxIndex = async function() {
                try {
                    const filePaths = this._Eclipse_getFilePathsValue();
                    if (!filePaths || !filePaths.trim()) {
                        // // // console.log(`[ReadPromptFiles] No file paths provided, max index = 0`);
                        return 0;
                    }
                    
                    const response = await api.fetchApi("/eclipse/read_prompt_files_count", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ file_paths: filePaths })
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        const count = data.count || 0;
                        const maxIndex = Math.max(0, count - 1);
                        // // // console.log(`[ReadPromptFiles] Server returned count: ${count}, calculated max index: ${maxIndex}`);
                        return maxIndex;
                    } else {
                        console.warn(`[ReadPromptFiles] Server error getting count: ${response.status} ${response.statusText}`);
                    }
                } catch (error) {
                    console.warn(`[ReadPromptFiles] Error getting max index:`, error);
                }
                // // // console.log(`[ReadPromptFiles] Defaulting to max index = 0 due to error`);
                return 0;
            };
            
            // Get file paths value from widget
            this._Eclipse_getFilePathsValue = function() {
                const filePathsWidget = this.widgets?.find(w => 
                    (w.name || '').toLowerCase().includes('file_paths') ||
                    (w.name || '').toLowerCase().includes('filepaths')
                );
                return filePathsWidget?.value || '';
            };
            
            // No external connections supported - index widget is always visible
            // This simplifies the UI and prevents out-of-bounds issues
            
            // Store references to the buttons for easier management
            this._Eclipse_navigationButtons = [randomizeButton, lastIndexButton];
            
            return result;
        };
    }
});