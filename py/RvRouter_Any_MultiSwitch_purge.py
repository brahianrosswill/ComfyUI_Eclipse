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

        def _is_empty(v):
            if v is None:
                return True
            if isinstance(v, (tuple, list)) and len(v) == 0:
                return True
            if isinstance(v, dict) and len(v) == 0:
                return True
            if isinstance(v, str) and v.strip() == "":
                return True
            return False

        for i in range(1, max(1, inputcount) + 1):
            key = f"any_{i}"
            val = kwargs.get(key)
            if not _is_empty(val):
                return io.NodeOutput(val)

        raise RuntimeError(f"RvRouter_Any_MultiSwitch_purge: no value found among any_1..any_{inputcount}.")
