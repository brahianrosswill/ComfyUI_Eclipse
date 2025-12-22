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

# Smart Language Model File Handling
# Handles file scanning, model list generation, download utilities, and hash verification

from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import hashlib

from .logger import log
from .smartlm_templates import (
    get_llm_models_path, get_config_value, update_template_settings,
)


@dataclass
class VerificationResult:
    # Result of model integrity verification.
    success: bool
    corrupted_files: List[Path]  # List of files that failed hash verification
    verified_count: int  # Number of files that passed verification
    skipped_count: int  # Number of files skipped (no reference hash)


# Local logging helpers with "SmartLM" prefix
def warning_log(message: str):
    # Print warning message only when log_level is 'warning' or higher.
    log.warning("SmartLM", message)


def msg_log(message: str):
    # Print regular message (always shown).
    log.msg("SmartLM", message)


def error_log(message: str):
    # Print error message (always shown).
    log.error("SmartLM", message)


def debug_log(message: str):
    # Print debug message only when log_level is 'debug'.
    log.debug("SmartLM", message)


def download_with_progress(url: str, path: str, name: str) -> None:
    # Download file with progress bar
    import urllib.request
    from tqdm import tqdm
    
    request = urllib.request.urlopen(url)
    total = int(request.headers.get('Content-Length', 0))
    with tqdm(total=total, desc=f'[SmartLM] Downloading {name}', unit='B', unit_scale=True, unit_divisor=1024) as progress:
        urllib.request.urlretrieve(url, path, reporthook=lambda count, block_size, total_size: progress.update(block_size))


def is_same_drive(path1: Path, path2: Path) -> bool:
    # Check if two paths are on the same drive/mount point.
    #
    # On Windows: compares drive letters (e.g., C: vs D:)
    # On Unix: compares mount points using os.stat().st_dev
    #
    # Args:
    #     path1: First path
    #     path2: Second path
    #
    # Returns:
    #     True if both paths are on the same drive/filesystem
    import os
    import platform
    
    try:
        if platform.system() == "Windows":
            # On Windows, compare drive letters
            drive1 = os.path.splitdrive(str(path1.resolve()))[0].upper()
            drive2 = os.path.splitdrive(str(path2.resolve()))[0].upper()
            return drive1 == drive2
        else:
            # On Unix, compare device IDs (st_dev)
            # Need to use existing parent dirs for paths that don't exist yet
            check_path1 = path1
            while not check_path1.exists() and check_path1.parent != check_path1:
                check_path1 = check_path1.parent
            
            check_path2 = path2
            while not check_path2.exists() and check_path2.parent != check_path2:
                check_path2 = check_path2.parent
            
            return os.stat(check_path1).st_dev == os.stat(check_path2).st_dev
    except Exception:
        # If we can't determine, assume different drives (safer)
        return False


