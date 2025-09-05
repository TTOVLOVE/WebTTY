from flask import Blueprint, render_template, request, jsonify, send_from_directory, send_file, current_app
from flask_login import login_required
import os
from datetime import datetime
from utils.helpers import human_readable_size
import tempfile
import shutil
import zipfile
import subprocess
import sys
import platform
import re

assets_bp = Blueprint('assets', __name__)

@assets_bp.route('/client_download')
@login_required
def client_download():
    """客户端下载页面"""
    return render_template('assets/client_download.html')

@assets_bp.route('/client_download/build', methods=['POST'])
@login_required
def client_download_build():
    """根据选择的平台/架构和服务器地址，生成客户端可执行文件或ZIP并返回下载"""
    data = request.get_json(force=True)
    target_platform = (data.get('platform') or '').lower()
    arch = (data.get('arch') or '').lower()
    server_ip = data.get('server_ip') or ''
    server_port = int(data.get('server_port') or 0)

    if target_platform not in ('windows', 'linux'):
        return ('非法平台参数', 400)
    if not server_ip or not server_port:
        return ('请提供服务器IP与端口', 400)

    # 准备源码与输出
    project_root = current_app.root_path
    client_dir = os.path.join(project_root, '客户端')
    if not os.path.isdir(client_dir):
        return ('找不到客户端源码目录', 500)

    if target_platform == 'windows':
        src_file = os.path.join(client_dir, 'client.py')
        out_base_name = f'client_windows_{arch}'
    else:
        src_file = os.path.join(client_dir, 'client_linux.py')
        out_base_name = f'client_linux_{arch}'

    if not os.path.isfile(src_file):
        return ('找不到客户端源码文件', 500)

    tmpdir = tempfile.mkdtemp(prefix='client_build_')
    try:
        # 读取源码并注入服务器地址与端口
        with open(src_file, 'r', encoding='utf-8') as f:
            code = f.read()

        if target_platform == 'linux':
            # 替换常量 SERVER_IP 与 SERVER_PORT
            code = re.sub(r"SERVER_IP\s*=\s*['\"]([^'\"]*)['\"]", f"SERVER_IP = '{server_ip}'", code)
            code = re.sub(r"SERVER_PORT\s*=\s*\d+", f"SERVER_PORT = {server_port}", code)
            out_src = os.path.join(tmpdir, 'client_linux.py')
        else:
            # 替换 Windows UI 默认IP/端口
            code = re.sub(r"self\.ip_entry\.insert\(0,\s*['\"][^'\"]*['\"]\)", f"self.ip_entry.insert(0, '{server_ip}')", code)
            code = re.sub(r"self\.port_entry\.insert\(0,\s*['\"][^'\"]*['\"]\)", f"self.port_entry.insert(0, '{server_port}')", code)
            out_src = os.path.join(tmpdir, 'client.py')

        with open(out_src, 'w', encoding='utf-8') as f:
            f.write(code)

        # 优先尝试使用 PyInstaller 打包（仅当服务器与目标平台一致时）
        sys_os = platform.system().lower()
        same_os = (sys_os.startswith('win') and target_platform == 'windows') or (sys_os.startswith('linux') and target_platform == 'linux')
        pyinstaller = shutil.which('pyinstaller')
        if same_os and pyinstaller:
            dist_dir = os.path.join(tmpdir, 'dist')
            build_dir = os.path.join(tmpdir, 'build')
            name_arg = out_base_name
            cmd = [pyinstaller, '--onefile', '--noconsole', '--clean', '--distpath', dist_dir, '--workpath', build_dir, '--name', name_arg, out_src]
            try:
                print("[*]调试信息:开始尝试构建exe")
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if proc.returncode == 0:
                    # 返回可执行文件
                    if target_platform == 'windows':
                        out_path = os.path.join(dist_dir, name_arg + '.exe')
                    else:
                        print("[*]调试信息:构建失败返回源码")
                        out_path = os.path.join(dist_dir, name_arg)

                    if os.path.isfile(out_path):
                        return send_file(out_path, as_attachment=True, download_name=os.path.basename(out_path))
                # 失败则回退为ZIP
            except Exception:
                pass

        # 回退：打包为ZIP源码
        zip_path = os.path.join(tmpdir, out_base_name + '.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(out_src, os.path.basename(out_src))
        return send_file(zip_path, as_attachment=True, download_name=os.path.basename(zip_path))
    finally:
        # 注意：不能立即删除 tmpdir，因为send_file需要读取。这里不清理临时目录，交由系统定期清理。
        pass


@assets_bp.route('/commands')
@login_required
def commands():
    """命令管理页面"""
    return render_template('assets/commands.html')

@assets_bp.route('/shell_script')
@login_required
def file_manager():
    """文件管理器页面"""
    # 获取URL参数中的客户端ID
    client_id = request.args.get('client', '')
    return render_template('assets/shell_script.html', client_id=client_id)

@assets_bp.route('/downloads')
@login_required
def downloads():
    """下载管理页面"""
    downloads_dir = current_app.config.get('DOWNLOADS_DIR', 'downloads')
    files = []
    
    if os.path.exists(downloads_dir):
        for filename in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append({
                    'name': filename,
                    'size': human_readable_size(stat.st_size),
                    'modified_time': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'url': f'/downloads/{filename}'
                })
    
    # 按修改时间排序，最新的在前面
    files.sort(key=lambda x: x['modified_time'], reverse=True)
    
    return render_template('assets/downloads_view.html', files=files)

@assets_bp.route('/screenshots')
@login_required
def screenshots():
    """截图管理页面"""
    downloads_dir = current_app.config.get('DOWNLOADS_DIR', 'downloads')
    screenshots = []
    
    if os.path.exists(downloads_dir):
        # 查找截图文件（假设截图文件名包含screenshot或png/jpg等图片扩展名）
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
        for filename in os.listdir(downloads_dir):
            if any(filename.lower().endswith(ext) for ext in image_extensions) or 'screenshot' in filename.lower():
                file_path = os.path.join(downloads_dir, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    screenshots.append({
                        'name': filename,
                        'url': f'/downloads/{filename}',
                        'modified_time': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
    
    # 按修改时间排序，最新的在前面
    screenshots.sort(key=lambda x: x['modified_time'], reverse=True)
    
    return render_template('assets/screenshot_gallery.html', screenshots=screenshots)

@assets_bp.route('/downloads/<filename>')
@login_required
def download_file(filename):
    """下载文件"""
    downloads_dir = current_app.config.get('DOWNLOADS_DIR', 'downloads')
    return send_from_directory(downloads_dir, filename)

@assets_bp.route('/api/files/<client_id>')
@login_required
def get_client_files(client_id):
    """获取客户端文件列表"""
    # 这里应该实现获取客户端文件列表的逻辑
    return jsonify({'files': [], 'client_id': client_id})

@assets_bp.route('/delete_file/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    """删除文件"""
    try:
        downloads_dir = current_app.config.get('DOWNLOADS_DIR', 'downloads')
        file_path = os.path.join(downloads_dir, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'success': True, 'message': '文件删除成功'})
        else:
            return jsonify({'success': False, 'error': '文件不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
