import os
import site
import subprocess

def main():
    print("Przygotowywanie kompilacji PyInstaller...")
    
    import sys
    import customtkinter
    import playwright_stealth
    import playwright
    
    ctk_path = os.path.dirname(customtkinter.__file__)
    stealth_path = os.path.dirname(playwright_stealth.__file__)
    pw_path = os.path.dirname(playwright.__file__)
    browsers_path = os.path.join(pw_path, "driver", "package", ".local-browsers")
    
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
        "app/desktop_main.py"
    ]
    
    print(f"Uruchamianie: {' '.join(cmd)}")
    subprocess.run(cmd)
    
    print("\n" + "="*50)
    print("GOTOWE!")
    print("Plik .exe znajduje się w folderze: dist/TicketMaster/")
    print("Pamiętaj: Upewnij się, że komputer docelowy ma zainstalowane przeglądarki Playwright (lub przenieś folder z przeglądarkami).")
    print("="*50)

if __name__ == "__main__":
    main()
