# Fast Bypasser - DEPRECATED: Use the Fast Mode Switcher instead.
# Virtual node for toggling bypass on connected nodes.
# Based on rgthree-comfy by rgthree (https://github.com/rgthree/rgthree-comfy).
# All behavior is handled by the frontend JavaScript (eclipse-mode-nodes.js).

from comfy_api.latest import io #type: ignore
from ...core import CATEGORY

class RvTools_FastBypasser(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Fast Bypasser [Eclipse]",
            display_name="⚠ Fast Bypasser",
            category=CATEGORY.MAIN.value + CATEGORY.DEPRECATED.value,
            inputs=[],
            outputs=[
                io.AnyType.Output("oc", tooltip="Optional connection to other mode nodes."),
            ],
            description="[DEPRECATED — use Fast Mode Switcher] Toggle-bypass connected nodes on the canvas.",
            is_deprecated=True,
        )

    @classmethod
    def execute(cls, **kwargs):
        return io.NodeOutput(None)
