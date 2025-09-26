import os

from . import create_app
from .extensions import socketio

app = create_app()

if __name__ == "__main__":
    port = os.getenv("SOCKETIO_PORT", 5000)
    socketio.run(app, host="0.0.0.0", port=port, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
