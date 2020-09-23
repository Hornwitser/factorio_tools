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
    move_window(pid, instance_index, args.rows, args.cols)
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
BOOL = ctypes.c_long
ULONG = ctypes.c_ulong
LONG = ctypes.c_long
UINT = ctypes.c_uint

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


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 3

class INPUT_I(ctypes.Union):
    _fields_ = [
        ('mi', MOUSEINPUT),
        # ('ki', KEYBDINPUT),
        # ('hi', HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ("ii",)
    _fields_ = [
        ('type', DWORD),
        ('ii', INPUT_I),
    ]
MONITOR_DEFAULTTOPRIMARY = 0x1

def get_monitor_work_area(hWnd):
    hMonitor = user32.MonitorFromWindow(hWnd, MONITOR_DEFAULTTOPRIMARY)
    info = MONITORINFO(ctypes.sizeof(MONITORINFO))
    success = user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))
    if not success:
        raise RuntimeError("Failed to get monitor info")

    return info.rcWork

# Ported from https://stackoverflow.com/a/21767578
class MainWindowData(ctypes.Structure):
    _fields_ = [
        ('pid', DWORD),
        ('hWnd', DWORD),
    ]

WNDENUMPROC = ctypes.WINFUNCTYPE(BOOL, DWORD, ctypes.POINTER(ctypes.c_void_p))

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

def move_window(pid, instance_index, rows, cols):
    hWnd = find_main_window(pid, 20)
    if not hWnd:
        raise RuntimeError("Unable to find Factorio window")

    ensure_not_maximized(hWnd)
    rcWork = get_monitor_work_area(hWnd)
    width = (rcWork.right - rcWork.left) // cols
    height = (rcWork.bottom - rcWork.top) // rows
    right = rcWork.right - (((instance_index - 1) // rows + 1) * width)
    top = rcWork.top + ((instance_index - 1) % rows * height)

    user32.MoveWindow(hWnd, right, top, width, height, False)

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

Size = collections.namedtuple('Size', 'x y width height')
virtual_size = None

def get_virtual_size():
    return Size(
        user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    )

def to_virtual(x, y):
    global virtual_size
    if not virtual_size:
        virtual_size = get_virtual_size()

    x = (x - virtual_size.x) * (2**16 - 1) // virtual_size.width
    y = (y - virtual_size.y) * (2**16 - 1) // virtual_size.height
    return x, y

def click_window(hWnd, x, y):
    rect = RECT()
    if not user32.GetWindowRect(hWnd, ctypes.byref(rect)):
        raise RuntimeError("Unable to get size of window")

    flags = (
        MOUSEEVENTF_MOVE
        | MOUSEEVENTF_LEFTDOWN
        | MOUSEEVENTF_LEFTUP
        | MOUSEEVENTF_ABSOLUTE
    )
    x, y = to_virtual(rect.left + x, rect.top + y)
    mi = MOUSEINPUT(x, y, 0, flags, 0, None)
    input = INPUT(INPUT_MOUSE, mi=mi)
    user32.SendInput(1, ctypes.byref(input), ctypes.sizeof(INPUT))

def click(args):
    factorio_windows = find_windows("Factorio")
    for hWnd in factorio_windows:
        click_window(hWnd, args.x, args.y)
        time.sleep(0.1)
