from typing import Any, Dict
from ..core import CATEGORY
from comfy_api.latest import io #type: ignore

# keys that should be treated as list-like when merging
_KNOWN_LIST_KEYS = {
    "images", 
    "images_ref", 
    "images_pp", 
    "images_pp1",
    "images_pp2", 
    "images_pp3",
    "mask", 
    "mask_1", 
    "mask_2", 
    "audio_in",
    "audio_out",
    "lora_names", 
    "loras", 
    "embeddings", 
    "positive_list", 
    "negative_list"
}


def _is_empty_value(value) -> bool:
    # Check if a value should be considered empty/invalid for merging
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in ('', 'None', 'none', 'null', 'NULL')
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    return False


class RvConversion_ConcatMulti(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Concat Pipe Multi [Eclipse]",
            display_name="Concat Pipe Multi",
            category=CATEGORY.MAIN.value + CATEGORY.CONVERSION.value,
            description="Merge multiple pipe/context inputs into a single context dict pipe.",
            inputs=[
                io.Int.Input("inputcount", default=2, min=2, max=256, step=1),
                io.Custom("pipe").Input("pipe_1"),
                io.Custom("pipe").Input("pipe_2", optional=True),
                io.Combo.Input("merge_strategy", options=["overwrite", "preserve", "merge"],
                    default="merge", optional=True,
                    tooltip="How to handle conflicting keys:\n"
                            "'overwrite' replaces earlier values,\n"
                            "'preserve' keeps first valid values,\n"
                            "'merge' combines lists and uses later values for conflicts"),
            ],
            outputs=[
                io.Custom("pipe").Output("pipe"),
            ],
        )

    @classmethod
    def execute(cls, inputcount: int = 2, merge_strategy: str = "merge", **kwargs) -> io.NodeOutput:
        result: Dict[str, Any] = {}

        aliases = {
            "Steps": "steps",
            "CFG": "cfg",
            "model_name": "model_name",
            "lora_names": "lora_names",
            "loras": "lora_names",
            "seed": "seed",
            "sampler_name": "sampler_name",
            "sampler": "sampler_name",
            "vae_name": "vae_name",
            "directory": "path",
        }

        def set_value(k, v):
            if merge_strategy == "preserve":
                if k in result and not _is_empty_value(result[k]):
                    return
                result[k] = v
                return

            if merge_strategy == "merge":
                if k in result:
                    existing = result[k]
                    if k in _KNOWN_LIST_KEYS and isinstance(existing, str) and isinstance(v, str):
                        result[k] = existing + ", " + v
                        return
                    if isinstance(existing, (list, tuple)) or isinstance(v, (list, tuple)) or k in _KNOWN_LIST_KEYS:
                        existing_list = list(existing) if not isinstance(existing, list) else existing
                        new_list = list(v) if isinstance(v, (list, tuple)) else [v]
                        result[k] = existing_list + new_list
                        return
                result[k] = v
                return

            result[k] = v

        for idx in range(1, inputcount + 1):
            pipe = kwargs.get(f"pipe_{idx}")
            if pipe is None:
                continue

            if isinstance(pipe, tuple):
                ctx = pipe[0] if pipe and isinstance(pipe[0], dict) else {}
            elif isinstance(pipe, dict):
                ctx = pipe
            else:
                raise ValueError(
                    f"Pipe input pipe_{idx} must be a dict or tuple containing a dict. Got: {type(pipe)}"
                )

            for k, v in ctx.items():
                if _is_empty_value(v):
                    continue
                key = aliases.get(k, k)
                if merge_strategy == "merge" and key in _KNOWN_LIST_KEYS and not isinstance(v, (list, tuple)) and not isinstance(v, str):
                    v = [v]
                set_value(key, v)

        if "pipe" not in result:
            result["pipe"] = result

        return io.NodeOutput(result)
