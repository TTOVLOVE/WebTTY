from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from flask_login import login_required
import os
from datetime import datetime
from utils.helpers import human_readable_size

assets_bp = Blueprint('assets', __name__)

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
