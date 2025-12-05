#!/bin/bash

echo "==================================================="
echo "Deploying to Raspberry Pi (192.168.68.159)..."
echo "User: urbanketl"
echo "==================================================="

# First, create the archive
echo "[0/4] Creating deployment archive..."
python3 create_archive.py

if [ ! -f "deployment.zip" ]; then
    echo "❌ Error: deployment.zip not created!"
    exit 1
fi

echo "[1/4] Setting up directory on Pi..."
ssh urbanketl@192.168.68.159 "mkdir -p /home/urbanketl/Downloads/BW-Modified"

echo "[2/4] Transferring files..."
scp deployment.zip urbanketl@192.168.68.159:/home/urbanketl/Downloads/BW-Modified/

echo "[3/4] Extracting files on Pi..."
ssh urbanketl@192.168.68.159 "cd /home/urbanketl/Downloads/BW-Modified && python3 -c \"import zipfile; zipfile.ZipFile('deployment.zip').extractall('.')\""

echo "[4/4] Running application with dependency check..."
ssh -t urbanketl@192.168.68.159 "cd /home/urbanketl/Downloads/BW-Modified && python3 run_with_dependencies.py"

echo "==================================================="
echo "Deployment completed!"
echo "==================================================="
