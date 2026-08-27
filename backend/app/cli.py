import click
from flask import Flask

from app.extensions import db
from app.models import User


def _normalized_email(value: str) -> str:
    return value.strip().lower()


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
