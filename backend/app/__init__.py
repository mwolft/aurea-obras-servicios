from flask import Flask, request

import app.models
from app.admin import init_admin
from app.cli import init_cli
from app.config import load_config
from app.extensions import babel, db, init_oauth, migrate
from app.routes.health import health_bp
from app.routes.auth import auth_bp
from app.routes.account import account_bp
from app.routes.tools import tools_bp


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    db.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app)
    init_oauth(app)
    init_cli(app)
    init_admin(app)
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(account_bp, url_prefix="/api/account")
    app.register_blueprint(tools_bp, url_prefix="/api/tools")

    @app.after_request
    def add_api_cors_headers(response):
        if (
            request.path.startswith("/api/")
            and request.headers.get("Origin") == app.config["FRONTEND_ORIGIN"]
        ):
            response.headers["Access-Control-Allow-Origin"] = app.config["FRONTEND_ORIGIN"]
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.vary.add("Origin")

        return response

    return app
