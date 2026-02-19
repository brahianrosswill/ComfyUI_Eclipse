from __future__ import annotations
from comfy_api.latest import io #type: ignore
from ..core import CATEGORY, purge_vram

class RvRouter_Any_MultiSwitch_purge(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Any Multi-Switch Purge [Eclipse]",
            display_name="Any Multi-Switch Purge",
            category=CATEGORY.MAIN.value + CATEGORY.ROUTER.value,
            description="Multi-switch for ANY inputs. Inputs update automatically when inputcount changes.",
            inputs=[
                io.Int.Input("inputcount", default=2, min=1, max=64, step=1, tooltip="Number of ANY inputs to expose. Inputs update automatically."),
                io.Boolean.Input("Purge_VRAM", default=False, tooltip="If enabled, purges VRAM before switching."),
                io.AnyType.Input("any_1", optional=True, tooltip="Any input #1 (highest priority). Leave empty to bypass."),
                io.AnyType.Input("any_2", optional=True, tooltip="Any input #2 (used if #1 is empty)."),
            ],
            outputs=[
                io.AnyType.Output("*"),
            ],
        )

    @classmethod
    def execute(cls, inputcount, Purge_VRAM=False, **kwargs):
        if Purge_VRAM:
            purge_vram()

        # Return the first connected (non-None) input.
        # Empty strings, empty lists, etc. are valid values — only None
        # (disconnected/muted) is skipped.
        for i in range(1, max(1, inputcount) + 1):
            key = f"any_{i}"
            val = kwargs.get(key)
            if val is not None:
                return io.NodeOutput(val)

        # All inputs are None (disconnected/muted) — pass through None
        return io.NodeOutput(None)
