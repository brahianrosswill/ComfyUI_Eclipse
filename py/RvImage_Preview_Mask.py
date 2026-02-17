import os
import sys
import random
import numpy as np  # type: ignore
import folder_paths #type: ignore

from PIL import Image #type: ignore
from comfy_api.latest import io #type: ignore

from ..core import CATEGORY

# Class-level state (initialized once at module load)
_output_dir = folder_paths.get_temp_directory()
_type = "temp"
_prefix_append = "_temp_" + ''.join(random.choice("abcdefghijklmnopqrstupvxyz") for x in range(5))
_compress_level = 1

class RvImage_Preview_Mask(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Preview Mask [Eclipse]",
            display_name="Preview Mask",
            category=CATEGORY.MAIN.value + CATEGORY.IMAGE.value,
            is_output_node=True,
            inputs=[
                io.Mask.Input("masks", tooltip="Batch of masks to preview"),
                io.Int.Input("Show_Masks", default=-1, min=-1, max=sys.maxsize, step=1, tooltip="Number of masks to preview (-1 for all, 0 for none)."),
            ],
            outputs=[
                io.Mask.Output("MASK"),
            ],
        )

    @classmethod
    def execute(cls, masks, Show_Masks=-1):
        filename_prefix = "ComfyUI"
        if masks is None or not hasattr(masks, '__iter__') or len(masks) == 0:
            return io.NodeOutput(masks, ui={"images": []})
        if not isinstance(Show_Masks, int):
            Show_Masks = -1

        prefix = filename_prefix + _prefix_append
        
        first_mask = masks[0]
        if hasattr(first_mask, 'shape'):
            temp_mask = first_mask
            while temp_mask.ndim > 2:
                temp_mask = temp_mask.squeeze(0) if temp_mask.shape[0] == 1 else temp_mask.squeeze()
            if temp_mask.ndim >= 2:
                height = temp_mask.shape[-2]
                width = temp_mask.shape[-1]
            else:
                height, width = 512, 512
        else:
            height, width = 512, 512
        
        full_output_folder, filename, counter, subfolder, prefix = folder_paths.get_save_image_path(
            prefix, _output_dir, width, height)
        results = []

        for batch_number, mask in enumerate(masks):
            if Show_Masks == 0:
                break

            mask_np = mask.cpu().numpy() if hasattr(mask, 'cpu') else np.array(mask)
            
            while mask_np.ndim > 2:
                if mask_np.shape[0] == 1:
                    mask_np = mask_np.squeeze(0)
                else:
                    mask_np = mask_np.squeeze()
            
            mask_normalized = np.clip(mask_np * 255.0, 0, 255).astype(np.uint8)
            img = Image.fromarray(mask_normalized, mode='L')

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, file), compress_level=_compress_level)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": _type
            })

            if Show_Masks > -1 and (batch_number + 1) == Show_Masks:
                break

            counter += 1

        return io.NodeOutput(masks, ui={"images": results})
