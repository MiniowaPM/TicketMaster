import os
import site
import subprocess
import sys

def main():
    print("Przygotowywanie kompilacji PyInstaller...")
    
    import customtkinter
    import playwright_stealth
    import playwright
    
    ctk_path = os.path.dirname(customtkinter.__file__)
    stealth_path = os.path.dirname(playwright_stealth.__file__)
    pw_path = os.path.dirname(playwright.__file__)
    browsers_path = os.path.join(pw_path, "driver", "package", ".local-browsers")
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "app", "data"))
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "TicketMaster",
        "--paths", "app",
        f"--add-data={ctk_path};customtkinter/",
        f"--add-data={stealth_path}/js;playwright_stealth/js/",
        f"--add-data={browsers_path};playwright/driver/package/.local-browsers/",
        f"--add-data={data_path};data/",
        "app/desktop_main.py"
    ]
    
    print(f"Uruchamianie: {' '.join(cmd)}")
    subprocess.run(cmd)
    
    print("\n" + "="*50)
    print("GOTOWE!")
    print("Plik .exe znajduje się w folderze: dist/TicketMaster/")
    print("Wersja Standalone zawiera wbudowaną przeglądarkę Chromium.")
    print("="*50)

if __name__ == "__main__":
    main()
