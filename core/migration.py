# Migration module for ComfyUI_Eclipse.
#
# Handles:
# - Extracting .example files with smart update support (hash-based)
# - Migrating user data from old models/Eclipse/ folder to repo
# - Migrating ancient pre-Eclipse folder structures
# - Creating wildcards junction/symlink for wildcard integration

import os
import json
import hashlib
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict

from .logger import log

_LOG_PREFIX = "Migration"
_MIGRATED_MARKER = ".migrated"
_MANIFEST_FILE = ".manifest.json"


# ============================================================================
# File hashing
# ============================================================================

def _file_hash(path: str) -> str:
    # Compute SHA-256 hash of a file's contents.
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


# ============================================================================
# Manifest (hash tracking for smart updates)
# ============================================================================

def _load_manifest(defaults_dir: str) -> Dict[str, str]:
    # Load the manifest that tracks which .example hash was last extracted.
    # Returns dict mapping relative path (without .example) → hash string.
    manifest_path = os.path.join(defaults_dir, _MANIFEST_FILE)
    if not os.path.isfile(manifest_path):
        return {}
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_manifest(defaults_dir: str, manifest: Dict[str, str]) -> None:
    # Save the manifest file. Entries are sorted for stable diffs.
    manifest_path = os.path.join(defaults_dir, _MANIFEST_FILE)
    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
    except OSError as e:
        log.warning(_LOG_PREFIX, f"Could not save manifest: {e}")


# ============================================================================
# .example file extraction (with smart update support)
# ============================================================================

def extract_all_example_files(repo_root: str) -> int:
    # Extract .example files from root .defaults/ folder to their repo locations.
    # The .defaults/ folder mirrors the repo structure:
    #   .defaults/config.json.example        → config.json
    #   .defaults/templates/*.json.example    → templates/*.json
    #   .defaults/patterns/*.json.example     → patterns/*.json
    #   .defaults/prompts/**/*.txt.example    → prompts/**/*.txt
    #   .defaults/styles/*.csv.example        → styles/*.csv
    #   .defaults/wildcards/*.txt.example     → wildcards/*.txt
    #
    # Smart update behavior:
    #   - New files (target doesn't exist) → extract and record hash
    #   - Updated .example (hash changed) + unmodified target → auto-update
    #   - Updated .example + user-modified target → skip (preserve edits)
    #   - Unchanged .example → skip
    #
    # Args:
    #     repo_root: Path to the ComfyUI_Eclipse repo root
    #
    # Returns:
    #     Total number of files extracted or updated
    defaults_path = os.path.join(repo_root, '.defaults')
    if not os.path.isdir(defaults_path):
        return 0

    _hide_on_windows(defaults_path)
    extracted, updated = _extract_defaults_dir(defaults_path, repo_root)
    if extracted > 0:
        log.msg(_LOG_PREFIX, f"Extracted {extracted} new default file(s)")
    if updated > 0:
        log.msg(_LOG_PREFIX, f"Updated {updated} default file(s) (unmodified by user)")
    return extracted + updated


def _hide_on_windows(path: str) -> None:
    # Set the Windows hidden attribute on a file/folder.
    # No-op on Linux/macOS (dot-prefix already hides it).
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        FILE_ATTRIBUTE_HIDDEN = 0x02
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs != -1 and not (attrs & FILE_ATTRIBUTE_HIDDEN):
            ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs | FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass


