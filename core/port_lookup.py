"""
Fast port-to-PID lookup via Windows IP Helper API (ctypes).

Used as a synchronous fallback when the polling-based connection tracker
hasn't indexed a new connection yet.  Calls GetExtendedTcpTable /
GetExtendedUdpTable directly so we can identify the owning process the
instant a packet is intercepted — no 200 ms polling delay.
"""

import ctypes
import ctypes.wintypes as wt
from ctypes import (
    POINTER, Structure, addressof, byref, c_byte, cast, sizeof, windll,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AF_INET = 2
TCP_TABLE_OWNER_PID_ALL = 5
UDP_TABLE_OWNER_PID = 1
NO_ERROR = 0
ERROR_INSUFFICIENT_BUFFER = 122
_MAX_RETRIES = 5


def _htons(port):
    """Host-order 16-bit port → network byte order."""
    return ((port >> 8) & 0xFF) | ((port & 0xFF) << 8)


# ---------------------------------------------------------------------------
# C structure mirrors (IPv4 only — our WinDivert filter is IPv4)
# ---------------------------------------------------------------------------

class _TcpRow(Structure):
    _fields_ = [
        ("dwState",      wt.DWORD),
        ("dwLocalAddr",  wt.DWORD),
        ("dwLocalPort",  wt.DWORD),
        ("dwRemoteAddr", wt.DWORD),
        ("dwRemotePort", wt.DWORD),
        ("dwOwningPid",  wt.DWORD),
    ]


class _TcpTable(Structure):
    _fields_ = [
        ("dwNumEntries", wt.DWORD),
        ("table",        _TcpRow * 1),
    ]


class _UdpRow(Structure):
    _fields_ = [
        ("dwLocalAddr",  wt.DWORD),
        ("dwLocalPort",  wt.DWORD),
        ("dwOwningPid",  wt.DWORD),
    ]


class _UdpTable(Structure):
    _fields_ = [
        ("dwNumEntries", wt.DWORD),
        ("table",        _UdpRow * 1),
    ]


# ---------------------------------------------------------------------------
# DLL bindings (loaded once at import time)
# ---------------------------------------------------------------------------
_iphlpapi = windll.iphlpapi

_GetExtTcp = _iphlpapi.GetExtendedTcpTable
_GetExtTcp.restype = wt.DWORD
_GetExtTcp.argtypes = [
    ctypes.c_void_p, POINTER(wt.DWORD), wt.BOOL,
    wt.DWORD, ctypes.c_int, wt.DWORD,
]

_GetExtUdp = _iphlpapi.GetExtendedUdpTable
_GetExtUdp.restype = wt.DWORD
_GetExtUdp.argtypes = [
    ctypes.c_void_p, POINTER(wt.DWORD), wt.BOOL,
    wt.DWORD, ctypes.c_int, wt.DWORD,
]


# ---------------------------------------------------------------------------
# Reusable buffers (grow-only, avoid allocation per call)
# ---------------------------------------------------------------------------

class _Buffer:
    __slots__ = ("_buf", "_size")

    def __init__(self, size=65536):
        self._size = size
        self._buf = (c_byte * size)()

    @property
    def ptr(self):
        return ctypes.cast(self._buf, ctypes.c_void_p)

    @property
    def size(self):
        return self._size

    def grow(self, needed):
        if needed > self._size:
            new_size = needed + needed // 4
            self._buf = (c_byte * new_size)()
            self._size = new_size


_tcp_buf = _Buffer()
_udp_buf = _Buffer()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_pid_for_tcp_port(port):
    """Return the PID owning the given local TCP port (IPv4), or None."""
    net_port = _htons(port)
    buf = _tcp_buf
    dw_size = wt.DWORD(buf.size)

    for _ in range(_MAX_RETRIES):
        ret = _GetExtTcp(
            buf.ptr, byref(dw_size), False,
            AF_INET, TCP_TABLE_OWNER_PID_ALL, 0,
        )
        if ret == NO_ERROR:
            break
        if ret == ERROR_INSUFFICIENT_BUFFER:
            buf.grow(dw_size.value)
            dw_size = wt.DWORD(buf.size)
            continue
        return None
    else:
        return None

    table = cast(buf.ptr, POINTER(_TcpTable)).contents
    n = table.dwNumEntries
    row_size = sizeof(_TcpRow)
    base = addressof(table.table)
    for i in range(n):
        row = cast(base + i * row_size, POINTER(_TcpRow)).contents
        if row.dwLocalPort == net_port:
            pid = row.dwOwningPid
            return pid if pid else None
    return None


def get_pid_for_udp_port(port):
    """Return the PID owning the given local UDP port (IPv4), or None."""
    net_port = _htons(port)
    buf = _udp_buf
    dw_size = wt.DWORD(buf.size)

    for _ in range(_MAX_RETRIES):
        ret = _GetExtUdp(
            buf.ptr, byref(dw_size), False,
            AF_INET, UDP_TABLE_OWNER_PID, 0,
        )
        if ret == NO_ERROR:
            break
        if ret == ERROR_INSUFFICIENT_BUFFER:
            buf.grow(dw_size.value)
            dw_size = wt.DWORD(buf.size)
            continue
        return None
    else:
        return None

    table = cast(buf.ptr, POINTER(_UdpTable)).contents
    n = table.dwNumEntries
    row_size = sizeof(_UdpRow)
    base = addressof(table.table)
    for i in range(n):
        row = cast(base + i * row_size, POINTER(_UdpRow)).contents
        if row.dwLocalPort == net_port:
            pid = row.dwOwningPid
            return pid if pid else None
    return None


def get_pid_for_port(port):
    """Try TCP first, then UDP. Returns PID or None."""
    return get_pid_for_tcp_port(port) or get_pid_for_udp_port(port)
