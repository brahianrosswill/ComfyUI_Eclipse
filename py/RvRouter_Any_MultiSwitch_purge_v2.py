from __future__ import annotations
from comfy_api.latest import io #type: ignore
from ..core import CATEGORY, purge_vram
from ..core.logger import log

_LOG_PREFIX = "AnyMultiSwitchV2_Purge"

class RvRouter_Any_MultiSwitch_purge_v2(io.ComfyNode):
    # Multi-switch with auto-growing slots and optional VRAM purge.
    # Returns the first connected non-empty input.

    @classmethod
    def define_schema(cls):
        matchtype = io.MatchType.Template("switch")
        autogrow = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("any", matchtype),
            prefix="any", min=0, max=64,
        )
        return io.Schema(
            node_id="Any Multi-Switch Purge v2 [Eclipse]",
            display_name="Any Multi-Switch Purge v2",
            category=CATEGORY.MAIN.value + CATEGORY.TESTS.value,
            description="Multi-switch for ANY inputs with auto-growing slots and optional VRAM purge.",
            inputs=[
                io.Boolean.Input("Purge_VRAM", default=False, tooltip="If enabled, purges VRAM before switching."),
                io.Autogrow.Input("inputs", template=autogrow),
            ],
            outputs=[
                io.MatchType.Output(template=matchtype, display_name="output"),
            ],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    def execute(cls, Purge_VRAM: bool, inputs: io.Autogrow.Type) -> io.NodeOutput:
        tag = f"{_LOG_PREFIX} #{cls.hidden.unique_id}"

        if Purge_VRAM:
            purge_vram()

        for key, val in inputs.items():
            if val is None or val == "":
                continue
            if isinstance(val, (dict, tuple, list)) and len(val) == 0:
                log.debug(tag, f"Skipping {key}: empty {type(val).__name__}")
                continue
            log.debug(tag, f"Passing {key}")
            return io.NodeOutput(val)

        for key, val in inputs.items():
            if val == "":
                log.debug(tag, f"All slots empty, returning empty string from {key}")
                return io.NodeOutput(val)

        log.debug(tag, "All slots disconnected or empty, passing None")
        return io.NodeOutput(None)
