/* eclipse-ram-cleanup.js - Minified for ComfyUI Eclipse */
import { app } from './comfy/index.js';
import { createWidgetVisibilityManager, smartResize } from './eclipse-widget-performance-utils.js';
const NODE_NAME = 'RAM Cleanup [Eclipse]';
let _serverPlatform = null,
    _platformFetchPromise = null;
async function getServerPlatform() {
    return null !== _serverPlatform
        ? _serverPlatform
        : _platformFetchPromise ||
              ((_platformFetchPromise = fetch('/eclipse/system_info')
                  .then((e) => (e.ok ? e.json() : null))
                  .then((e) => ((_serverPlatform = e?.platform || 'Unknown'), _serverPlatform))
                  .catch(() => ((_serverPlatform = 'Unknown'), _serverPlatform))
                  .finally(() => {
                      _platformFetchPromise = null;
                  })),
              _platformFetchPromise);
}
app.registerExtension({
    name: 'Eclipse.RAMCleanup',
    async beforeRegisterNodeDef(e, t, r) {
        if (t.name !== NODE_NAME) return;
        const o = e.prototype.onNodeCreated;
        e.prototype.onNodeCreated = function () {
            const e = o ? o.apply(this, arguments) : void 0,
                t = this,
                r = createWidgetVisibilityManager(t),
                i = (e) => {
                    const o = 'Windows' === e;
                    (r.setVisible('clean_file_cache', o),
                        r.setVisible('clean_processes', o),
                        r.setVisible('retry_times', o),
                        smartResize(t, { minWidth: 0, minHeight: 0, padding: 0 }));
                };
            setTimeout(async () => {
                const e = await getServerPlatform();
                i(e);
            }, 0);
            const n = t.onConfigure;
            return (
                (t.onConfigure = function (e) {
                    (n && n.apply(this, arguments), getServerPlatform().then(i));
                }),
                e
            );
        };
    },
});