def _extract_defaults_dir(defaults_dir: str, output_dir: str) -> tuple:
    # Extract and smart-update .example files from a .defaults/ directory.
    # Walks recursively, preserving subdirectory structure.
    # Strips the .example suffix to create the usable file.
    #
    # Smart update logic per file:
    #   1. Target doesn't exist → extract, record hash in manifest
    #   2. Target exists, no manifest entry → record current .example hash
    #      (assume user has the file, don't overwrite — backward compat for
    #      users who installed before the manifest existed)
    #   3. Target exists, manifest entry matches current .example hash →
    #      no update needed (skip)
    #   4. Target exists, manifest entry differs from current .example hash →
    #      .example was updated (developer pushed changes):
    #      a. Target hash matches OLD manifest hash → user didn't modify →
    #         safe to auto-update
    #      b. Target hash differs from OLD manifest hash → user modified →
    #         skip (preserve their edits)
    #
    # Args:
    #     defaults_dir: The .defaults/ directory containing .example files
    #     output_dir: The parent folder where extracted files are written
    #
    # Returns:
    #     Tuple of (extracted_count, updated_count)
    manifest = _load_manifest(defaults_dir)
    extracted = 0
    updated = 0
    manifest_changed = False

    for root, _dirs, files in os.walk(defaults_dir):
        for f in sorted(files):
            if not f.endswith('.example'):
                continue

            example_path = os.path.join(root, f)
            # Compute relative path from .defaults/ dir, strip .example suffix
            rel_path = os.path.relpath(example_path, defaults_dir)
            target_name = rel_path[:-8]  # Strip ".example"
            target_path = os.path.join(output_dir, target_name)
            # Use forward slashes for consistent manifest keys across platforms
            manifest_key = target_name.replace(os.sep, '/')

            example_hash = _file_hash(example_path)

            if not os.path.exists(target_path):
                # Case 1: New file — extract it
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(example_path, target_path)
                manifest[manifest_key] = example_hash
                manifest_changed = True
                extracted += 1

            elif manifest_key not in manifest:
                # Case 2: File exists but no manifest entry (pre-manifest install).
                # Record current .example hash so future updates can be tracked.
                # Don't overwrite — the user may have customized the file.
                manifest[manifest_key] = example_hash
                manifest_changed = True

            elif manifest[manifest_key] == example_hash:
                # Case 3: .example unchanged since last extraction — nothing to do
                pass

            else:
                # Case 4: .example was updated (developer pushed changes)
                old_example_hash = manifest[manifest_key]
                target_hash = _file_hash(target_path)

                if target_hash == old_example_hash:
                    # Case 4a: User didn't modify the file — safe to auto-update
                    shutil.copy2(example_path, target_path)
                    manifest[manifest_key] = example_hash
                    manifest_changed = True
                    updated += 1
                    log.debug(_LOG_PREFIX, f"Auto-updated: {target_name}")
                else:
                    # Case 4b: User modified the file — preserve their edits
                    manifest[manifest_key] = example_hash
                    manifest_changed = True
                    log.debug(_LOG_PREFIX, f"Skipped (user-modified): {target_name}")

    if manifest_changed:
        _save_manifest(defaults_dir, manifest)

    return extracted, updated


# ============================================================================
# User folder → repo migration (models/Eclipse/ → repo root)
# ============================================================================

# Mapping: user folder subfolder → repo folder
_USER_TO_REPO_MAP = {
    'loader_templates': 'templates',      # models/Eclipse/loader_templates/ → templates/
    'patterns': 'patterns',               # models/Eclipse/patterns/ → patterns/
    'smart_prompt': 'prompts',            # models/Eclipse/smart_prompt/ → prompts/
    'styles': 'styles',                   # models/Eclipse/styles/ → styles/
}


def migrate_user_folder_to_repo(repo_root: str, comfyui_root: str) -> bool:
    # Migrate user data from models/Eclipse/ to the repo folders.
    # Copies files that don't already exist in the repo (preserves newer defaults).
    # After successful migration, renames models/Eclipse/ → models/Eclipse_backup/.
    # Writes a .migrated marker in the repo so this never runs again.
    #
    # Args:
    #     repo_root: Path to ComfyUI_Eclipse repo root
    #     comfyui_root: Path to ComfyUI root directory
    #
    # Returns:
    #     True if migration was performed, False if skipped
    marker = os.path.join(repo_root, _MIGRATED_MARKER)
    if os.path.exists(marker):
        return False

    eclipse_dir = os.path.join(comfyui_root, 'models', 'Eclipse')

    # Skip if user folder doesn't exist (fresh install)
    if not os.path.isdir(eclipse_dir):
        _write_marker(marker)
        return False

    backup_dir = os.path.join(comfyui_root, 'models', 'Eclipse_backup')
    migrated_count = 0

    for user_sub, repo_sub in _USER_TO_REPO_MAP.items():
        user_path = os.path.join(eclipse_dir, user_sub)
        repo_path = os.path.join(repo_root, repo_sub)

        if not os.path.isdir(user_path):
            continue

        count = _copy_missing_files(user_path, repo_path)
        if count > 0:
            log.msg(_LOG_PREFIX, f"Migrated {count} file(s) from models/Eclipse/{user_sub}/ → {repo_sub}/")
            migrated_count += count

    # Rename user folder to backup
    if migrated_count > 0 or os.path.isdir(eclipse_dir):
        try:
            os.rename(eclipse_dir, backup_dir)
            log.msg(_LOG_PREFIX, "Renamed models/Eclipse/ → models/Eclipse_backup/ (migration complete)")
        except Exception as e:
            log.warning(_LOG_PREFIX, f"Could not rename Eclipse folder to backup: {e}")

    _write_marker(marker)
    return migrated_count > 0


