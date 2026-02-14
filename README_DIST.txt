=======================================
  Freakuency v0.3.0-alpha
  Per-app VPN split tunneling for Windows
=======================================

QUICK START
-----------
1. Connect to your VPN using your VPN client (OpenVPN, WireGuard, NordVPN, etc.)
2. Run Freakuency.exe (a UAC admin prompt will appear — this is required)
3. Pick your mode:
     - VPN Default (Exclude): all traffic through VPN, toggled apps bypass it
     - Direct Default (Include): all traffic direct, toggled apps go through VPN
4. Toggle the apps you want to reroute
5. Click Start

EXITING
-------
Always exit Freakuency through File > Exit or the tray icon > Exit.
This ensures the WinDivert kernel driver is properly unloaded.

Do NOT force-kill the process (Task Manager > End Task) unless necessary,
as this may leave the driver loaded and lock files in the folder.

TROUBLESHOOTING: CAN'T DELETE THE FOLDER
-----------------------------------------
If you closed Freakuency and cannot delete the folder because
WinDivert64.sys is locked:

1. Right-click "cleanup_driver.bat" and select "Run as administrator"
2. The script will stop and remove the WinDivert driver service
3. You should now be able to delete the folder

If the file is still locked after running the script, restart your PC.
The driver will be fully unloaded on reboot.

LOGS & TROUBLESHOOTING
-----------------------
Freakuency writes logs to the "logs" folder next to the executable.

To export logs for a bug report:
1. Open Freakuency
2. Go to File > Export Logs...
3. Save the .log file and attach it to your bug report

Log files rotate automatically (5 MB per file, up to 4 files kept).

FILES IN THIS FOLDER
---------------------
Freakuency.exe       - Main application (run this)
cleanup_driver.bat   - Driver cleanup script (run as admin if folder won't delete)
_internal/           - Application dependencies (do not modify)

REQUIREMENTS
------------
- Windows 10 or 11 (64-bit)
- Administrator privileges
- An active VPN connection

MORE INFO
---------
GitHub: https://github.com/MoeJaafar/Freakuency
