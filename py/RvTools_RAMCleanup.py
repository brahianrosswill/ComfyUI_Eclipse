#
# Credits to LAOGOU-666: https://github.com/LAOGOU-666/Comfyui-Memory_Cleanup.git
# improved and adapted for Comfyui_Eclipse

import psutil
import ctypes
import time
import platform
import subprocess
from comfy_api.latest import io #type: ignore
from ..core import CATEGORY
from ..core.logger import log

_LOG_PREFIX = "RAM Cleanup"
# Import Windows-specific modules only on Windows
if platform.system() == "Windows":
    from ctypes import wintypes


def _get_ram_usage():
    # Get current RAM usage statistics
    memory = psutil.virtual_memory()
    return memory.percent, memory.available / (1024 * 1024)


def _get_detailed_memory_info():
    # Get detailed memory information
    memory = psutil.virtual_memory()
    return {
        'total': memory.total / (1024 * 1024),  # MB
        'available': memory.available / (1024 * 1024),  # MB
        'used': memory.used / (1024 * 1024),  # MB
        'percent': memory.percent,
        'free': memory.free / (1024 * 1024)  # MB
    }


def _clear_file_cache_windows():
    # Clear Windows file cache
    try:
        result = ctypes.windll.kernel32.SetSystemFileCacheSize(-1, -1, 0)
        return result == 0
    except Exception as e:
        return False


