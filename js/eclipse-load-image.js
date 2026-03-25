/**
 * Eclipse - Load Image + Load Image Pipe extension
 * Adds folder source mode-bar (input/output) and a 🗑️ Delete Image button.
 * Uses two plain combos (no upload widget) — all preview loading is manual.
 */

import { app, api } from './comfy/index.js';
import { createWidgetVisibilityManager } from './eclipse-widget-performance-utils.js';

const NODE_CONFIGS = {
    'Load Image (Metadata Pipe) [Eclipse]': { extName: 'Eclipse.LoadImage', cssPrefix: 'li', logPrefix: 'LoadImage', widgetName: '_li_source' },
    'Load Image (Pipe) [Eclipse]': { extName: 'Eclipse.LoadImagePipe', cssPrefix: 'lip', logPrefix: 'LoadImagePipe', widgetName: '_lip_source' },
};
const NODE_NAMES = Object.keys(NODE_CONFIGS);
const MODE_OPTIONS = ['input', 'output'];

// --- Inject mode-bar CSS for each prefix ---
const _cssInjectedPrefixes = new Set();
function injectModeBarCSS(prefix) {
    if (_cssInjectedPrefixes.has(prefix)) return;
    _cssInjectedPrefixes.add(prefix);
    const style = document.createElement('style');
    style.textContent = `
.eclipse-${prefix}-mode-bar {
    display: flex; align-items: center; gap: 4px;
    width: 100%; height: 100%; padding: 0 6px; box-sizing: border-box;
}
.eclipse-${prefix}-mode-chip {
    cursor: pointer; padding: 2px 10px; border-radius: 4px;
    font-size: 0.75rem; font-family: sans-serif; user-select: none;
    background: #2a2a2a; color: #888; border: 1px solid #444;
    flex: 1; text-align: center;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.eclipse-${prefix}-mode-chip.selected {
    background: #2a5a3a; color: #ddd; border-color: #4a8a5a;
}`;
    document.head.appendChild(style);
}
for (const cfg of Object.values(NODE_CONFIGS)) { injectModeBarCSS(cfg.cssPrefix); }

// Fetch image file list from the appropriate endpoint
async function fetchImageList(source) {
    const url = source === 'output'
        ? '/eclipse/load_image/list_output'
        : '/eclipse/load_image/list';
    try {
        const resp = await api.fetchApi(url, { cache: 'no-store' });
        const data = await resp.json();
        return data.success ? data.files : [];
    } catch (e) {
        console.error('[Eclipse LoadImage] Failed to fetch image list:', e);
        return [];
    }
}

// Parse a relative path into {filename, subfolder} for ComfyUI's /view API
function parseImagePath(rel) {
    const parts = (rel || '').split('/');
    const filename = parts.pop();
    const subfolder = parts.join('/');
    return { filename, subfolder };
}

// Build a /view URL for any image
function buildViewURL(rel, type) {
    const { filename, subfolder } = parseImagePath(rel);
    const params = new URLSearchParams({ filename, type, subfolder });
    return api.apiURL(`/view?${params.toString()}`);
}

// Manually load a preview image into node.imgs
async function loadPreview(node, rel, type) {
    // Clear framework output store to prevent unsafeUpdatePreviews interference
    const nodeId = String(node.id);
    if (app.nodeOutputs?.[nodeId]?.images) {
        delete app.nodeOutputs[nodeId].images;
    }
    if (!rel || rel === 'none') {
        node.imgs = null;
        node.setDirtyCanvas(true, true);
        return;
    }
    try {
        const url = buildViewURL(rel, type);
        const img = new Image();
        img.crossOrigin = 'anonymous';
        await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = reject;
            img.src = url + `&cb=${Date.now()}`;
        });
        node.imgs = [img];
    } catch {
        node.imgs = null;
    }
    node.setDirtyCanvas(true, true);
}

// Shared file list cache (global across all Eclipse Load Image nodes)
const _fileListCache = window._eclipseFileListCache || (window._eclipseFileListCache = {
    data: {},     // { input: [...], output: [...] }
    pending: {},  // { input: Promise, output: Promise } — deduplicates concurrent fetches
});

async function getCachedFileList(source) {
    if (_fileListCache.data[source]) return _fileListCache.data[source];
    if (!_fileListCache.pending[source]) {
        _fileListCache.pending[source] = fetchImageList(source).then(files => {
            _fileListCache.data[source] = files;
            _fileListCache.pending[source] = null;
            return files;
        });
    }
    return _fileListCache.pending[source];
}

function invalidateFileListCache(source) {
    delete _fileListCache.data[source];
    delete _fileListCache.pending[source];
}

