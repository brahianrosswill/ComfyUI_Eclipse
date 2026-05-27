# ComfyUI Frontend Patch — v1.42.11

Fixes a bug where **copy-pasting nodes jumps node IDs into the thousands** (1900+)
instead of continuing sequentially from where your workflow left off.

---

## The Problem

If your workflow contains a **subgraph** (a node group/module), copy-pasting any
nodes — even regular ones — causes all pasted node IDs to skip to very high numbers.

- You paste 4 nodes → they become **1951, 1952, 1953, 1954**
- Over time your `last_node_id` inflates into the thousands, even with only a
  handful of actual nodes

This happens because the subgraph stores its own internal counter, and a bug in the
frontend causes that value to overwrite the root workflow counter during paste.

---

## The Fix

With the patch applied, pasted nodes get the next clean sequential IDs:

- You paste 4 nodes → they become **18, 19, 20, 21** ✓
- Subgraph internal nodes are renumbered to compact sequential IDs (1, 2, 3...) as intended

Five changes are applied to the bundle:

**Paste-path fixes:**

1. **Removed bad remap** — deleted the loop that called `nextUniqueNodeId()` for subgraph
   nodes, which was the original source of the counter jumping into the thousands
2. **Compact renumber** — on paste, each subgraph's internal nodes are renumbered starting
   from 1, and all internal references are updated (link `origin_id`/`target_id`, promoted
   widget IDs, proxy widget refs). The subgraph's saved `state.lastNodeId` becomes e.g. `4`
   instead of `1520`
3. **Paste-time guard** — saves and restores `rootGraph.state.lastNodeId` around
   `subgraph.configure()` calls during paste, blocking any residual contamination

**Load-path fixes** (prevent subgraph IDs from bumping the root counter when opening a workflow):

4. **Dedup local state** — `deduplicateSubgraphNodeIds` now uses a local counter copy when
   calling `remapNodeIds`, so the conflict-resolver's increments never write back to
   `rootGraph.state.lastNodeId`
5. **Subgraph.configure guard** — saves and restores `rootGraph.state.lastNodeId` around
   `super.configure()` inside `Subgraph.configure()`, blocking the `addNode` and `Math.max`
   paths that would otherwise bump the root counter as each subgraph node is registered

---

## How to Apply

1. Copy `api-yYmjF75S.js` from this folder into:

```
<your_comfy_env>/lib/python3.12/site-packages/comfyui_frontend_package/static/assets/
```

> **Linux example:**
> ```
> cp api-yYmjF75S.js /mnt/data/AI/comfy_env/lib/python3.12/site-packages/comfyui_frontend_package/static/assets/
> ```

2. Hard-reload ComfyUI in the browser (`Ctrl+Shift+R`)

---

## ⚠️ Important

- This patch is for **ComfyUI frontend v1.42.11 only**
- Check your installed version before applying — the file name contains a content hash
  that changes with each frontend release
- The patched file will be **overwritten if you update the frontend package** via pip —
  you will need to re-apply the patch after any frontend update
