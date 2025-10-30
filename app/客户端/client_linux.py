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
import hashlib
import uuid

SERVER_IP = '192.168.55.102'
SERVER_PORT = 2383

# 发送加锁，避免多线程发送数据时内容交叉
SEND_LOCK = threading.Lock()

# ========== 连接码机制和设备识别 ==========

def get_hardware_id():
    """获取Linux系统的硬件ID"""
    try:
        # Linux: 优先获取机器ID
        try:
            with open('/etc/machine-id', 'r') as f:
                machine_id = f.read().strip()
                if machine_id:
                    return machine_id
        except:
            pass
        
        # 备选方案：dbus机器ID
        try:
            with open('/var/lib/dbus/machine-id', 'r') as f:
                machine_id = f.read().strip()
                if machine_id:
                    return machine_id
        except:
            pass
        
        # 备选方案：通过DMI获取系统UUID
        try:
            with open('/sys/class/dmi/id/product_uuid', 'r') as f:
                uuid_str = f.read().strip()
                if uuid_str and uuid_str != '00000000-0000-0000-0000-000000000000':
                    return uuid_str
        except:
            pass
        
        # 备选方案：主板序列号
        try:
            with open('/sys/class/dmi/id/board_serial', 'r') as f:
                serial = f.read().strip()
                if serial and serial.lower() not in ['none', 'to be filled by o.e.m.']:
                    return serial
        except:
            pass
            
    except Exception as e:
        print(f"[警告] 获取硬件ID失败: {e}")

    # 如果无法获取硬件ID，生成一个基于MAC地址的ID
    try:
        mac = get_mac_address()
        if mac:
            return hashlib.md5(mac.encode()).hexdigest()
    except:
        pass
    
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

# ========== 桌面环境检测和实时屏幕监控 ==========

