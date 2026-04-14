# Mode Bridge - Virtual node that syncs mode state across subgraph boundaries
# by matching named bridges. When named, all bridges with the same name across
# all graphs sync their mode instantly. Connect target nodes as dynamic inputs
# for selective mode control — no group fallback (unlike the Repeater).
# All behavior is handled by the frontend JavaScript (eclipse-mode-nodes.js).

from comfy_api.latest import io #type: ignore
from ..core import CATEGORY

class RvTools_ModeBridge(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mode Bridge [Eclipse]",
            display_name="Mode Bridge",
            category=CATEGORY.MAIN.value + CATEGORY.TOOLS.value,
            inputs=[],
            outputs=[
                io.AnyType.Output("oc", tooltip="Connect to Fast Muter/Bypasser, Repeater, Relay, or another Mode Bridge."),
            ],
            description="Syncs mode (Mute/Bypass/Active) across subgraph boundaries by name. Set a bridge name (right-click menu -> Properties Panel), then place same-named bridges in other graphs. Connect target nodes as dynamic inputs for selective control — only connected nodes are affected, never the entire group.",
        )

    @classmethod
    def execute(cls, **kwargs):
        return io.NodeOutput(None)
