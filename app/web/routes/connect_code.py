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