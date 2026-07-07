#!/bin/bash
# build_deb.sh
# Script to build an OTA Debian package (.deb) for the Urban Kettle Kiosk

set -e

if [ -z "$1" ]; then
    echo "Usage: ./build_deb.sh <version>"
    echo "Example: ./build_deb.sh 1.2.0"
    exit 1
fi

VERSION=$1
PACKAGE_NAME="urban-kettle"
BUILD_DIR="/tmp/${PACKAGE_NAME}-build"
INSTALL_DIR="/opt/${PACKAGE_NAME}"

echo "=========================================="
echo " Building Urban Kettle .deb (v$VERSION)"
echo "=========================================="

# 1. Clean up old build directories
rm -rf "$BUILD_DIR"
mkdir -p "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}${INSTALL_DIR}"

# 2. Create the DEBIAN/control file
cat << EOF > "${BUILD_DIR}/DEBIAN/control"
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Architecture: all
Maintainer: Urban Kettle Team
Description: Urban Kettle Kiosk Python Application
 This package installs the kiosk UI and backend polling server.
EOF

# 3. Create the postinst (Post-Install) script
# This runs automatically on the Pi after the files are copied.
cat << 'EOF' > "${BUILD_DIR}/DEBIAN/postinst"
#!/bin/bash
echo "Installing Python dependencies..."
cd /opt/urban-kettle

# Migrate machine_config.py from initial setup if it doesn't exist
if [ ! -f "machine_config.py" ]; then
    echo "machine_config.py not found in /opt, checking initial clone directories..."
    if [ -f "/home/urbanketl/urban-kettle/machine_config.py" ]; then
        cp "/home/urbanketl/urban-kettle/machine_config.py" ./
        echo "Migrated machine_config.py from /home/urbanketl"
    elif [ -f "/home/pi/urban-kettle/machine_config.py" ]; then
        cp "/home/pi/urban-kettle/machine_config.py" ./
        echo "Migrated machine_config.py from /home/pi"
    else
        echo "WARNING: machine_config.py NOT FOUND! App will crash until configured."
    fi
fi

# Ensure venv exists (if they didn't run setup.sh, we make it)
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate and install requirements
source venv/bin/activate
pip install -r requirements.txt

# Ensure permissions
chmod +x *.sh

# Setup Auto-Start (systemd) automatically if not already installed
if [ -f "install_autostart.sh" ]; then
    echo "Setting up Systemd Auto-Start..."
    echo "y" | ./install_autostart.sh > /dev/null
fi

# Fix ownership so the desktop user can read/write to the app directory
echo "Fixing permissions in /opt/urban-kettle..."
if id "urbanketl" &>/dev/null; then
    chown -R urbanketl:urbanketl /opt/urban-kettle
elif id "pi" &>/dev/null; then
    chown -R pi:pi /opt/urban-kettle
fi

# Setup Watchdog & OTA Updater Cronjobs automatically
echo "Setting up Software Watchdog and Updater Cronjobs..."
CRON_WATCHDOG="* * * * * /opt/urban-kettle/software_watchdog.sh"
(crontab -l 2>/dev/null | grep -v "software_watchdog.sh"; echo "$CRON_WATCHDOG") | crontab -

# Set up udev rule for screen brightness so the app can control it without sudo
echo "Setting up backlight permissions (udev)..."
echo 'SUBSYSTEM=="backlight", RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness"' > /etc/udev/rules.d/99-backlight.rules
udevadm control --reload-rules || true
udevadm trigger || true


# OTA Update Schedule — Runs every 1 hour
CRON_UPDATE="0 * * * * /opt/urban-kettle/update.sh"
(crontab -l 2>/dev/null | grep -v "update.sh"; echo "$CRON_UPDATE") | crontab -

# Restart the service (don't fail if the service isn't active yet)
echo "Restarting urban-kettle service..."
systemctl restart urban-kettle || true
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

# 4. Copy the code files into the fakeroot directory
echo "Copying application files..."
rsync -av --progress ./ "${BUILD_DIR}${INSTALL_DIR}/" \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude 'venv' \
    --exclude 'machine_config.py' \
    --exclude '*.deb' \
    --exclude 'node_modules' \
    --exclude 'kulhad' \
    --exclude '*.log' \
    --exclude 'test_*.py' \
    --exclude 'test_*.sh' \
    --exclude 'benchmark_apis.py' \
    --exclude 'api_benchmark_*.json' \
    --exclude '*.bat' \
    --exclude '.claude' \
    --exclude 'Dockerfile' \
    --exclude 'docker-compose.yml' \
    --exclude 'run_demo.py' \
    --exclude 'run_remote.sh' \
    --exclude 'run_diagnostic.sh' \
    --exclude 'run_navigation_test.sh' \
    --exclude 'run_with_dependencies.py' \
    --exclude 'mock_polling_server.py' \
    --exclude 'create_archive.py' \
    --exclude 'deploy_to_pi.sh' \
    --exclude 'setup_pi_deploy.sh' \
    --exclude 'run.txt' \
    --exclude 'live_monitor.py' \
    --exclude 'rpi_diagnostic.py' \
    --exclude 'kivy_profiler.py' \
    --exclude '.gitignore' \
    --exclude '*.md' \
    --exclude 'build_deb.sh' \
    --exclude 'wait_for_display.sh' \
    --exclude 'run_all.sh' \
    --exclude 'assets/screensaver_*'

# Write the version directly into the package so the machine knows its version instantly
echo "${VERSION}" > "${BUILD_DIR}${INSTALL_DIR}/current_version.txt"

# 5. Build the .deb file
echo "Compiling .deb package..."
dpkg-deb --build "$BUILD_DIR" "${PACKAGE_NAME}_${VERSION}_all.deb"

# 6. Cleanup
rm -rf "$BUILD_DIR"

echo "=========================================="
echo " ✅ Success! Created: ${PACKAGE_NAME}_${VERSION}_all.deb"
echo " You can now upload this file to your server!"
echo "=========================================="