def detect_desktop_environment():
    """检测Linux桌面环境是否可用"""
    try:
        # 检查DISPLAY环境变量
        display = os.environ.get('DISPLAY')
        if not display:
            return False, "未检测到DISPLAY环境变量，可能没有图形界面"
        
        # 检查是否可以连接到X服务器
        try:
            import subprocess
            result = subprocess.run(['xdpyinfo'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False, "无法连接到X服务器"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # 尝试使用其他方法检测
            try:
                result = subprocess.run(['echo', '$DISPLAY'], capture_output=True, text=True, timeout=2)
                if not result.stdout.strip():
                    return False, "DISPLAY变量为空"
            except:
                return False, "无法验证图形环境"
        
        # 检查常见的截图工具
        screenshot_tools = ['scrot', 'gnome-screenshot', 'import', 'xwd']
        available_tools = []
        
        for tool in screenshot_tools:
            try:
                result = subprocess.run(['which', tool], capture_output=True, timeout=2)
                if result.returncode == 0:
                    available_tools.append(tool)
            except:
                continue
        
        if not available_tools:
            return False, "未找到可用的截图工具 (scrot, gnome-screenshot, imagemagick, xwd)"
        
        return True, f"桌面环境可用，DISPLAY={display}，可用截图工具: {', '.join(available_tools)}"
        
    except Exception as e:
        return False, f"检测桌面环境时出错: {e}"


def take_screenshot_linux():
    """Linux系统截图函数，尝试多种截图方法"""
    try:
        # 首先检查桌面环境
        desktop_available, message = detect_desktop_environment()
        if not desktop_available:
            raise Exception(f"桌面环境不可用: {message}")
        
        # 尝试多种截图方法
        screenshot_methods = [
            ('scrot', ['scrot', '-z', '-']),  # scrot输出到stdout
            ('gnome-screenshot', ['gnome-screenshot', '-f', '/tmp/screenshot.png']),
            ('import', ['import', '-window', 'root', '/tmp/screenshot.png']),  # ImageMagick
            ('xwd', ['xwd', '-root', '-out', '/tmp/screenshot.xwd'])
        ]
        
        for method_name, cmd in screenshot_methods:
            try:
                if method_name == 'scrot' and '-' in cmd:
                    # scrot直接输出到stdout
                    result = subprocess.run(cmd, capture_output=True, timeout=10)
                    if result.returncode == 0 and result.stdout:
                        from PIL import Image
                        from io import BytesIO
                        img = Image.open(BytesIO(result.stdout))
                        return img
                else:
                    # 其他方法输出到临时文件
                    temp_file = '/tmp/screenshot.png'
                    if method_name == 'xwd':
                        temp_file = '/tmp/screenshot.xwd'
                    
                    # 清理可能存在的临时文件
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    
                    result = subprocess.run(cmd, capture_output=True, timeout=10)
                    if result.returncode == 0 and os.path.exists(temp_file):
                        from PIL import Image
                        
                        if method_name == 'xwd':
                            # 转换xwd格式到png
                            convert_cmd = ['convert', temp_file, '/tmp/screenshot.png']
                            convert_result = subprocess.run(convert_cmd, capture_output=True, timeout=5)
                            if convert_result.returncode == 0:
                                temp_file = '/tmp/screenshot.png'
                        
                        img = Image.open(temp_file)
                        # 清理临时文件
                        try:
                            os.remove(temp_file)
                            if os.path.exists('/tmp/screenshot.xwd'):
                                os.remove('/tmp/screenshot.xwd')
                        except:
                            pass
                        return img
                        
            except subprocess.TimeoutExpired:
                print(f"[警告] {method_name} 截图超时")
                continue
            except Exception as e:
                print(f"[警告] {method_name} 截图失败: {e}")
                continue
        
        # 所有方法都失败
        raise Exception("所有截图方法都失败")
        
    except Exception as e:
        print(f"[错误] Linux截图失败: {e}")
        raise


# ========== 实时屏幕流（Linux） ==========

# 全局变量
SEND_LOCK = threading.Lock()

# 屏幕流相关全局变量
_screen_thread = None
_screen_stop_event = threading.Event()

# 混合式视频流控制变量
_hybrid_stream_enabled = False
_base_layer_thread = None
_enhancement_layer_thread = None
_base_layer_stop_event = threading.Event()
_enhancement_layer_stop_event = threading.Event()

def _screen_stream_loop_linux(sock, stop_event, fps=15, quality=60, max_width=1280):
    """Linux实时屏幕流循环"""
    import time
    from io import BytesIO
    from PIL import Image
    
    try:
        # 检查桌面环境
        desktop_available, message = detect_desktop_environment()
        if not desktop_available:
            print(f"[错误] 无法启动屏幕流: {message}")
            reliable_send(sock, {"output": f"屏幕流启动失败: {message}"})
            return
        
        print(f"[屏幕流] Linux屏幕流启动: {max_width}px @ {fps}fps, 质量={quality}")
        print(f"[屏幕流] {message}")
        
        target_frame_time = 1.0 / fps
        frame_count = 0
        start_time = time.time()
        last_stats_time = start_time
        
        # 性能统计变量
        total_screenshot_time = 0
        total_scale_time = 0
        total_encode_time = 0
        total_send_time = 0
        
        # 自适应质量控制
        performance_samples = []
        quality_adjustment = 0
        last_quality_check = start_time
        
        while not stop_event.is_set():
            frame_start = time.time()
            
            # 截图
            screenshot_start = time.time()
            try:
                screenshot = take_screenshot_linux()
            except Exception as e:
                print(f"[错误] Linux截图失败: {e}")
                time.sleep(1.0)  # 截图失败时等待更长时间
                continue
            
            screenshot_time = (time.time() - screenshot_start) * 1000
            
            # 缩放处理
            scale_start = time.time()
            original_size = screenshot.size
            
            if original_size[0] > max_width:
                target_size = (max_width, int(original_size[1] * max_width / original_size[0]))
                screenshot = screenshot.resize(target_size, Image.LANCZOS)
            
            scale_time = (time.time() - scale_start) * 1000
            
            # 自适应质量控制
            current_time = time.time()
            frame_process_time = current_time - frame_start
            
            performance_samples.append(frame_process_time)
            if len(performance_samples) > 10:
                performance_samples.pop(0)
            
            # 每5秒检查一次性能并调整质量
            if current_time - last_quality_check > 5.0 and len(performance_samples) >= 5:
                avg_frame_time = sum(performance_samples) / len(performance_samples)
                
                if avg_frame_time > target_frame_time * 1.3:
                    quality_adjustment = min(quality_adjustment + 5, 20)
                elif avg_frame_time < target_frame_time * 0.8:
                    quality_adjustment = max(quality_adjustment - 2, 0)
                
                last_quality_check = current_time
            
            # 编码
            encode_start = time.time()
            adjusted_quality = max(25, quality - quality_adjustment)
            
            from io import BytesIO
            buffer = BytesIO()
            screenshot.save(buffer, format='JPEG', quality=adjusted_quality, optimize=False)
            img_data = buffer.getvalue()
            buffer.close()
            
            encode_time = (time.time() - encode_start) * 1000
            
            # 发送数据
            send_start = time.time()
            try:
                frame_data = {
                    "type": "screen_frame",
                    "data": base64.b64encode(img_data).decode('utf-8'),
                    "w": screenshot.size[0],
                    "h": screenshot.size[1],
                    "vx": 0,  # Linux暂时不支持虚拟屏幕信息
                    "vy": 0,
                    "vw": screenshot.size[0],
                    "vh": screenshot.size[1]
                }
                reliable_send(sock, frame_data)
            except Exception as e:
                print(f"[错误] 发送屏幕帧失败: {e}")
                break
            
            send_time = (time.time() - send_start) * 1000
            
            # 更新统计
            frame_count += 1
            total_screenshot_time += screenshot_time
            total_scale_time += scale_time
            total_encode_time += encode_time
            total_send_time += send_time
            
            # 性能统计输出
            current_time = time.time()
            if current_time - last_stats_time >= 5.0:
                elapsed = current_time - start_time
                actual_fps = frame_count / elapsed
                avg_screenshot = total_screenshot_time / frame_count
                avg_scale = total_scale_time / frame_count
                avg_encode = total_encode_time / frame_count
                avg_send = total_send_time / frame_count
                
                print(f"[性能统计] 实际FPS: {actual_fps:.1f} | 截图: {avg_screenshot:.1f}ms | 缩放: {avg_scale:.1f}ms | 编码: {avg_encode:.1f}ms | 发送: {avg_send:.1f}ms")
                
                if actual_fps < fps * 0.5:
                    print(f"[警告] 性能严重下降，实际FPS({actual_fps:.1f}) < 目标FPS({fps}) * 50%")
                
                last_stats_time = current_time
            
            # 帧率控制
            elapsed_frame_time = time.time() - frame_start
            sleep_time = target_frame_time - elapsed_frame_time
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    except Exception as e:
        print(f"[错误] Linux屏幕流异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[屏幕流] Linux屏幕流已停止")


# ========== 鼠标键盘控制（Linux） ==========

def handle_mouse_linux(arg, state):
    """处理Linux鼠标事件"""
    try:
        # 检查桌面环境
        desktop_available, message = detect_desktop_environment()
        if not desktop_available:
            return {"output": f"鼠标控制不可用: {message}"}
        
        if not arg:
            return {"output": "mouse 命令缺少参数"}
        
        parts = str(arg).split()
        if not parts:
            return {"output": "mouse 命令参数无效"}
        
        action = parts[0].lower()
        
        # 尝试多种鼠标控制方法
        control_methods = []
        
        # 方法1：尝试xdotool
        try:
            subprocess.run(['which', 'xdotool'], capture_output=True, check=True, timeout=2)
            control_methods.append('xdotool')
        except:
            pass
        
        # 方法2：尝试uinput
        try:
            import uinput
            control_methods.append('uinput')
        except ImportError:
            pass
        
        # 方法3：尝试evemu
        try:
            subprocess.run(['which', 'evemu-event'], capture_output=True, check=True, timeout=2)
            control_methods.append('evemu')
        except:
            pass
        
        # 方法4：直接写入设备文件
        if _find_mouse_device():
            control_methods.append('direct')
        
        if not control_methods:
            return {"output": "未找到可用的鼠标控制方法。建议安装: xdotool, python-uinput, evemu-tools"}
        
        # 解析参数
        if action == 'move' and len(parts) >= 3:
            try:
                x = int(float(parts[1]))
                y = int(float(parts[2]))
                
                # 尝试各种控制方法
                for method in control_methods:
                    if method == 'xdotool':
                        try:
                            result = subprocess.run(['xdotool', 'mousemove', str(x), str(y)], 
                                                  capture_output=True, timeout=5)
                            if result.returncode == 0:
                                return {"output": f"鼠标移动到 ({x},{y}) [xdotool]"}
                        except:
                            continue
                    
                    elif method == 'uinput':
                        success, msg = _control_mouse_uinput('move', x, y)
                        if success:
                            return {"output": f"鼠标移动到 ({x},{y}) [uinput]"}
                    
                    elif method == 'evemu':
                        success, msg = _control_mouse_evemu('move', x, y)
                        if success:
                            return {"output": f"鼠标移动到 ({x},{y}) [evemu]"}
                    
                    elif method == 'direct':
                        success, msg = _control_mouse_direct('move', x, y)
                        if success:
                            return {"output": f"鼠标移动到 ({x},{y}) [direct]"}
                
                return {"output": f"所有鼠标控制方法都失败"}
                
            except Exception as e:
                return {"output": f"鼠标移动失败: {e}"}
        
        elif action in ('down', 'up', 'click') and len(parts) >= 2:
            btn = parts[1].lower()
            
            if btn not in ['left', 'right', 'middle']:
                return {"output": f"未知按键: {btn}"}
            
            # 尝试各种控制方法
            for method in control_methods:
                if method == 'xdotool':
                    try:
                        btn_map = {'left': '1', 'right': '3', 'middle': '2'}
                        if action == 'down':
                            cmd = ['xdotool', 'mousedown', btn_map[btn]]
                        elif action == 'up':
                            cmd = ['xdotool', 'mouseup', btn_map[btn]]
                        else:  # click
                            cmd = ['xdotool', 'click', btn_map[btn]]
                        
                        result = subprocess.run(cmd, capture_output=True, timeout=5)
                        if result.returncode == 0:
                            return {"output": f"鼠标{action} {btn} [xdotool]"}
                    except:
                        continue
                
                elif method == 'uinput':
                    success, msg = _control_mouse_uinput(action, button=btn)
                    if success:
                        return {"output": f"鼠标{action} {btn} [uinput]"}
                
                elif method == 'evemu':
                    success, msg = _control_mouse_evemu(action, button=btn)
                    if success:
                        return {"output": f"鼠标{action} {btn} [evemu]"}
                
                elif method == 'direct':
                    success, msg = _control_mouse_direct(action, button=btn)
                    if success:
                        return {"output": f"鼠标{action} {btn} [direct]"}
            
            return {"output": f"所有鼠标{action}方法都失败"}
        
        elif action == 'wheel' and len(parts) >= 2:
            try:
                delta = int(float(parts[1]))
                if delta == 0:
                    return {"output": "滚轮 delta=0 被忽略"}
                
                # 尝试各种控制方法
                for method in control_methods:
                    if method == 'xdotool':
                        try:
                            # xdotool滚轮：4=向上，5=向下
                            btn = '4' if delta > 0 else '5'
                            scroll_count = max(1, abs(delta) // 120)
                            
                            for _ in range(scroll_count):
                                result = subprocess.run(['xdotool', 'click', btn], 
                                                      capture_output=True, timeout=2)
                                if result.returncode != 0:
                                    break
                            else:
                                return {"output": f"滚轮 {delta} [xdotool]"}
                        except:
                            continue
                    
                    elif method == 'uinput':
                        success, msg = _control_mouse_uinput('wheel', delta=delta)
                        if success:
                            return {"output": f"滚轮 {delta} [uinput]"}
                    
                    elif method == 'evemu':
                        success, msg = _control_mouse_evemu('wheel', delta=delta)
                        if success:
                            return {"output": f"滚轮 {delta} [evemu]"}
                    
                    elif method == 'direct':
                        success, msg = _control_mouse_direct('wheel', delta=delta)
                        if success:
                            return {"output": f"滚轮 {delta} [direct]"}
                
                return {"output": f"所有滚轮控制方法都失败"}
                
            except Exception as e:
                return {"output": f"滚轮操作失败: {e}"}
        
        return {"output": f"不支持的 mouse 子命令: {action}"}
        
    except Exception as e:
        return {"output": f"mouse 执行失败: {e}"}


def handle_key_linux(arg, state):
    """处理Linux键盘事件"""
    try:
        # 检查桌面环境
        desktop_available, message = detect_desktop_environment()
        if not desktop_available:
            return {"output": f"键盘控制不可用: {message}"}
        
        if not arg:
            return {"output": "key 命令缺少参数"}
        
        parts = str(arg).split()
        if not parts:
            return {"output": "key 命令参数无效"}
        
        action = parts[0].lower()
        key = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        # 检查xdotool是否可用
        try:
            subprocess.run(['which', 'xdotool'], capture_output=True, check=True, timeout=2)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return {"output": "键盘控制需要安装xdotool工具"}
        
        # 键名映射
        key_map = {
            'Enter': 'Return',
            'Escape': 'Escape',
            'Backspace': 'BackSpace',
            'Tab': 'Tab',
            'Space': 'space',
            ' ': 'space',
            'Shift': 'shift',
            'Control': 'ctrl',
            'Alt': 'alt',
            'ArrowLeft': 'Left',
            'ArrowUp': 'Up',
            'ArrowRight': 'Right',
            'ArrowDown': 'Down'
        }
        
        # 处理VK_前缀
        if key.upper().startswith('VK_'):
            vk_name = key.upper().replace('VK_', '')
            if vk_name == 'RETURN':
                key = 'Return'
            elif vk_name == 'ESCAPE':
                key = 'Escape'
            elif vk_name == 'BACK':
                key = 'BackSpace'
            elif vk_name == 'SPACE':
                key = 'space'
            elif vk_name == 'SHIFT':
                key = 'shift'
            elif vk_name == 'CONTROL':
                key = 'ctrl'
            elif vk_name == 'MENU':
                key = 'alt'
            else:
                key = vk_name.lower()
        else:
            # 应用键名映射
            key = key_map.get(key, key)
        
        try:
            if action == 'down':
                cmd = ['xdotool', 'keydown', key]
            elif action == 'up':
                cmd = ['xdotool', 'keyup', key]
            elif action == 'press':
                cmd = ['xdotool', 'key', key]
            else:
                return {"output": f"不支持的 key 子命令: {action}"}
            
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0:
                return {"output": f"key {action} {key}"}
            else:
                return {"output": f"key {action}失败: {result.stderr.decode()}"}
                
        except Exception as e:
            return {"output": f"key 执行失败: {e}"}
        
    except Exception as e:
        return {"output": f"key 执行失败: {e}"}


def handle_start_screen_linux(arg, state):
    """启动Linux屏幕流"""
    global _screen_thread, _screen_stop_event
    
    # 检查桌面环境
    desktop_available, message = detect_desktop_environment()
    if not desktop_available:
        return {"output": f"无法启动屏幕流: {message}"}
    
    if _screen_thread and _screen_thread.is_alive():
        return {"output": "屏幕流已在运行"}
    
    # 解析参数
    params = {}
    if arg:
        try:
            for pair in str(arg).split(','):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    params[k.strip()] = v.strip()
        except Exception:
            pass
    
    fps = int(params.get('fps', 15))
    quality = int(params.get('quality', 60))
    max_width = int(params.get('width', 1280))
    
    # 限制参数范围
    fps = max(1, min(fps, 30))
    quality = max(25, min(quality, 95))
    max_width = max(640, min(max_width, 1920))
    
    try:
        _screen_stop_event.clear()
        _screen_thread = threading.Thread(
            target=_screen_stream_loop_linux,
            args=(state['socket'], _screen_stop_event, fps, quality, max_width),
            daemon=True
        )
        _screen_thread.start()
        
        return {"output": f"Linux屏幕流已启动: {max_width}px @ {fps}fps, 质量={quality}"}
    except Exception as e:
        return {"output": f"启动屏幕流失败: {e}"}


def handle_stop_screen_linux(arg, state):
    """停止Linux屏幕流"""
    global _screen_thread
    _screen_stop_event.set()
    if _screen_thread and _screen_thread.is_alive():
        _screen_thread.join(timeout=2)
    _screen_thread = None
    return {"output": "屏幕流已停止。"}


def _base_layer_stream_loop_linux(sock, stop_event, fps=8, quality=50, max_width=960):
    """Linux混合式视频流基础层循环"""
    import time
    from io import BytesIO
    from PIL import Image
    
    frame_interval = 1.0 / fps
    last_frame_time = 0
    
    print(f"[调试] Linux基础层流开始: fps={fps}, quality={quality}, max_width={max_width}")
    
    while not stop_event.is_set():
        try:
            current_time = time.time()
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.01)
                continue
            
            # 检查桌面环境
            desktop_available, message = detect_desktop_environment()
            if not desktop_available:
                print(f"[错误] 基础层流: {message}")
                break
            
            # 获取截图
            screenshot = take_screenshot_linux()
            
            # 调整图像大小
            original_width, original_height = screenshot.size
            if original_width > max_width:
                scale_factor = max_width / original_width
                new_width = max_width
                new_height = int(original_height * scale_factor)
                screenshot = screenshot.resize((new_width, new_height), Image.LANCZOS)
            
            # 压缩图像
            buffer = BytesIO()
            screenshot.save(buffer, format='JPEG', quality=quality, optimize=True)
            img_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            buffer.close()
            
            # 发送基础层数据
            frame_data = {
                "type": "base_layer_frame",
                "data": img_data,
                "width": screenshot.size[0],
                "height": screenshot.size[1],
                "timestamp": current_time
            }
            
            with SEND_LOCK:
                reliable_send(sock, frame_data)
            
            last_frame_time = current_time
            
        except Exception as e:
            print(f"[错误] Linux基础层流异常: {e}")
            time.sleep(0.1)
    
    print("[调试] Linux基础层流结束")


def _enhancement_layer_stream_loop_linux(sock, stop_event, fps=30, quality=70):
    """Linux混合式视频流增强层循环"""
    import time
    from io import BytesIO
    from PIL import Image
    
    frame_interval = 1.0 / fps
    last_frame_time = 0
    
    print(f"[调试] Linux增强层流开始: fps={fps}, quality={quality}")
    
    while not stop_event.is_set():
        try:
            current_time = time.time()
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.01)
                continue
            
            # 检查桌面环境
            desktop_available, message = detect_desktop_environment()
            if not desktop_available:
                print(f"[错误] 增强层流: {message}")
                break
            
            # 获取全分辨率截图
            screenshot = take_screenshot_linux()
            
            # 压缩图像
            buffer = BytesIO()
            screenshot.save(buffer, format='JPEG', quality=quality, optimize=True)
            img_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            buffer.close()
            
            # 发送增强层数据
            frame_data = {
                "type": "enhancement_layer_frame",
                "data": img_data,
                "width": screenshot.size[0],
                "height": screenshot.size[1],
                "timestamp": current_time
            }
            
            with SEND_LOCK:
                reliable_send(sock, frame_data)
            
            last_frame_time = current_time
            
        except Exception as e:
            print(f"[错误] Linux增强层流异常: {e}")
            time.sleep(0.1)
    
    print("[调试] Linux增强层流结束")


def handle_start_hybrid_screen_linux(arg, state):
    """启动Linux混合式屏幕流"""
    global _hybrid_stream_enabled, _base_layer_thread, _enhancement_layer_thread
    
    if _hybrid_stream_enabled:
        return {"output": "混合式屏幕流已在运行。"}
    
    # 检查桌面环境
    desktop_available, message = detect_desktop_environment()
    if not desktop_available:
        return {"output": f"混合式屏幕流不可用: {message}"}
    
    # 解析参数
    params = _parse_kv_arg(arg)
    base_fps = int(params.get('base_fps', '8'))
    base_quality = int(params.get('base_quality', '50'))
    base_width = int(params.get('base_width', '960'))
    enhancement_fps = int(params.get('enhancement_fps', '30'))
    enhancement_quality = int(params.get('enhancement_quality', '70'))
    
    try:
        # 重置停止事件
        _base_layer_stop_event.clear()
        _enhancement_layer_stop_event.clear()
        
        # 启动基础层线程
        _base_layer_thread = threading.Thread(
            target=_base_layer_stream_loop_linux,
            args=(state['socket'], _base_layer_stop_event, base_fps, base_quality, base_width),
            daemon=True
        )
        _base_layer_thread.start()
        
        # 启动增强层线程
        _enhancement_layer_thread = threading.Thread(
            target=_enhancement_layer_stream_loop_linux,
            args=(state['socket'], _enhancement_layer_stop_event, enhancement_fps, enhancement_quality),
            daemon=True
        )
        _enhancement_layer_thread.start()
        
        _hybrid_stream_enabled = True
        
        return {"output": f"Linux混合式屏幕流已启动 (基础层: {base_fps}fps/{base_quality}%/{base_width}px, 增强层: {enhancement_fps}fps/{enhancement_quality}%)"}
        
    except Exception as e:
        return {"output": f"启动Linux混合式屏幕流失败: {e}"}


def handle_stop_hybrid_screen_linux(arg, state):
    """停止Linux混合式屏幕流"""
    global _hybrid_stream_enabled, _base_layer_thread, _enhancement_layer_thread
    
    if not _hybrid_stream_enabled:
        return {"output": "混合式屏幕流未在运行。"}
    
    try:
        # 停止线程
        _base_layer_stop_event.set()
        _enhancement_layer_stop_event.set()
        
        # 等待线程结束
        if _base_layer_thread and _base_layer_thread.is_alive():
            _base_layer_thread.join(timeout=2)
        if _enhancement_layer_thread and _enhancement_layer_thread.is_alive():
            _enhancement_layer_thread.join(timeout=2)
        
        _base_layer_thread = None
        _enhancement_layer_thread = None
        _hybrid_stream_enabled = False
        
        return {"output": "Linux混合式屏幕流已停止。"}
        
    except Exception as e:
        return {"output": f"停止Linux混合式屏幕流失败: {e}"}


def reliable_send(sock, data_dict):
    """将字典可靠地编码为JSON并附加换行符后发送（线程安全）"""
    try:
        # 使用更快的JSON编码选项
        json_data = json.dumps(data_dict, separators=(',', ':'), ensure_ascii=False).encode('utf-8') + b'\n'
        with SEND_LOCK:
            # 设置TCP_NODELAY以减少延迟
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except:
                pass  # 忽略设置失败
            sock.sendall(json_data)
    except socket.error as e:
        print(f"[错误] 发送数据时发生Socket错误: {e}")
        raise


# --- command handlers (mapping) ---
def handle_cd(arg, state):
    if not arg:
        return {"output": "错误: 'cd' 需要目录参数。"}
    try:
        expanded_arg = os.path.expanduser(arg)
        os.chdir(expanded_arg)
        state['cwd'] = os.getcwd()
        return {"output": f"已切换目录到: {state['cwd']}"}
    except Exception as e:
        return {"output": f"切换目录错误: {e}"}


def handle_download(arg, state):
    if not arg:
        return {"output": "错误: 'download' 需要文件路径。"}
    expanded_arg = os.path.expanduser(arg)
    if os.path.exists(expanded_arg) and os.path.isfile(expanded_arg):
        try:
            with open(expanded_arg, 'rb') as f:
                encoded_content = base64.b64encode(f.read()).decode('utf-8')
            return {"file": os.path.basename(expanded_arg), "data": encoded_content, "source_path": expanded_arg}
        except Exception as e:
            return {"output": f"读取文件失败: {e}"}
    else:
        return {"output": f"错误: 文件 '{expanded_arg}' 不存在。"}


def handle_screenshot(arg, state):
    """处理截图命令"""
    try:
        # 检查桌面环境
        desktop_available, message = detect_desktop_environment()
        if not desktop_available:
            return {"output": f"截图功能不可用: {message}"}
        
        screenshot = take_screenshot_linux()
        
        # 转换为base64
        from io import BytesIO
        buffer = BytesIO()
        screenshot.save(buffer, format='PNG')
        img_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        buffer.close()
        
        return {"screenshot": img_data}
    except Exception as e:
        return {"output": f"截图失败: {e}"}


def handle_exec(arg, state):
    """把 action 当作可执行命令"""
    full_command = arg or ""
    try:
        # 在Linux上使用 /bin/bash -c
        result = subprocess.run(
            ['/bin/bash', '-c', full_command],
            capture_output=True,
            text=False,  # 获取原始字节
            cwd=state['cwd'],
            timeout=30,
            check=False
        )
        # Linux默认使用UTF-8编码
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        if not output.strip() and result.returncode != 0:
            output = f"命令执行完毕，退出码: {result.returncode}，但无输出。"
        return {"output": output}
    except subprocess.TimeoutExpired:
        return {"output": "命令执行超时（30秒）"}
    except Exception as e:
        return {"output": f"执行命令时发生错误: {e}"}


def handle_list_dir(arg, state):
    target_path = os.path.expanduser(arg) if arg else state['cwd']
    try:
        entries = []
        with os.scandir(target_path) as it:
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
        return {"dir_list": {"cwd": os.path.abspath(target_path), "entries": entries}}
    except Exception as e:
        return {"output": f"列目录失败: {e}"}


def is_image_file(filename):
    """检查文件是否为图片格式"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'}
    return os.path.splitext(filename.lower())[1] in image_extensions

def handle_read_file(arg, state):
    if not arg:
        return {"output": "错误: read_file 需要路径参数。"}
    expanded_arg = os.path.expanduser(arg)
    if not os.path.exists(expanded_arg) or not os.path.isfile(expanded_arg):
        return {"output": f"错误: 文件 '{expanded_arg}' 不存在或不是文件。"}
    try:
        size = os.path.getsize(expanded_arg)
        
        # 对于图片文件，允许更大的文件大小（最大5MB）
        if is_image_file(expanded_arg):
            max_size = 5 * 1024 * 1024  # 5MB
        else:
            max_size = 200 * 1024  # 200KB
            
        if size > max_size:
            return {"output": f"文件过大（{size} bytes），无法直接在线打开。请下载。"}
            
        with open(expanded_arg, 'rb') as f:
            raw = f.read()
            
        # 对于图片文件，直接返回Base64编码
        if is_image_file(expanded_arg):
            text = base64.b64encode(raw).decode('utf-8')
            return {"file_text": text, "path": expanded_arg, "is_base64": True}
            
        # 对于非图片文件，尝试文本解码
        try:
            text = raw.decode('utf-8')
        except:
            try:
                text = raw.decode('latin-1', errors='replace')
            except:
                text = base64.b64encode(raw).decode('utf-8')
                return {"file_text": text, "path": expanded_arg, "is_base64": True}
        return {"file_text": text, "path": expanded_arg, "is_base64": False}
    except Exception as e:
        return {"output": f"读取文件失败: {e}"}


def handle_delete_path(arg, state):
    if not arg:
        return {"output": "错误: delete_path 需要路径参数。"}
    try:
        expanded_arg = os.path.expanduser(arg)
        if os.path.isdir(expanded_arg):
            shutil.rmtree(expanded_arg)
            return {"output": f"目录已删除: {expanded_arg}"}
        elif os.path.isfile(expanded_arg):
            os.remove(expanded_arg)
            return {"output": f"文件已删除: {expanded_arg}"}
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
        # 展开用户路径
        expanded_filename = os.path.expanduser(filename)
        mode = 'ab'
        with open(expanded_filename, mode) as f:
            f.write(base64.b64decode(data_b64))
        if is_last:
            return {"upload_ack": f"上传完成: {expanded_filename}"}
        else:
            return {"output": f"已写入块 {chunk_index} (文件: {expanded_filename})"}
    except Exception as e:
        return {"output": f"写入上传文件失败: {e}"}


def _parse_kv_arg(arg: str):
    """解析键值对参数字符串
    例如: 'fps=10,quality=70,width=1280' -> {'fps': '10', 'quality': '70', 'width': '1280'}
    """
    if not arg:
        return {}
    
    result = {}
    try:
        pairs = arg.split(',')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                result[key.strip()] = value.strip()
    except Exception as e:
        print(f"[警告] 解析参数失败: {e}")
    
    return result


COMMAND_HANDLERS = {
    "cd": lambda arg, state: handle_cd(arg, state),
    "download": lambda arg, state: handle_download(arg, state),
    "screenshot": lambda arg, state: handle_screenshot(arg, state),
    "exec": lambda arg, state: handle_exec(arg, state),
    "list_dir": lambda arg, state: handle_list_dir(arg, state),
    "read_file": lambda arg, state: handle_read_file(arg, state),
    "delete_path": lambda arg, state: handle_delete_path(arg, state),
    "upload_file_chunk": lambda arg, state: handle_upload_file_chunk(arg, state),
    # Linux屏幕流控制
    "start_screen": lambda arg, state: handle_start_screen_linux(arg, state),
    "stop_screen": lambda arg, state: handle_stop_screen_linux(arg, state),
    # Linux混合式视频流控制
    "start_hybrid_screen": lambda arg, state: handle_start_hybrid_screen_linux(arg, state),
    "stop_hybrid_screen": lambda arg, state: handle_stop_hybrid_screen_linux(arg, state),
    # Linux输入控制
    "mouse": lambda arg, state: handle_mouse_linux(arg, state),
    "key": lambda arg, state: handle_key_linux(arg, state)
}


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


def main_loop(server_ip, server_port, connection_code):
    """
    客户端主函数，循环连接和处理命令。
    现在接受 server_ip、server_port、connection_code 作为参数。
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
                    "user": os.environ.get('USER', os.getlogin()), 
                    "os": os_info,
                    "device_fingerprint": device_fingerprint,
                    "hardware_id": hardware_id,
                    "mac_address": mac_address,
                    "hostname": hostname,
                    "connection_code": connection_code  # 添加连接码到握手信息
                }
                reliable_send(client_socket, connection_info)
                print(f"[调试] 已发送连接信息，包含连接码")
            except Exception as e:
                print(f"[错误] 发送初始连接信息失败: {e}")
                break

            # 等待服务端的握手确认
            handshake_completed = False
            handshake_timeout = time.time() + 10  # 10秒超时
            
            while not handshake_completed and time.time() < handshake_timeout:
                try:
                    part = client_socket.recv(4096)
                    if not part:
                        print("[调试] 服务器关闭了连接。")
                        break
                    buffer += part
                except socket.error as e:
                    print(f"[错误] 接收握手响应时发生Socket错误: {e}")
                    break

                while b'\n' in buffer:
                    message, buffer = buffer.split(b'\n', 1)
                    try:
                        response = json.loads(message.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        print(f"[错误] 解析握手响应失败: {e}")
                        continue

                    # 处理握手确认
                    if response.get('type') == 'hello_ack':
                        if response.get('ok'):
                            mode = response.get('mode', 'unknown')
                            print(f"[+] 握手成功！模式: {mode}")
                            handshake_completed = True
                            break
                        else:
                            error = response.get('error', 'unknown_error')
                            print(f"[错误] 握手失败: {error}")
                            return  # 退出主循环，不重连
                
            if not handshake_completed:
                print("[错误] 握手超时")
                break

            # 握手成功后进入正常命令处理循环
            print("[调试] 进入命令处理循环，等待服务器命令...")
            
            # 为状态更新线程创建一个停止事件
            stop_status_thread = threading.Event()
            status_thread = threading.Thread(
                target=send_status_updates,
                args=(client_socket, stop_status_thread),
                daemon=True
            )
            status_thread.start()
            
            while True:
                try:
                    print("[调试] 等待接收数据...")
                    part = client_socket.recv(4096)
                    if not part:
                        print("[调试] 服务器关闭了连接。")
                        break
                    print(f"[调试] 接收到数据: {part}")
                    buffer += part
                except socket.error as e:
                    print(f"[错误] 接收数据时发生Socket错误: {e}")
                    break

                while b'\n' in buffer:
                    message, buffer = buffer.split(b'\n', 1)
                    print(f"[调试] 处理消息: {message}")
                    try:
                        cmd_data = json.loads(message.decode('utf-8'))
                        print(f"[调试] 解析的命令数据: {cmd_data}")
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

                    print(f"[调试] 执行命令: {action}")
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

                        print(f"[调试] 命令执行结果: {result}")
                        if isinstance(result, dict):
                            reliable_send(client_socket, result)
                        else:
                            reliable_send(client_socket, {"output": str(result)})
                        print("[调试] 结果已发送回服务器")
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
            
            # 停止混合式视频流线程
            _base_layer_stop_event.set()
            _enhancement_layer_stop_event.set()
            try:
                if _base_layer_thread and _base_layer_thread.is_alive():
                    _base_layer_thread.join(timeout=1)
                if _enhancement_layer_thread and _enhancement_layer_thread.is_alive():
                    _enhancement_layer_thread.join(timeout=1)
            except Exception:
                pass
            
            # 停止状态更新线程
            if 'stop_status_thread' in locals():
                stop_status_thread.set()
                if 'status_thread' in locals():
                    status_thread.join(timeout=2)
                    
            if client_socket:
                try:
                    client_socket.close()
                except Exception:
                    pass

        buffer = b''
        print("[调试] 5秒后尝试重新连接...")
        time.sleep(5)

def main():
    """简单的命令行启动函数"""
    import sys
    
    # 默认参数
    server_ip = SERVER_IP
    server_port = SERVER_PORT
    connection_code = ""
    
    # 解析命令行参数
    if len(sys.argv) >= 2:
        server_ip = sys.argv[1]
    if len(sys.argv) >= 3:
        server_port = int(sys.argv[2])
    if len(sys.argv) >= 4:
        connection_code = sys.argv[3]
    
    # 如果没有提供连接码，提示用户输入
    if not connection_code:
        try:
            connection_code = input("请输入连接码: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[退出] 用户取消操作")
            return
    
    if not connection_code:
        print("[错误] 连接码不能为空")
        return
    
    print(f"[信息] 连接参数: {server_ip}:{server_port}, 连接码: {'*' * len(connection_code)}")
    
    # 调用主循环函数
    main_loop(server_ip, server_port, connection_code)

if __name__ == '__main__':
    main()


def _find_mouse_device():
    """查找鼠标输入设备"""
    try:
        import subprocess
        result = subprocess.run(['grep', 'mouse', '/proc/bus/input/devices'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'Handlers=' in line and 'event' in line:
                    # 提取event设备号
                    parts = line.split()
                    for part in parts:
                        if part.startswith('event'):
                            return f'/dev/input/{part}'
    except:
        pass
    
    # 备选方案：尝试常见的鼠标设备
    for i in range(20):
        device_path = f'/dev/input/event{i}'
        if os.path.exists(device_path):
            try:
                # 检查设备是否支持鼠标事件
                with open(device_path, 'rb') as f:
                    # 简单检查：如果能打开就认为可能是鼠标设备
                    return device_path
            except:
                continue
    
    return None

def _send_mouse_event_direct(device_path, event_type, event_code, value):
    """直接向输入设备发送鼠标事件"""
    try:
        import struct
        import time
        
        # Linux input event结构：时间戳(8字节) + type(2字节) + code(2字节) + value(4字节)
        timestamp = int(time.time())
        
        # 构造事件数据
        event_data = struct.pack('llHHi', timestamp, 0, event_type, event_code, value)
        
        with open(device_path, 'wb') as f:
            f.write(event_data)
            # 发送同步事件
            sync_data = struct.pack('llHHi', timestamp, 0, 0, 0, 0)  # EV_SYN
            f.write(sync_data)
        
        return True
    except Exception as e:
        print(f"[警告] 直接发送鼠标事件失败: {e}")
        return False

def _control_mouse_uinput(action, x=0, y=0, button=None, delta=0):
    """使用uinput控制鼠标"""
    try:
        # 尝试导入python-uinput
        try:
            import uinput
        except ImportError:
            return False, "需要安装python-uinput库"
        
        # 创建虚拟鼠标设备
        events = (
            uinput.REL_X,
            uinput.REL_Y,
            uinput.BTN_LEFT,
            uinput.BTN_RIGHT,
            uinput.BTN_MIDDLE,
            uinput.REL_WHEEL,
        )
        
        with uinput.Device(events) as device:
            if action == 'move':
                device.emit(uinput.REL_X, x)
                device.emit(uinput.REL_Y, y)
            elif action == 'click':
                btn_map = {'left': uinput.BTN_LEFT, 'right': uinput.BTN_RIGHT, 'middle': uinput.BTN_MIDDLE}
                if button in btn_map:
                    device.emit_click(btn_map[button])
            elif action == 'down':
                btn_map = {'left': uinput.BTN_LEFT, 'right': uinput.BTN_RIGHT, 'middle': uinput.BTN_MIDDLE}
                if button in btn_map:
                    device.emit(btn_map[button], 1)
            elif action == 'up':
                btn_map = {'left': uinput.BTN_LEFT, 'right': uinput.BTN_RIGHT, 'middle': uinput.BTN_MIDDLE}
                if button in btn_map:
                    device.emit(btn_map[button], 0)
            elif action == 'wheel':
                device.emit(uinput.REL_WHEEL, 1 if delta > 0 else -1)
        
        return True, "成功"
    except Exception as e:
        return False, f"uinput控制失败: {e}"

def _control_mouse_evemu(action, x=0, y=0, button=None, delta=0):
    """使用evemu工具控制鼠标"""
    try:
        # 查找鼠标设备
        device_path = _find_mouse_device()
        if not device_path:
            return False, "未找到鼠标设备"
        
        import subprocess
        
        if action == 'move':
            # 发送相对移动事件
            cmd1 = ['evemu-event', device_path, '--type', 'EV_REL', '--code', 'REL_X', '--value', str(x)]
            cmd2 = ['evemu-event', device_path, '--type', 'EV_REL', '--code', 'REL_Y', '--value', str(y), '--sync']
            
            result1 = subprocess.run(cmd1, capture_output=True, timeout=5)
            result2 = subprocess.run(cmd2, capture_output=True, timeout=5)
            
            if result1.returncode == 0 and result2.returncode == 0:
                return True, "移动成功"
        elif action in ['click', 'down', 'up']:
            btn_map = {'left': '272', 'right': '273', 'middle': '274'}  # BTN_LEFT, BTN_RIGHT, BTN_MIDDLE
            if button in btn_map:
                value = '1' if action in ['click', 'down'] else '0'
                cmd = ['evemu-event', device_path, '--type', 'EV_KEY', '--code', btn_map[button], '--value', value, '--sync']
                
                result = subprocess.run(cmd, capture_output=True, timeout=5)
                if result.returncode == 0:
                    if action == 'click':
                        # 点击需要先按下再释放
                        cmd_up = ['evemu-event', device_path, '--type', 'EV_KEY', '--code', btn_map[button], '--value', '0', '--sync']
                        subprocess.run(cmd_up, capture_output=True, timeout=5)
                    return True, f"{action}成功"
        elif action == 'wheel':
            # 滚轮事件
            value = str(1 if delta > 0 else -1)
            cmd = ['evemu-event', device_path, '--type', 'EV_REL', '--code', 'REL_WHEEL', '--value', value, '--sync']
            
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0:
                return True, "滚轮成功"
        
        return False, "操作失败"
    except Exception as e:
        return False, f"evemu控制失败: {e}"

def _control_mouse_direct(action, x=0, y=0, button=None, delta=0):
    """直接写入设备文件控制鼠标"""
    try:
        device_path = _find_mouse_device()
        if not device_path:
            return False, "未找到鼠标设备"
        
        if action == 'move':
            # EV_REL=2, REL_X=0, REL_Y=1
            success1 = _send_mouse_event_direct(device_path, 2, 0, x)
            success2 = _send_mouse_event_direct(device_path, 2, 1, y)
            if success1 and success2:
                return True, "移动成功"
        elif action in ['click', 'down', 'up']:
            # EV_KEY=1, BTN_LEFT=272, BTN_RIGHT=273, BTN_MIDDLE=274
            btn_map = {'left': 272, 'right': 273, 'middle': 274}
            if button in btn_map:
                value = 1 if action in ['click', 'down'] else 0
                success = _send_mouse_event_direct(device_path, 1, btn_map[button], value)
                if success and action == 'click':
                    # 点击需要先按下再释放
                    _send_mouse_event_direct(device_path, 1, btn_map[button], 0)
                if success:
                    return True, f"{action}成功"
        elif action == 'wheel':
            # EV_REL=2, REL_WHEEL=8
            value = 1 if delta > 0 else -1
            success = _send_mouse_event_direct(device_path, 2, 8, value)
            if success:
                return True, "滚轮成功"
        
        return False, "操作失败"
    except Exception as e:
        return False, f"直接控制失败: {e}"

# ... existing code ...
