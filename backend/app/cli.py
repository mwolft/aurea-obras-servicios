import click
from flask import Flask
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User
from app.services.authentication import MINIMUM_PASSWORD_LENGTH, is_valid_password, normalize_email


def _normalized_email(value: str) -> str:
    return normalize_email(value)


def init_cli(app: Flask) -> None:
    """Register local-only operational commands that change administrator access."""

    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin(email: str) -> None:
        user = User.query.filter_by(email=_normalized_email(email)).one_or_none()
        if user is None:
            raise click.ClickException("No se ha encontrado ningún usuario con ese email.")

        if user.is_admin:
            click.echo("El usuario ya tiene acceso administrativo.")
            return

        user.is_admin = True
        db.session.commit()
        click.echo("Acceso administrativo concedido.")

    @app.cli.command("revoke-admin")
    @click.argument("email")
    def revoke_admin(email: str) -> None:
        user = User.query.filter_by(email=_normalized_email(email)).one_or_none()
        if user is None:
            raise click.ClickException("No se ha encontrado ningún usuario con ese email.")

        if not user.is_admin:
            click.echo("El usuario no tiene acceso administrativo.")
            return

        user.is_admin = False
        db.session.commit()
        click.echo("Acceso administrativo revocado.")

    @app.cli.command("set-password")
    @click.argument("email")
    def set_password(email: str) -> None:
        """Set or reset an existing user's password without changing its access flags."""
        user = User.query.filter_by(email=_normalized_email(email)).one_or_none()
        if user is None:
            raise click.ClickException("No se ha encontrado ningún usuario con ese email.")

        password = click.prompt(
            "Nueva contraseña",
            hide_input=True,
            confirmation_prompt=True,
        )
        if not is_valid_password(password):
            raise click.ClickException(
                f"La contraseña debe contener al menos {MINIMUM_PASSWORD_LENGTH} caracteres."
            )

        user.password_hash = generate_password_hash(password)
        db.session.commit()
        click.echo("Contraseña actualizada.")
