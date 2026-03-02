import os
import sys
import torch #type: ignore
import numpy as np
import folder_paths #type: ignore
import hashlib
import comfy #type: ignore

from PIL import Image, ImageOps, ImageSequence #type: ignore
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "comfy"))

from comfy_api.latest import io #type: ignore

from ..core import CATEGORY
from ..core.image_metadata import extract_image_metadata

#credits to comfyanonymous for the initial code of the image load node, which was modified for this project
#credits to https://github.com/Jordach/comfy-plasma for the initial code of the metadata extraction, which was modified for this project


class RvImage_LoadImage(io.ComfyNode):
	@classmethod
	def define_schema(cls):
		input_dir = folder_paths.get_input_directory()
		files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
		files = folder_paths.filter_files_content_types(files, ["image"])
		# Add TIFF files explicitly (ComfyUI may not recognize them by default)
		tiff_files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f)) and f.lower().endswith(('.tif', '.tiff'))]
		files = sorted(list(set(files + tiff_files)))

		return io.Schema(
			node_id="Load Image (Metadata Pipe) [Eclipse]",
			display_name="Load Image (Metadata Pipe)",
			category=CATEGORY.MAIN.value + CATEGORY.IMAGE.value,
			inputs=[
				io.Combo.Input("image", options=files, upload=io.UploadType.image),
			],
			outputs=[
				io.Image.Output("image"),
				io.Mask.Output("mask"),
				io.Custom("pipe").Output("pipe"),
			],
		)

	@classmethod
	def execute(cls, image: str):
		image_path = folder_paths.get_annotated_filepath(image)

		img = Image.open(image_path)

		output_images: List[torch.Tensor] = []
		output_masks: List[torch.Tensor] = []
		w, h = None, None

		excluded_formats = ['MPO']

		for i in ImageSequence.Iterator(img):
			i = ImageOps.exif_transpose(i)

			if i.mode == 'I':
				i = i.point(lambda i: i * (1 / 255))
			image_rgb = i.convert("RGB")

			if len(output_images) == 0:
				w = image_rgb.size[0]
				h = image_rgb.size[1]

			if image_rgb.size[0] != w or image_rgb.size[1] != h:
				continue

			image_np = np.array(image_rgb).astype(np.float32) / 255.0
			image_tensor = torch.from_numpy(image_np)[None,]
			if 'A' in i.getbands():
				mask_np = np.array(i.getchannel('A')).astype(np.float32) / 255.0
				mask_tensor = 1. - torch.from_numpy(mask_np)
			else:
				mask_tensor = torch.zeros((64,64), dtype=torch.float32, device="cpu")
			output_images.append(image_tensor)
			output_masks.append(mask_tensor.unsqueeze(0))

		if len(output_images) > 1 and img.format not in excluded_formats:
			output_image = torch.cat(output_images, dim=0)
			output_mask = torch.cat(output_masks, dim=0)
		else:
			output_image = output_images[0]
			output_mask = output_masks[0]

		# Extract metadata using shared utility
		pipe = extract_image_metadata(img)
		# Override width/height with actual frame dimensions
		pipe["width"] = w
		pipe["height"] = h
		pipe["image"] = output_image
		
		return io.NodeOutput(output_image, output_mask, pipe)

	@classmethod
	def fingerprint_inputs(cls, **kwargs):
		image = kwargs.get("image", "")
		image_path = folder_paths.get_annotated_filepath(image)
		m = hashlib.sha256()
		with open(image_path, 'rb') as f:
			m.update(f.read())
		return m.digest().hex()

	@classmethod
	def validate_inputs(cls, **kwargs):
		image = kwargs.get("image", "")
		if not folder_paths.exists_annotated_filepath(image):
			return "Invalid image file: {}".format(image)

		return True