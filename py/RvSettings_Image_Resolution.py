# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ..core import CATEGORY
from ..core.common import RESOLUTION_PRESETS, RESOLUTION_MAP
from typing import Dict, Any, Tuple

MAX_RESOLUTION = 32768

class RvSettings_Image_Resolution:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {
            "required": {
                "resolution": (RESOLUTION_PRESETS, {
                    "default": "1024x1024 (1:1)",
                    "tooltip": "Select a preset resolution or 'Custom' to enter custom dimensions."
                }),
                "width": ("INT", {
                    "default": 1024,
                    "min": 16,
                    "max": MAX_RESOLUTION,
                    "step": 8,
                    "tooltip": "Custom width (used when 'Custom' is selected)."
                }),
                "height": ("INT", {
                    "default": 1024,
                    "min": 16,
                    "max": MAX_RESOLUTION,
                    "step": 8,
                    "tooltip": "Custom height (used when 'Custom' is selected)."
                }),
            },
        }

    CATEGORY = CATEGORY.MAIN.value + CATEGORY.SETTINGS.value
    RETURN_TYPES = ("INT", "INT",)
    RETURN_NAMES = ("width", "height")
    FUNCTION = "execute"

    def execute(self, resolution: str, width: int, height: int) -> Tuple[int, int]:
        # Return custom width/height if "Custom" selected, otherwise use preset values.
        if resolution == "Custom":
            return (width, height)
        
        preset_width, preset_height = RESOLUTION_MAP.get(resolution, (1024, 1024))
        return (preset_width, preset_height)

NODE_NAME = 'Image Resolution [Eclipse]'
NODE_DESC = 'Image Resolution'

NODE_CLASS_MAPPINGS = {
   NODE_NAME: RvSettings_Image_Resolution
}

NODE_DISPLAY_NAME_MAPPINGS = {
    NODE_NAME: NODE_DESC
}