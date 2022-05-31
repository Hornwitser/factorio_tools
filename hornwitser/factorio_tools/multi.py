# factorio_tools - Debugging utilities for Factorio
# Copyright (C) 2020  Hornwitser
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
multi.py - Spawn and handle multiple Factorio clients
"""

import collections
import configparser
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time


def generate_base(args):
    config_dir = os.path.join(args.base, 'config')
    os.makedirs(config_dir, exist_ok=True)

    if not args.data:
        args.data = os.path.join('__PATH__executable__', '..', '..', 'data')

    config = configparser.ConfigParser()
    config['path'] = {
        'read-data': args.data,
        'write-data': os.path.abspath(args.base),
    }
    config['other'] = { 'check-updates': 'false' }
    config['sound'] = { 'music-volume': '0.000000' }
    config['graphics'] = { 'full-screen': 'false' }

    with open(os.path.join(config_dir, 'config.ini'), 'x', newline='\n') as f:
        f.write('; version=7\n')
        config.write(f, space_around_delimiters=False)

def generate_instances(args):
    with open(os.path.join(args.base, 'player-data.json')) as f:
        player_data = json.load(f)

    base_name = player_data["service-username"]

    for i in range(1, args.count+1):
        dst = os.path.join(args.output, f'{args.prefix}{i}')
        shutil.copytree(args.base, dst, dirs_exist_ok=True)

        player_data["service-username"] = f"{base_name}{i}"
        with open(os.path.join(dst, 'player-data.json'), 'w') as f:
            json.dump(player_data, f, indent=2)

        config_path = os.path.join(dst, 'config', 'config.ini')
        with open(config_path, 'r', newline='\n') as f:
            config_content = f.read()

        def escape(string):
            return string.replace('\\', '\\\\')

        config_content = re.sub(
            r'^write-data=.*$',
            f'write-data={escape(os.path.abspath(dst))}',
            config_content,
            flags=re.MULTILINE
        )

        with open(config_path, 'w', newline='\n') as f:
            f.write(config_content)

def find_factorio():
    """Look for the factorio executable"""
    if os.environ["FACTORIO"]:
        return os.environ["FACTORIO"]

    dir = os.getcwd()
    while True:
        exe = os.path.join(dir, 'bin', 'x64', 'factorio.exe')
        if os.path.exists(exe):
            return exe

        parent = os.path.normpath(os.path.join(dir, '..'))
        if parent == dir:
            break
        dir = parent

    raise RuntimeError(
        "Unable to locate factorio executable, specify it with --factorio"
    )

def spawn(args):
    spawn_one(args.path, args)

def spawn_multi(args):
    instance_index = spawn_instance(1, args)
    for i in range(args.count - 1):
        time.sleep(args.delay)
        instance_index = spawn_instance(instance_index, args)

def spawn_instance(instance_index, args):
    while True:
        write_dir = os.path.join(args.instance_dirs, f'{args.prefix}{instance_index}')
        if not os.path.exists(os.path.join(write_dir, '.lock')):
            break
        instance_index += 1

    pid = spawn_one(write_dir, args)
    move_window(pid, instance_index, args.monitor, args.rows, args.cols)
    return instance_index + 1

def spawn_one(write_dir, args):
    disown = 'pyw -m hornwitser.factorio_tools.disown'
    factorio = args.factorio if args.factorio else find_factorio()
    cfg_path = os.path.join(write_dir, 'config', 'config.ini')
    extra_args = '' if not args.args else f' {args.args}'
    spawn_result = subprocess.run(
        f'{disown} "{factorio} --config {cfg_path}{extra_args}"',
        capture_output=True, text=True
    )
    pid = int(spawn_result.stdout)
    if args.title:
        hWnd = find_main_window(pid, 20)
        if hWnd:
            set_title(hWnd, args.title)

    return pid


# --- Windows API interactions -----------------------------------------

DWORD = ctypes.c_ulong
WORD = ctypes.c_short
BOOL = ctypes.c_long
ULONG = ctypes.c_ulong
LONG = ctypes.c_long
UINT = ctypes.c_uint

HANDLE = ctypes.c_void_p
HDC = HANDLE
HMONITOR = HANDLE

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

class RECT(ctypes.Structure):
    _fields_ = [
        ('left', LONG),
        ('top', LONG),
        ('right', LONG),
        ('bottom', LONG),
    ]

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', DWORD),
        ('rcMonitor', RECT),
        ('rcWork', RECT),
        ('dwFlags', DWORD),
    ]

MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_LEFTDOWN    = 0x0002
MOUSEEVENTF_LEFTUP      = 0x0004
MOUSEEVENTF_RIGHTDOWN   = 0x0008
MOUSEEVENTF_RIGHTUP     = 0x0010
MOUSEEVENTF_MIDDLEDOWN  = 0x0020
MOUSEEVENTF_MIDDLEUP    = 0x0040
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE    = 0x8000

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', LONG),
        ('dy', LONG),
        ('mouseData', DWORD),
        ('dwFlags', DWORD),
        ('time', DWORD),
        ('dwExtraInfo', ctypes.POINTER(ULONG)),
    ]

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_SCANCODE    = 0x0008
KEYEVENT_UNICODE      = 0x0004

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', WORD),
        ('wScan', WORD),
        ('dwFlags', DWORD),
        ('time', DWORD),
        ('dwExtraInfo', ctypes.POINTER(ULONG))
    ]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 3

class INPUT_I(ctypes.Union):
    _fields_ = [
        ('mi', MOUSEINPUT),
        ('ki', KEYBDINPUT),
        # ('hi', HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ("ii",)
    _fields_ = [
        ('type', DWORD),
        ('ii', INPUT_I),
    ]

MONITOR_DEFAULTTONULL = 0x0
MONITOR_DEFAULTTOPRIMARY = 0x1

MONITORENUMPROC = ctypes.WINFUNCTYPE(BOOL, HMONITOR, HDC, ctypes.POINTER(RECT), ctypes.c_void_p)

def get_monitor_handle(monitor):
    callback = MONITORENUMPROC(get_monitor_handle_callback)
    monitors = []
    user32.EnumDisplayMonitors(None, None, callback, ctypes.byref(ctypes.py_object(monitors)))
    clamped = max(1, min(len(monitors), monitor))
    if clamped != monitor:
        print(f"Warning: monitor index out of range [1-{len(monitors)}]")
    return monitors[clamped-1]

def get_monitor_handle_callback(hMonitor, hdc, p_rect, p_void):
    monitors = ctypes.cast(p_void, ctypes.POINTER(ctypes.py_object))[0]
    monitors.append(hMonitor)
    return True

def get_monitor_info(hMonitor):
    info = MONITORINFO(ctypes.sizeof(MONITORINFO))
    success = user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))
    if not success:
        raise RuntimeError("Failed to get monitor info")

    return info

# Ported from https://stackoverflow.com/a/21767578
class MainWindowData(ctypes.Structure):
    _fields_ = [
        ('pid', DWORD),
        ('hWnd', DWORD),
    ]

WNDENUMPROC = ctypes.WINFUNCTYPE(BOOL, DWORD, ctypes.c_void_p)

def find_main_window(pid, tries):
    data = MainWindowData(pid, 0)
    callback = WNDENUMPROC(find_main_window_callback)
    for i in range(tries):
        user32.EnumWindows(callback, ctypes.byref(data))
        if data.hWnd:
            break
        time.sleep(0.1)
    return data.hWnd

def find_main_window_callback(hWnd, p_void):
    p_data = ctypes.cast(p_void, ctypes.POINTER(MainWindowData))
    pid = DWORD()
    user32.GetWindowThreadProcessId(hWnd, ctypes.byref(pid))
    if (pid.value != p_data[0].pid or not is_main_window(hWnd)):
        return True
    p_data[0].hWnd = hWnd
    return False

def is_main_window(hWnd):
    return user32.GetWindow(hWnd, 4) == 0 and user32.IsWindowVisible(hWnd)

def set_title(hWnd, text):
    user32.SetWindowTextW(hWnd, text)

FindWindowData = collections.namedtuple('FindWindowData', 'name hWnds')

def find_windows(name):
    """Find Windows who's title starts with name"""
    data = FindWindowData(name, [])
    callback = WNDENUMPROC(find_windows_callback)
    user32.EnumWindows(callback, ctypes.byref(ctypes.py_object(data)))
    return data.hWnds

