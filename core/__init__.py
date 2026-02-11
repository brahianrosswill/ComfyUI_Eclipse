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

from .keys import *
from .logger import cstr  # cstr is now in logger.py
from .common import *

__all__ = ["keys", "common", "logger", "__version__", "version"]

# Read version from pyproject.toml
def _read_pyproject_version() -> str:
	try:
		from pathlib import Path
		import re
		
		for parent in Path(__file__).resolve().parents:
			toml_file = parent / "pyproject.toml"
			if not toml_file.exists():
				continue
			
			content = toml_file.read_text(encoding="utf-8")
			match = re.search(r"\bversion\s*=\s*['\"]([^'\"]+)['\"]", content)
			if match:
				return match.group(1)
	except Exception:
		pass
	return "1.0.50"

try:
	__version__ = _read_pyproject_version()
	version = __version__
except Exception:
	__version__ = "1.0.50"
	version = "1.0.50"

