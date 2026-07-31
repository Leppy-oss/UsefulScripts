"""
Convert python file(s) into executable(s), with option to automatically add it to the system path
Dependencies: `pip install pyinstaller`
Usage: `python pyexe.py [file1.py] [file2.py] ... --add-to-path
"""

import os
import sys
import logging
import argparse
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("files", nargs="+", help="Python files to convert")
parser.add_argument("-p", "--p", "-path", "--path", "--add-to-path", action="store_true")

args = parser.parse_args()

logging.basicConfig(level=logging.WARNING, force=True)

curr_dir = Path.cwd()
out_dir = Path.home() / ".pyexe/out"
os.makedirs(out_dir, exist_ok=True)

platform = sys.platform
print(f"Detected platform: {platform}")

def add_to_path(fpath):
    if platform.startswith("win32"):
        import winreg

        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS
        )
        try:
            old_PATH, _ = winreg.QueryValueEx(reg_key, "Path")
        except FileNotFoundError:
            old_PATH = ""

        if str(fpath) not in old_PATH:
            new_PATH = f"{old_PATH};{fpath}" if old_PATH else str(fpath)
            winreg.SetValueEx(reg_key, "Path", 0, winreg.REG_EXPAND_SZ, new_PATH)
            print(f"Added {fpath} to PATH")
        else:
            print(f"{fpath} already exists in PATH")
        winreg.CloseKey(reg_key)

    else:
        shell = os.environ.get("SHELL", "")
        if not shell:
            try:
                shell = Path(os.readlink("/proc/self/exe")).name
            except Exception:
                shell = os.environ.get("TERM", "")

        home_dir = Path.home()

        if "zsh" in shell:
            profile = home_dir / ".zshrc"
        elif "bash" in shell:
            profile = home_dir / ".bashrc"
        else:
            profile = (
                home_dir / ".profile"
                if platform.startswith("linux")
                else home_dir / ".zprofile"
            )

        export_cmd = f'export PATH="$PATH:{fpath}"\n'

        already_added = False
        if profile.exists():
            with open(profile, "r") as f:
                if str(fpath) in f.read():
                    already_added = True

        if not already_added:
            with open(profile, "a") as f:
                f.write(f"\n# Added by pyexe.py\n{export_cmd}")
            print(f"Added {fpath} to $PATH")
        else:
            print(f"{fpath} already exists in $PATH")

for f in args.files:
    fpath = curr_dir / f
    if not fpath.exists():
        print(f"Error: {f} not found in {curr_dir}")
        sys.exit(1)

    print(f"Compiling {f}...")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--log-level",
                "WARN",
                "--onefile",
                "--distpath",
                str(out_dir),
                str(fpath),
            ],
            check=True,
        )
        fpath.with_suffix(".spec").unlink()
    except Exception as e:
        print(f"Error compiling {f}: {e}")

if args.p:
    add_to_path(out_dir)
