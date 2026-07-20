"""
Billing Software — Flask Application Factory
"""
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config")
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    # Register blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.api import api_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; connect-src 'self'",
        )
        return response

    return app
