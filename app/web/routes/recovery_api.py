#!/usr/bin/env python3
"""
客户端状态恢复API
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...services.client_recovery import check_recovery_needed, recover_client_manager_state
from ...services import client_manager

recovery_api_bp = Blueprint('recovery_api', __name__, url_prefix='/api/recovery')

@recovery_api_bp.route('/status', methods=['GET'])
@login_required
def get_recovery_status():
    """获取恢复状态信息"""
    try:
        # 检查当前状态
        manager_count = len(client_manager.client_info)
        needs_recovery = check_recovery_needed()
        
        return jsonify({
            'success': True,
            'manager_client_count': manager_count,
            'needs_recovery': needs_recovery,
            'client_info': dict(client_manager.client_info)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@recovery_api_bp.route('/trigger', methods=['POST'])
@login_required
def trigger_recovery():
    """触发客户端状态恢复"""
    try:
        # 检查用户权限（可选：只允许管理员执行）
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': '权限不足，只有管理员可以执行恢复操作'
            }), 403
        
        # 检查是否需要恢复
        if not check_recovery_needed():
            return jsonify({
                'success': True,
                'message': '客户端管理器状态正常，无需恢复',
                'recovered_count': 0
            })
        
        # 执行恢复
        recovered_count = recover_client_manager_state()
        
        return jsonify({
            'success': True,
            'message': f'恢复完成，共恢复 {recovered_count} 个客户端',
            'recovered_count': recovered_count,
            'client_info': dict(client_manager.client_info)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'恢复过程中出错: {str(e)}'
        }), 500

@recovery_api_bp.route('/clear', methods=['POST'])
@login_required
def clear_client_manager():
    """清空客户端管理器（用于测试）"""
    try:
        # 检查用户权限
        if not current_user.is_admin:
            return jsonify({
                'success': False,
                'error': '权限不足，只有管理员可以执行清空操作'
            }), 403
        
        # 清空客户端管理器
        original_count = len(client_manager.client_info)
        client_manager.client_info.clear()
        client_manager.clients.clear()
        client_manager.client_queues.clear()
        
        return jsonify({
            'success': True,
            'message': f'已清空客户端管理器，原有 {original_count} 个客户端',
            'cleared_count': original_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'清空过程中出错: {str(e)}'
        }), 500