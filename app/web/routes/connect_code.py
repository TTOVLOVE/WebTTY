from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
import secrets, string
from ...extensions import db
from ...models import ConnectCode
from werkzeug.security import generate_password_hash

connect_code_bp = Blueprint('connect_code', __name__, url_prefix='/api/connect-codes')


def _hash_code(raw: str) -> str:
    return generate_password_hash(raw)


def _gen_code(n=8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))


def _ensure_guest_session_id():
    sid = request.cookies.get('guest_session_id')
    if not sid:
        sid = secrets.token_urlsafe(24)
    return sid


@connect_code_bp.route('/user/status', methods=['GET'])
@login_required
def get_user_code_status():
    """获取用户连接码状态（不返回明文，只返回是否存在）"""
    code = ConnectCode.query.filter_by(user_id=current_user.id, code_type='user', is_active=True).first()
    if code:
        return jsonify({
            'exists': True,
            'last_rotated_at': code.last_rotated_at.isoformat() if code.last_rotated_at else None,
            'message': '连接码已存在，点击重置按钮可查看新的连接码'
        })
    else:
        return jsonify({
            'exists': False,
            'message': '尚未生成连接码，点击重置按钮生成新的连接码'
        })


@connect_code_bp.route('/user/rotate', methods=['POST'])
@login_required
def rotate_user_code():
    raw = _gen_code()
    now = datetime.utcnow()

    # 删除旧码
    ConnectCode.query.filter_by(user_id=current_user.id, code_type='user').delete()
    db.session.flush()

    code = ConnectCode(
        code_hash=_hash_code(raw),
        code_type='user',
        user_id=current_user.id,
        is_active=True,
        last_rotated_at=now,
    )
    db.session.add(code)
    db.session.commit()

    return jsonify({'success': True, 'code': raw, 'type': 'user', 'rotated_at': now.isoformat()})


@connect_code_bp.route('/guest/ensure', methods=['POST'])
def ensure_guest_code():
    sid = _ensure_guest_session_id()
    code = ConnectCode.query.filter_by(guest_session_id=sid, code_type='guest', is_active=True).first()
    if not code:
        # 占位创建，不返回明文
        placeholder_raw = _gen_code()
        code = ConnectCode(
            code_hash=_hash_code(placeholder_raw),
            code_type='guest',
            guest_session_id=sid,
            is_active=True,
        )
        db.session.add(code)
        db.session.commit()

    resp = jsonify({'ok': True})
    # 注意：开发环境下 secure=False；生产应为 True 并启用 HTTPS
    resp.set_cookie('guest_session_id', sid, httponly=True, samesite='Lax', secure=False, max_age=30*24*3600)
    return resp


@connect_code_bp.route('/user/view', methods=['GET'])
@login_required
def view_current_user_connect_code():
    """查看当前用户的连接码（重新生成以确保安全）"""
    try:
        user = current_user
        
        # 查找现有连接码
        existing_code = ConnectCode.query.filter_by(user_id=user.id, code_type='user', is_active=True).first()
        
        if existing_code:
            # 重新生成连接码以确保安全
            new_code = _gen_code()
            existing_code.code_hash = _hash_code(new_code)
            existing_code.last_rotated_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                'success': True,
                'code': new_code,
                'rotated_at': existing_code.last_rotated_at.isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': '用户没有连接码，请先生成'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'查看连接码失败: {str(e)}'
        }), 500


@connect_code_bp.route('/guest/rotate', methods=['POST'])
def rotate_guest_code():
    sid = _ensure_guest_session_id()
    raw = _gen_code()
    now = datetime.utcnow()

    ConnectCode.query.filter_by(guest_session_id=sid, code_type='guest').delete()
    db.session.flush()

    code = ConnectCode(
        code_hash=_hash_code(raw),
        code_type='guest',
        guest_session_id=sid,
        is_active=True,
        last_rotated_at=now,
    )
    db.session.add(code)
    db.session.commit()

    resp = jsonify({'code': raw, 'type': 'guest', 'rotated_at': now.isoformat()})
    resp.set_cookie('guest_session_id', sid, httponly=True, samesite='Lax', secure=False, max_age=30*24*3600)
    return resp