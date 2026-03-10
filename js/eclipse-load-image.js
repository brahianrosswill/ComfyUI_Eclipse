/**
 * Eclipse - Load Image (Metadata Pipe) extension
 * Adds a 🗑️ Delete Image button to remove the selected image from the input folder.
 */

import { app, api } from './comfy/index.js';

const NODE_NAME = 'Load Image (Metadata Pipe) [Eclipse]';

app.registerExtension({
    name: 'Eclipse.LoadImage',

    async beforeRegisterNodeDef(nodeType, nodeData, _app) {
        if (nodeData.name !== NODE_NAME) return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origOnNodeCreated?.apply(this, arguments);

            const node = this;
            let deleteBtn = null;

            // Helper: find the image combo widget
            const getImageWidget = () => node.widgets?.find(w => w.name === 'image');

            // Helper: refresh the image list from server and select neighbor of deleted image
            const refreshImageList = async (deletedIndex) => {
                try {
                    const resp = await api.fetchApi('/eclipse/load_image/list', { cache: 'no-store' });
                    const data = await resp.json();
                    if (!data.success) return;

                    const imgWidget = getImageWidget();
                    if (!imgWidget || !imgWidget.options) return;

                    imgWidget.options.values = data.files;

                    // Select neighbor: prefer previous, fall back to next, then empty
                    if (!data.files.includes(imgWidget.value)) {
                        let pick = '';
                        if (data.files.length > 0 && deletedIndex >= 0) {
                            // Previous image if available, otherwise next (same index = next after removal)
                            const idx = deletedIndex > 0 ? deletedIndex - 1 : 0;
                            pick = data.files[Math.min(idx, data.files.length - 1)];
                        }
                        imgWidget.value = pick;
                        if (imgWidget.callback) imgWidget.callback(imgWidget.value);
                    }
                } catch (e) {
                    console.error('[Eclipse LoadImage] Failed to refresh image list:', e);
                }
            };

            // Delete handler
            const handleDelete = async () => {
                const imgWidget = getImageWidget();
                if (!imgWidget) return;

                const filename = imgWidget.value;
                if (!filename) return;

                // Remember position before deletion for neighbor selection
                const oldList = imgWidget.options?.values || [];
                const deletedIndex = oldList.indexOf(filename);

                try {
                    const resp = await api.fetchApi('/eclipse/load_image/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filename }),
                    });
                    const result = await resp.json();
                    if (result.success) {
                        console.log(`[Eclipse LoadImage] ✓ Deleted "${filename}"`);
                        await refreshImageList(deletedIndex);
                    } else {
                        console.error(`[Eclipse LoadImage] Delete failed: ${result.error}`);
                        alert(`Failed to delete: ${result.error}`);
                    }
                } catch (e) {
                    console.error('[Eclipse LoadImage] Delete request failed:', e);
                    alert('Delete request failed. Check console for details.');
                }
            };

            // Add the delete button once widgets are ready
            const addDeleteButton = () => {
                if (deleteBtn) return; // already added
                const imgWidget = getImageWidget();
                if (!imgWidget) return;

                deleteBtn = node.addWidget('button', '🗑️ Delete Image', null, handleDelete);
                deleteBtn.serialize = false;
            };

            // Defer button creation slightly so the image widget is resolved
            setTimeout(() => addDeleteButton(), 100);
        };
    },
});
