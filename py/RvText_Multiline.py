from comfy_api.latest import io #type: ignore
from ..core import CATEGORY

class RvText_Multiline(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="String Multiline [Eclipse]",
            display_name="String Multiline",
            category=CATEGORY.MAIN.value + CATEGORY.TEXT.value,
            inputs=[
                io.String.Input("string", multiline=True, default="", tooltip="Multiline string input. Splits into a list of lines and returns the full string joined by commas."),
            ],
            outputs=[
                io.String.Output("string"),
                io.String.Output("string_list", is_output_list=True),
            ],
        )

    @classmethod
    def execute(cls, string=None):
        # Outputs the input multiline string as a single joined string and as a list of lines.
        if not isinstance(string, str) or not string or string.isspace():
            return io.NodeOutput("", [""])

        # Strip and split the input
        string = string.strip()
        string_list = string.split('\n')

        # Filter out empty lines and strip whitespace
        string_list = [line.strip() for line in string_list if line.strip()]

        # If no valid lines found, return empty
        if not string_list:
            return io.NodeOutput("", [""])

        # Output: fallback for single item
        if len(string_list) == 1:
            return io.NodeOutput(string_list[0], string_list)
        joined_string = " ".join(string_list)
        return io.NodeOutput(joined_string, string_list)