for (const [nodeName, cfg] of Object.entries(NODE_CONFIGS)) {
app.registerExtension({
    name: cfg.extName,

    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== nodeName) return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origOnNodeCreated?.apply(this, arguments);

            const node = this;
            const vis = createWidgetVisibilityManager(node);

            // Listen for file list changes from other nodes (delete/upload/refresh)
            document.addEventListener('eclipse-filelist-changed', (e) => {
                const source = e.detail?.source;
                if (source && getCurrentSource() === source) {
                    getCachedFileList(source).then(files => applyFileList(files, source));
                }
            });

            // --- Helpers ---
            const getWidget = (name) => node.widgets?.find(w => w.name === name);
            const getSourceWidget = () => getWidget('folder_source');
            const getInputCombo = () => getWidget('image');
            const getOutputCombo = () => getWidget('output_image');

            // Get current folder source from backing widget
            const getCurrentSource = () => {
                const w = getSourceWidget();
                return (w && w.value === 'output') ? 'output' : 'input';
            };

            // Get the active combo widget for the current mode
            const getActiveCombo = () => getCurrentSource() === 'output' ? getOutputCombo() : getInputCombo();

            // Sync mode-bar → backing widget
            function syncSourceToBacking(source) {
                const w = getSourceWidget();
                if (w && w.value !== source) w.value = source;
            }

            // Apply a file list to the correct combo and update preview
            async function applyFileList(files, source, selectFile) {
                const combo = source === 'output' ? getOutputCombo() : getInputCombo();
                if (!combo || !combo.options) return;

                combo.options.values = files;
                if (selectFile && files.includes(selectFile)) {
                    combo.value = selectFile;
                } else if (!files.includes(combo.value)) {
                    combo.value = files.length > 0 ? files[0] : '';
                }
                await loadPreview(node, combo.value, source);
            }

            // Fetch fresh file list from server, update cache, and apply
            async function fetchAndApply(source, selectFile) {
                const files = await getCachedFileList(source);
                await applyFileList(files, source, selectFile);
            }

            // Switch to a mode — use shared cache
            async function switchToMode(source, selectFile) {
                const files = await getCachedFileList(source);
                await applyFileList(files, source, selectFile);
            }

            // Toggle combo visibility based on mode
            function updateModeUI(source) {
                vis.setVisible('image', source === 'input');
                vis.setVisible('output_image', source === 'output');
                vis.setVisible('_btn_upload', source === 'input');
            }

            // --- Mode-bar widget setup (inline radio chips) ---
            const sourceW = getSourceWidget();
            const origIdx = sourceW ? node.widgets.indexOf(sourceW) : 0;

            // Hide backing widget (it still serializes)
            if (sourceW) {
                sourceW.hidden = true;
                if (sourceW.options) sourceW.options.hidden = true;
            }
            vis.setVisible('folder_source', false);

            let currentMode = getCurrentSource();

            const bar = document.createElement('div');
            bar.className = `eclipse-${cfg.cssPrefix}-mode-bar`;

            const chipEls = [];
            for (const opt of MODE_OPTIONS) {
                const chip = document.createElement('span');
                chip.className = `eclipse-${cfg.cssPrefix}-mode-chip` + (opt === currentMode ? ' selected' : '');
                chip.textContent = opt;
                chip.addEventListener('pointerdown', (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (opt === currentMode) return;
                    currentMode = opt;
                    for (const c of chipEls) c.classList.toggle('selected', c.textContent === currentMode);
                    syncSourceToBacking(currentMode);
                    updateModeUI(currentMode);
                    switchToMode(currentMode);
                });
                chipEls.push(chip);
                bar.appendChild(chip);
            }

            const modeWidget = node.addDOMWidget(cfg.widgetName, 'custom', bar, {
                getValue: () => currentMode,
                setValue: (v) => {
                    if (MODE_OPTIONS.includes(v)) {
                        currentMode = v;
                        for (const c of chipEls) c.classList.toggle('selected', c.textContent === currentMode);
                    }
                },
                getMinHeight: () => 26,
                getMaxHeight: () => 26,
                serialize: false,
            });

            // Reposition to where folder_source was
            const newIdx = node.widgets.indexOf(modeWidget);
            if (newIdx >= 0 && newIdx !== origIdx) {
                node.widgets.splice(newIdx, 1);
                node.widgets.splice(origIdx, 0, modeWidget);
            }

            // Hook callbacks on both combos for manual preview loading
            const inputCombo = getInputCombo();
            if (inputCombo) {
                inputCombo.callback = function (value) {
                    if (getCurrentSource() === 'input') {
                        loadPreview(node, value, 'input');
                    }
                };
            }

            const outputCombo = getOutputCombo();
            if (outputCombo) {
                outputCombo.callback = function (value) {
                    if (getCurrentSource() === 'output') {
                        loadPreview(node, value, 'output');
                    }
                };
            }

            // --- Delete button ---
            const handleDelete = async () => {
                const source = getCurrentSource();
                const combo = getActiveCombo();
                if (!combo) return;

                const filename = combo.value;
                if (!filename || filename === 'none') return;

                const oldList = combo.options?.values || [];
                const deletedIndex = oldList.indexOf(filename);

                try {
                    const resp = await api.fetchApi('/eclipse/load_image/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filename, folder: source }),
                    });
                    const result = await resp.json();
                    if (result.success) {
                        console.log(`[Eclipse ${cfg.logPrefix}] ✓ Deleted "${filename}" from ${source}`);
                        invalidateFileListCache(source);
                        const files = await getCachedFileList(source);
                        combo.options.values = files;
                        if (!files.includes(combo.value)) {
                            let pick = '';
                            if (files.length > 0 && deletedIndex >= 0) {
                                const idx = deletedIndex > 0 ? deletedIndex - 1 : 0;
                                pick = files[Math.min(idx, files.length - 1)];
                            }
                            combo.value = pick;
                        }
                        await loadPreview(node, combo.value || '', source);
                        document.dispatchEvent(new CustomEvent('eclipse-filelist-changed', { detail: { source } }));
                    } else {
                        console.error(`[Eclipse ${cfg.logPrefix}] Delete failed: ${result.error}`);
                        alert(`Failed to delete: ${result.error}`);
                    }
                } catch (e) {
                    console.error(`[Eclipse ${cfg.logPrefix}] Delete request failed:`, e);
                    alert('Delete request failed. Check console for details.');
                }
            };

            // --- Upload button (input mode only) ---
            const uploadBtn = node.addWidget('button', '_btn_upload', null, () => {
                const input = document.createElement('input');
                input.type = 'file';
                input.multiple = true;
                input.accept = 'image/png,image/jpeg,image/webp,image/bmp,image/gif,image/tiff,.tif,.tiff';
                input.onchange = async () => {
                    if (!input.files?.length) return;
                    const formData = new FormData();
                    for (const f of input.files) formData.append('images', f, f.name);
                    try {
                        const resp = await api.fetchApi('/eclipse/load_image/upload', {
                            method: 'POST',
                            body: formData,
                        });
                        const result = await resp.json();
                        if (result.success && result.files?.length) {
                            const lastFile = result.files[result.files.length - 1];
                            console.log(`[Eclipse ${cfg.logPrefix}] ✓ Uploaded ${result.files.length} file(s)`);
                            invalidateFileListCache('input');
                            await fetchAndApply('input', lastFile);
                            document.dispatchEvent(new CustomEvent('eclipse-filelist-changed', { detail: { source: 'input' } }));
                        } else {
                            console.error(`[Eclipse ${cfg.logPrefix}] Upload failed:`, result.error || result.errors);
                        }
                    } catch (e) {
                        console.error(`[Eclipse ${cfg.logPrefix}] Upload request failed:`, e);
                    }
                };
                input.click();
            });
            uploadBtn.label = '📁 Upload Image(s)';
            uploadBtn.serialize = false;

            // --- Refresh button ---
            const refreshBtn = node.addWidget('button', '_btn_refresh', null, () => {
                invalidateFileListCache(getCurrentSource());
                fetchAndApply(getCurrentSource());
                document.dispatchEvent(new CustomEvent('eclipse-filelist-changed', { detail: { source: getCurrentSource() } }));
            });
            refreshBtn.label = '🔄 Refresh';
            refreshBtn.serialize = false;

            // --- Delete button ---
            const deleteBtn = node.addWidget('button', '_btn_delete', null, handleDelete);
            deleteBtn.label = '🗑️ Delete Image';
            deleteBtn.serialize = false;

            // Re-sync mode-bar, combo visibility, and preview from restored widget values
            function initFromRestoredState() {
                const source = getCurrentSource();
                currentMode = source;
                for (const c of chipEls) c.classList.toggle('selected', c.textContent === currentMode);
                updateModeUI(source);
                // Always fetch fresh file list (schema options may be stale)
                fetchAndApply(source);
            }

            // onConfigure fires AFTER deserialization restores widget values
            const origOnConfigure = node.onConfigure;
            node.onConfigure = function (config) {
                origOnConfigure?.call(this, config);
                initFromRestoredState();
            };

            // Immediate init for freshly created nodes
            initFromRestoredState();

            // Re-apply file list from shared cache when node becomes active after mute/bypass
            const origOnModeChange = node.onModeChange;
            node.onModeChange = function (newMode) {
                origOnModeChange?.call(this, newMode);
                if (newMode === 0) {  // 0 = ALWAYS (active)
                    const source = getCurrentSource();
                    getCachedFileList(source).then(files => applyFileList(files, source));
                }
            };
        };
    },
});
} // end for NODE_CONFIGS
