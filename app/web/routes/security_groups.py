"""
安全组管理路由
提供安全组和命令黑名单的管理API
"""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from datetime import datetime
from ...models import (
    SecurityGroup, CommandBlacklistRule, ClientSecurityGroup, 
    CommandExecutionLog, Client, User, db
)
from ...services.command_security import command_security_service
from functools import wraps
import json

def admin_required(f):
    """检查用户是否为管理员"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': '未登录'}), 401
        if not hasattr(current_user, 'role') or not current_user.is_administrator():
            return jsonify({'error': '权限不足'}), 403
        return f(*args, **kwargs)
    return decorated_function

security_groups_bp = Blueprint('security_groups', __name__)


@security_groups_bp.route('/dashboard/security-groups')
@login_required
@admin_required
def security_groups_page():
    """安全组管理页面"""
    return render_template('dashboard/security_groups.html')


# ==================== 安全组管理API ====================

@security_groups_bp.route('/api/security-groups', methods=['GET'])
@login_required
@admin_required
def get_security_groups():
    """获取安全组列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        group_type = request.args.get('group_type', '').strip()
        
        # 构建查询
        query = SecurityGroup.query
        
        if search:
            query = query.filter(
                or_(
                    SecurityGroup.name.contains(search),
                    SecurityGroup.description.contains(search)
                )
            )
        
        if group_type:
            query = query.filter(SecurityGroup.group_type == group_type)
        
        # 分页
        pagination = query.order_by(SecurityGroup.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        security_groups = [group.to_dict() for group in pagination.items]
        
        return jsonify({
            'success': True,
            'data': {
                'security_groups': security_groups,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_prev': pagination.has_prev,
                    'has_next': pagination.has_next
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取安全组列表失败: {str(e)}'}), 500


@security_groups_bp.route('/api/security-groups', methods=['POST'])
@login_required
@admin_required
def create_security_group():
    """创建安全组"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data.get('name'):
            return jsonify({'success': False, 'message': '安全组名称不能为空'}), 400
        
        # 检查名称是否已存在
        existing = SecurityGroup.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({'success': False, 'message': '安全组名称已存在'}), 400
        
        # 创建安全组
        security_group = SecurityGroup(
            name=data['name'],
            description=data.get('description', ''),
            group_type=data.get('group_type', 'custom'),
            parent_group_id=data.get('parent_group_id'),
            is_active=data.get('is_active', True),
            created_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(security_group)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '安全组创建成功',
            'data': security_group.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'创建安全组失败: {str(e)}'}), 500


@security_groups_bp.route('/api/security-groups/<int:group_id>', methods=['PUT'])
@login_required
@admin_required
def update_security_group(group_id):
    """更新安全组"""
    try:
        security_group = SecurityGroup.query.get_or_404(group_id)
        data = request.get_json()
        
        # 检查名称是否与其他安全组冲突
        if data.get('name') and data['name'] != security_group.name:
            existing = SecurityGroup.query.filter_by(name=data['name']).first()
            if existing:
                return jsonify({'success': False, 'message': '安全组名称已存在'}), 400
        
        # 更新字段
        if 'name' in data:
            security_group.name = data['name']
        if 'description' in data:
            security_group.description = data['description']
        if 'group_type' in data:
            security_group.group_type = data['group_type']
        if 'parent_group_id' in data:
            security_group.parent_group_id = data['parent_group_id']
        if 'is_active' in data:
            security_group.is_active = data['is_active']
        
        security_group.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '安全组更新成功',
            'data': security_group.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新安全组失败: {str(e)}'}), 500


@security_groups_bp.route('/api/security-groups/<int:group_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_security_group(group_id):
    """删除安全组"""
    try:
        security_group = SecurityGroup.query.get_or_404(group_id)
        
        # 检查是否有客户端正在使用此安全组
        active_assignments = ClientSecurityGroup.query.filter_by(
            security_group_id=group_id,
            is_active=True
        ).count()
        
        if active_assignments > 0:
            return jsonify({
                'success': False, 
                'message': f'无法删除安全组，仍有 {active_assignments} 个客户端正在使用'
            }), 400
        
        # 删除安全组（级联删除规则和分配记录）
        db.session.delete(security_group)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '安全组删除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除安全组失败: {str(e)}'}), 500


# ==================== 安全组规则管理API ====================

@security_groups_bp.route('/api/security-groups/<int:group_id>/rules', methods=['GET'])
@login_required
@admin_required
def get_security_group_rules(group_id):
    """获取安全组规则列表"""
    try:
        security_group = SecurityGroup.query.get_or_404(group_id)
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # 获取规则
        pagination = CommandBlacklistRule.query.filter_by(
            security_group_id=group_id
        ).order_by(
            CommandBlacklistRule.priority.asc(),
            CommandBlacklistRule.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        rules = [rule.to_dict() for rule in pagination.items]
        
        return jsonify({
            'success': True,
            'data': {
                'security_group': security_group.to_dict(),
                'rules': rules,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_prev': pagination.has_prev,
                    'has_next': pagination.has_next
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取规则列表失败: {str(e)}'}), 500


@security_groups_bp.route('/api/security-groups/<int:group_id>/rules', methods=['POST'])
@login_required
@admin_required
def add_security_group_rule(group_id):
    """添加安全组规则"""
    try:
        security_group = SecurityGroup.query.get_or_404(group_id)
        data = request.get_json()
        
        # 验证必填字段
        if not data.get('rule_type') or not data.get('rule_value'):
            return jsonify({'success': False, 'message': '规则类型和规则值不能为空'}), 400
        
        # 验证规则类型
        valid_rule_types = ['command', 'pattern', 'category']
        if data['rule_type'] not in valid_rule_types:
            return jsonify({'success': False, 'message': '无效的规则类型'}), 400
        
        # 验证动作类型
        valid_actions = ['block', 'warn', 'allow']
        action = data.get('action', 'block')
        if action not in valid_actions:
            return jsonify({'success': False, 'message': '无效的动作类型'}), 400
        
        # 创建规则
        rule = CommandBlacklistRule(
            security_group_id=group_id,
            rule_type=data['rule_type'],
            rule_value=data['rule_value'],
            os_type=data.get('os_type', 'all'),
            action=action,
            priority=data.get('priority', 100),
            is_active=data.get('is_active', True),
            description=data.get('description', ''),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(rule)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '规则添加成功',
            'data': rule.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'添加规则失败: {str(e)}'}), 500


@security_groups_bp.route('/api/security-groups/rules/<int:rule_id>', methods=['PUT'])
@login_required
@admin_required
def update_security_group_rule(rule_id):
    """更新安全组规则"""
    try:
        rule = CommandBlacklistRule.query.get_or_404(rule_id)
        data = request.get_json()
        
        # 更新字段
        if 'rule_type' in data:
            valid_rule_types = ['command', 'pattern', 'category']
            if data['rule_type'] not in valid_rule_types:
                return jsonify({'success': False, 'message': '无效的规则类型'}), 400
            rule.rule_type = data['rule_type']
        
        if 'rule_value' in data:
            rule.rule_value = data['rule_value']
        
        if 'os_type' in data:
            rule.os_type = data['os_type']
        
        if 'action' in data:
            valid_actions = ['block', 'warn', 'allow']
            if data['action'] not in valid_actions:
                return jsonify({'success': False, 'message': '无效的动作类型'}), 400
            rule.action = data['action']
        
        if 'priority' in data:
            rule.priority = data['priority']
        
        if 'is_active' in data:
            rule.is_active = data['is_active']
        
        if 'description' in data:
            rule.description = data['description']
        
        rule.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '规则更新成功',
            'data': rule.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新规则失败: {str(e)}'}), 500


@security_groups_bp.route('/api/security-groups/rules/<int:rule_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_security_group_rule(rule_id):
    """删除安全组规则"""
    try:
        rule = CommandBlacklistRule.query.get_or_404(rule_id)
        
        db.session.delete(rule)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '规则删除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除规则失败: {str(e)}'}), 500


# ==================== 客户端安全组分配API ====================

@security_groups_bp.route('/api/clients/<int:client_id>/security-group', methods=['GET'])
@login_required
def get_client_security_group(client_id):
    """获取客户端关联的安全组"""
    try:
        client = Client.query.get_or_404(client_id)
        
        # 权限检查
        if not current_user.can_view_client(client):
            return jsonify({'success': False, 'message': '权限不足'}), 403
        
        # 获取安全组信息
        security_info = command_security_service.get_client_security_info(client_id)
        
        return jsonify({
            'success': True,
            'data': security_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取客户端安全组失败: {str(e)}'}), 500


@security_groups_bp.route('/api/clients/<int:client_id>/security-group', methods=['POST'])
@login_required
@admin_required
def assign_client_security_group(client_id):
    """为客户端分配安全组"""
    try:
        client = Client.query.get_or_404(client_id)
        data = request.get_json()
        
        security_group_id = data.get('security_group_id')
        if not security_group_id:
            return jsonify({'success': False, 'message': '安全组ID不能为空'}), 400
        
        security_group = SecurityGroup.query.get_or_404(security_group_id)
        if not security_group.is_active:
            return jsonify({'success': False, 'message': '安全组未激活'}), 400
        
        # 若已分配到同一安全组则直接返回，避免重复分配
        existing_active = ClientSecurityGroup.query.filter_by(
            client_id=client_id,
            is_active=True
        ).first()
        if existing_active and existing_active.security_group_id == security_group_id:
            return jsonify({
                'success': True,
                'message': '客户端已在该安全组，无需重复分配',
                'data': existing_active.to_dict()
            })

        # 停用现有的安全组分配
        existing_assignments = ClientSecurityGroup.query.filter_by(
            client_id=client_id,
            is_active=True
        ).all()
        for assignment in existing_assignments:
            assignment.is_active = False
        
        # 创建新的分配
        new_assignment = ClientSecurityGroup(
            client_id=client_id,
            security_group_id=security_group_id,
            assigned_by=current_user.id,
            assigned_at=datetime.utcnow(),
            is_active=True
        )
        
        db.session.add(new_assignment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '安全组分配成功',
            'data': new_assignment.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'分配安全组失败: {str(e)}'}), 500


@security_groups_bp.route('/api/clients/batch-assign-security-group', methods=['POST'])
@login_required
@admin_required
def batch_assign_security_group():
    """批量分配安全组"""
    try:
        data = request.get_json()
        
        client_ids = data.get('client_ids', [])
        security_group_id = data.get('security_group_id')
        
        if not client_ids:
            return jsonify({'success': False, 'message': '客户端列表不能为空'}), 400
        
        if not security_group_id:
            return jsonify({'success': False, 'message': '安全组ID不能为空'}), 400
        
        security_group = SecurityGroup.query.get_or_404(security_group_id)
        if not security_group.is_active:
            return jsonify({'success': False, 'message': '安全组未激活'}), 400
        
        success_count = 0
        failed_clients = []
        skipped_clients = []
        
        for client_id in client_ids:
            try:
                client = Client.query.get(client_id)
                if not client:
                    failed_clients.append({'client_id': client_id, 'reason': '客户端不存在'})
                    continue
                
                # 若已分配到同一安全组则跳过
                existing_active = ClientSecurityGroup.query.filter_by(
                    client_id=client_id,
                    is_active=True
                ).first()
                if existing_active and existing_active.security_group_id == security_group_id:
                    skipped_clients.append({'client_id': client_id, 'reason': '已在该安全组'})
                    continue

                # 停用现有的安全组分配
                existing_assignments = ClientSecurityGroup.query.filter_by(
                    client_id=client_id,
                    is_active=True
                ).all()
                for assignment in existing_assignments:
                    assignment.is_active = False
                
                # 创建新的分配
                new_assignment = ClientSecurityGroup(
                    client_id=client_id,
                    security_group_id=security_group_id,
                    assigned_by=current_user.id,
                    assigned_at=datetime.utcnow(),
                    is_active=True
                )
                
                db.session.add(new_assignment)
                success_count += 1
                
            except Exception as e:
                failed_clients.append({'client_id': client_id, 'reason': str(e)})
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'批量分配完成，成功: {success_count}，跳过: {len(skipped_clients)}，失败: {len(failed_clients)}',
            'data': {
                'success_count': success_count,
                'failed_clients': failed_clients,
                'skipped_count': len(skipped_clients),
                'skipped_clients': skipped_clients
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'批量分配失败: {str(e)}'}), 500


# ==================== 命令执行日志API ====================

@security_groups_bp.route('/api/command-execution-logs', methods=['GET'])
@login_required
@admin_required
def get_command_execution_logs():
    """获取命令执行日志"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        client_id = request.args.get('client_id', type=int)
        action = request.args.get('action', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        
        # 构建查询
        query = CommandExecutionLog.query
        
        if client_id:
            query = query.filter(CommandExecutionLog.client_id == client_id)
        
        if action:
            query = query.filter(CommandExecutionLog.action == action)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                query = query.filter(CommandExecutionLog.execution_time >= start_dt)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                query = query.filter(CommandExecutionLog.execution_time <= end_dt)
            except ValueError:
                pass
        
        # 分页
        pagination = query.order_by(CommandExecutionLog.execution_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        logs = [log.to_dict() for log in pagination.items]
        
        return jsonify({
            'success': True,
            'data': {
                'logs': logs,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_prev': pagination.has_prev,
                    'has_next': pagination.has_next
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取命令执行日志失败: {str(e)}'}), 500


# ==================== 安全组模板API ====================

@security_groups_bp.route('/api/security-groups/templates', methods=['GET'])
@login_required
@admin_required
def get_security_group_templates():
    """获取安全组模板"""
    templates = {
        'default': {
            'name': '默认安全组',
            'description': '默认安全策略，允许大部分常用命令',
            'group_type': 'default',
            'rules': [
                {
                    'rule_type': 'command',
                    'rule_value': 'format',
                    'os_type': 'windows',
                    'action': 'block',
                    'priority': 10,
                    'description': '阻止格式化命令'
                },
                {
                    'rule_type': 'command',
                    'rule_value': 'rm',
                    'os_type': 'linux',
                    'action': 'warn',
                    'priority': 20,
                    'description': '删除文件时警告'
                }
            ]
        },
        'restricted': {
            'name': '受限安全组',
            'description': '受限安全策略，阻止危险命令',
            'group_type': 'restricted',
            'rules': [
                {
                    'rule_type': 'category',
                    'rule_value': 'system',
                    'os_type': 'all',
                    'action': 'block',
                    'priority': 10,
                    'description': '阻止系统管理命令'
                },
                {
                    'rule_type': 'pattern',
                    'rule_value': r'.*\s+(--force|-f)\s+.*',
                    'os_type': 'all',
                    'action': 'warn',
                    'priority': 20,
                    'description': '强制操作时警告'
                }
            ]
        },
        'high_security': {
            'name': '高安全组',
            'description': '高安全策略，严格限制命令执行',
            'group_type': 'high_security',
            'rules': [
                {
                    'rule_type': 'category',
                    'rule_value': 'network',
                    'os_type': 'all',
                    'action': 'block',
                    'priority': 10,
                    'description': '阻止网络相关命令'
                },
                {
                    'rule_type': 'category',
                    'rule_value': 'file',
                    'os_type': 'all',
                    'action': 'warn',
                    'priority': 20,
                    'description': '文件操作时警告'
                }
            ]
        }
    }
    
    return jsonify({
        'success': True,
        'data': templates
    })


@security_groups_bp.route('/api/security-groups/import-template', methods=['POST'])
@login_required
@admin_required
def import_security_group_template():
    """导入安全组模板"""
    try:
        data = request.get_json()
        template_name = data.get('template_name')
        custom_name = data.get('custom_name', '')
        
        if not template_name:
            return jsonify({'success': False, 'message': '模板名称不能为空'}), 400
        
        # 获取模板
        templates_response = get_security_group_templates()
        templates = templates_response.get_json()['data']
        
        if template_name not in templates:
            return jsonify({'success': False, 'message': '模板不存在'}), 404
        
        template = templates[template_name]
        
        # 创建安全组
        group_name = custom_name or template['name']
        
        # 检查名称是否已存在
        existing = SecurityGroup.query.filter_by(name=group_name).first()
        if existing:
            return jsonify({'success': False, 'message': '安全组名称已存在'}), 400
        
        security_group = SecurityGroup(
            name=group_name,
            description=template['description'],
            group_type=template['group_type'],
            is_active=True,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(security_group)
        db.session.flush()  # 获取ID
        
        # 创建规则
        for rule_data in template['rules']:
            rule = CommandBlacklistRule(
                security_group_id=security_group.id,
                rule_type=rule_data['rule_type'],
                rule_value=rule_data['rule_value'],
                os_type=rule_data['os_type'],
                action=rule_data['action'],
                priority=rule_data['priority'],
                is_active=True,
                description=rule_data['description'],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(rule)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '模板导入成功',
            'data': security_group.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'导入模板失败: {str(e)}'}), 500