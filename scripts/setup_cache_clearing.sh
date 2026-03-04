#!/bin/bash
# Setup passwordless sudo for file cache clearing
# This allows ComfyUI RAM Cleanup node to clear system file cache without password
#
# Security design:
#   - A root-owned wrapper script (/usr/local/bin/comfyui-drop-pagecache) is installed
#   - The wrapper hardcodes "echo 1" (pagecache only) — value 3 is NOT possible
#   - The sudoers rule ONLY permits this wrapper — no direct tee/sysctl access
#   - This prevents privilege escalation via arbitrary writes to drop_caches

set -e

echo "=== ComfyUI Cache Clearing Setup ==="
echo ""
echo "This script installs a secure wrapper for pagecache clearing."
echo "You will be prompted for your password to install system files."
echo ""

# Get current username
CURRENT_USER="${SUDO_USER:-$USER}"

echo "Setting up for user: $CURRENT_USER"
echo ""

SUDOERS_FILE="/etc/sudoers.d/comfyui-cache"
SYSTEM_WRAPPER="/usr/local/bin/comfyui-drop-pagecache"

# ── 1. Install wrapper script (root-owned, not writable by user) ──

WRAPPER_CONTENT='#!/bin/bash
# Wrapper: drops pagecache ONLY (value 1). No arguments accepted.
# Owned by root:root, mode 0755 — users cannot modify.
sync
echo 1 > /proc/sys/vm/drop_caches
'

echo "Installing wrapper script: $SYSTEM_WRAPPER"
echo "$WRAPPER_CONTENT" | sudo tee "$SYSTEM_WRAPPER" > /dev/null
sudo chown root:root "$SYSTEM_WRAPPER"
sudo chmod 0755 "$SYSTEM_WRAPPER"
echo "✓ Wrapper installed (root:root, mode 0755)"
echo ""

# ── 2. Create sudoers rule (only allows the wrapper, nothing else) ──

SUDOERS_CONTENT="# Allow ComfyUI to drop pagecache without password
# ONLY the wrapper script is permitted — no direct tee/sysctl access
$CURRENT_USER ALL=(ALL) NOPASSWD: $SYSTEM_WRAPPER
"

echo "Creating sudoers rule: $SUDOERS_FILE"
echo "$SUDOERS_CONTENT" | sudo tee "$SUDOERS_FILE" > /dev/null
sudo chmod 0440 "$SUDOERS_FILE"
echo "✓ Sudoers rule created"
echo ""

# Validate sudoers syntax
if sudo visudo -c -f "$SUDOERS_FILE" > /dev/null 2>&1; then
    echo "✓ Sudoers syntax validated"
else
    echo "✗ Sudoers syntax validation failed! Rolling back."
    sudo rm -f "$SUDOERS_FILE" "$SYSTEM_WRAPPER"
    exit 1
fi

# ── 3. Test ──

echo ""
echo "=== Testing Configuration ==="
if sudo -n "$SYSTEM_WRAPPER" > /dev/null 2>&1; then
    echo "✓ Pagecache clearing works without password!"
else
    echo "✗ Test failed. You may need to log out and back in."
fi

echo ""
echo "=== Setup Complete ==="
echo "The RAM Cleanup node can now clear pagecache on Linux."
echo "Only value 1 (pagecache) is permitted — value 3 is blocked by design."
echo ""
echo "To remove: bash scripts/remove_cache_clearing.sh"