def find_windows_callback(hWnd, p_void):
    data = ctypes.cast(p_void, ctypes.POINTER(ctypes.py_object))[0]
    if (not is_main_window(hWnd)):
        return True

    buffer = ctypes.create_unicode_buffer(200)
    user32.GetWindowTextW(hWnd, ctypes.byref(buffer), 200)
    name = ctypes.wstring_at(buffer)
    if (name.startswith(data.name)):
        data.hWnds.append(hWnd)

    return True

class POINT(ctypes.Structure):
    _fields_ = [
        ('x', LONG),
        ('y', LONG),
    ]

SW_MAXIMIZE = 3
SW_RESTORE = 9

class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ('length', UINT),
        ('flags', UINT),
        ('showCmd', UINT),
        ('ptMinPosition', POINT),
        ('ptMaxPosition', POINT),
        ('rcNormalPosition', RECT),
        ('rcDevice', RECT),
    ]

WM_SYSCOMMAND = 0x0112
SC_RESTORE = 0xf120

def ensure_not_maximized(hWnd):
    window_placement = WINDOWPLACEMENT(ctypes.sizeof(WINDOWPLACEMENT))
    user32.GetWindowPlacement(hWnd, ctypes.byref(window_placement))

    if window_placement.showCmd == SW_MAXIMIZE:
        user32.SendMessageW(hWnd, WM_SYSCOMMAND, SC_RESTORE, 0)

