from __future__ import annotations
from comfy_api.latest import io #type: ignore
from ..core import CATEGORY
from ..core.logger import log

_LOG_PREFIX = "AnyMultiSwitchV2"

class RvRouter_Any_MultiSwitch_v2(io.ComfyNode):
    # Multi-switch with auto-growing slots via V3 Autogrow API.
    # Returns the first connected non-empty input.
    # Type propagation is handled natively by MatchType (no JS needed).

    @classmethod
    def define_schema(cls):
        matchtype = io.MatchType.Template("switch")
        autogrow = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("any", matchtype),
            prefix="any", min=0, max=64,
        )
        return io.Schema(
            node_id="Any Multi-Switch v2 [Eclipse]",
            display_name="Any Multi-Switch v2",
            category=CATEGORY.MAIN.value + CATEGORY.TESTS.value,
            description="Multi-switch for ANY inputs with auto-growing slots. Returns the first connected non-empty input.",
            inputs=[
                io.Autogrow.Input("inputs", template=autogrow),
            ],
            outputs=[
                io.MatchType.Output(template=matchtype, display_name="output"),
            ],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    def execute(cls, inputs: io.Autogrow.Type) -> io.NodeOutput:
        tag = f"{_LOG_PREFIX} #{cls.hidden.unique_id}"

        # First pass: return the first connected input that has real data.
        for key, val in inputs.items():
            if val is None or val == "":
                continue
            if isinstance(val, (dict, tuple, list)) and len(val) == 0:
                log.debug(tag, f"Skipping {key}: empty {type(val).__name__}")
                continue
            log.debug(tag, f"Passing {key}")
            return io.NodeOutput(val)

        # Second pass: return empty string if any slot had one
        for key, val in inputs.items():
            if val == "":
                log.debug(tag, f"All slots empty, returning empty string from {key}")
                return io.NodeOutput(val)

        # All inputs are None/empty
        log.debug(tag, "All slots disconnected or empty, passing None")
        return io.NodeOutput(None)