def _write_marker(path: str) -> None:
    # Write migration marker file so user-folder migration is skipped on future startups.
    try:
        with open(path, 'w') as f:
            f.write('Migration completed. This file prevents re-running user folder migration.\n')
    except OSError:
        pass


def _copy_missing_files(source_dir: str, target_dir: str) -> int:
    # Copy files from source to target that don't already exist in target.
    # Handles subdirectories recursively.
    #
    # Args:
    #     source_dir: Source directory (user folder)
    #     target_dir: Target directory (repo folder)
    #
    # Returns:
    #     Number of files copied
    count = 0
    for root, _dirs, files in os.walk(source_dir):
        rel_path = os.path.relpath(root, source_dir)
        target_root = os.path.join(target_dir, rel_path) if rel_path != '.' else target_dir

        for f in files:
            target_file = os.path.join(target_root, f)
            if not os.path.exists(target_file):
                os.makedirs(target_root, exist_ok=True)
                shutil.copy2(os.path.join(root, f), target_file)
                count += 1
    return count


# ============================================================================
# Pre-Eclipse folder migration (ancient structure → repo)
# ============================================================================

def migrate_old_folders(repo_root: str, comfyui_root: str) -> None:
    # Migrate from ancient pre-Eclipse folder structure directly to repo.
    #
    # Old locations:
    #   models/smart_loader_templates/ → repo templates/
    #   models/wildcards/smartprompt/  → repo prompts/
    migrations = [
        {
            'old': os.path.join(comfyui_root, 'models', 'smart_loader_templates'),
            'new': os.path.join(repo_root, 'templates'),
            'name': 'Smart Loader templates'
        },
        {
            'old': os.path.join(comfyui_root, 'models', 'wildcards', 'smartprompt'),
            'new': os.path.join(repo_root, 'prompt'),
            'name': 'Smart Prompt files'
        }
    ]

    for migration in migrations:
        old_path = migration['old']
        new_path = migration['new']
        name = migration['name']

        if not os.path.exists(old_path):
            continue

        count = _copy_missing_files(old_path, new_path)
        if count > 0:
            log.msg(_LOG_PREFIX, f"Migrated {count} {name} from old location")

        # Clean up old folder
        try:
            shutil.rmtree(old_path)
            log.msg(_LOG_PREFIX, f"Removed old {name} folder")
        except Exception as e:
            log.warning(_LOG_PREFIX, f"Could not remove old {name} folder: {e}")


# ============================================================================
# Wildcards junction
# ============================================================================

def create_wildcards_junction(repo_root: str, comfyui_root: str) -> bool:
    # Create a junction/symlink from models/wildcards/smart_prompt/ → repo prompts/.
    # Enables wildcard integration without file duplication.
    # Users reference __smart_prompt/... in wildcard syntax, so the name must stay.
    #
    # Args:
    #     repo_root: Path to ComfyUI_Eclipse repo root
    #     comfyui_root: Path to ComfyUI root directory
    #
    # Returns:
    #     True if created or already exists, False on error
    source_dir = os.path.join(repo_root, 'prompts')
    link_dir = os.path.join(comfyui_root, 'models', 'wildcards', 'smart_prompt')

    # Already a valid symlink/junction pointing to the right place
    if os.path.islink(link_dir) or _is_junction(link_dir):
        return True

    # Orphaned regular directory from old approach — remove it so we can create a proper link
    if os.path.isdir(link_dir):
        try:
            shutil.rmtree(link_dir)
            log.msg(_LOG_PREFIX, "Removed orphaned wildcards/smart_prompt directory")
        except Exception as e:
            log.warning(_LOG_PREFIX, f"Could not remove orphaned wildcards/smart_prompt: {e}")
            return False

    if not os.path.exists(source_dir):
        log.warning(_LOG_PREFIX, f"Junction source not found: {source_dir}")
        return False

    try:
        os.makedirs(os.path.dirname(link_dir), exist_ok=True)
        system = platform.system()

        if system == "Windows":
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", link_dir, source_dir],
                check=True, capture_output=True
            )
            log.msg(_LOG_PREFIX, "Created junction: wildcards/smart_prompt → repo prompts/")
        else:
            os.symlink(source_dir, link_dir, target_is_directory=True)
            log.msg(_LOG_PREFIX, "Created symlink: wildcards/smart_prompt → repo prompts/")

        return True

    except Exception as e:
        log.warning(_LOG_PREFIX, f"Could not create wildcards junction (optional): {e}")
        return False


