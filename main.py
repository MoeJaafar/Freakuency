"""
Freakuency — Entry point.
Ensures admin privileges before launching the application.
(Admin is required for WinDivert packet interception.)
"""

import ctypes
import sys
import os


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def main():
    if not is_admin():
        # Re-launch with admin privileges
        params = " ".join(f'"{a}"' for a in sys.argv)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        sys.exit(0)

    # Set working directory to script location so relative paths work
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    from app import SplitTunnelApp
    app = SplitTunnelApp()
    app.run()


if __name__ == "__main__":
    main()
