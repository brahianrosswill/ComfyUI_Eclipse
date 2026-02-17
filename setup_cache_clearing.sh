#!/bin/bash
# Setup passwordless sudo for file cache clearing
# This allows ComfyUI RAM Cleanup node to clear system file cache without password

set -e

echo "=== ComfyUI Cache Clearing Setup ==="
echo ""
echo "This script will configure passwordless sudo for file cache clearing."
echo "You will be prompted for your password ONCE to add the sudoers rule."
echo ""

# Get current username
CURRENT_USER="${SUDO_USER:-$USER}"

echo "Setting up for user: $CURRENT_USER"
echo ""

# Create sudoers rule
SUDOERS_FILE="/etc/sudoers.d/comfyui-cache"
SUDOERS_CONTENT="# Allow ComfyUI to clear file cache without password
# Only pagecache clearing (value 1) - safer than full clear (value 3)
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/bin/tee /proc/sys/vm/drop_caches
$CURRENT_USER ALL=(ALL) NOPASSWD: /usr/sbin/sysctl vm.drop_caches=1
"

echo "$SUDOERS_CONTENT" | sudo tee "$SUDOERS_FILE" > /dev/null

# Set correct permissions
sudo chmod 0440 "$SUDOERS_FILE"

echo "✓ Sudoers rule created: $SUDOERS_FILE"
echo ""

# Validate sudoers syntax
if sudo visudo -c -f "$SUDOERS_FILE" > /dev/null 2>&1; then
    echo "✓ Sudoers syntax validated successfully"
else
    echo "✗ Sudoers syntax validation failed!"
    sudo rm -f "$SUDOERS_FILE"
    exit 1
fi

echo ""
echo "=== Testing Configuration ==="
echo ""

# Test if it works
if echo 3 | sudo -n tee /proc/sys/vm/drop_caches > /dev/null 2>&1; then
    echo "✓ File cache clearing works without password!"
    echo ""
    echo "Setup complete! ComfyUI RAM Cleanup node can now clear file cache."
else
    echo "✗ Test failed. You may need to restart your shell or re-login."
    echo "  Try running: newgrp $(id -gn)"
fi

echo ""
echo "=== Setup Complete ==="
echo "You can now use the RAM Cleanup node in ComfyUI without sudo."