# ============================================================================
# Main entry point
# ============================================================================

def run_migrations(repo_root: Optional[str] = None, comfyui_root: Optional[str] = None) -> None:
    # Run all migrations in the correct order.
    # Called once from __init__.py on startup.
    #
    # Args:
    #     repo_root: Path to ComfyUI_Eclipse repo root (auto-detected if None)
    #     comfyui_root: Path to ComfyUI root directory (auto-detected if None)
    if repo_root is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if comfyui_root is None:
        comfyui_root = os.path.abspath(os.path.join(repo_root, '..', '..'))

    # 1. Ancient pre-Eclipse folder migration
    migrate_old_folders(repo_root, comfyui_root)

    # 2. User folder (models/Eclipse/) → repo migration
    migrate_user_folder_to_repo(repo_root, comfyui_root)

    # 3. Rename eclipse_config.json → config.json (v2.x migration)
    _migrate_config_rename(repo_root)

    # 4. Extract .example files (seed defaults for first run)
    extract_all_example_files(repo_root)

    # 5. Wildcards junction for wildcard integration
    create_wildcards_junction(repo_root, comfyui_root)

    # 6. Model folder junctions (models/Eclipse/* → repo folders)
    create_model_junctions(repo_root, comfyui_root)


# ============================================================================
# Model folder junctions (models/Eclipse/* → repo)
# ============================================================================

def create_model_junctions(repo_root: str, comfyui_root: str) -> None:
    # Create junctions/symlinks from models/Eclipse/* → repo folders.
    # Preserves familiar models/ folder structure while files live in repo.
    #
    # Mapping:
    #   models/Eclipse/templates/ → repo templates/
    #   models/Eclipse/patterns/  → repo patterns/
    #   models/Eclipse/styles/    → repo styles/
    #   models/Eclipse/prompts/   → repo prompts/
    eclipse_dir = os.path.join(comfyui_root, 'models', 'Eclipse')
    os.makedirs(eclipse_dir, exist_ok=True)

    mappings = {
        'templates': os.path.join(repo_root, 'templates'),
        'patterns': os.path.join(repo_root, 'patterns'),
        'styles': os.path.join(repo_root, 'styles'),
        'prompts': os.path.join(repo_root, 'prompts'),
    }

    for name, source in mappings.items():
        _create_junction(os.path.join(eclipse_dir, name), source)


# ============================================================================
# Junction/symlink helpers
# ============================================================================

def _is_junction(path: str) -> bool:
    # Check if path is a Windows junction point.
    if platform.system() != "Windows":
        return os.path.islink(path)
    try:
        import ctypes
        FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        return attrs != -1 and bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return False


def _create_junction(link_path: str, target_path: str) -> bool:
    # Create a junction (Windows) or symlink (Linux/macOS) from link_path → target_path.
    # Skips if link already exists or target doesn't exist.
    if os.path.exists(link_path) or os.path.islink(link_path):
        return True
    if not os.path.isdir(target_path):
        return False
    try:
        os.makedirs(os.path.dirname(link_path), exist_ok=True)
        if platform.system() == "Windows":
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", link_path, target_path],
                check=True, capture_output=True
            )
        else:
            os.symlink(target_path, link_path, target_is_directory=True)
        log.msg(_LOG_PREFIX, f"Junction: {os.path.basename(link_path)} → {target_path}")
        return True
    except Exception as e:
        log.debug(_LOG_PREFIX, f"Could not create junction {link_path}: {e}")
        return False


# ============================================================================
# Config file rename migration (eclipse_config.json → config.json)
# ============================================================================

def _migrate_config_rename(repo_root: str) -> None:
    # Rename eclipse_config.json → config.json if old name still exists.
    # Also handles the .example file.
    old_config = os.path.join(repo_root, "eclipse_config.json")
    new_config = os.path.join(repo_root, "config.json")
    old_example = os.path.join(repo_root, "eclipse_config.json.example")

    if os.path.exists(old_config) and not os.path.exists(new_config):
        os.rename(old_config, new_config)
        log.msg(_LOG_PREFIX, "Renamed eclipse_config.json → config.json")

    # Clean up old .example file (now lives in .defaults/)
    if os.path.exists(old_example):
        try:
            os.remove(old_example)
        except OSError:
            pass

    # Clean up old file if both exist (new takes priority)
    if os.path.exists(old_config) and os.path.exists(new_config):
        try:
            os.remove(old_config)
            log.msg(_LOG_PREFIX, "Removed leftover eclipse_config.json (config.json already exists)")
        except OSError:
            pass
