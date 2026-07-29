from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])

def init_security(app):
    is_prod = app.config.get("DEBUG") is False
    Talisman(
        app,
        force_https=is_prod,
        content_security_policy={
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline'",
            "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src": "https://fonts.gstatic.com",
        },
    )
    limiter.init_app(app)
