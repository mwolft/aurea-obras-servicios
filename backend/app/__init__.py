from flask import Flask, request

import app.models
from app.admin import init_admin
from app.config import load_config
from app.extensions import db, migrate
from app.routes.health import health_bp
from app.routes.tools import tools_bp


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    db.init_app(app)
    migrate.init_app(app, db)
    if app.config["APP_ENV"] == "development":
        init_admin(app)
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(tools_bp, url_prefix="/api/tools")

    @app.after_request
    def add_api_cors_headers(response):
        if (
            request.path.startswith("/api/")
            and request.headers.get("Origin") == app.config["FRONTEND_ORIGIN"]
        ):
            response.headers["Access-Control-Allow-Origin"] = app.config["FRONTEND_ORIGIN"]
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Vary"] = "Origin"

        return response

    return app
