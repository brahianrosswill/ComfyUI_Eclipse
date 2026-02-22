import os
import sys
import random
import time
import numpy as np  # type: ignore
import folder_paths #type: ignore

from PIL import Image #type: ignore
from comfy_api.latest import io #type: ignore

from ..core import CATEGORY

# Class-level state (initialized once at module load)
_output_dir = folder_paths.get_temp_directory()
_type = "temp"
_compress_level = 1
# Per-session prefix (same as core ComfyUI PreviewImage behavior)
_prefix_append = "_temp_" + ''.join(random.choice("abcdefghijklmnopqrstupvxyz") for x in range(5))

class RvImage_Preview_Image(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Preview Image [Eclipse]",
            display_name="Preview Image",
            category=CATEGORY.MAIN.value + CATEGORY.IMAGE.value,
            is_output_node=True,
            inputs=[
                io.Image.Input("images", tooltip="Batch of images to preview"),
                io.Int.Input("Show_Images", default=-1, min=-1, max=sys.maxsize, step=1, tooltip="Number of images to preview (-1 for all, 0 for none)."),
            ],
            outputs=[
                io.Image.Output("IMAGE"),
            ],
        )

    @classmethod
    def execute(cls, images, Show_Images=-1):
        filename_prefix = "ComfyUI"
        if images is None or not hasattr(images, '__iter__') or len(images) == 0:
            return io.NodeOutput(images, ui={"images": []})
        if not isinstance(Show_Images, int):
            Show_Images = -1

        first_img = images[0]
        if hasattr(first_img, 'shape') and first_img.shape[0] == 1:
            height, width = first_img.shape[1], first_img.shape[2]
        else:
            height, width = first_img.shape[0], first_img.shape[1]

        filename_prefix += _prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(
            filename_prefix, _output_dir, width, height)
        results = []

        for batch_number, image in enumerate(images):
            if Show_Images == 0:
                break

            if hasattr(image, 'shape') and image.ndim == 4 and image.shape[0] == 1:
                image = image.squeeze(0)
            
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            # Add timestamp to filename for cache-busting
            timestamp = int(time.time() * 1000) % 100000000  # Last 8 digits of ms timestamp
            file = f"{filename_with_batch_num}_{counter:05}_{timestamp}_.png"
            filepath = os.path.join(full_output_folder, file)
            img.save(filepath, compress_level=_compress_level)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": _type
            })

            if Show_Images > -1 and (batch_number + 1) == Show_Images:
                break

            counter += 1

        return io.NodeOutput(images, ui={"images": results})