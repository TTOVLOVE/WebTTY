"""
命令安全检查服务
提供基于安全组的命令黑名单检查功能
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from flask import current_app
from ..models import (
    SecurityGroup, CommandBlacklistRule, ClientSecurityGroup, 
    CommandExecutionLog, Client, User, db
)


class CommandSecurityService:
    """命令安全检查服务"""
    
    def __init__(self):
        self._command_categories = self._load_command_categories()
    
    def _load_command_categories(self) -> Dict[str, List[str]]:
        """加载命令分类信息"""
        try:
            # 加载Windows命令分类
            with open('static/data/windows_commands.json', 'r', encoding='utf-8') as f:
                windows_commands = json.load(f)
            
            # 加载Linux命令分类
            with open('static/data/linux_commands.json', 'r', encoding='utf-8') as f:
                linux_commands = json.load(f)
            
            # 构建分类映射
            categories = {}
            
            # 处理Windows命令
            for cmd in windows_commands:
                category = cmd.get('category', 'other')
                if category not in categories:
                    categories[category] = []
                categories[category].append(cmd['name'])
            
            # 处理Linux命令
            for cmd in linux_commands:
                category = cmd.get('category', 'other')
                if category not in categories:
                    categories[category] = []
                if cmd['name'] not in categories[category]:
                    categories[category].append(cmd['name'])
            
            return categories
            
        except Exception as e:
            current_app.logger.error(f"Failed to load command categories: {e}")
            return {}
    
    def check_command_permission(
        self, 
        client_id: int, 
        command: str, 
        command_type: str = 'execute_command',
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, any]:
        """
        检查命令执行权限
        
        Args:
            client_id: 客户端ID
            command: 要执行的命令
            command_type: 命令类型 (execute_command, shell_command)
            user_id: 用户ID
            session_id: 会话ID
            ip_address: IP地址
            user_agent: 用户代理
            
        Returns:
            Dict包含检查结果:
            {
                'allowed': bool,  # 是否允许执行
                'action': str,    # 动作 (allowed, blocked, warned)
                'message': str,   # 响应消息
                'rule_matched': str,  # 匹配的规则
                'security_group_id': int,  # 安全组ID
                'rule_id': int    # 规则ID
            }
        """
        try:
            # 获取客户端信息
            client = Client.query.get(client_id)
            if not client:
                return self._create_result(False, 'blocked', '客户端不存在')
            
            # 获取客户端关联的安全组
            security_group_assignment = ClientSecurityGroup.query.filter_by(
                client_id=client_id,
                is_active=True
            ).first()
            
            if not security_group_assignment:
                # 没有分配安全组，默认允许
                self._log_command_execution(
                    client_id, command, command_type, 'allowed',
                    user_id=user_id, session_id=session_id,
                    ip_address=ip_address, user_agent=user_agent,
                    response_message='未分配安全组，默认允许'
                )
                return self._create_result(True, 'allowed', '未分配安全组，默认允许')
            
            security_group = security_group_assignment.security_group
            if not security_group or not security_group.is_active:
                # 安全组不存在或未激活，默认允许
                self._log_command_execution(
                    client_id, command, command_type, 'allowed',
                    user_id=user_id, session_id=session_id,
                    ip_address=ip_address, user_agent=user_agent,
                    response_message='安全组未激活，默认允许'
                )
                return self._create_result(True, 'allowed', '安全组未激活，默认允许')
            
            # 获取所有相关的安全组规则（包括继承的规则，不再按操作系统过滤）
            rules = self._get_applicable_rules(security_group)
            
            # 检查命令是否匹配任何规则
            matched_rule = self._match_command_against_rules(command, rules)
            
            if matched_rule:
                action = matched_rule.action
                message = self._get_action_message(action, matched_rule)
                
                # 记录日志
                self._log_command_execution(
                    client_id, command, command_type, action,
                    security_group_id=security_group.id,
                    rule_id=matched_rule.id,
                    rule_matched=matched_rule.rule_value,
                    user_id=user_id, session_id=session_id,
                    ip_address=ip_address, user_agent=user_agent,
                    response_message=message
                )
                
                return {
                    'allowed': action != 'block',
                    'action': action,
                    'message': message,
                    'rule_matched': matched_rule.rule_value,
                    'security_group_id': security_group.id,
                    'rule_id': matched_rule.id
                }
            else:
                # 没有匹配的规则，默认允许
                self._log_command_execution(
                    client_id, command, command_type, 'allowed',
                    security_group_id=security_group.id,
                    user_id=user_id, session_id=session_id,
                    ip_address=ip_address, user_agent=user_agent,
                    response_message='未匹配任何规则，默认允许'
                )
                return self._create_result(True, 'allowed', '未匹配任何规则，默认允许')
                
        except Exception as e:
            current_app.logger.error(f"Command permission check failed: {e}")
            # 发生错误时默认允许，避免影响正常功能
            return self._create_result(True, 'allowed', f'权限检查异常，默认允许: {str(e)}')
    
    def _get_applicable_rules(self, security_group: SecurityGroup) -> List[CommandBlacklistRule]:
        """获取适用的规则（包括继承的规则）。
        新逻辑：不再基于客户端操作系统过滤规则，规则仅按安全组和启用状态生效。
        """
        rules = []
        current_group = security_group
        
        # 递归获取当前组及父组的规则
        while current_group:
            group_rules = CommandBlacklistRule.query.filter_by(
                security_group_id=current_group.id,
                is_active=True
            ).order_by(CommandBlacklistRule.priority.asc()).all()
            
            rules.extend(group_rules)
            current_group = current_group.parent_group
        
        # 按优先级排序
        rules.sort(key=lambda x: x.priority)
        return rules
    
    def _match_command_against_rules(
        self,
        command: str,
        rules: List[CommandBlacklistRule]
    ) -> Optional[CommandBlacklistRule]:
        """检查命令是否匹配规则"""
        command_lower = command.lower().strip()
        
        for rule in rules:
            if self._is_rule_match(command_lower, rule):
                return rule
        
        return None
    
    def _is_rule_match(self, command: str, rule: CommandBlacklistRule) -> bool:
        """检查单个规则是否匹配"""
        rule_value = rule.rule_value.lower()
        
        if rule.rule_type == 'command':
            # 精确命令匹配
            command_parts = command.split()
            if command_parts:
                return command_parts[0] == rule_value
                
        elif rule.rule_type == 'pattern':
            # 正则表达式匹配
            try:
                return bool(re.search(rule_value, command, re.IGNORECASE))
            except re.error:
                current_app.logger.warning(f"Invalid regex pattern in rule {rule.id}: {rule_value}")
                return False
                
        elif rule.rule_type == 'category':
            # 分类匹配
            category_commands = self._command_categories.get(rule_value, [])
            command_parts = command.split()
            if command_parts:
                return command_parts[0] in [cmd.lower() for cmd in category_commands]
        
        return False
    
    def _get_action_message(self, action: str, rule: CommandBlacklistRule) -> str:
        """获取动作对应的消息"""
        messages = {
            'block': f'命令被安全策略阻止: {rule.description or rule.rule_value}',
            'warn': f'命令触发安全警告: {rule.description or rule.rule_value}',
            'allow': f'命令被安全策略明确允许: {rule.description or rule.rule_value}'
        }
        return messages.get(action, f'未知动作: {action}')
    
    def _create_result(self, allowed: bool, action: str, message: str) -> Dict[str, any]:
        """创建检查结果"""
        return {
            'allowed': allowed,
            'action': action,
            'message': message,
            'rule_matched': None,
            'security_group_id': None,
            'rule_id': None
        }
    
    def _log_command_execution(
        self,
        client_id: int,
        command: str,
        command_type: str,
        action: str,
        security_group_id: Optional[int] = None,
        rule_id: Optional[int] = None,
        rule_matched: Optional[str] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_message: Optional[str] = None
    ):
        """记录命令执行日志"""
        try:
            log_entry = CommandExecutionLog(
                client_id=client_id,
                user_id=user_id,
                session_id=session_id,
                command=command,
                command_type=command_type,
                action=action,
                security_group_id=security_group_id,
                rule_id=rule_id,
                rule_matched=rule_matched,
                ip_address=ip_address,
                user_agent=user_agent,
                execution_time=datetime.utcnow(),
                response_message=response_message
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Failed to log command execution: {e}")
            db.session.rollback()
    
    def get_client_security_info(self, client_id: int) -> Dict[str, any]:
        """获取客户端安全信息"""
        try:
            client = Client.query.get(client_id)
            if not client:
                return {'error': '客户端不存在'}
            
            # 获取安全组分配
            assignment = ClientSecurityGroup.query.filter_by(
                client_id=client_id,
                is_active=True
            ).first()
            
            if not assignment:
                return {
                    'client_id': client_id,
                    'hostname': client.hostname,
                    'security_group': None,
                    'rules_count': 0,
                    'last_command_log': None
                }
            
            security_group = assignment.security_group
            rules_count = CommandBlacklistRule.query.filter_by(
                security_group_id=security_group.id,
                is_active=True
            ).count()
            
            # 获取最近的命令日志
            last_log = CommandExecutionLog.query.filter_by(
                client_id=client_id
            ).order_by(CommandExecutionLog.execution_time.desc()).first()
            
            return {
                'client_id': client_id,
                'hostname': client.hostname,
                'security_group': security_group.to_dict(),
                'rules_count': rules_count,
                'last_command_log': last_log.to_dict() if last_log else None,
                'assigned_at': assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                'assigned_by': assignment.assigner.username if assignment.assigner else None
            }
            
        except Exception as e:
            current_app.logger.error(f"Failed to get client security info: {e}")
            return {'error': f'获取客户端安全信息失败: {str(e)}'}


# 全局实例
command_security_service = CommandSecurityService()