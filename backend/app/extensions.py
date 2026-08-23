from authlib.integrations.flask_client import OAuth
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate()
oauth = OAuth()


def init_oauth(app) -> None:
    """Configure the optional Google OpenID Connect client for this Flask app."""
    oauth.init_app(app)

    client_id = app.config["GOOGLE_CLIENT_ID"]
    client_secret = app.config["GOOGLE_CLIENT_SECRET"]
    if not client_id or not client_secret:
        return

    oauth.register(
        name="google",
        overwrite=True,
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
