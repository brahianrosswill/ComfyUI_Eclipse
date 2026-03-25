/* eclipse-loader-shared.js - Shared helpers for all loader nodes */

// --- Deduplicating fetch for model files ---
let _pendingModelFilesFetch = null;

export async function fetchSharedModelFiles() {
    if (_pendingModelFilesFetch) return _pendingModelFilesFetch;
    const v = Date.now();
    _pendingModelFilesFetch = fetch(`/eclipse/model_files_all?v=${v}`)
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
        .finally(() => { _pendingModelFilesFetch = null; });
    return _pendingModelFilesFetch;
}

// --- Deduplicating fetch for template list ---
let _pendingTemplateListFetch = null;

export async function fetchSharedTemplateList() {
    if (_pendingTemplateListFetch) return _pendingTemplateListFetch;
    const v = Date.now();
    _pendingTemplateListFetch = fetch(`/eclipse/loader_templates_list?v=${v}`)
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
        .finally(() => { _pendingTemplateListFetch = null; });
    return _pendingTemplateListFetch;
}

// --- Template change broadcast ---
export const TEMPLATE_CHANGED_EVENT = 'eclipse-loader-templates-changed';

export function broadcastTemplateListChanged(templates, sourceNodeId) {
    if (templates) {
        document.dispatchEvent(new CustomEvent(TEMPLATE_CHANGED_EVENT, { detail: { templates, sourceNodeId } }));
    }
}