def download_file_via_temp(
    url: str,
    final_path: Path,
    filename: str,
    expected_hash: str = None,
    max_verify_attempts: int = 3
) -> bool:
    # Download a file to temp folder first, verify hash, then move to final location.
    #
    # This approach is more reliable for drives with issues because:
    # - Temp folder (usually on SSD) may be faster and more reliable
    # - If verification fails, we don't leave corrupted files in the model folder
    # - The move operation is atomic on the same filesystem
    #
    # If temp folder is on the same drive as target, downloads directly to target
    # (no benefit from temp folder in that case).
    #
    # Args:
    #     url: URL to download from
    #     final_path: Final destination path for the file
    #     filename: Display name for progress bar
    #     expected_hash: Optional SHA256 hash to verify against
    #     max_verify_attempts: Max attempts to download and verify (default 3)
    #
    # Returns:
    #     True if download and verification succeeded, False otherwise
    import tempfile
    import shutil
    
    # Check if temp folder is on the same drive as target
    temp_check_dir = Path(tempfile.gettempdir())
    use_temp_folder = not is_same_drive(temp_check_dir, final_path)
    
    if not use_temp_folder:
        debug_log(f"Temp folder is on same drive as target, downloading directly")
    
    for attempt in range(max_verify_attempts):
        temp_dir = None
        try:
            if use_temp_folder:
                # Create temp directory for download
                temp_dir = tempfile.mkdtemp(prefix="eclipse_download_")
                download_path = Path(temp_dir) / filename
            else:
                # Download directly to final location
                final_path.parent.mkdir(parents=True, exist_ok=True)
                download_path = final_path
            
            if attempt > 0:
                msg_log(f"Retry attempt {attempt + 1}/{max_verify_attempts} for {filename}...")
            
            # Download to target location (temp or final)
            download_with_progress(url, str(download_path), filename)
            
            if not download_path.exists():
                error_log(f"Download failed: file not created")
                continue
            
            # Verify hash if provided
            verified_hash = None
            if expected_hash:
                location_desc = "temp location" if use_temp_folder else "download location"
                msg_log(f"Verifying {filename} in {location_desc}...")
                actual_hash = calculate_file_hash(download_path, show_progress=True)
                
                if actual_hash != expected_hash:
                    error_log(f"✗ Hash verification failed for {filename} (attempt {attempt + 1}/{max_verify_attempts})")
                    error_log(f"  Expected: {expected_hash}")
                    error_log(f"  Got:      {actual_hash}")
                    # Clean up and retry download
                    if download_path.exists():
                        download_path.unlink()
                    continue
                
                msg_log(f"✓ Hash verified in {location_desc}")
                verified_hash = actual_hash
            
            # If using temp folder, copy to final location (keep temp for retry if copy fails)
            if use_temp_folder:
                # Ensure target directory exists
                final_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Retry loop for copy operation (don't need to re-download if copy fails)
                max_copy_attempts = 3
                copy_success = False
                corrupted_file_exists = False  # Track if we have a corrupted file occupying sectors
                
                for copy_attempt in range(max_copy_attempts):
                    try:
                        # On first attempt or if no corrupted file, copy directly to final path
                        # On retry after corruption: copy to temp name to force different sectors
                        if corrupted_file_exists:
                            # Copy to temporary name (corrupted file still occupies original sectors)
                            temp_final_path = final_path.parent / f"{final_path.name}.new"
                            target_path = temp_final_path
                            msg_log(f"Copying to alternate location to avoid bad sectors...")
                        else:
                            # Delete existing file if present (first attempt)
                            if final_path.exists():
                                final_path.unlink()
                            target_path = final_path
                        
                        # Copy from temp to target location
                        shutil.copy2(str(download_path), str(target_path))
                        
                        if copy_attempt > 0:
                            msg_log(f"✓ Copied {filename} (attempt {copy_attempt + 1})")
                        else:
                            msg_log(f"✓ Copied {filename} to final location")
                        
                        # Verify hash after copy to detect target drive issues
                        if expected_hash:
                            msg_log(f"Verifying {filename} after copy...")
                            post_copy_hash = calculate_file_hash(target_path, show_progress=False)
                            
                            if post_copy_hash != expected_hash:
                                error_log(f"⚠ DRIVE ISSUE DETECTED: File corrupted after copy to target drive!")
                                error_log(f"  File was verified correct in temp folder but corrupted after copying.")
                                error_log(f"  This indicates your target drive may have bad sectors or write errors.")
                                error_log(f"  Expected: {expected_hash}")
                                error_log(f"  Got:      {post_copy_hash}")
                                
                                if not corrupted_file_exists:
                                    # First corruption - keep the file to occupy bad sectors
                                    corrupted_file_exists = True
                                    msg_log(f"Keeping corrupted file to force write to different sectors on retry...")
                                else:
                                    # Retry with temp name also failed - delete it
                                    if target_path.exists():
                                        target_path.unlink()
                                
                                if copy_attempt < max_copy_attempts - 1:
                                    msg_log(f"Retrying copy (attempt {copy_attempt + 2}/{max_copy_attempts})...")
                                continue  # Retry copy
                            
                            # Use the post-copy hash (verified to match expected)
                            verified_hash = post_copy_hash
                        
                        # If we used a temp name, rename to final name
                        if corrupted_file_exists:
                            # Delete the corrupted file and rename the good one
                            if final_path.exists():
                                final_path.unlink()
                            target_path.rename(final_path)
                            msg_log(f"✓ Renamed to final filename after successful verification")
                        
                        copy_success = True
                        break
                        
                    except Exception as e:
                        error_log(f"Copy error (attempt {copy_attempt + 1}/{max_copy_attempts}): {e}")
                        # Clean up temp file if it exists
                        if corrupted_file_exists:
                            temp_final_path = final_path.parent / f"{final_path.name}.new"
                            if temp_final_path.exists():
                                try:
                                    temp_final_path.unlink()
                                except:
                                    pass
                
                # Clean up after copy attempts
                if copy_success:
                    # Clean up temp download file
                    try:
                        if download_path.exists():
                            download_path.unlink()
                    except:
                        pass  # Not critical if temp cleanup fails
                else:
                    # All copy attempts failed - clean up and retry download
                    error_log(f"All {max_copy_attempts} copy attempts failed for {filename}")
                    # Clean up any leftover files
                    if final_path.exists():
                        try:
                            final_path.unlink()
                        except:
                            pass
                    temp_final_path = final_path.parent / f"{final_path.name}.new"
                    if temp_final_path.exists():
                        try:
                            temp_final_path.unlink()
                        except:
                            pass
                    if download_path.exists():
                        download_path.unlink()
                    continue  # Retry download
            
            # Save hash file only if we have a verified hash
            if verified_hash:
                try:
                    sha_file = final_path.parent / f"{final_path.name}.sha256"
                    sha_file.write_text(verified_hash)
                    debug_log(f"Saved hash file: {sha_file.name}")
                except Exception as e:
                    warning_log(f"Could not cache hash: {e}")
            
            return True
            
        except Exception as e:
            error_log(f"Download error (attempt {attempt + 1}/{max_verify_attempts}): {e}")
            # Clean up failed download if downloading directly
            if not use_temp_folder and final_path.exists():
                try:
                    final_path.unlink()
                except Exception:
                    pass
        finally:
            # Clean up temp directory
            if temp_dir and Path(temp_dir).exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
    
    error_log(f"✗ Failed to download {filename} after {max_verify_attempts} attempts")
    return False


def get_hf_file_hash(repo_id: str, filename: str) -> str | None:
    # Get SHA256 hash for a file from HuggingFace metadata.
    #
    # Args:
    #     repo_id: HuggingFace repo_id (user/repo format)
    #     filename: Filename to get hash for
    #
    # Returns:
    #     SHA256 hash string or None if not available
    try:
        from huggingface_hub import hf_hub_url, get_hf_file_metadata
        
        url = hf_hub_url(repo_id=repo_id, filename=filename, repo_type="model")
        metadata = get_hf_file_metadata(url=url)
        
        if hasattr(metadata, 'etag') and metadata.etag:
            return metadata.etag
    except Exception as e:
        debug_log(f"Could not get HF hash for {filename}: {e}")
    
    return None


def get_llm_model_list() -> List[str]:
    # Scan models/LLM folder and return list of available models.
    # First collects all model files, then filters to show:
    # - For shard files: show folder/ instead of individual files
    # - For single files: show full relative path to the file
    try:
        llm_dir = get_llm_models_path()
        
        if not llm_dir.exists():
            return ["(No models/LLM folder found)"]
        
        model_extensions = {'.safetensors', '.gguf', '.bin', '.pt'}
        all_model_files = []
        
        # Step 1: Recursively scan and collect all model files
        def scan_files(base_path: Path, relative_path: str = ""):
            # Recursively collect all model files
            try:
                for item in base_path.iterdir():
                    if item.is_file() and item.suffix in model_extensions:
                        # Build full relative path
                        if relative_path:
                            file_path = f"{relative_path}/{item.name}"
                        else:
                            file_path = item.name
                        all_model_files.append(file_path)
                    elif item.is_dir():
                        # Recurse into subdirectories (limit depth to avoid infinite loops)
                        item_rel_path = f"{relative_path}/{item.name}" if relative_path else item.name
                        if relative_path.count('/') < 4:  # Max 4 levels deep
                            scan_files(item, item_rel_path)
            except PermissionError:
                pass  # Skip directories we can't access
        
        scan_files(llm_dir)
        
        if not all_model_files:
            return ["(No models found in models/LLM)"]
        
        # Step 2: Group files by their parent folder
        folder_files = defaultdict(list)
        
        for file_path in all_model_files:
            if '/' in file_path:
                folder = file_path.rsplit('/', 1)[0]
                filename = file_path.rsplit('/', 1)[1]
            else:
                folder = ""  # Root level
                filename = file_path
            
            folder_files[folder].append(filename)
        
        # Step 3: Check for config.json to identify model repositories
        llm_base = get_llm_models_path()
        
        folders_with_config = set()
        for folder in folder_files.keys():
            if folder:  # Skip root level
                config_path = llm_base / folder / "config.json"
                if config_path.exists():
                    folders_with_config.add(folder)
        
        # Step 4: Filter to create final model list
        models = []
        
        for folder, files in folder_files.items():
            # Separate mmproj files from model files
            model_files = [f for f in files if 'mmproj' not in f.lower()]
            
            # Separate GGUF files from other model files
            gguf_files = [f for f in model_files if f.lower().endswith('.gguf')]
            non_gguf_files = [f for f in model_files if not f.lower().endswith('.gguf')]
            
            # Check if any non-GGUF file is a shard file
            has_shards = any('-of-' in f or '.shard' in f.lower() for f in non_gguf_files)
            
            # Check if folder has config.json (indicates it's a model repository)
            has_config = folder in folders_with_config
            
            # For non-GGUF files: show folder/ if has shards or config.json
            if non_gguf_files and (has_shards or has_config):
                # Show folder/ for sharded models or model repositories with config.json
                if folder:
                    models.append(folder + "/")
                else:
                    # Shards in root - shouldn't happen but handle it
                    for f in non_gguf_files:
                        models.append(f)
            elif non_gguf_files:
                # List individual non-GGUF files
                for f in non_gguf_files:
                    if folder:
                        models.append(f"{folder}/{f}")
                    else:
                        models.append(f)
            
            # GGUF files: ALWAYS show individual files (even if folder has config.json)
            # This allows users to select specific quantization variants
            for f in gguf_files:
                if folder:
                    models.append(f"{folder}/{f}")
                else:
                    models.append(f)
        
        return sorted(models)
    
    except Exception as e:
        error_log(f"Error scanning models/LLM: {e}")
        return ["(Error scanning models folder)"]


def get_mmproj_list() -> List[str]:
    # Scan models/LLM folder for mmproj files for GGUF QwenVL models.
    # Returns only individual .mmproj files and .gguf files containing 'mmproj' in the name.
    # Never shows folders, only file paths.
    try:
        llm_dir = get_llm_models_path()
        
        if not llm_dir.exists():
            return ["None", "(No models/LLM folder found)"]
        
        mmproj_files = ["None"]  # Add None option for when mmproj is not needed
        
        def scan_for_mmproj(base_path: Path, relative_path: str = ""):
            # Recursively scan for mmproj files
            try:
                for item in base_path.iterdir():
                    if item.is_file():
                        # Match .mmproj files or .gguf files with 'mmproj' in name
                        if item.suffix == '.mmproj' or (item.suffix == '.gguf' and 'mmproj' in item.name.lower()):
                            if relative_path:
                                mmproj_files.append(f"{relative_path}/{item.name}")
                            else:
                                mmproj_files.append(item.name)
                    elif item.is_dir():
                        # Recurse into subdirectories (limit depth to avoid infinite loops)
                        item_rel_path = f"{relative_path}/{item.name}" if relative_path else item.name
                        if relative_path.count('/') < 4:  # Max 4 levels deep
                            scan_for_mmproj(item, item_rel_path)
            except PermissionError:
                pass  # Skip directories we can't access
        
        # Start recursive scan from LLM root
        scan_for_mmproj(llm_dir)
        
        if len(mmproj_files) == 1:  # Only "None" option
            mmproj_files.append("(No mmproj files found)")
        
        return sorted(mmproj_files)
    
    except Exception as e:
        error_log(f"Error scanning for mmproj files: {e}")
        return ["None", "(Error scanning mmproj files)"]


def search_model_file(filename: str, llm_base: Path) -> Path | None:
    # Search recursively for a model file in the LLM folder.
    # Used to find legacy model files when template paths are outdated.
    # Returns Path object if found, None otherwise.
    try:
        if not llm_base.exists():
            return None
        
        # Search recursively (limit depth implicitly by rglob)
        for path in llm_base.rglob(filename):
            if path.is_file():
                return path
        
        return None
    except Exception as e:
        warning_log(f"Error searching for {filename}: {e}")
        return None


def calculate_model_size(target_path: Path) -> float:
    # Calculate total model size in GB from a file or directory.
    # Handles sharded models, single files, and directories with multiple model files.
    # Returns size in GB, or 0.0 if calculation fails.
    try:
        total_size_gb = 0.0
        
        if target_path.is_file():
            # Single file (GGUF, safetensors, etc.)
            total_size_gb = target_path.stat().st_size / (1024**3)
        elif target_path.is_dir():
            # Model folder - check for sharded models first, then single files
            # Priority: .safetensors (preferred) > .bin > .pt > .gguf
            all_files = list(target_path.rglob('*'))
            model_files = [f for f in all_files if f.is_file()]
            
            # Check for shard files (e.g., model-00001-of-00005.safetensors)
            safetensors_files = [f for f in model_files if f.suffix == '.safetensors']
            bin_files = [f for f in model_files if f.suffix == '.bin']
            pt_files = [f for f in model_files if f.suffix == '.pt']
            gguf_files = [f for f in model_files if f.suffix == '.gguf']
            
            # Check if we have shards (files with -of- pattern)
            has_shards = lambda files: any('-of-' in f.name for f in files)
            
            # Priority: safetensors shards > single safetensors > bin shards > single bin > pt > gguf
            if has_shards(safetensors_files):
                # Use safetensors shards
                for file in safetensors_files:
                    if '-of-' in file.name:
                        total_size_gb += file.stat().st_size / (1024**3)
            elif safetensors_files:
                # Single safetensors file (no shards)
                for file in safetensors_files:
                    total_size_gb += file.stat().st_size / (1024**3)
            elif has_shards(bin_files):
                # Use bin shards
                for file in bin_files:
                    if '-of-' in file.name:
                        total_size_gb += file.stat().st_size / (1024**3)
            elif bin_files:
                # Single bin file
                for file in bin_files:
                    total_size_gb += file.stat().st_size / (1024**3)
            elif pt_files:
                # PT files
                for file in pt_files:
                    total_size_gb += file.stat().st_size / (1024**3)
            elif gguf_files:
                # GGUF files
                for file in gguf_files:
                    total_size_gb += file.stat().st_size / (1024**3)
        
        return total_size_gb
    
    except Exception as e:
        warning_log(f"Error calculating model size: {e}")
        return 0.0


def calculate_file_hash(file_path: Path, show_progress: bool = True) -> str:
    # Calculate SHA256 hash of a file with optional progress display.
    #
    # Args:
    #     file_path: Path to the file to hash
    #     show_progress: Whether to display progress for large files (>100MB)
    #
    # Returns:
    #     Hexadecimal SHA256 hash string
    import sys
    
    sha256_hash = hashlib.sha256()
    file_size = file_path.stat().st_size
    bytes_processed = 0
    last_progress = -1
    
    # Show initial message with file size for large files
    size_mb = file_size / (1024 * 1024)
    if show_progress and file_size > 100 * 1024 * 1024:
        msg_log(f"Calculating hash for {file_path.name} ({size_mb:.1f} MB)...")
    elif show_progress:
        msg_log(f"Calculating hash for {file_path.name}...")
    
    with open(file_path, "rb") as f:
        while chunk := f.read(8192 * 1024):  # 8MB chunks for speed
            sha256_hash.update(chunk)
            bytes_processed += len(chunk)
            # Show progress for large files (> 100MB)
            if show_progress and file_size > 100 * 1024 * 1024:
                progress = int((bytes_processed / file_size) * 100)
                # Update every 1% to keep progress smooth
                if progress != last_progress:
                    # Use carriage return to overwrite the same line
                    sys.stdout.write(f"\rEclipse: [SmartLM]   Hashing: {progress}% ({bytes_processed / (1024*1024):.0f}/{size_mb:.0f} MB)")
                    sys.stdout.flush()
                    last_progress = progress
    
    # Print newline after progress is complete to preserve the final line
    if show_progress and file_size > 100 * 1024 * 1024:
        print()  # Move to next line
    
    return sha256_hash.hexdigest()


def verify_model_integrity(model_path: Path, repo_id: str = None, hf_filename: str = None, return_details: bool = False):
    # Verify model file integrity using SHA256 checksums.
    # Calculates and saves hashes on first load, then verifies on subsequent loads.
    #
    # Args:
    #     model_path: Path to model file or directory
    #     repo_id: HuggingFace repo_id (user/repo format or full URL)
    #     hf_filename: Optional filename to use for HuggingFace lookup (for renamed files)
    #     return_details: If True, return VerificationResult with details; otherwise return bool
    #
    # Returns:
    #     If return_details=False: True if verification passes, False if corruption detected
    #     If return_details=True: VerificationResult with success status and list of corrupted files
    corrupted_files = []
    
    try:
        # Look for model.safetensors or pytorch_model.bin
        critical_files = []
        if model_path.is_dir():
            safetensors = list(model_path.glob("*.safetensors"))
            bin_files = list(model_path.glob("pytorch_model*.bin"))
            critical_files = safetensors if safetensors else bin_files
        else:
            critical_files = [model_path] if model_path.suffix in ['.gguf', '.safetensors', '.bin'] else []
        
        if not critical_files:
            warning_log(f"No model files found to verify at {model_path}")
            if return_details:
                return VerificationResult(success=True, corrupted_files=[], verified_count=0, skipped_count=0)
            return True  # Skip verification
        
        verified_count = 0
        failed_count = 0
        calculated_count = 0
        
        for file_path in critical_files:
            sha_file = file_path.parent / f"{file_path.name}.sha256"
            expected_hash = None
            
            # Check if we have a cached hash file first
            if sha_file.exists():
                try:
                    expected_hash = sha_file.read_text().strip().split()[0]
                    verified_count += 1
                    continue  # Skip hash calculation, already verified
                except:
                    pass
            
            # If no cached hash, try to get it from HuggingFace
            if not expected_hash and repo_id:
                try:
                    from huggingface_hub import hf_hub_url, get_hf_file_metadata
                    
                    # Use provided hf_filename if available (for renamed files), otherwise use local filename
                    lookup_filename = hf_filename if hf_filename else file_path.name
                    msg_log(f"Fetching hash from HuggingFace for {lookup_filename}...")
                    
                    # Construct URL and get metadata
                    url = hf_hub_url(repo_id=repo_id, filename=lookup_filename, repo_type="model")
                    metadata = get_hf_file_metadata(url=url)
                    
                    # ETag is the SHA256 hash for git-lfs files (per HuggingFace docs)
                    if hasattr(metadata, 'etag') and metadata.etag:
                        expected_hash = metadata.etag
                        msg_log(f"Retrieved hash from HuggingFace")
                    else:
                        warning_log(f"No hash available in HuggingFace metadata for {lookup_filename}")
                except Exception as e:
                    warning_log(f"Could not retrieve hash from HuggingFace ({repo_id}/{lookup_filename}): {e}")

            # If we still don't have a reference hash, skip verification
            if not expected_hash:
                warning_log(f"No reference hash available for {file_path.name}, skipping verification")
                calculated_count += 1
                continue
            
            # Calculate actual hash using centralized function
            actual_hash = calculate_file_hash(file_path, show_progress=True)
            
            # Verify against HuggingFace hash
            if actual_hash == expected_hash:
                msg_log(f"✓ {file_path.name} integrity verified")
                verified_count += 1
                
                # Save hash file for future fast verification
                try:
                    sha_file.write_text(expected_hash)
                    msg_log(f"Cached hash to {sha_file.name}")
                except Exception as e:
                    warning_log(f"Could not cache hash: {e}")
            else:
                error_log(f"✗ {file_path.name} CORRUPTED! Hash mismatch.")
                error_log(f"  Expected: {expected_hash}")
                error_log(f"  Got:      {actual_hash}")
                failed_count += 1
                corrupted_files.append(file_path)
                # Don't save hash file on failure - user needs to redownload
        
        if failed_count > 0:
            error_log(f"⚠ Model verification FAILED! {failed_count} corrupted file(s) detected.")
            if return_details:
                return VerificationResult(success=False, corrupted_files=corrupted_files, verified_count=verified_count, skipped_count=calculated_count)
            return False
        elif verified_count > 0:
            msg_log(f"✓ Model integrity verified ({verified_count} file(s))")
        elif calculated_count > 0:
            warning_log(f"⚠ No reference hash available, skipping verification for {calculated_count} file(s)")
        
        if return_details:
            return VerificationResult(success=True, corrupted_files=[], verified_count=verified_count, skipped_count=calculated_count)
        return True
        
    except Exception as e:
        warning_log(f"Model verification error (non-critical): {e}")
        if return_details:
            return VerificationResult(success=True, corrupted_files=[], verified_count=0, skipped_count=0)
        return True  # Don't block loading on verification errors


def check_model_completeness(model_path: Path, repo_id: str = None, hf_token: str = None) -> Tuple[bool, List[str]]:
    # Check if all required model files are present by reading the model index file.
    #
    # For sharded models, reads model.safetensors.index.json or pytorch_model.bin.index.json
    # to get the list of required weight files and checks if they all exist.
    #
    # Note: Consolidated files are intentionally ignored - users may have deleted them
    # to save space since they're only needed for specific loading methods.
    #
    # Args:
    #     model_path: Path to model directory
    #     repo_id: HuggingFace repo_id for re-downloading missing files
    #     hf_token: Optional HuggingFace token for authenticated downloads
    #
    # Returns:
    #     Tuple of (is_complete, missing_files_list)
    import json
    
    if not model_path.is_dir():
        # Single file model (e.g., GGUF) - just check if file exists
        if model_path.exists():
            return (True, [])
        return (False, [model_path.name])
    
    missing_files = []
    
    # Check for safetensors index file first (preferred), then pytorch
    index_files = [
        model_path / "model.safetensors.index.json",
        model_path / "pytorch_model.bin.index.json",
    ]
    
    index_file = None
    for idx_file in index_files:
        if idx_file.exists():
            index_file = idx_file
            break
    
    if not index_file:
        # No index file - model is either single-file or we can't check
        # Just verify basic config exists
        config_file = model_path / "config.json"
        if not config_file.exists():
            return (False, ["config.json"])
        return (True, [])
    
    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        
        # Get unique weight files from the weight_map
        weight_map = index_data.get("weight_map", {})
        required_files = set(weight_map.values())
        
        # Check each required file (but ignore consolidated files - user may have deleted them intentionally)
        for filename in required_files:
            # Skip consolidated files - these are optional alternative formats
            # Users often delete them to save disk space
            if "consolidated" in filename.lower():
                continue
            
            file_path = model_path / filename
            if not file_path.exists():
                missing_files.append(filename)
                debug_log(f"Missing model file: {filename}")
        
        # Also check essential config files
        essential_files = ["config.json"]
        for filename in essential_files:
            file_path = model_path / filename
            if not file_path.exists():
                missing_files.append(filename)
        
        if missing_files:
            warning_log(f"Model incomplete: {len(missing_files)} file(s) missing")
            return (False, missing_files)
        
        return (True, [])
        
    except Exception as e:
        warning_log(f"Could not read model index file: {e}")
        return (True, [])  # Assume complete if we can't check


def download_missing_files(
    model_path: Path,
    missing_files: List[str],
    repo_id: str,
    hf_token: str = None
) -> bool:
    # Download specific missing files from HuggingFace via temp folder.
    #
    # Downloads to temp folder first, verifies hash, then moves to final location.
    # This is more reliable for drives with issues. If temp folder is on the same
    # drive as target, downloads directly (no benefit from temp folder).
    #
    # Args:
    #     model_path: Path to model directory
    #     missing_files: List of filenames that are missing
    #     repo_id: HuggingFace repo_id (user/repo format)
    #     hf_token: Optional HuggingFace token for authenticated downloads
    #
    # Returns:
    #     True if all files were successfully downloaded, False otherwise
    import tempfile
    import shutil
    
    if not missing_files:
        return True
    
    if not repo_id:
        error_log("Cannot download missing files: no repo_id provided")
        return False
    
    # Extract clean repo_id if it's a URL
    clean_repo_id = extract_repo_id_from_url(repo_id)
    if not clean_repo_id:
        error_log(f"Cannot extract repo_id from: {repo_id}")
        return False
    
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        error_log("huggingface_hub not installed, cannot download missing files")
        return False
    
    # Check if temp folder is on the same drive as target
    temp_check_dir = Path(tempfile.gettempdir())
    use_temp_folder = not is_same_drive(temp_check_dir, model_path)
    
    if use_temp_folder:
        debug_log(f"Using temp folder for download (temp={temp_check_dir.drive}, target={model_path.drive})")
    else:
        debug_log(f"Temp folder is on same drive as target ({temp_check_dir.drive}), downloading directly")
    
    msg_log(f"Downloading {len(missing_files)} missing file(s) from {clean_repo_id}...")
    
    # Pre-fetch all hashes upfront (reduces interleaved HEAD requests during downloads)
    debug_log(f"Pre-fetching hashes for {len(missing_files)} file(s)...")
    file_hashes = {}
    for filename in missing_files:
        hash_value = get_hf_file_hash(clean_repo_id, filename)
        file_hashes[filename] = hash_value
        if hash_value:
            debug_log(f"  Got hash for {filename}: {hash_value[:16]}...")
        else:
            debug_log(f"  No hash available for {filename}")
    
    success_count = 0
    failed_files = []
    max_attempts = get_config_value("retry_download_attempts", 2) + 1
    
    for filename in missing_files:
        file_success = False
        final_path = model_path / filename
        
        # Use pre-fetched hash
        expected_hash = file_hashes.get(filename)
        
        for attempt in range(max_attempts):
            temp_dir = None
            try:
                if attempt > 0:
                    msg_log(f"  Retry attempt {attempt + 1}/{max_attempts} for {filename}...")
                else:
                    msg_log(f"  Downloading {filename}...")
                
                if use_temp_folder:
                    # Create temp directory for download
                    temp_dir = tempfile.mkdtemp(prefix="eclipse_download_")
                    download_dir = Path(temp_dir)
                    debug_log(f"  Created temp dir: {temp_dir}")
                else:
                    # Download directly to final location (same drive optimization)
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    download_dir = model_path
                    debug_log(f"  Direct download to: {download_dir}")
                
                download_kwargs = {
                    "repo_id": clean_repo_id,
                    "filename": filename,
                    "local_dir": str(download_dir),
                    "local_dir_use_symlinks": False,
                }
                
                if hf_token:
                    download_kwargs["token"] = hf_token
                
                hf_hub_download(**download_kwargs)
                
                # File is downloaded to download_dir/filename
                downloaded_file = download_dir / filename
                if not downloaded_file.exists():
                    error_log(f"  Download failed: file not created")
                    continue
                
                # Verify hash if available
                verified_hash = None
                if expected_hash:
                    actual_hash = calculate_file_hash(downloaded_file, show_progress=False)
                    if actual_hash != expected_hash:
                        error_log(f"  ✗ Hash mismatch for {filename} (attempt {attempt + 1}/{max_attempts})")
                        if downloaded_file.exists():
                            downloaded_file.unlink()
                        continue
                    debug_log(f"  Hash verified for {filename}")
                    verified_hash = actual_hash
                else:
                    debug_log(f"  No hash available for {filename}, skipping verification")
                    # For direct downloads without hash, calculate hash for saving
                    if not use_temp_folder:
                        verified_hash = calculate_file_hash(downloaded_file, show_progress=False)
                
                # Copy to final location if using temp folder (keep temp for retry if copy fails)
                if use_temp_folder:
                    debug_log(f"  Copying from temp to final location...")
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Retry loop for copy operation
                    max_copy_attempts = 3
                    copy_success = False
                    corrupted_file_exists = False  # Track if we have a corrupted file occupying sectors
                    
                    for copy_attempt in range(max_copy_attempts):
                        try:
                            # On retry after corruption: copy to temp name to force different sectors
                            if corrupted_file_exists:
                                temp_final_path = final_path.parent / f"{final_path.name}.new"
                                target_path = temp_final_path
                                debug_log(f"  Copying to alternate location to avoid bad sectors...")
                            else:
                                if final_path.exists():
                                    final_path.unlink()
                                target_path = final_path
                            
                            shutil.copy2(str(downloaded_file), str(target_path))
                            
                            # Verify hash after copy to detect target drive issues
                            if expected_hash:
                                post_copy_hash = calculate_file_hash(target_path, show_progress=False)
                                
                                if post_copy_hash != expected_hash:
                                    error_log(f"  ⚠ DRIVE ISSUE: File corrupted after copy to target drive!")
                                    error_log(f"    This indicates your target drive may have write errors.")
                                    
                                    if not corrupted_file_exists:
                                        corrupted_file_exists = True
                                        debug_log(f"  Keeping corrupted file to force write to different sectors...")
                                    else:
                                        if target_path.exists():
                                            target_path.unlink()
                                    
                                    if copy_attempt < max_copy_attempts - 1:
                                        debug_log(f"  Retrying copy (attempt {copy_attempt + 2}/{max_copy_attempts})...")
                                    continue  # Retry copy
                                
                                verified_hash = post_copy_hash
                            
                            # If we used a temp name, rename to final name
                            if corrupted_file_exists:
                                if final_path.exists():
                                    final_path.unlink()
                                target_path.rename(final_path)
                                debug_log(f"  Renamed to final filename after successful verification")
                            
                            copy_success = True
                            debug_log(f"  Copy successful to {final_path}")
                            break
                            
                        except Exception as e:
                            error_log(f"  Copy error (attempt {copy_attempt + 1}/{max_copy_attempts}): {e}")
                            if corrupted_file_exists:
                                temp_final_path = final_path.parent / f"{final_path.name}.new"
                                if temp_final_path.exists():
                                    try:
                                        temp_final_path.unlink()
                                    except:
                                        pass
                    
                    # Clean up after copy attempts
                    if copy_success:
                        try:
                            if downloaded_file.exists():
                                downloaded_file.unlink()
                        except:
                            pass
                    else:
                        error_log(f"  All {max_copy_attempts} copy attempts failed for {filename}")
                        # Clean up any leftover files
                        if final_path.exists():
                            try:
                                final_path.unlink()
                            except:
                                pass
                        temp_final_path = final_path.parent / f"{final_path.name}.new"
                        if temp_final_path.exists():
                            try:
                                temp_final_path.unlink()
                            except:
                                pass
                        if downloaded_file.exists():
                            downloaded_file.unlink()
                        continue  # Retry download
                
                # Save hash file only if we have a verified hash
                if verified_hash:
                    try:
                        sha_file = final_path.parent / f"{final_path.name}.sha256"
                        sha_file.write_text(verified_hash)
                        debug_log(f"  Saved hash file: {sha_file.name}")
                    except Exception as e:
                        warning_log(f"  Could not save hash file: {e}")
                
                msg_log(f"  ✓ Downloaded {filename}")
                success_count += 1
                file_success = True
                break
                
            except Exception as e:
                error_log(f"  \u2717 Error downloading {filename} (attempt {attempt + 1}/{max_attempts}): {e}")
                # Clean up failed download if downloading directly
                if not use_temp_folder and final_path.exists():
                    try:
                        final_path.unlink()
                    except Exception:
                        pass
            finally:
                # Clean up temp directory
                if temp_dir and Path(temp_dir).exists():
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception:
                        pass
        
        if not file_success:
            failed_files.append(filename)
    
    if failed_files:
        error_log(f"Failed to download {len(failed_files)} file(s): {', '.join(failed_files)}")
        return False
    
    msg_log(f"\u2713 Successfully downloaded {success_count} missing file(s)")
    return True


def redownload_corrupted_files(
    corrupted_files: List[Path],
    repo_id: str,
    local_dir: Path,
    hf_token: str = None
) -> bool:
    # Re-download only the corrupted files instead of the entire model.
    #
    # Downloads to temp folder first, verifies hash, then moves to final location.
    # This is more reliable for drives with issues - if verification fails in temp,
    # we retry without leaving corrupted files in the model folder.
    #
    # If temp folder is on the same drive as target, downloads directly
    # (no benefit from temp folder in that case).
    #
    # Args:
    #     corrupted_files: List of Path objects for files that failed hash verification
    #     repo_id: HuggingFace repo_id (user/repo format, not URL)
    #     local_dir: Local directory where the model is stored
    #     hf_token: Optional HuggingFace token for authenticated downloads
    #
    # Returns:
    #     True if all files were successfully re-downloaded and verified, False otherwise
    import tempfile
    import shutil
    
    if not corrupted_files:
        return True
    
    if not repo_id:
        warning_log("Cannot re-download files: no repo_id provided")
        return False
    
    # Extract clean repo_id if it's a URL
    clean_repo_id = extract_repo_id_from_url(repo_id)
    if not clean_repo_id:
        warning_log(f"Cannot extract repo_id from: {repo_id}")
        return False
    
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        error_log("huggingface_hub not installed, cannot re-download individual files")
        return False
    
    # Check if temp folder is on the same drive as target
    temp_check_dir = Path(tempfile.gettempdir())
    use_temp_folder = not is_same_drive(temp_check_dir, local_dir)
    
    if not use_temp_folder:
        debug_log("Temp folder is on same drive as target, downloading directly")
    
    # Pre-fetch all hashes upfront (reduces interleaved HEAD requests during downloads)
    file_hashes = {}
    for file_path in corrupted_files:
        filename = file_path.name
        expected_hash = get_hf_file_hash(clean_repo_id, filename)
        if expected_hash:
            file_hashes[filename] = expected_hash
        else:
            warning_log(f"Could not get expected hash for {filename}, will download without verification")
            file_hashes[filename] = None
    
    success_count = 0
    failed_files = []
    max_attempts = get_config_value("retry_download_attempts", 2) + 1
    
    for file_path in corrupted_files:
        filename = file_path.name
        file_success = False
        final_path = local_dir / filename
        
        # Delete the corrupted file and its hash file first
        try:
            if file_path.exists():
                file_path.unlink()
                msg_log(f"Deleted corrupted file: {filename}")
            
            sha_file = file_path.parent / f"{filename}.sha256"
            if sha_file.exists():
                sha_file.unlink()
        except Exception as e:
            warning_log(f"Failed to delete corrupted file {filename}: {e}")
        
        # Use pre-fetched hash
        expected_hash = file_hashes.get(filename)
        
        for attempt in range(max_attempts):
            temp_dir = None
            try:
                if attempt > 0:
                    msg_log(f"Retry attempt {attempt + 1}/{max_attempts} for {filename}...")
                else:
                    location_desc = "via temp" if use_temp_folder else "directly"
                    msg_log(f"Re-downloading {filename} from {clean_repo_id} ({location_desc})...")
                
                if use_temp_folder:
                    # Create temp directory for download
                    temp_dir = tempfile.mkdtemp(prefix="eclipse_redownload_")
                    download_dir = Path(temp_dir)
                else:
                    # Download directly to final location
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    download_dir = local_dir
                
                download_kwargs = {
                    "repo_id": clean_repo_id,
                    "filename": filename,
                    "local_dir": str(download_dir),
                    "local_dir_use_symlinks": False,
                    "force_download": True,  # Force re-download even if cached
                }
                
                if hf_token:
                    download_kwargs["token"] = hf_token
                
                hf_hub_download(**download_kwargs)
                
                # File is downloaded to download_dir/filename
                downloaded_file = download_dir / filename
                if not downloaded_file.exists():
                    error_log(f"Download failed: file not created")
                    continue
                
                # Verify hash in download location
                verified_hash = None
                if expected_hash:
                    location_desc = "temp location" if use_temp_folder else "download location"
                    msg_log(f"Verifying {filename} in {location_desc}...")
                    actual_hash = calculate_file_hash(downloaded_file, show_progress=True)
                    
                    if actual_hash != expected_hash:
                        error_log(f"✗ Hash verification failed (attempt {attempt + 1}/{max_attempts})")
                        error_log(f"  Expected: {expected_hash}")
                        error_log(f"  Got:      {actual_hash}")
                        # Clean up and retry download
                        if downloaded_file.exists():
                            downloaded_file.unlink()
                        continue
                    
                    msg_log(f"✓ Hash verified in {location_desc}")
                    verified_hash = actual_hash
                
                # Copy verified file to final location if using temp folder (keep temp for retry if copy fails)
                if use_temp_folder:
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Retry loop for copy operation
                    max_copy_attempts = 3
                    copy_success = False
                    corrupted_file_exists = False  # Track if we have a corrupted file occupying sectors
                    
                    for copy_attempt in range(max_copy_attempts):
                        try:
                            # On retry after corruption: copy to temp name to force different sectors
                            if corrupted_file_exists:
                                temp_final_path = final_path.parent / f"{final_path.name}.new"
                                target_path = temp_final_path
                                msg_log(f"Copying to alternate location to avoid bad sectors...")
                            else:
                                if final_path.exists():
                                    final_path.unlink()
                                target_path = final_path
                            
                            shutil.copy2(str(downloaded_file), str(target_path))
                            
                            if copy_attempt > 0:
                                msg_log(f"✓ Copied {filename} (attempt {copy_attempt + 1})")
                            
                            # Verify hash after copy to detect target drive issues
                            if expected_hash:
                                msg_log(f"Verifying {filename} after copy...")
                                post_copy_hash = calculate_file_hash(target_path, show_progress=False)
                                
                                if post_copy_hash != expected_hash:
                                    error_log(f"⚠ DRIVE ISSUE DETECTED: File corrupted after copy to target drive!")
                                    error_log(f"  File was verified correct in temp folder but corrupted after copying.")
                                    error_log(f"  This indicates your target drive may have bad sectors or write errors.")
                                    error_log(f"  Consider running disk check (chkdsk) or moving models to a different drive.")
                                    
                                    if not corrupted_file_exists:
                                        corrupted_file_exists = True
                                        msg_log(f"Keeping corrupted file to force write to different sectors on retry...")
                                    else:
                                        if target_path.exists():
                                            target_path.unlink()
                                    
                                    if copy_attempt < max_copy_attempts - 1:
                                        msg_log(f"Retrying copy (attempt {copy_attempt + 2}/{max_copy_attempts})...")
                                    continue  # Retry copy
                                
                                verified_hash = post_copy_hash
                            
                            # If we used a temp name, rename to final name
                            if corrupted_file_exists:
                                if final_path.exists():
                                    final_path.unlink()
                                target_path.rename(final_path)
                                msg_log(f"✓ Renamed to final filename after successful verification")
                            
                            copy_success = True
                            break
                            
                        except Exception as e:
                            error_log(f"Copy error (attempt {copy_attempt + 1}/{max_copy_attempts}): {e}")
                            if corrupted_file_exists:
                                temp_final_path = final_path.parent / f"{final_path.name}.new"
                                if temp_final_path.exists():
                                    try:
                                        temp_final_path.unlink()
                                    except:
                                        pass
                    
                    # Clean up after copy attempts
                    if copy_success:
                        try:
                            if downloaded_file.exists():
                                downloaded_file.unlink()
                        except:
                            pass
                    else:
                        error_log(f"All {max_copy_attempts} copy attempts failed for {filename}")
                        # Clean up any leftover files
                        if final_path.exists():
                            try:
                                final_path.unlink()
                            except:
                                pass
                        temp_final_path = final_path.parent / f"{final_path.name}.new"
                        if temp_final_path.exists():
                            try:
                                temp_final_path.unlink()
                            except:
                                pass
                        if downloaded_file.exists():
                            downloaded_file.unlink()
                        continue  # Retry download
                
                # Save hash file only if we have a verified hash
                if verified_hash:
                    try:
                        sha_file = final_path.parent / f"{final_path.name}.sha256"
                        sha_file.write_text(verified_hash)
                        debug_log(f"Saved hash file: {sha_file.name}")
                    except Exception as e:
                        warning_log(f"Could not cache hash: {e}")
                
                msg_log(f"✓ Successfully re-downloaded and verified {filename}")
                success_count += 1
                file_success = True
                break
                
            except Exception as e:
                error_log(f"\u2717 Error re-downloading {filename} (attempt {attempt + 1}/{max_attempts}): {e}")
                # Clean up failed download if downloading directly
                if not use_temp_folder and final_path.exists():
                    try:
                        final_path.unlink()
                    except Exception:
                        pass
            finally:
                # Clean up temp directory
                if temp_dir and Path(temp_dir).exists():
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception:
                        pass
        
        if not file_success:
            failed_files.append(filename)
    
    if failed_files:
        error_log(f"Failed to re-download {len(failed_files)} file(s): {', '.join(failed_files)}")
        return False
    
    msg_log(f"✓ Successfully re-downloaded {success_count} corrupted file(s)")
    return True


def extract_repo_id_from_url(repo_id: str) -> str:
    # Extract actual repo_id (namespace/repo_name) from a HuggingFace URL.
    #
    # Args:
    #     repo_id: Either a direct repo_id like "user/repo" or a full HuggingFace URL
    #
    # Returns:
    #     Extracted repo_id in format "user/repo", or original string if not a URL
    #
    # Examples:
    #     "bartowski/model" -> "bartowski/model"
    #     "https://huggingface.co/user/repo/resolve/main/file.gguf" -> "user/repo"
    if not repo_id:
        return ""
    
    # If it's a URL, extract the repo_id part
    if repo_id.startswith("http") and "huggingface.co" in repo_id:
        parts = repo_id.split('/')
        if len(parts) >= 5:
            # URL format: https://huggingface.co/USER/REPO/resolve/main/file
            return f"{parts[3]}/{parts[4]}"
    
    # Already in correct format or not a URL
    return repo_id


# ============================================================================
# Model Discovery Functions (v2 workflow)
# ============================================================================

def _verify_fp8_tensors(model_path: Path) -> bool:
    # Verify a model folder actually contains FP8 quantized tensors.
    #
    # Checks safetensors files for float8_e4m3fn dtype or FP8 scale patterns.
    # This is used to distinguish true FP8 models from models that were
    # converted/dequantized to BF16 but still have FP8 in their config.
    #
    # Args:
    #     model_path: Path to model folder
    #
    # Returns:
    #     True if actual FP8 tensors are found
    try:
        from safetensors import safe_open
        
        sf_files = list(model_path.glob("*.safetensors"))
        if not sf_files:
            return False
        
        # Check first safetensors file
        with safe_open(str(sf_files[0]), framework="pt") as f:
            # Check a few weight tensors for FP8 dtype
            for key in list(f.keys())[:20]:
                if "weight" in key.lower() and "scale" not in key.lower():
                    tensor = f.get_tensor(key)
                    dtype_str = str(tensor.dtype).lower()
                    if "float8" in dtype_str or "e4m3" in dtype_str or "e5m2" in dtype_str:
                        return True
            
            # Also check for FP8 scale tensors (weight_scale_inv, activation_scale)
            tensor_keys = list(f.keys())
            has_fp8_scales = any("weight_scale" in k.lower() or "scale_inv" in k.lower() for k in tensor_keys)
            if has_fp8_scales:
                return True
                
    except Exception:
        pass
    
    return False


def detect_prequantized_model(model_path: Path) -> tuple[bool, str]:
    # Check if a model is pre-quantized by inspecting config.json and safetensors.
    #
    # Detects: AWQ, GPTQ, BitsAndBytes (BNB), FP8, GGML/GGUF markers.
    # Also checks actual tensor dtypes in safetensors to verify FP8 vs BF16.
    #
    # Args:
    #     model_path: Path to model folder or GGUF file
    #
    # Returns:
    #     Tuple of (is_quantized: bool, quant_type: str)
    #     quant_type is one of: "awq", "gptq", "bnb", "fp8", "gguf", "unknown", ""
    import json
    
    model_path = Path(model_path)
    
    # GGUF files are always pre-quantized
    if model_path.is_file() and model_path.suffix.lower() == ".gguf":
        return True, "gguf"
    
    if not model_path.is_dir():
        return False, ""
    
    # Check config.json for quantization_config
    config_file = model_path / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
            if "quantization_config" in config:
                quant_config = config["quantization_config"]
                quant_method = quant_config.get("quant_method", "").lower()
                
                # AWQ
                if quant_method == "awq":
                    return True, "awq"
                
                # GPTQ
                if quant_method == "gptq":
                    return True, "gptq"
                
                # BitsAndBytes
                if quant_method in ["bitsandbytes", "bnb"] or quant_config.get("load_in_4bit") or quant_config.get("load_in_8bit"):
                    return True, "bnb"
                
                # FP8 (various indicators in config)
                if quant_method == "fp8" or "activation_scheme" in quant_config:
                    # Double-check: verify safetensors actually contain FP8 tensors
                    # Some models may have config from FP8 but weights converted to BF16
                    if _verify_fp8_tensors(model_path):
                        return True, "fp8"
                    # Config says FP8 but no FP8 tensors found - not actually quantized
                    # (model was likely converted/dequantized to BF16)                 
                # Unknown quantization config present
                if quant_method:
                    return True, quant_method
                    
        except Exception:
            pass
    
    # Check params.json (Mistral native format)
    params_file = model_path / "params.json"
    if params_file.exists():
        try:
            params = json.loads(params_file.read_text())
            if "quantization" in params:
                qformat = params["quantization"].get("qformat_weight", "")
                if "fp8" in qformat.lower():
                    return True, "fp8"
                if qformat:
                    return True, qformat.lower()
        except Exception:
            pass
    
    # Fallback: check filename markers (less reliable but catches edge cases)
    model_name_lower = model_path.name.lower()
    
    # Standard quantization format markers
    quant_markers = {
        "awq": ["-awq", "_awq", ".awq"],
        "gptq": ["-gptq", "_gptq", ".gptq"],
        "bnb": ["-bnb", "_bnb"],
        "fp8": ["-fp8", "_fp8"],
        "int8": ["-int8", "_int8"],
        "int4": ["-int4", "_int4"],
    }
    for quant_type, markers in quant_markers.items():
        if any(m in model_name_lower for m in markers):
            return True, quant_type
    
    # GGUF quantization markers (Q4_K_M, Q5_K_S, Q8_0, etc.)
    # These appear in GGUF filenames and folder names
    gguf_quant_markers = [
        "_q4_", "_q5_", "_q6_", "_q8_",  # underscore style
        "-q4-", "-q5-", "-q6-", "-q8-",  # dash style
        "_k_m", "_k_s", "_k_l",          # quality suffixes (K_M, K_S, K_L)
        "q4_k", "q5_k", "q6_k", "q8_0",  # full quant names
        ".q4_", ".q5_", ".q6_", ".q8_",  # dot prefix style
        "_iq4", "_iq3", "_iq2",          # imatrix quants
    ]
    if any(m in model_name_lower for m in gguf_quant_markers):
        return True, "gguf"
    
    return False, ""


def detect_fp8_model(model_path: Path) -> bool:
    # Check if a model folder contains FP8 quantized weights.
    #
    # Checks:
    # 1. params.json for quantization.qformat_weight containing "fp8"
    # 2. config.json for quantization_config with FP8 indicators
    # 3. Safetensors files for float8_e4m3fn dtype tensors
    #
    # Args:
    #     model_path: Path to model folder
    #
    # Returns:
    #     True if model uses FP8 quantization
    import json
    
    # Check params.json (Mistral native format)
    params_file = model_path / "params.json"
    if params_file.exists():
        try:
            params = json.loads(params_file.read_text())
            if "quantization" in params:
                qformat = params["quantization"].get("qformat_weight", "")
                if "fp8" in qformat.lower():
                    return True
        except:
            pass
    
    # Check config.json for quantization_config
    config_file = model_path / "config.json"
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
            if "quantization_config" in config:
                quant_config = config["quantization_config"]
                quant_method = quant_config.get("quant_method", "")
                # FP8 indicators
                if quant_method == "fp8" or "activation_scheme" in quant_config:
                    return True
        except:
            pass
    
    # Check safetensors metadata for tensor dtype info
    # Use metadata check instead of loading tensors (much faster)
    try:
        import safetensors
        sf_files = list(model_path.glob("*.safetensors"))
        if sf_files:
            # Read file metadata without loading tensors
            with safetensors.safe_open(str(sf_files[0]), framework="pt") as f:
                metadata = f.metadata()
                # Some models include dtype info in metadata
                if metadata:
                    format_str = str(metadata).lower()
                    if "float8" in format_str or "fp8" in format_str or "e4m3" in format_str:
                        return True
                
                # Fallback: check tensor names for FP8 scale patterns
                # FP8 models typically have weight_scale or scale_inv tensors
                tensor_keys = list(f.keys())
                has_fp8_scales = any("scale" in k.lower() for k in tensor_keys[:50])
                if has_fp8_scales and any("weight" in k.lower() and "scale" in k.lower() for k in tensor_keys[:50]):
                    return True
    except:
        pass
    
    return False


def discover_models_in_folder(folder_path: Path = None) -> List[dict]:
    # Scan LLM folder and discover all models with their detected families.
    #
    # Args:
    #     folder_path: Optional path to scan (defaults to models/LLM)
    #
    # Returns:
    #     List of dicts with keys: name, path, family, is_gguf, is_folder, is_fp8
    try:
        from .smartlm_types import get_model_family_from_name
        
        if folder_path is None:
            folder_path = get_llm_models_path()
        
        if not folder_path.exists():
            return []
        
        models = []
        model_extensions = {'.safetensors', '.gguf', '.bin', '.pt'}
        
        def scan_dir(base_path: Path, relative_path: str = ""):
            # Recursively scan for models.
            try:
                for item in base_path.iterdir():
                    if item.is_file() and item.suffix in model_extensions:
                        # Skip mmproj files
                        if 'mmproj' in item.name.lower():
                            continue
                        
                        file_path = f"{relative_path}/{item.name}" if relative_path else item.name
                        family = get_model_family_from_name(item.name)
                        
                        models.append({
                            "name": file_path,
                            "path": str(item),
                            "family": family.value,
                            "is_gguf": item.suffix == '.gguf',
                            "is_folder": False,
                            "is_fp8": False,  # Single files are not FP8 (GGUF has own quant)
                        })
                    elif item.is_dir():
                        # Check if this is a model folder (has config.json or model files)
                        has_config = (item / "config.json").exists()
                        has_safetensors = any(item.glob("*.safetensors"))
                        has_gguf = list(item.glob("*.gguf"))
                        has_model_files = any(
                            (item / f).exists() for f in ["model.safetensors", "pytorch_model.bin"]
                        ) or has_safetensors or has_gguf
                        
                        if has_config or has_model_files:
                            folder_name = f"{relative_path}/{item.name}/" if relative_path else f"{item.name}/"
                            # Pass full path so config.json can be read for family detection
                            family = get_model_family_from_name(str(item))
                            
                            # Check for FP8 quantization
                            is_fp8 = detect_fp8_model(item)
                            
                            # Add folder entry for non-GGUF models (safetensors, bin, etc.)
                            # Only add folder if there are non-GGUF model files
                            non_gguf_models = has_safetensors or any(
                                (item / f).exists() for f in ["model.safetensors", "pytorch_model.bin"]
                            )
                            if non_gguf_models:
                                models.append({
                                    "name": folder_name,
                                    "path": str(item),
                                    "family": family.value,
                                    "is_gguf": False,
                                    "is_folder": True,
                                    "is_fp8": is_fp8,
                                })
                            
                            # ALWAYS list individual GGUF files (even if folder has config.json)
                            # This allows users to select specific quantization variants
                            for gguf_file in has_gguf:
                                # Skip mmproj files
                                if 'mmproj' in gguf_file.name.lower():
                                    continue
                                gguf_path = f"{relative_path}/{item.name}/{gguf_file.name}" if relative_path else f"{item.name}/{gguf_file.name}"
                                gguf_family = get_model_family_from_name(gguf_file.name)
                                models.append({
                                    "name": gguf_path,
                                    "path": str(gguf_file),
                                    "family": gguf_family.value,
                                    "is_gguf": True,
                                    "is_folder": False,
                                    "is_fp8": False,
                                })
                        else:
                            # Recurse into subdirectory
                            item_rel = f"{relative_path}/{item.name}" if relative_path else item.name
                            if relative_path.count('/') < 4:
                                scan_dir(item, item_rel)
            except PermissionError:
                pass
        
        scan_dir(folder_path)
        return sorted(models, key=lambda x: x["name"])
    
    except Exception as e:
        error_log(f"Error discovering models: {e}")
        return []


def filter_models_by_family_and_method(
    models: List[dict],
    family: str,
    loading_method: str
) -> List[str]:
    # Filter discovered models by family and loading method.
    #
    # FP8 models are excluded from Transformers loading method since they
    # use Mistral's proprietary format that is incompatible with HuggingFace.
    # FP8 models can be used with vLLM (Docker) which has native FP8 support.
    #
    # Args:
    #     models: List from discover_models_in_folder()
    #     family: Model family name (e.g., "Qwen", "Mistral")
    #     loading_method: Loading method (e.g., "GGUF (llama-cpp-python)", "Transformers")
    #
    # Returns:
    #     List of model names matching the criteria
    filtered = []
    
    for model in models:
        # Match family
        if model["family"] != family:
            continue
        
        # Match loading method
        if loading_method == "GGUF (llama-cpp-python)":
            if model["is_gguf"]:
                filtered.append(model["name"])
        elif loading_method == "Transformers":
            # Transformers: exclude GGUF and FP8 models
            # FP8 models use Mistral's proprietary format that is incompatible
            if not model["is_gguf"] and not model.get("is_fp8", False):
                filtered.append(model["name"])
        else:
            # vLLM (Docker) can handle FP8 models natively
            if not model["is_gguf"]:
                filtered.append(model["name"])
    
    return filtered


# ============================================================================
# Model Download Functions (shared between v1 and v2)
# ============================================================================

def ensure_mmproj_path(
    template_info: dict,
    model_folder: str,
    template_name: str = None,
) -> str | None:
    # Ensure mmproj file exists locally, downloading if needed.
    #
    # This function handles the separation between:
    # - mmproj_path: Local file path (relative to LLM folder) - for loading and dropdown selection
    # - mmproj_url: URL for downloading - used when local file doesn't exist
    #
    # Search order when mmproj_path is empty:
    # 1. Check if expected target file exists (derived from URL)
    # 2. Search for any .mmproj.gguf file in model folder
    # 3. Download from URL if not found
    #
    # After resolving/downloading, updates the template's mmproj_path with the local path.
    #
    # Args:
    #     template_info: Template dict with mmproj_path (local) and mmproj_url (for download)
    #     model_folder: Folder to download mmproj into (usually model folder)
    #     template_name: Optional template name for updating after download
    #
    # Returns:
    #     Absolute path to mmproj file, or None if not available
    import re
    import folder_paths
    
    mmproj_path = template_info.get("mmproj_path", "")
    mmproj_url = template_info.get("mmproj_url", "")
    
    # Skip if neither path nor URL is provided
    if not mmproj_path and not mmproj_url:
        return None
    
    llm_dir = get_llm_models_path()
    model_folder_path = Path(model_folder)
    
    # Helper to update template with resolved local path
    def _update_template_mmproj_path(resolved_path: Path):
        if not template_name:
            return
        try:
            relative_path = resolved_path.relative_to(llm_dir).as_posix()
        except ValueError:
            relative_path = resolved_path.name
        update_template_settings(template_name, {"mmproj_path": relative_path})
    
    # Case 1: mmproj_path is a local path (not URL) - check if it exists
    if mmproj_path and not mmproj_path.startswith("http"):
        # Resolve to absolute path
        if '/' in mmproj_path or '\\' in mmproj_path:
            local_file = llm_dir / mmproj_path
        else:
            local_file = model_folder_path / mmproj_path
        
        if local_file.exists():
            # Update template to ensure path is saved
            _update_template_mmproj_path(local_file)
            return str(local_file)
        # Local path specified but file doesn't exist - fall through to search/download
    
    # Case 2: mmproj_path is empty or file not found - search for existing mmproj files
    # Search in model folder for any file with 'mmproj' in the name (broader pattern)
    if model_folder_path.exists():
        # Broader search: any .gguf file with 'mmproj' in the name
        # This catches patterns like: model.mmproj-Q8_0.gguf, model.mmproj.gguf, mmproj-fp16.gguf
        all_gguf = list(model_folder_path.glob("*.gguf"))
        mmproj_files = [f for f in all_gguf if 'mmproj' in f.name.lower()]
        if mmproj_files:
            found_file = mmproj_files[0]
            msg_log(f"✓ Found existing mmproj: {found_file.name}")
            _update_template_mmproj_path(found_file)
            return str(found_file)
    
    # Case 3: Need to download from URL
    if not mmproj_url:
        if mmproj_path:
            warning_log(f"mmproj_path specified but file not found and no mmproj_url: {mmproj_path}")
        return None
    
    # Determine target filename and path from URL
    original_filename = mmproj_url.split('/')[-1]
    
    # Preserve precision info (fp16, bf16, f16, etc.) when renaming
    precision_match = re.search(r'(fp16|bf16|f16|f32)', original_filename.lower())
    precision_suffix = f"-{precision_match.group(1)}" if precision_match else ""
    
    model_base = model_folder_path.name
    target_filename = f"{model_base}{precision_suffix}.mmproj.gguf"
    target = model_folder_path / target_filename
    
    # Check if target already exists (may have been downloaded previously with expected name)
    if target.exists():
        _update_template_mmproj_path(target)
        return str(target)
    
    # Also check for original filename (user might have downloaded manually)
    original_target = model_folder_path / original_filename
    if original_target.exists():
        msg_log(f"✓ Found mmproj with original filename: {original_filename}")
        _update_template_mmproj_path(original_target)
        return str(original_target)
    
    # Download from URL
    msg_log(f"Downloading MMProj from {mmproj_url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    
    parts = mmproj_url.split('/')
    if 'huggingface.co' in mmproj_url and len(parts) >= 6:
        download_with_progress(mmproj_url, str(target), target_filename)
        msg_log(f"✓ MMProj downloaded as {target_filename}")
        
        # Verify integrity
        if target.exists():
            if not verify_model_integrity(target, extract_repo_id_from_url(mmproj_url), original_filename):
                warning_log(f"MMProj verification failed for {target_filename}")
            
            # Update template with local path
            _update_template_mmproj_path(target)
            return str(target)
    else:
        warning_log(f"Invalid mmproj_url format: {mmproj_url}")
    
    return None


def ensure_model_path(
    template_info: dict,
    template_name: str,
) -> tuple:
    # Download model if needed and return (model_path, model_folder_path, repo_id).
    #
    # This is the unified model download function used by both v1 and v2.
    # Supports automatic retry on hash verification failure (configurable via retry_download_attempts).
    #
    # Args:
    #     template_info: Template dict with local_path, repo_id, model_type
    #     template_name: Template name for updating after download
    #
    # Returns:
    #     Tuple of (model_path, model_folder_path, repo_id)
    #
    # Raises:
    #     ValueError: If template is invalid or path not found
    #     RuntimeError: If model verification fails after all retries
    import shutil
    from .smartlm_types import detect_model_type, ModelType
    
    local_path = template_info.get("local_path")
    repo_id = template_info.get("repo_id")
    
    is_direct_url = repo_id and (repo_id.startswith("http://") or repo_id.startswith("https://"))
    
    if not repo_id and not local_path:
        raise ValueError(f"Template '{template_name}' missing repo_id or local_path")
    
    model_type = detect_model_type(template_info)
    models_base = get_llm_models_path()
    
    # Get retry attempts from config (default 2)
    max_retries = get_config_value("retry_download_attempts", 2)
    
    # For Florence2 models, also check the models/florence2/ folder (used by comfyui-florence2 node)
    import folder_paths
    florence2_base = Path(folder_paths.models_dir) / "florence2"
    # For QwenVL models, also check the models/llm/Qwen-VL/ folder (used by other ComfyUI nodes)
    qwenvl_base = models_base / "Qwen-VL"
    
    target = None
    
    # Construct target path
    if local_path:
        if local_path.lower().endswith(".gguf"):
            if '/' in local_path or '\\' in local_path:
                target = models_base / local_path
            else:
                model_name = Path(local_path).stem
                # Download GGUF files directly to models/llm/model_name/ (not Qwen-VL subfolder)
                target = models_base / model_name / Path(local_path).name
                
                # But also check Qwen-VL folder for existing models (backward compatibility)
                if not target.exists() and (model_type == ModelType.QWENVL or "qwen" in local_path.lower()):
                    qwenvl_target = qwenvl_base / model_name / Path(local_path).name
                    if qwenvl_target.exists():
                        target = qwenvl_target
                        msg_log(f"✓ Found QwenVL model in Qwen-VL folder: {model_name}")
        else:
            # Check if local_path starts with a known subfolder of models_dir (e.g., "florence2/")
            # This handles paths like "florence2/base-PromptGen-v1.5/"
            local_path_parts = local_path.replace('\\', '/').split('/')
            models_dir = Path(folder_paths.models_dir)
            
            if local_path_parts and (models_dir / local_path_parts[0]).exists():
                # Path is relative to models_dir (e.g., "florence2/model_name/")
                target = models_dir / local_path
            else:
                # Path is relative to LLM folder (models_base)
                target = models_base / local_path
            
            # For Florence2 models, check the florence2 folder if not found in LLM folder
            if not target.exists() and model_type == ModelType.FLORENCE2 and florence2_base.exists():
                # Extract just the model name from local_path (remove any folder prefix)
                local_path_clean = local_path.replace('\\', '/').rstrip('/')
                model_folder_name = local_path_clean.split('/')[-1]  # Get last component
                
                # Try exact match first
                florence2_target = florence2_base / model_folder_name
                if florence2_target.exists():
                    target = florence2_target
                    msg_log(f"✓ Found Florence2 model in models/florence2/: {model_folder_name}")
                else:
                    # Try alternative names (remove Florence-2- prefix)
                    alt_names = []
                    if model_folder_name.startswith("Florence-2-"):
                        alt_names.append(model_folder_name[len("Florence-2-"):])
                    if model_folder_name.startswith("Florence-2.1-"):
                        alt_names.append(model_folder_name[len("Florence-2.1-"):])
                    
                    for alt_name in alt_names:
                        alt_target = florence2_base / alt_name
                        if alt_target.exists():
                            target = alt_target
                            msg_log(f"✓ Found Florence2 model in models/florence2/: {alt_name}")
                            break
        
        # Search for GGUF files if not found
        if not target.exists() and local_path.lower().endswith('.gguf'):
            filename = Path(local_path).name
            msg_log(f"Searching for GGUF file: {filename}...")
            found_path = search_model_file(filename, models_base)
            if found_path:
                target = found_path
                msg_log(f"✓ Found at {target}")
    else:
        model_name = repo_id.split("/")[-1]
        if is_direct_url and model_name.lower().endswith(".gguf"):
            filename = model_name
            folder_name = Path(filename).stem
            # Download GGUF files directly to models/llm/folder_name/ (not Qwen-VL subfolder)
            target = models_base / folder_name / filename
            
            # Search for existing file (including in Qwen-VL subfolder for backward compatibility)
            if not target.exists():
                msg_log(f"Searching for GGUF file: {filename}...")
                found_path = search_model_file(filename, models_base)
                if found_path:
                    target = found_path
                    msg_log(f"✓ Found at {target}")
        elif model_type == ModelType.QWENVL:
            # Download new QwenVL models directly to models/llm/ (not Qwen-VL subfolder)
            target = models_base / model_name
            # But check Qwen-VL folder for existing models (backward compatibility with other ComfyUI nodes)
            if not target.exists() and qwenvl_base.exists():
                qwenvl_target = qwenvl_base / model_name
                if qwenvl_target.exists():
                    target = qwenvl_target
                    msg_log(f"✓ Found QwenVL model in Qwen-VL folder: {model_name}")
        elif model_type == ModelType.FLORENCE2:
            # Florence2: check both LLM folder and florence2 folder
            target = models_base / model_name
            if not target.exists() and florence2_base.exists():
                # Try exact match first
                florence2_target = florence2_base / model_name
                if florence2_target.exists():
                    target = florence2_target
                    msg_log(f"✓ Found Florence2 model in models/florence2/: {model_name}")
                else:
                    # Some models use shorter folder names (e.g., "base-PromptGen-v2.0" instead of "Florence-2-base-PromptGen-v2.0")
                    # Try removing common prefixes
                    alt_names = []
                    if model_name.startswith("Florence-2-"):
                        alt_names.append(model_name[len("Florence-2-"):])  # Remove "Florence-2-" prefix
                    if model_name.startswith("Florence-2.1-"):
                        alt_names.append(model_name[len("Florence-2.1-"):])
                    
                    for alt_name in alt_names:
                        alt_target = florence2_base / alt_name
                        if alt_target.exists():
                            target = alt_target
                            msg_log(f"✓ Found Florence2 model in models/florence2/: {alt_name}")
                            break
        else:
            target = models_base / model_name
    
    def _delete_corrupted_files(path: Path, specific_files: List[Path] = None):
        # Delete corrupted model files for re-download.
        #
        # Args:
        #     path: Model directory or file path (used as fallback)
        #     specific_files: If provided, only delete these specific files instead of entire folder
        try:
            if specific_files:
                # Delete only the specific corrupted files
                for file_path in specific_files:
                    if file_path.exists():
                        file_path.unlink()
                        msg_log(f"Deleted corrupted file: {file_path.name}")
                    # Also delete any .sha256 hash file
                    sha_file = file_path.parent / f"{file_path.name}.sha256"
                    if sha_file.exists():
                        sha_file.unlink()
            elif path.is_dir():
                # Delete the entire model folder (fallback for full re-download)
                shutil.rmtree(path)
                msg_log(f"Deleted corrupted folder: {path}")
            elif path.is_file():
                # Delete the single file
                path.unlink()
                msg_log(f"Deleted corrupted file: {path}")
                # Also delete any .sha256 hash file
                sha_file = path.parent / f"{path.name}.sha256"
                if sha_file.exists():
                    sha_file.unlink()
        except Exception as e:
            error_log(f"Failed to delete corrupted files: {e}")
    
    def _download_model(target_path: Path) -> bool:
        # Perform the actual download. Returns True if downloaded.
        # Get HF token from environment or config for faster downloads
        # Priority: HF_TOKEN env > HUGGING_FACE_HUB_TOKEN env > config
        import os
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if not hf_token:
            config_token = get_config_value("hf_token", "")
            if config_token and config_token.strip():
                hf_token = config_token.strip()
        
        if is_direct_url:
            msg_log(f"Downloading from {repo_id}")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            parts = repo_id.split('/')
            if 'huggingface.co' in repo_id and len(parts) >= 6:
                filename = parts[-1]
                
                # Get expected hash from HuggingFace for verification
                hf_repo_id = extract_repo_id_from_url(repo_id)
                expected_hash = get_hf_file_hash(hf_repo_id, filename) if hf_repo_id else None
                
                # Use temp folder approach for more reliable downloads
                if download_file_via_temp(repo_id, target_path, filename, expected_hash):
                    msg_log(f"✓ Downloaded to {target_path}")
                    return True
                else:
                    raise RuntimeError(f"Failed to download {filename} after multiple attempts")
            else:
                raise ValueError(f"Invalid URL format: {repo_id}")
        elif repo_id:
            msg_log(f"Downloading {repo_id} to {target_path}")
            from huggingface_hub import snapshot_download
            
            download_kwargs = {
                "repo_id": repo_id,
                "local_dir": str(target_path),
                "local_dir_use_symlinks": False,
                "ignore_patterns": ["*.md", ".git*"],
            }
            
            # Add token if available for faster authenticated downloads
            if hf_token:
                download_kwargs["token"] = hf_token
                debug_log("Using HF token for authenticated download")
            
            snapshot_download(**download_kwargs)
            return True
        else:
            raise ValueError(f"Template '{template_name}' path not found: {target_path}")
    
    def _get_hf_token() -> str:
        # Get HuggingFace token from environment or config.
        import os
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if not hf_token:
            config_token = get_config_value("hf_token", "")
            if config_token and config_token.strip():
                hf_token = config_token.strip()
        return hf_token
    
    # Download with retry logic
    downloaded = False
    verification_failed = False
    last_corrupted_files = []  # Track corrupted files for selective re-download
    
    for attempt in range(max_retries + 1):  # +1 because first attempt is not a "retry"
        # Download if target doesn't exist
        if not target.exists():
            try:
                downloaded = _download_model(target)
            except Exception as e:
                # Download threw an exception - check if partial files were created
                if target.exists():
                    warning_log(f"Download failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    # Check if download is incomplete and delete partial files
                    is_complete, missing = check_model_completeness(target, extract_repo_id_from_url(repo_id) if repo_id else None)
                    if not is_complete:
                        warning_log(f"Incomplete download detected ({len(missing)} files missing), cleaning up...")
                        _delete_corrupted_files(target)  # Delete entire folder for clean retry
                    if attempt < max_retries:
                        continue
                    raise
                else:
                    if attempt < max_retries:
                        warning_log(f"Download failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                        continue
                    raise
        elif target.exists() and not downloaded:
            # Target exists but wasn't downloaded in this session - verify completeness
            is_complete, missing = check_model_completeness(target, extract_repo_id_from_url(repo_id) if repo_id else None)
            if not is_complete and missing:
                msg_log(f"Existing model folder is incomplete: {len(missing)} file(s) missing")
                hf_token = _get_hf_token()
                clean_repo_id = extract_repo_id_from_url(repo_id) if repo_id else None
                if clean_repo_id and download_missing_files(target, missing, clean_repo_id, hf_token):
                    downloaded = True  # Mark as downloaded for verification
                else:
                    warning_log("Could not download missing files")
                    if attempt < max_retries:
                        _delete_corrupted_files(target)
                        continue
                    raise RuntimeError(f"Model incomplete and could not download missing files: {', '.join(missing)}")
            else:
                # Model is complete, no need to download
                downloaded = True  # Trigger verification
        
        # Verify integrity after download
        if downloaded and target.exists():
            # Use return_details=True to get list of corrupted files
            verification_result = verify_model_integrity(target, extract_repo_id_from_url(repo_id), return_details=True)
            
            if verification_result.success:
                # Verification passed
                verification_failed = False
                break
            else:
                # Verification failed
                verification_failed = True
                last_corrupted_files = verification_result.corrupted_files
                
                if attempt < max_retries:
                    # Try selective re-download of only corrupted files (if we have a valid repo_id)
                    clean_repo_id = extract_repo_id_from_url(repo_id)
                    
                    if last_corrupted_files and clean_repo_id and not is_direct_url:
                        # Selective re-download: only re-download corrupted files
                        msg_log(f"⚠ {len(last_corrupted_files)} file(s) failed verification (attempt {attempt + 1}/{max_retries + 1})")
                        msg_log(f"Attempting selective re-download of corrupted files only...")
                        
                        hf_token = _get_hf_token()
                        if redownload_corrupted_files(last_corrupted_files, clean_repo_id, target, hf_token):
                            # Files were re-downloaded, continue to next verification attempt
                            # Don't set downloaded=False since the folder still exists
                            continue
                        else:
                            # Selective re-download failed, fall back to full re-download
                            warning_log("Selective re-download failed, falling back to full re-download...")
                            _delete_corrupted_files(target)
                            downloaded = False
                    else:
                        # No repo_id or direct URL - delete and re-download everything
                        warning_log(f"⚠ Hash verification failed (attempt {attempt + 1}/{max_retries + 1}), will retry download...")
                        _delete_corrupted_files(target)
                        downloaded = False  # Reset to trigger re-download
                else:
                    error_log(f"✗ Hash verification failed after {max_retries + 1} attempts")
                    # Delete corrupted files so next restart will trigger fresh download
                    if last_corrupted_files:
                        msg_log("Deleting corrupted files to allow fresh download on restart...")
                        _delete_corrupted_files(target, last_corrupted_files)
        else:
            # downloaded is False and target doesn't exist - shouldn't happen, but break to avoid infinite loop
            if not target.exists():
                raise RuntimeError(f"Model download failed: target does not exist after download attempt: {target}")
            # Target exists but downloaded is False - this means completeness check didn't trigger download
            # This is a valid state for pre-existing complete models that don't need verification
            break
    
    # Final check - raise error if verification still failed
    if verification_failed:
        corrupted_names = [f.name for f in last_corrupted_files] if last_corrupted_files else []
        raise RuntimeError(
            f"Model verification failed for {target} after {max_retries + 1} attempts.\n"
            f"Corrupted files: {', '.join(corrupted_names) if corrupted_names else 'unknown'}\n"
            f"The download may be corrupted. Please check your network connection and try again."
        )
    
    # Update template with local path
    # Prefer relative path to LLM folder, but also support models in other locations (e.g., models/florence2/)
    current_local_path = None
    
    # First try: relative to LLM folder (models_base)
    try:
        relative_path = target.relative_to(models_base)
        current_local_path = relative_path.as_posix()
        if target.is_dir() and not current_local_path.endswith('/'):
            current_local_path += '/'
    except ValueError:
        pass
    
    # Second try: relative to ComfyUI models folder (e.g., "florence2/model_name/")
    if current_local_path is None:
        try:
            relative_path = target.relative_to(Path(folder_paths.models_dir))
            current_local_path = relative_path.as_posix()
            if target.is_dir() and not current_local_path.endswith('/'):
                current_local_path += '/'
        except ValueError:
            # Model is not under models_dir - don't update local_path
            pass
    
    if current_local_path and template_name and (not local_path or local_path != current_local_path):
        update_template_settings(template_name, {"local_path": current_local_path})
    
    return (str(target), str(target.parent), repo_id or "")
