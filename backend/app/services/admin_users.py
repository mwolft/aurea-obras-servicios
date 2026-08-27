from sqlalchemy import select

from app.extensions import db
from app.models import User


class AdminAccessChangeError(Exception):
    """Raised when an administrator-access transition is not permitted."""


def change_admin_access(actor_id: int, target_id: int, grant_access: bool) -> None:
    """Safely grant or revoke administrator access without leaving zero admins."""
    with db.session.begin():
        locked_users = db.session.execute(
            select(User)
            .where(User.id.in_((actor_id, target_id)))
            .order_by(User.id)
            .with_for_update()
        ).scalars().all()
        users_by_id = {user.id: user for user in locked_users}
        actor = users_by_id.get(actor_id)
        target = users_by_id.get(target_id)

        if actor is None or not actor.is_admin:
            raise AdminAccessChangeError("No tienes permiso para gestionar administradores.")
        if target is None:
            raise AdminAccessChangeError("El usuario no existe.")
        if target.is_admin == grant_access:
            raise AdminAccessChangeError("El acceso administrativo ya tiene ese estado.")

        if not grant_access:
            if actor.id == target.id:
                raise AdminAccessChangeError("No puedes retirar tu propio acceso administrativo.")

            administrators = db.session.execute(
                select(User).where(User.is_admin.is_(True)).order_by(User.id).with_for_update()
            ).scalars().all()
            if len(administrators) <= 1:
                raise AdminAccessChangeError("No se puede retirar el acceso al último administrador.")

        target.is_admin = grant_access
