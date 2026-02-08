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
 * Performance utilities for Eclipse nodes with dynamic widget visibility
 * Provides debouncing, visibility detection, and canvas update batching
 */

import { app } from './comfy/index.js';

/**
 * Debounce function to limit how often a function can fire
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function to ensure a function is called at most once per interval
 * @param {Function} func - Function to throttle
 * @param {number} limit - Minimum time between calls in milliseconds
 * @returns {Function} Throttled function
 */
export function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Check if a node is currently visible in the canvas viewport
 * @param {Object} node - The LiteGraph node
 * @returns {boolean} True if node is visible
 */
export function isNodeVisible(node) {
    if (!node || !app.canvas) return false;
    
    // Check if canvas exists and has the isNodeVisible method
    if (app.canvas.isNodeVisible && typeof app.canvas.isNodeVisible === 'function') {
        return app.canvas.isNodeVisible(node);
    }
    
    // Fallback: Manual visibility check using visible_area
    const canvas = app.canvas;
    if (!canvas.visible_area || !node.pos || !node.size) return true; // Assume visible if we can't determine
    
    const [vx, vy, vw, vh] = canvas.visible_area;
    const [nx, ny] = node.pos;
    const [nw, nh] = node.size;
    
    // Check if node bounding box overlaps with visible area
    return !(nx > vx + vw || nx + nw < vx || ny > vy + vh || ny + nh < vy);
}

/**
 * Batch canvas dirty flag updates to avoid multiple redraws
 */
export const canvasDirtyBatcher = {
    pending: new Map(),
    scheduled: false,
    
    /**
     * Mark a node as needing a canvas update
     * Uses Map keyed by node ID to deduplicate multiple marks per frame
     * @param {Object} node - The node to mark dirty
     * @param {boolean} foreground - Whether to mark foreground dirty
     * @param {boolean} background - Whether to mark background dirty
     */
    markDirty(node, foreground = true, background = false) {
        const key = node?.id ?? node;
        const existing = this.pending.get(key);
        if (existing) {
            // Merge flags - once true, stays true
            existing.foreground = existing.foreground || foreground;
            existing.background = existing.background || background;
        } else {
            this.pending.set(key, { node, foreground, background });
        }
        
        if (!this.scheduled) {
            this.scheduled = true;
            requestAnimationFrame(() => this.flush());
        }
    },
    
    /**
     * Flush all pending dirty marks
     */
    flush() {
        this.scheduled = false;
        
        if (this.pending.size === 0) return;
        
        // Apply all dirty marks at once
        for (const { node, foreground, background } of this.pending.values()) {
            if (node && node.setDirtyCanvas) {
                node.setDirtyCanvas(foreground, background);
            }
        }
        
        this.pending.clear();
    }
};

/**
 * Create a widget visibility manager for a node
 * Handles showing/hiding widgets with caching to avoid redundant updates
 * @param {Object} node - The LiteGraph node
 * @returns {Object} Widget visibility manager
 */
export function createWidgetVisibilityManager(node) {
    const cache = new Map();
    
    return {
        /**
         * Set a widget's visibility state
         * @param {string} widgetName - Name of the widget
         * @param {boolean} visible - Whether widget should be visible
         */
        setVisible(widgetName, visible) {
            const widget = node.widgets?.find(w => w.name === widgetName);
            if (!widget) return;
            
            // Check cache to avoid redundant updates
            const cachedState = cache.get(widgetName);
            if (cachedState === visible) {
                return; // No change needed
            }
            cache.set(widgetName, visible);

            if (visible) {
                // Show widget - restore original type
                if (widget.origType) {
                    widget.type = widget.origType;
                } else if (widget.type === "converted-widget") {
                    // Default to "combo" as that's what most widgets are
                    console.warn(`[Eclipse] Widget "${widgetName}" is converted-widget but has no origType, defaulting to combo`);
                    widget.type = "combo";
                    widget.origType = "combo";
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
        },
        
        /**
         * Get a widget's value safely
         * @param {string} name - Widget name
         * @returns {*} Widget value or null
         */
        getValue(name) {
            const widget = node.widgets?.find(w => w.name === name);
            return widget ? widget.value : null;
        },
        
        /**
         * Clear the visibility cache
         */
        clearCache() {
            cache.clear();
        }
    };
}

/**
 * Setup lazy initialization for a node that only runs when node becomes visible
 * @param {Object} node - The LiteGraph node
 * @param {Function} initCallback - Callback to run when node becomes visible
 */
export function setupLazyInit(node, initCallback) {
    if (!node._Eclipse_visibilityInitialized) {
        node._Eclipse_visibilityInitialized = false;
        
        const originalOnDrawForeground = node.onDrawForeground;
        
        node.onDrawForeground = function(ctx) {
            if (originalOnDrawForeground) {
                originalOnDrawForeground.call(this, ctx);
            }
            
            if (!this._Eclipse_visibilityInitialized) {
                this._Eclipse_visibilityInitialized = true;
                
                requestAnimationFrame(() => {
                    if (typeof initCallback === 'function') {
                        initCallback.call(this);
                    }
                });
            }
        };
    }
}

/**
 * Create a debounced resize handler for a node
 * @param {Object} node - The LiteGraph node
 * @param {number} debounceTime - Debounce time in milliseconds (default: 100)
 * @returns {Function} Debounced resize function
 */
export function createDebouncedResize(node, debounceTime = 100) {
    const doResize = () => {
        if (!isNodeVisible(node)) return;
        
        requestAnimationFrame(() => {
            const computedSize = node.computeSize();
            const currentSize = node.size;
            
            if (computedSize && currentSize) {
                node.setSize([currentSize[0], computedSize[1]]);
                canvasDirtyBatcher.markDirty(node, true, false);
            }
        });
    };
    
    return debounce(doResize, debounceTime);
}

/**
 * Batch multiple node updates together
 * Useful when multiple nodes need to update at once (e.g., when scrolling into view)
 */
export const nodeBatchUpdater = {
    pending: new Set(),
    scheduled: false,
    
    /**
     * Schedule a node update
     * @param {Object} node - Node to update
     * @param {Function} updateFn - Update function to call
     */
    schedule(node, updateFn) {
        this.pending.add({ node, updateFn });
        
        if (!this.scheduled) {
            this.scheduled = true;
            requestAnimationFrame(() => this.process());
        }
    },
    
    /**
     * Process all pending updates
     */
    process() {
        this.scheduled = false;
        
        if (this.pending.size === 0) return;
        
        // Only process visible nodes
        const updates = Array.from(this.pending).filter(({ node }) => isNodeVisible(node));
        
        // Process in batches to avoid blocking the UI
        const BATCH_SIZE = 5;
        let index = 0;
        
        const processBatch = () => {
            const batch = updates.slice(index, index + BATCH_SIZE);
            
            for (const { node, updateFn } of batch) {
                try {
                    if (typeof updateFn === 'function') {
                        updateFn.call(node);
                    }
                } catch (error) {
                    console.error('[Eclipse] Error processing node update:', error);
                }
            }
            
            index += BATCH_SIZE;
            
            if (index < updates.length) {
                requestAnimationFrame(processBatch);
            } else {
                this.pending.clear();
            }
        };
        
        processBatch();
    }
};

export default {
    debounce,
    throttle,
    isNodeVisible,
    canvasDirtyBatcher,
    createWidgetVisibilityManager,
    setupLazyInit,
    createDebouncedResize,
    nodeBatchUpdater
};
