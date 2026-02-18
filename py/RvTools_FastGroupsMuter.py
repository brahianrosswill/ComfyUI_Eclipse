# Fast Groups Muter - Virtual node that auto-discovers workflow groups
# and provides toggle switches to mute/unmute all nodes within each group.
# Based on rgthree-comfy by rgthree (https://github.com/rgthree/rgthree-comfy).
# Rewritten for ComfyUI V3 API and Vue/Nodes 2.0 compatibility.
# All behavior is handled by the frontend JavaScript (eclipse-mode-nodes.js).

from comfy_api.latest import io #type: ignore
from ..core import CATEGORY

class RvTools_FastGroupsMuter(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Fast Groups Muter [Eclipse]",
            display_name="Fast Groups Muter",
            category=CATEGORY.MAIN.value + CATEGORY.TOOLS.value,
            inputs=[],
            outputs=[
                io.AnyType.Output("oc", tooltip="Optional connection to other mode nodes."),
            ],
            description="Auto-discovers workflow groups and provides toggle switches to mute/unmute all nodes within each group. Supports color/title filtering and sorting.",
        )

    @classmethod
    def execute(cls):
        return io.NodeOutput(None)
