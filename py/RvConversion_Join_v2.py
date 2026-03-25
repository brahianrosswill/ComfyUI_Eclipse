import torch #type: ignore
import re
from ..core import CATEGORY
from ..core.logger import log
from comfy_api.latest import io #type: ignore

_LOG_PREFIX = "JoinV2"

# Inline pattern to avoid regex_patterns dependency
RE_NEWLINES = re.compile(r'[\r\n]+', re.IGNORECASE)


def _join_images(inputs):
    # Join IMAGE tensors into a batch, resizing to match first image dimensions
    tensors = []
    for img in inputs:
        if isinstance(img, torch.Tensor) and img.ndim == 4:
            tensors.append(img)

    if not tensors:
        return (None,)

    target_height = tensors[0].shape[1]
    target_width = tensors[0].shape[2]

    resized_tensors = []
    for tensor in tensors:
        if tensor.shape[1] != target_height or tensor.shape[2] != target_width:
            tensor_bchw = tensor.permute(0, 3, 1, 2)
            resized = torch.nn.functional.interpolate(
                tensor_bchw,
                size=(target_height, target_width),
                mode='bilinear',
                align_corners=False
            )
            tensor = resized.permute(0, 2, 3, 1)
        resized_tensors.append(tensor)

    result = torch.cat(resized_tensors, dim=0)
    return (result,)


def _join_masks(inputs):
    # Join MASK tensors into a batch, resizing to match first mask dimensions
    tensors = []
    for mask in inputs:
        if isinstance(mask, torch.Tensor):
            if mask.ndim == 2:
                mask = mask.unsqueeze(0)
            elif mask.ndim == 4:
                mask = mask.squeeze(0)
            tensors.append(mask)

    if not tensors:
        return (None,)

    target_height = tensors[0].shape[1]
    target_width = tensors[0].shape[2]

    resized_tensors = []
    for tensor in tensors:
        if tensor.shape[1] != target_height or tensor.shape[2] != target_width:
            tensor_bchw = tensor.unsqueeze(1)
            resized = torch.nn.functional.interpolate(
                tensor_bchw,
                size=(target_height, target_width),
                mode='bilinear',
                align_corners=False
            )
            tensor = resized.squeeze(1)
        resized_tensors.append(tensor)

    result = torch.cat(resized_tensors, dim=0)
    return (result,)


def _join_strings(inputs, delimiter: str):
    # Join STRING values with delimiter
    if delimiter in ("\n", "\\n"):
        delimiter = "\n"

    text_inputs = []
    for v in inputs:
        if isinstance(v, str):
            v = v.strip()
            v = v.rstrip('.,;:!?')
            if v:
                text_inputs.append(v)

    if not text_inputs:
        return ("",)

    merged_text = delimiter.join(text_inputs)
    merged_text = RE_NEWLINES.sub(" ", merged_text)
    return (merged_text,)


def _join_primitives(inputs, delimiter: str):
    # Join INT/FLOAT/LIST values as delimited string
    if delimiter in ("\n", "\\n"):
        delimiter = "\n"

    text_inputs = []
    for v in inputs:
        if v is not None:
            text_inputs.append(str(v))

    if not text_inputs:
        return ("",)

    merged_text = delimiter.join(text_inputs)
    return (merged_text,)


class RvConversion_Join_v2(io.ComfyNode):
    # Join multiple inputs into one output.
    # Auto-growing slots via V3 Autogrow API.
    # Type-aware: batches images/masks, concatenates strings, converts primitives.

    @classmethod
    def define_schema(cls):
        matchtype = io.MatchType.Template("input")
        autogrow = io.Autogrow.TemplatePrefix(
            io.MatchType.Input("input", matchtype),
            prefix="input", min=0, max=64,
        )
        return io.Schema(
            node_id="Join v2 [Eclipse]",
            display_name="Join v2",
            category=CATEGORY.MAIN.value + CATEGORY.CONVERSION.value,
            description="Join multiple inputs into one. Auto-growing slots. Batches images/masks, concatenates strings.",
            inputs=[
                io.String.Input("delimiter", default=", ", optional=True,
                    tooltip="Delimiter for STRING types. Use \\n for newline. Ignored for IMAGE/MASK."),
                io.Autogrow.Input("inputs", template=autogrow),
            ],
            outputs=[
                io.MatchType.Output(template=matchtype, display_name="output"),
            ],
        )

    @classmethod
    def execute(cls, delimiter: str = ", ", inputs: io.Autogrow.Type = None) -> io.NodeOutput:
        if not inputs:
            return io.NodeOutput(None)

        values = [v for v in inputs.values() if v is not None]
        if not values:
            return io.NodeOutput(None)

        first = values[0]

        if isinstance(first, torch.Tensor) and first.ndim == 4:
            return io.NodeOutput(*_join_images(values))
        elif isinstance(first, torch.Tensor) and first.ndim in (2, 3):
            return io.NodeOutput(*_join_masks(values))
        elif isinstance(first, str):
            return io.NodeOutput(*_join_strings(values, delimiter))
        elif isinstance(first, (int, float, list, tuple)):
            return io.NodeOutput(*_join_primitives(values, delimiter))

        log.warning(_LOG_PREFIX, f"Unknown type: {type(first)}, returning first input")
        return io.NodeOutput(first)