def move_window(pid, instance_index, monitor, rows, cols):
    hWnd = find_main_window(pid, 20)
    if not hWnd:
        raise RuntimeError("Unable to find Factorio window")

    ensure_not_maximized(hWnd)
    if monitor is None:
        hMonitor = user32.MonitorFromWindow(hWnd, MONITOR_DEFAULTTOPRIMARY)
    else:
        hMonitor = get_monitor_handle(monitor)
    rcWork = get_monitor_info(hMonitor).rcWork
    width = (rcWork.right - rcWork.left) // cols
    height = (rcWork.bottom - rcWork.top) // rows
    right = rcWork.right - (((instance_index - 1) // rows + 1) * width)
    top = rcWork.top + ((instance_index - 1) % rows * height)

    user32.MoveWindow(hWnd, right, top, width, height, False)


def window_to_virtual(hWnd, x, y):
    rect = RECT()
    if not user32.GetWindowRect(hWnd, ctypes.byref(rect)):
        raise RuntimeError("Unable to get size of window")
    return x + rect.left, y + rect.top

def click_window(hWnd, x, y):
    flags = (
        MOUSEEVENTF_LEFTDOWN
        | MOUSEEVENTF_LEFTUP
    )
    x, y = window_to_virtual(hWnd, x, y)
    user32.SetCursorPos(x, y)
    user32.SetCursorPos(x, y) # Make sure it actually moves
    mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
    input = INPUT(INPUT_MOUSE, mi=mi)
    user32.SendInput(1, ctypes.byref(input), ctypes.sizeof(INPUT))

def click(args):
    factorio_windows = find_windows("Factorio")
    for hWnd in factorio_windows:
        click_window(hWnd, args.x, args.y)
        time.sleep(0.1)

vk_codes = {
    'LBUTTON': 0x01, 'RBUTTON': 0x02,
    'CANCEL': 0x03,
    'MBUTTON': 0x04,
    'XBUTTON1': 0x05,
    'XBUTTON2': 0x06,
    'BACK': 0x08,
    'TAB': 0x09,
    'CLEAR': 0x0C,
    'RETURN': 0x0D,
    'SHIFT': 0x10,
    'CONTROL': 0x11,
    'MENU': 0x12,
    'PAUSE': 0x13,
    'CAPITAL': 0x14,
    'KANA': 0x15,
    'HANGUEL': 0x15,
    'HANGUL': 0x15,
    'IME_ON': 0x16,
    'JUNJA': 0x17,
    'FINAL': 0x18,
    'HANJA': 0x19,
    'KANJI': 0x19,
    'IME_OFF': 0x1A,
    'ESCAPE': 0x1B,
    'CONVERT': 0x1C,
    'NONCONVERT': 0x1D,
    'ACCEPT': 0x1E,
    'MODECHANGE': 0x1F,
    'SPACE': 0x20,
    'PRIOR': 0x21,
    'NEXT': 0x22,
    'END': 0x23,
    'HOME': 0x24,
    'LEFT': 0x25,
    'UP': 0x26,
    'RIGHT': 0x27,
    'DOWN': 0x28,
    'SELECT': 0x29,
    'PRINT': 0x2A,
    'EXECUTE': 0x2B,
    'SNAPSHOT': 0x2C,
    'INSERT': 0x2D,
    'DELETE': 0x2E,
    'HELP': 0x2F,
    '0': 0x30,
    '1': 0x31,
    '2': 0x32,
    '3': 0x33,
    '4': 0x34,
    '5': 0x35,
    '6': 0x36,
    '7': 0x37,
    '8': 0x38,
    '9': 0x39,
    'A': 0x41,
    'B': 0x42,
    'C': 0x43,
    'D': 0x44,
    'E': 0x45,
    'F': 0x46,
    'G': 0x47,
    'H': 0x48,
    'I': 0x49,
    'J': 0x4A,
    'K': 0x4B,
    'L': 0x4C,
    'M': 0x4D,
    'N': 0x4E,
    'O': 0x4F,
    'P': 0x50,
    'Q': 0x51,
    'R': 0x52,
    'S': 0x53,
    'T': 0x54,
    'U': 0x55,
    'V': 0x56,
    'W': 0x57,
    'X': 0x58,
    'Y': 0x59,
    'Z': 0x5A,
    'LWIN': 0x5B,
    'RWIN': 0x5C,
    'APPS': 0x5D,
    '-': 0x5E,
    'SLEEP': 0x5F,
    'NUMPAD0': 0x60,
    'NUMPAD1': 0x61,
    'NUMPAD2': 0x62,
    'NUMPAD3': 0x63,
    'NUMPAD4': 0x64,
    'NUMPAD5': 0x65,
    'NUMPAD6': 0x66,
    'NUMPAD7': 0x67,
    'NUMPAD8': 0x68,
    'NUMPAD9': 0x69,
    'MULTIPLY': 0x6A,
    'ADD': 0x6B,
    'SEPARATOR': 0x6C,
    'SUBTRACT': 0x6D,
    'DECIMAL': 0x6E,
    'DIVIDE': 0x6F,
    'F1': 0x70,
    'F2': 0x71,
    'F3': 0x72,
    'F4': 0x73,
    'F5': 0x74,
    'F6': 0x75,
    'F7': 0x76,
    'F8': 0x77,
    'F9': 0x78,
    'F10': 0x79,
    'F11': 0x7A,
    'F12': 0x7B,
    'F13': 0x7C,
    'F14': 0x7D,
    'F15': 0x7E,
    'F16': 0x7F,
    'F17': 0x80,
    'F18': 0x81,
    'F19': 0x82,
    'F20': 0x83,
    'F21': 0x84,
    'F22': 0x85,
    'F23': 0x86,
    'F24': 0x87,
    'NUMLOCK': 0x90,
    'SCROLL': 0x91,
    'LSHIFT': 0xA0,
    'RSHIFT': 0xA1,
    'LCONTROL': 0xA2,
    'RCONTROL': 0xA3,
    'LMENU': 0xA4,
    'RMENU': 0xA5,
    'BROWSER_BACK': 0xA6,
    'BROWSER_FORWARD': 0xA7,
    'BROWSER_REFRESH': 0xA8,
    'BROWSER_STOP': 0xA9,
    'BROWSER_SEARCH': 0xAA,
    'BROWSER_FAVORITES': 0xAB,
    'BROWSER_HOME': 0xAC,
    'VOLUME_MUTE': 0xAD,
    'VOLUME_DOWN': 0xAE,
    'VOLUME_UP': 0xAF,
    'MEDIA_NEXT_TRACK': 0xB0,
    'MEDIA_PREV_TRACK': 0xB1,
    'MEDIA_STOP': 0xB2,
    'MEDIA_PLAY_PAUSE': 0xB3,
    'LAUNCH_MAIL': 0xB4,
    'LAUNCH_MEDIA_SELECT': 0xB5,
    'LAUNCH_APP1': 0xB6,
    'LAUNCH_APP2': 0xB7,
    'OEM_1': 0xBA,
    'OEM_PLUS': 0xBB,
    'OEM_COMMA': 0xBC,
    'OEM_MINUS': 0xBD,
    'OEM_PERIOD': 0xBE,
    'OEM_2': 0xBF,
    'OEM_3': 0xC0,
    'OEM_4': 0xDB,
    'OEM_5': 0xDC,
    'OEM_6': 0xDD,
    'OEM_7': 0xDE,
    'OEM_8': 0xDF,
    'OEM_102': 0xE2,
    'PROCESSKEY': 0xE5,
    'ATTN': 0xF6,
    'CRSEL': 0xF7,
    'EXSEL': 0xF8,
    'EREOF': 0xF9,
    'PLAY': 0xFA,
    'ZOOM': 0xFB,
    'NONAME': 0xFC,
    'PA1': 0xFD,
    'OEM_CLEAR': 0xFE,
}

def key_window(hWnd, vks, scans):
    this_id = kernel32.GetCurrentThreadId()
    target_id = user32.GetWindowThreadProcessId(hWnd, None)
    user32.AttachThreadInput(this_id, target_id, True)
    user32.SetForegroundWindow(hWnd)
    user32.AttachThreadInput(this_id, target_id, False)

    inputs = []
    for vk, scan in reversed(list(zip(vks, scans))):
        inputs.insert(0, INPUT(INPUT_KEYBOARD, ki=KEYBDINPUT(vk, scan)))
        inputs.append(INPUT(INPUT_KEYBOARD, ki=KEYBDINPUT(vk, scan, KEYEVENTF_KEYUP)))

    inputs = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), ctypes.byref(inputs), ctypes.sizeof(INPUT))

def key(args):
    factorio_windows = find_windows("Factorio")
    for key in args.keys:
        vks = list(map(lambda k: vk_codes[k.upper()], key.split("-")))
        scans = list(map(lambda vk: user32.MapVirtualKeyW(vk, 0), vks))
        for hWnd in factorio_windows:
            key_window(hWnd, vks, scans)
            time.sleep(0.01)
