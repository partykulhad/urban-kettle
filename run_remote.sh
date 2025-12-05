#!/bin/bash

echo "==================================================="
echo "Launching Urban Kettle on Raspberry Pi..."
echo "User: urbanketl"
echo "==================================================="

ssh -t urbanketl@192.168.68.159 "cd /home/urbanketl/Downloads/BW-Modified && python3 -m venv .venv && .venv/bin/python3 run_with_dependencies.py"

echo "==================================================="
echo "Application session ended."
echo "==================================================="
