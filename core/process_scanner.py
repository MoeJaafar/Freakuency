"""
Enumerate running processes and extract their icons.
Groups by executable path and filters out system noise.
"""

import ctypes
import ctypes.wintypes
import os
import logging

import psutil
from PIL import Image

log = logging.getLogger(__name__)

# Processes to always hide from the list
_SYSTEM_NOISE = {
    "system", "idle", "svchost.exe", "csrss.exe", "smss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "winlogon.exe",
    "fontdrvhost.exe", "dwm.exe", "conhost.exe", "dllhost.exe",
    "sihost.exe", "taskhostw.exe", "runtimebroker.exe",
    "searchhost.exe", "startmenuexperiencehost.exe",
    "textinputhost.exe", "shellexperiencehost.exe",
    "applicationframehost.exe", "systemsettings.exe",
    "securityhealthservice.exe", "securityhealthsystray.exe",
    "registry", "memory compression", "spoolsv.exe",
    "lsaiso.exe", "ctfmon.exe", "audiodg.exe",
    "searchindexer.exe", "searchprotocolhost.exe",
    "searchfilterhost.exe", "wmiprvse.exe",
}

# Icon cache: exe_path -> PIL.Image or None
_icon_cache = {}


class ProcessInfo:
    """Represents a unique running application."""
    __slots__ = ("name", "exe_path", "pids")

    def __init__(self, name, exe_path):
        self.name = name
        self.exe_path = exe_path
        self.pids = []

    def __repr__(self):
        return f"ProcessInfo({self.name!r}, pids={len(self.pids)})"


def scan_processes():
    """
    Return a sorted list of ProcessInfo objects for running user applications.
    Groups processes by exe path and deduplicates.
    """
    seen = {}  # exe_path -> ProcessInfo
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            info = proc.info
            name = (info["name"] or "").strip()
            exe = info["exe"]
            pid = info["pid"]

            if not name or not exe or pid in (0, 4):
                continue
            if name.lower() in _SYSTEM_NOISE:
                continue
            # Skip processes in Windows system directories
            exe_lower = exe.lower()
            if "\\windows\\system32\\" in exe_lower or "\\windows\\syswow64\\" in exe_lower:
                continue

            if exe not in seen:
                # Use the filename without extension as display name
                display_name = os.path.splitext(os.path.basename(exe))[0]
                seen[exe] = ProcessInfo(display_name, exe)
            seen[exe].pids.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    processes = sorted(seen.values(), key=lambda p: p.name.lower())
    return processes


def extract_icon(exe_path, size=32):
    """
    Extract the first icon from an exe file and return a PIL Image.
    Returns None if extraction fails.
    """
    if exe_path in _icon_cache:
        return _icon_cache[exe_path]

    icon_image = _extract_icon_win32(exe_path, size)
    _icon_cache[exe_path] = icon_image
    return icon_image


def _extract_icon_win32(exe_path, size):
    """Use Win32 API to extract icon from exe."""
    try:
        # shell32.ExtractIconExW
        shell32 = ctypes.windll.shell32
        large = (ctypes.wintypes.HICON * 1)()
        small = (ctypes.wintypes.HICON * 1)()

        count = shell32.ExtractIconExW(exe_path, 0, large, small, 1)
        if count == 0:
            return None

        hicon = large[0] if large[0] else small[0]
        if not hicon:
            return None

        try:
            image = _hicon_to_pil(hicon, size)
            return image
        finally:
            ctypes.windll.user32.DestroyIcon(hicon)
            if large[0] and small[0]:
                ctypes.windll.user32.DestroyIcon(small[0])
    except Exception as e:
        log.debug(f"Icon extraction failed for {exe_path}: {e}")
        return None


def _hicon_to_pil(hicon, size):
    """Convert a Windows HICON to a PIL Image."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # GetIconInfo
    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", ctypes.wintypes.BOOL),
            ("xHotspot", ctypes.wintypes.DWORD),
            ("yHotspot", ctypes.wintypes.DWORD),
            ("hbmMask", ctypes.wintypes.HBITMAP),
            ("hbmColor", ctypes.wintypes.HBITMAP),
        ]

    icon_info = ICONINFO()
    if not user32.GetIconInfo(hicon, ctypes.byref(icon_info)):
        return None

    # Get bitmap info
    class BITMAP(ctypes.Structure):
        _fields_ = [
            ("bmType", ctypes.c_long),
            ("bmWidth", ctypes.c_long),
            ("bmHeight", ctypes.c_long),
            ("bmWidthBytes", ctypes.c_long),
            ("bmPlanes", ctypes.wintypes.WORD),
            ("bmBitsPixel", ctypes.wintypes.WORD),
            ("bmBits", ctypes.c_void_p),
        ]

    bmp = BITMAP()
    hbm = icon_info.hbmColor if icon_info.hbmColor else icon_info.hbmMask
    gdi32.GetObjectW(hbm, ctypes.sizeof(BITMAP), ctypes.byref(bmp))

    width = bmp.bmWidth
    height = bmp.bmHeight
    if width == 0 or height == 0:
        gdi32.DeleteObject(icon_info.hbmMask)
        if icon_info.hbmColor:
            gdi32.DeleteObject(icon_info.hbmColor)
        return None

    # Create a device context and bitmap to draw into
    hdc_screen = user32.GetDC(0)
    hdc = gdi32.CreateCompatibleDC(hdc_screen)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.wintypes.DWORD),
            ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long),
            ("biPlanes", ctypes.wintypes.WORD),
            ("biBitCount", ctypes.wintypes.WORD),
            ("biCompression", ctypes.wintypes.DWORD),
            ("biSizeImage", ctypes.wintypes.DWORD),
            ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long),
            ("biClrUsed", ctypes.wintypes.DWORD),
            ("biClrImportant", ctypes.wintypes.DWORD),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0  # BI_RGB

    bits = ctypes.c_void_p()
    hbm_dib = gdi32.CreateDIBSection(
        hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0
    )

    old_bm = gdi32.SelectObject(hdc, hbm_dib)

    # Draw the icon
    user32.DrawIconEx(hdc, 0, 0, hicon, width, height, 0, 0, 0x0003)  # DI_NORMAL

    # Copy pixel data
    buf_size = width * height * 4
    buf = (ctypes.c_ubyte * buf_size)()
    ctypes.memmove(buf, bits, buf_size)

    # Convert BGRA to RGBA
    for i in range(0, buf_size, 4):
        buf[i], buf[i + 2] = buf[i + 2], buf[i]

    image = Image.frombytes("RGBA", (width, height), bytes(buf))
    image = image.resize((size, size), Image.Resampling.LANCZOS)

    # Cleanup
    gdi32.SelectObject(hdc, old_bm)
    gdi32.DeleteObject(hbm_dib)
    gdi32.DeleteDC(hdc)
    user32.ReleaseDC(0, hdc_screen)
    gdi32.DeleteObject(icon_info.hbmMask)
    if icon_info.hbmColor:
        gdi32.DeleteObject(icon_info.hbmColor)

    return image
