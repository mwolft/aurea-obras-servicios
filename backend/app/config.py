import os


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

    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured.")

    if not secret_key:
        raise RuntimeError("SECRET_KEY must be configured.")

    return {
        "APP_ENV": os.getenv("APP_ENV", "development"),
        "FRONTEND_ORIGIN": os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        "DATABASE_URL": database_url,
        "SQLALCHEMY_DATABASE_URI": normalize_database_url(database_url),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SECRET_KEY": secret_key,
        "CLOUDINARY_CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
        "CLOUDINARY_API_KEY": os.getenv("CLOUDINARY_API_KEY"),
        "CLOUDINARY_API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
    }
