from comfy_api.latest import io #type: ignore
from ..core import CATEGORY, purge_vram

class RvRouter_Any_DualSwitch_purge(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Any Dual-Switch Purge [Eclipse]",
            display_name="Any Dual-Switch Purge",
            category=CATEGORY.MAIN.value + CATEGORY.ROUTER.value,
            inputs=[
                io.Int.Input("Input", default=1, min=1, max=2, tooltip="Select which input to output (1 or 2)."),
                io.Boolean.Input("Purge_VRAM", default=False, tooltip="If True, purges VRAM before switching."),
                io.AnyType.Input("input1", optional=True, tooltip="First input (any type)."),
                io.AnyType.Input("input2", optional=True, tooltip="Second input (any type)."),
            ],
            outputs=[
                io.AnyType.Output("*"),
            ],
        )

    @classmethod
    def execute(cls, Input, Purge_VRAM, input1=None, input2=None):
        if Purge_VRAM:
            purge_vram()
        if Input == 1:
            return io.NodeOutput(input1)
        else:
            return io.NodeOutput(input2)
