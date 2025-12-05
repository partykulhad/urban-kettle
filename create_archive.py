import zipfile
import os

def create_zip(output_filename):
    print(f"Creating {output_filename}...")
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            # Exclude directories
            dirs[:] = [d for d in dirs if d not in ['.git', '.venv', '__pycache__', 'firmware', 'assets', 'ui_pages', 'utils'] or d in ['assets', 'ui_pages', 'utils']]
            
            # Actually, I want to exclude specific hidden ones, but keep assets/ui/utils
            # Let's refine.
            
            # Exclude hidden directories starting with .
            if any(part.startswith('.') and part != '.' for part in root.split(os.sep)):
                continue
                
            for file in files:
                if file == output_filename or file.endswith('.pyc') or file == 'create_archive.py':
                    continue
                
                file_path = os.path.join(root, file)
                zipf.write(file_path, arcname=os.path.relpath(file_path, '.'))
                print(f"Added {file_path}")

if __name__ == "__main__":
    create_zip("deployment.zip")
