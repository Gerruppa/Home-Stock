"""Start the app: .venv/Scripts/python.exe main.py"""

import multiprocessing

from home_stock.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
