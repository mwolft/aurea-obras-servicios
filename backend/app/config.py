import os


VALID_APP_ENVS = {"development", "production", "test"}


def normalize_database_url(database_url: str) -> str:
    """Use the installed psycopg v3 driver for standard PostgreSQL URLs."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)

    return database_url


def load_config() -> dict[str, str | bool | None]:
    """Load the minimal runtime configuration from environment variables."""
    database_url = os.getenv("DATABASE_URL")
    secret_key = os.getenv("SECRET_KEY")
    app_env = os.getenv("APP_ENV", "development")

    if app_env not in VALID_APP_ENVS:
        raise RuntimeError("APP_ENV must be development, production, or test.")

    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured.")

    if not secret_key:
        raise RuntimeError("SECRET_KEY must be configured.")

    frontend_origin = os.getenv("FRONTEND_ORIGIN")
    cloudinary_values = {
        "CLOUDINARY_CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
        "CLOUDINARY_API_KEY": os.getenv("CLOUDINARY_API_KEY"),
        "CLOUDINARY_API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
    }
    google_values = {
        "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
        "GOOGLE_REDIRECT_URI": os.getenv("GOOGLE_REDIRECT_URI"),
    }

    if app_env == "production":
        if not frontend_origin:
            raise RuntimeError("FRONTEND_ORIGIN must be configured in production.")

        missing_cloudinary_values = [name for name, value in cloudinary_values.items() if not value]
        if missing_cloudinary_values:
            raise RuntimeError(
                "Cloudinary must be fully configured in production: "
                + ", ".join(missing_cloudinary_values)
            )

        if any(google_values.values()) and not all(google_values.values()):
            raise RuntimeError(
                "Google OAuth must be fully configured when enabled in production."
            )

    return {
        "APP_ENV": app_env,
        "FRONTEND_ORIGIN": frontend_origin or "http://localhost:3000",
        "DATABASE_URL": database_url,
        "SQLALCHEMY_DATABASE_URI": normalize_database_url(database_url),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SECRET_KEY": secret_key,
        "DEBUG": app_env == "development",
        "SESSION_COOKIE_NAME": "aurea_session",
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": app_env == "production",
        **google_values,
        **cloudinary_values,
    }
