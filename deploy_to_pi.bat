@echo off
echo ===================================================
echo Deploying to Raspberry Pi (192.168.68.159)...
echo User: urbanketl (No password - Press Enter when prompted)
echo ===================================================

echo [1/3] Setting up directory on Pi...
ssh urbanketl@192.168.68.159 "mkdir -p /home/urbanketl/Downloads/BW-Modified"

echo [2/3] Transferring files...
scp deployment.zip urbanketl@192.168.68.159:/home/urbanketl/Downloads/BW-Modified/

echo [3/3] Extracting and Running...
ssh -t urbanketl@192.168.68.159 "cd /home/urbanketl/Downloads/BW-Modified && python3 -c \"import zipfile; zipfile.ZipFile('deployment.zip').extractall('.')\" && python3 run_with_dependencies.py"

echo ===================================================
echo Deployment script finished.
echo ===================================================
pause
