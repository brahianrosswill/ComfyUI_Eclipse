from comfy_api.latest import io #type: ignore
from ..core import CATEGORY, purge_vram

class RvSwitch_IfExecute(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="IF A Else B [Eclipse]",
            display_name="IF A Else B",
            category=CATEGORY.MAIN.value + CATEGORY.ROUTER.value,
            inputs=[
                io.AnyType.Input("on_true", tooltip="Value to return if boolean is True."),
                io.AnyType.Input("on_false", tooltip="Value to return if boolean is False."),
                io.Boolean.Input("boolean", force_input=True, tooltip="Condition to select on_true or on_false."),
                io.Boolean.Input("Purge_VRAM", default=False, tooltip="If True, purges VRAM before switching."),
            ],
            outputs=[
                io.AnyType.Output("output"),
            ],
        )

    @classmethod
    def execute(cls, on_true, on_false, boolean=True, Purge_VRAM=False):
        if Purge_VRAM:
            purge_vram()
        if boolean:
            return io.NodeOutput(on_true)
        else:
            return io.NodeOutput(on_false)
