

if __name__ == "__main__":
    import os
    import subprocess
    import signal
    import time
    import sys

    command =r"pyinstaller --onefile --clean --hidden-import cv2 --add-binary $(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")/libpython3.13.dylib:. --log-level=INFO  main_processing_computer.py"

    