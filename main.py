"""Start the app: .venv/Scripts/python.exe main.py (also the script PyInstaller freezes into HomeStock.exe)"""

import multiprocessing

from home_stock.app import main

if __name__ == "__main__":
    # The frozen HomeStock.exe opens its native window in a spawned copy of itself, which must stop here
    multiprocessing.freeze_support()
    main()
