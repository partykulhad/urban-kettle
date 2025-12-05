import sys
import subprocess
import importlib.util
import os

def check_and_install_dependencies():
    """
    Reads requirements.txt and installs missing dependencies.
    """
    print("🔍 Checking dependencies...")
    
    # Map package names (in requirements.txt) to import names
    package_map = {
        "opencv-python": "cv2",
        "Pillow": "PIL",
        "kivy": "kivy",
        "kivymd": "kivymd",
        "numpy": "numpy",
        "requests": "requests",
        "flask": "flask",
        "pyscard": "smartcard"
    }
    
    requirements_file = "requirements.txt"
    if not os.path.exists(requirements_file):
        print(f"❌ {requirements_file} not found!")
        return False

    with open(requirements_file, 'r') as f:
        lines = f.readlines()

    install_needed = False
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        # Clean line of comments for pip install
        clean_line = line.split('#')[0].strip()
            
        # Extract package name (ignore version constraints for check)
        package_name = clean_line.split('==')[0].split('>=')[0].split('<')[0].strip()
        
        # Determine import name
        import_name = package_map.get(package_name, package_name)
        
        # Check if installed
        if importlib.util.find_spec(import_name) is None:
            print(f"📦 Package '{package_name}' not found. Installing...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", clean_line])
                install_needed = True
            except subprocess.CalledProcessError:
                print(f"⚠️ Failed to install {package_name} globally. Trying with --user...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", clean_line])
                    install_needed = True
                except subprocess.CalledProcessError:
                    print(f"❌ Failed to install {package_name} (even with --user)")
                    return False
        else:
            print(f"✅ {package_name} is installed.")

    if install_needed:
        print("\n🎉 Dependencies installed successfully.")
    else:
        print("\n✨ All dependencies are already satisfied.")
        
    return True

def run_main_app():
    """
    Runs the main application.
    """
    print("\n🚀 Starting Urban Kettle App...")
    try:
        # Run main_app.py using the same python interpreter
        subprocess.run([sys.executable, "main_app.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Application crashed with exit code {e.returncode}")
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user.")

if __name__ == "__main__":
    if check_and_install_dependencies():
        run_main_app()
    else:
        print("❌ Dependency check failed. Exiting.")
        sys.exit(1)
