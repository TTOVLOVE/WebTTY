import threading
import time
from datetime import datetime, timedelta

from ..extensions import db
from ..models import ConnectCode


def _guest_cleanup_loop(app, interval_seconds: int = 600):
    """
    后台清理循环：定期将超过24小时未使用的游客连接码置为失效。
    - 若 last_used_at 存在并早于当前时间24小时，则置为失效；
    - 若从未使用过(last_used_at 为空)，且 created_at 早于24小时，也置为失效。
    """
    while True:
        try:
            with app.app_context():
                now = datetime.utcnow()
                cutoff = now - timedelta(hours=24)
                codes = ConnectCode.query.filter_by(code_type='guest', is_active=True).all()
                changed = False
                for code in codes:
                    last_used_ok = code.last_used_at and code.last_used_at < cutoff
                    never_used_and_old = (not code.last_used_at) and code.created_at and code.created_at < cutoff
                    if last_used_ok or never_used_and_old:
                        code.is_active = False
                        changed = True
                if changed:
                    db.session.commit()
        except Exception as e:
            # 记录错误但不中断循环
            print(f"[cleanup] 游客码清理错误: {e}")
        finally:
            time.sleep(interval_seconds)


def start_guest_cleanup(app, interval_seconds: int = 600):
    """
    启动游客连接码清理线程。确保仅启动一次。
    """
    if getattr(app, "_guest_cleanup_started", False):
        return

    t = threading.Thread(target=_guest_cleanup_loop, args=(app, interval_seconds), daemon=True)
    t.start()
    app._guest_cleanup_started = True