#!/bin/bash
# Quick Test Runner for Hardware Navigation

echo "=============================================="
echo "🧪 Hardware Navigation Test"
echo "=============================================="
echo ""
echo "This will test:"
echo "  Hardware Error Page → Payment Method Page"
echo ""
echo "Starting mock server in 3 seconds..."
echo "Then run: python3 main_app.py in another terminal"
echo ""
sleep 3

python3 test_hardware_navigation.py