def _check_sudo_available():
    # Check if sudo is available and configured for cache clearing
    try:
        # Check if sudo command exists
        result = subprocess.run(
            ["which", "sudo"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return False, "sudo command not found"

        # Test the ACTUAL command we'll use (tee to drop_caches)
        # This checks if the sudoers rule is properly configured
        result = subprocess.run(
            ["sudo", "-n", "-l", "tee", "/proc/sys/vm/drop_caches"],
            capture_output=True,
            text=True,
            timeout=2
        )
        # sudo -l returns 0 if the command is allowed
        if result.returncode != 0:
            return False, "sudo not configured for cache clearing (run setup_cache_clearing.sh)"

        return True, "sudo configured for cache clearing"
    except (subprocess.TimeoutExpired, Exception) as e:
        return False, f"sudo check failed: {str(e)}"


def _clear_file_cache_linux():
    # Clear Linux file cache using multiple methods
    # Requires passwordless sudo configured via setup_cache_clearing.sh
    #
    # SAFETY: Linux kernel docs require sync before drop_caches to flush
    # dirty buffers to disk. drop_caches only frees clean pages, but
    # syncing first ensures no dirty data is left unflushed.

    # Check if sudo is available first
    sudo_ok, sudo_msg = _check_sudo_available()
    if not sudo_ok:
        log.warning(_LOG_PREFIX, f"Cannot clear file cache on Linux: {sudo_msg}")
        log.warning(_LOG_PREFIX, f"Run setup_cache_clearing.sh to configure passwordless sudo")
        return False

    # CRITICAL: sync filesystem buffers BEFORE dropping caches
    # Per kernel docs: "the user should run sync first"
    try:
        subprocess.run(["sync"], capture_output=True, timeout=10)
    except (subprocess.TimeoutExpired, Exception) as e:
        log.warning(_LOG_PREFIX, f"Sync failed before cache drop, skipping drop_caches for safety: {e}")
        return False

    # Use value 1 (drop pagecache only) instead of 3 (pagecache + dentries + inodes)
    # This is safer - dropping dentries/inodes (value 3) can cause significant I/O
    # storms on systems with many files and slow storage
    cache_value = b"1\n"

    # Try tee method (most reliable, recommended)
    try:
        result = subprocess.run(
            ["sudo", "-n", "tee", "/proc/sys/vm/drop_caches"],
            input=cache_value,
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            return True
    except (subprocess.TimeoutExpired, Exception):
        pass

    # Fallback to sysctl method
    try:
        result = subprocess.run(
            ["sudo", "-n", "sysctl", "vm.drop_caches=1"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True
    except (subprocess.TimeoutExpired, Exception):
        pass

    return False


def _clear_process_memory_windows():
    # Clear working set of user processes (safely)
    cleaned_count = 0

    # System processes to avoid (case-insensitive)
    system_processes = {
        'system', 'system idle process', 'svchost.exe', 'csrss.exe', 'wininit.exe',
        'winlogon.exe', 'lsass.exe', 'services.exe', 'smss.exe', 'explorer.exe'
    }

    try:
        for process in psutil.process_iter(['pid', 'name']):
            try:
                process_name = process.info['name']
                if process_name and process_name.lower() in system_processes:
                    continue

                # Only clean processes that are not system critical
                handle = ctypes.windll.kernel32.OpenProcess(
                    wintypes.DWORD(0x001F0FFF),  # PROCESS_ALL_ACCESS
                    wintypes.BOOL(False),
                    wintypes.DWORD(process.info['pid'])
                )

                if handle:
                    result = ctypes.windll.psapi.EmptyWorkingSet(handle)
                    ctypes.windll.kernel32.CloseHandle(handle)
                    if result == 0:  # Success
                        cleaned_count += 1

            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                # Skip processes we can't access or that disappear
                continue
            except Exception:
                continue

        return cleaned_count

    except Exception:
        return 0


def _clear_dlls_windows():
    # Clear current process working set
    try:
        # This affects the current Python process
        result = ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
        return result == 0
    except Exception:
        return False


def _clear_dlls_linux():
    # Sync filesystem buffers on Linux (safe, non-destructive)
    # This writes any dirty pages to disk - always safe to call
    try:
        subprocess.run(["sync"], check=True, capture_output=True, timeout=10)
        return True
    except (subprocess.TimeoutExpired, Exception):
        return False


class RvTools_RAMCleanup(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="RAM Cleanup [Eclipse]",
            display_name="RAM Cleanup",
            category=CATEGORY.MAIN.value + CATEGORY.TOOLS.value,
            inputs=[
                io.AnyType.Input("anything"),
                io.Boolean.Input("clean_file_cache", default=True, tooltip="Clear File Cache"),
                io.Boolean.Input("clean_processes", default=True, tooltip="Clear Process Memory"),
                io.Boolean.Input("clean_dlls", default=True, tooltip="Clear Unused DLLs"),
                io.Int.Input("retry_times", default=3, min=1, max=10, step=1, tooltip="Retry Times"),
            ],
            outputs=[
                io.AnyType.Output("output"),
            ],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, anything, clean_file_cache, clean_processes, clean_dlls, retry_times):
        # Main RAM cleanup function with improved error handling and safety
        if retry_times < 1 or retry_times > 10:
            log.warning(_LOG_PREFIX, f"Invalid retry_times value: {retry_times}. Using default of 3.")
            retry_times = 3

        try:
            initial_mem = _get_detailed_memory_info()
            system = platform.system()

            # Start message
            log.msg(_LOG_PREFIX, f"=== RAM Cleanup Started ===")
            log.msg(_LOG_PREFIX, f"Initial - Usage: {initial_mem['percent']:.1f}% | Available: {initial_mem['available']:.1f}MB | Total: {initial_mem['total']:.1f}MB")

            total_cleaned_processes = 0
            operations_completed = set()
            attempt_details = []

            for attempt in range(retry_times):
                attempt_operations = []
                attempt_cleaned_processes = 0

                # File cache cleanup
                if clean_file_cache:
                    if system == "Windows":
                        if _clear_file_cache_windows():
                            attempt_operations.append("Cache")
                            operations_completed.add("File Cache")
                    elif system == "Linux":
                        if _clear_file_cache_linux():
                            attempt_operations.append("Cache")
                            operations_completed.add("File Cache")

                # Process memory cleanup
                if clean_processes:
                    if system == "Windows":
                        cleaned = _clear_process_memory_windows()
                        if cleaned > 0:
                            attempt_cleaned_processes = cleaned
                            total_cleaned_processes += cleaned
                            attempt_operations.append(f"Proc({cleaned})")
                            operations_completed.add("Processes")

                # DLL/working set cleanup
                if clean_dlls:
                    if system == "Windows":
                        if _clear_dlls_windows():
                            attempt_operations.append("DLL")
                            operations_completed.add("DLL Working Set")
                    elif system == "Linux":
                        if _clear_dlls_linux():
                            attempt_operations.append("Sync")
                            operations_completed.add("Filesystem Sync")

                # Store attempt details
                current_mem = _get_detailed_memory_info()
                attempt_details.append({
                    'attempt': attempt + 1,
                    'operations': attempt_operations,
                    'usage': current_mem['percent'],
                    'available': current_mem['available']
                })

                # Brief pause between attempts
                if attempt < retry_times - 1:
                    time.sleep(0.5)

            # Final summary with all attempts
            final_mem = _get_detailed_memory_info()
            memory_change = final_mem['available'] - initial_mem['available']

            # Build single consolidated message
            summary_lines = ["\n=== RAM Cleanup Progress ==="]

            for detail in attempt_details:
                ops = ', '.join(detail['operations']) if detail['operations'] else 'None'
                summary_lines.append(
                    f"Attempt {detail['attempt']}/{retry_times}: [{ops}] → "
                    f"Usage: {detail['usage']:.1f}% | Available: {detail['available']:.1f}MB"
                )

            summary_lines.append("\n=== Cleanup Complete ===")
            summary_lines.append(f"Operations: {', '.join(sorted(operations_completed)) if operations_completed else 'None'}")
            summary_lines.append(f"Processes Cleaned: {total_cleaned_processes}")
            summary_lines.append(f"Memory Change: {memory_change:+.1f}MB")
            summary_lines.append(f"Final - Usage: {final_mem['percent']:.1f}% | Available: {final_mem['available']:.1f}MB")

            # Print single consolidated message
            log.msg(_LOG_PREFIX, "\n".join(summary_lines))

        except Exception as e:
            log.error(_LOG_PREFIX, f"Critical error during RAM cleanup process: {e}")
            import traceback
            traceback.print_exc()

        return io.NodeOutput(anything)