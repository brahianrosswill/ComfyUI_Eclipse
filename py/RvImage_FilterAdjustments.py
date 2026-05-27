#
# Image Filter Adjustments — per-image brightness, contrast, saturation,
# sharpness, blur, gaussian blur, edge enhance, and detail enhance filters.
# Ported from WAS Node Suite (MIT licence, original author WASasquatch / ltdata).
#

import numpy as np  # type: ignore
import torch  # type: ignore
from PIL import Image, ImageEnhance, ImageFilter  # type: ignore

from comfy_api.latest import io  # type: ignore
from ..core import CATEGORY
from ..core.image_helpers import tensor2pil, pil2tensor

_LOG_PREFIX = "ImageFilterAdjustments"


class RvImage_FilterAdjustments(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Image Filter Adjustments [Eclipse]",
            display_name="Image Filter Adjustments",
            category=CATEGORY.MAIN.value + CATEGORY.IMAGE.value,
            description="Apply brightness, contrast, saturation, sharpness, blur, "
                        "gaussian blur, edge enhance, and detail enhance filters to an image.",
            inputs=[
                io.Image.Input("image"),
                io.Float.Input("brightness", default=0.0, min=-1.0, max=1.0, step=0.01,
                               tooltip="Additive brightness offset. 0 = no change."),
                io.Float.Input("contrast", default=1.0, min=-1.0, max=2.0, step=0.01,
                               tooltip="Multiplicative contrast factor. 1 = no change."),
                io.Float.Input("saturation", default=1.0, min=0.0, max=5.0, step=0.01,
                               tooltip="Colour saturation factor. 1 = no change."),
                io.Float.Input("sharpness", default=1.0, min=-5.0, max=5.0, step=0.01,
                               tooltip="Sharpness factor. 1 = no change."),
                io.Int.Input("blur", default=0, min=0, max=16, step=1,
                             tooltip="Number of box-blur passes."),
                io.Float.Input("gaussian_blur", default=0.0, min=0.0, max=1024.0, step=0.1,
                               tooltip="Gaussian blur radius. 0 = disabled."),
                io.Float.Input("edge_enhance", default=0.0, min=0.0, max=1.0, step=0.01,
                               tooltip="Edge enhancement blend strength. 0 = disabled."),
                io.Boolean.Input("detail_enhance", default=False,
                                 tooltip="Apply PIL DETAIL filter."),
            ],
            outputs=[
                io.Image.Output("image"),
            ],
        )

    @classmethod
    def execute(cls, image, brightness, contrast, saturation, sharpness,
                blur, gaussian_blur, edge_enhance, detail_enhance):
        if image.dim() == 3:
            image = image.unsqueeze(0)

        results = []
        for frame in image:
            # Additive/multiplicative ops in numpy
            arr = frame.float().cpu().numpy()
            if brightness != 0.0:
                arr = np.clip(arr + brightness, 0.0, 1.0)
            if contrast != 1.0:
                arr = np.clip(arr * contrast, 0.0, 1.0)

            t = torch.from_numpy(arr)
            pil_image = None

            if saturation != 1.0:
                pil_image = tensor2pil(t)
                pil_image = ImageEnhance.Color(pil_image).enhance(saturation)

            if sharpness != 1.0:
                pil_image = pil_image or tensor2pil(t)
                pil_image = ImageEnhance.Sharpness(pil_image).enhance(sharpness)

            if blur > 0:
                pil_image = pil_image or tensor2pil(t)
                for _ in range(blur):
                    pil_image = pil_image.filter(ImageFilter.BLUR)

            if gaussian_blur > 0.0:
                pil_image = pil_image or tensor2pil(t)
                pil_image = pil_image.filter(ImageFilter.GaussianBlur(radius=gaussian_blur))

            if edge_enhance > 0.0:
                pil_image = pil_image or tensor2pil(t)
                enhanced = pil_image.filter(ImageFilter.EDGE_ENHANCE_MORE)
                mask = Image.new("L", pil_image.size, round(edge_enhance * 255))
                pil_image = Image.composite(enhanced, pil_image, mask)

            if detail_enhance:
                pil_image = pil_image or tensor2pil(t)
                pil_image = pil_image.filter(ImageFilter.DETAIL)

            results.append(pil2tensor(pil_image) if pil_image else t.unsqueeze(0))

        return io.NodeOutput(torch.cat(results, dim=0))
