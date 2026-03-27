import re
from comfy_api.latest import io #type: ignore
from ..core import CATEGORY

# Inline pattern to avoid regex_patterns dependency
RE_NEWLINES = re.compile(r'[\r\n]+', re.IGNORECASE)


class RvConversion_MergeStrings_v2(io.ComfyNode):
    # Merge multiple string inputs with auto-growing slots via V3 Autogrow API.
    # Supports delimiter control and list output mode.

    @classmethod
    def define_schema(cls):
        autogrow = io.Autogrow.TemplatePrefix(
            io.String.Input("string", force_input=True, default=""),
            prefix="string", min=0, max=64,
        )
        return io.Schema(
            node_id="Merge Strings v2 [Eclipse]",
            display_name="Merge Strings v2",
            category=CATEGORY.MAIN.value + CATEGORY.TESTS.value,
            description="Merge multiple string inputs with auto-growing slots.",
            inputs=[
                io.String.Input("Delimiter", default=", ",
                    tooltip="Delimiter to use between strings when merging. Use \\n for newline."),
                io.Boolean.Input("return_as_list", default=False,
                    tooltip="If true, return list of individual strings; if false, return single merged string."),
                io.Autogrow.Input("strings", template=autogrow),
            ],
            outputs=[
                io.String.Output("string", is_output_list=True),
            ],
        )

    @classmethod
    def execute(cls, Delimiter: str = ", ", return_as_list: bool = False,
                strings: io.Autogrow.Type = None) -> io.NodeOutput:
        text_inputs = []

        # Handle special case for literal newlines
        if Delimiter in ("\n", "\\n"):
            Delimiter = "\n"

        if strings:
            for v in strings.values():
                if isinstance(v, str):
                    v = v.strip()
                    v = v.rstrip('.,;:!?')
                    if v:
                        text_inputs.append(v)

        if return_as_list:
            return io.NodeOutput(text_inputs)
        else:
            merged_text = Delimiter.join(text_inputs)
            merged_text = RE_NEWLINES.sub(" ", merged_text)
            return io.NodeOutput([merged_text])
