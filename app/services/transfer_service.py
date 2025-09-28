import os
import time
from datetime import datetime
from ..config import BaseConfig
from ..utils.helpers import human_readable_size


def save_screenshot(client_id, filename, image_data):
    """
    保存截图到服务器本地
    """
    from ..models import Client
    
    os.makedirs(BaseConfig.DOWNLOADS_DIR, exist_ok=True)

    # 获取客户端信息，使用hostname作为文件名前缀
    client = Client.query.get(client_id)
    if client and client.hostname:
        # 清理hostname中的特殊字符，确保文件名安全
        safe_hostname = "".join(c for c in client.hostname if c.isalnum() or c in ('-', '_')).rstrip()
        if not safe_hostname:  # 如果清理后为空，使用默认名称
            safe_hostname = f"Client_{client_id}"
        client_prefix = safe_hostname
    else:
        # 如果没有hostname或客户端不存在，使用默认格式
        client_prefix = f"Client_{client_id}"

    # 创建唯一的文件名，保持与其他地方一致的时间戳格式
    timestamp = int(time.time())
    safe_filename = f"{client_prefix}_{timestamp}_{filename}"

    file_path = os.path.join(BaseConfig.DOWNLOADS_DIR, safe_filename)

    # 保存文件
    with open(file_path, "wb") as f:
        f.write(image_data)

    return safe_filename


def get_screenshot_gallery():
    """
    获取截图画廊的文件列表，并返回可供展示的截图信息
    """
    screenshots = []
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif')
    try:
        all_files = [os.path.join(BaseConfig.DOWNLOADS_DIR, f) for f in os.listdir(BaseConfig.DOWNLOADS_DIR)]
        image_files = [f for f in all_files if f.lower().endswith(image_extensions) and os.path.isfile(f)]
        image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        for image_path in image_files:
            screenshots.append({
                'name': os.path.basename(image_path),
                'url': f"/downloads/{os.path.basename(image_path)}",
                'modified_time': datetime.fromtimestamp(os.path.getmtime(image_path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    except Exception as e:
        print(f"[错误] 获取截图画廊失败: {e}")

    return screenshots
