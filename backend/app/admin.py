import logging
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_admin import Admin, AdminIndexView, BaseView
from flask_admin import babel as admin_babel
from flask_admin.base import expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import SecureForm
from markupsafe import Markup
from wtforms import FileField, PasswordField, StringField
from wtforms.validators import InputRequired
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import Reservation, Tool, ToolBlock, ToolImage, User
from app.services.authentication import (
    authenticate_with_password,
    get_current_user,
    is_valid_password,
    start_user_session,
)
from app.services.admin_calendar import get_agenda_events, group_agenda_events
from app.services.admin_users import AdminAccessChangeError, change_admin_access
from app.services.availability import reservation_status_label
from app.services.cloudinary_storage import get_cloudinary_storage
from app.services.reservations import (
    ReservationCancellationError,
    ReservationReviewError,
    cancel_reservation,
    review_delivery_reservation,
)
from app.services.tool_blocks import (
    ToolBlockConflictError,
    ToolBlockNotFoundError,
    ToolBlockValidationError,
    create_tool_block,
    delete_tool_block,
    update_tool_block,
)


logger = logging.getLogger(__name__)

ADMIN_TEXT_OVERRIDES = {
    "Save": "Guardar",
    "Save and Add Another": "Guardar y agregar otro",
    "Save and Continue Editing": "Guardar y continuar editando",
}


def spanish_admin_gettext(message: str, **variables: str) -> str:
    """Keep Flask-Admin's Spanish catalog, correcting its save labels for Spain."""
    return ADMIN_TEXT_OVERRIDES.get(message, admin_babel.gettext(message, **variables))


class AdminAccessMixin:
    """Apply the Flask session's administrator flag to every Admin view."""

    def is_accessible(self) -> bool:
        user = get_current_user()
        return user is not None and user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        if get_current_user() is None:
            return redirect(url_for("admin_login"))

        abort(403)


class AuthenticatedAdminIndexView(AdminAccessMixin, AdminIndexView):
    pass


class SecureModelView(AdminAccessMixin, ModelView):
    form_base_class = SecureForm

    def render(self, template, **kwargs):
        self._template_args["_gettext"] = spanish_admin_gettext
        return super().render(template, **kwargs)


class AdminCsrfForm(SecureForm):
    pass


class AdminLoginForm(SecureForm):
    email = StringField("Correo electrónico", validators=[InputRequired()])
    password = PasswordField("Contraseña", validators=[InputRequired()])


class ChangePasswordForm(SecureForm):
    current_password = PasswordField("Contraseña actual")
    new_password = PasswordField("Nueva contraseña", validators=[InputRequired()])
    confirm_password = PasswordField("Repetir nueva contraseña", validators=[InputRequired()])


def admin_login():
    """Authenticate an existing administrator using the regular User credentials."""
    current_user = get_current_user()
    if current_user is not None and current_user.is_admin:
        return redirect(url_for("admin.index"))

    form = AdminLoginForm(request.form)
    if request.method == "POST":
        if not form.validate():
            abort(400)

        user = authenticate_with_password(form.email.data, form.password.data)
        if user is not None and user.is_admin:
            start_user_session(user)
            return redirect(url_for("admin.index"))

        flash("Credenciales incorrectas o acceso no autorizado.", "error")

    return render_template("admin/login.html", form=form)


def admin_logout():
    """End the shared Flask session from the administrative interface."""
    form = AdminCsrfForm(request.form)
    if not form.validate():
        abort(400)

    session.clear()
    return redirect(url_for("admin_login"))


class ToolAdmin(SecureModelView):
    can_delete = False
    column_list = (
        "name",
        "category",
        "daily_price",
        "deposit_amount",
        "is_published",
        "is_available",
        "delivery_available",
    )
    column_searchable_list = ("name", "category")
    column_filters = ("category", "is_published", "is_available")
    column_labels = {
        "name": "Nombre",
        "category": "Categoría",
        "description": "Descripción",
        "daily_price": "Precio diario",
        "deposit_amount": "Fianza",
        "pickup_available": "Recogida en almacén",
        "delivery_available": "Transporte disponible",
        "delivery_price_per_km": "Tarifa transporte €/km",
        "is_published": "Publicada",
        "is_available": "Disponible",
        "included_km": "Kilómetros incluidos",
        "extra_km_price": "Precio km excedido",
        "created_at": "Creada",
        "updated_at": "Actualizada",
    }
    form_columns = (
        "name",
        "category",
        "description",
        "daily_price",
        "deposit_amount",
        "pickup_available",
        "delivery_available",
        "delivery_price_per_km",
        "is_published",
        "is_available",
        "included_km",
        "extra_km_price",
    )


class ToolImageAdmin(SecureModelView):
    column_list = ("tool", "position", "created_at")
    column_default_sort = ("position", False)
    form_extra_fields = {"image_file": FileField("Archivo de imagen")}
    form_columns = ("tool", "image_file", "position")
    column_labels = {
        "tool": "Herramienta",
        "image_file": "Archivo de imagen",
        "position": "Orden",
        "created_at": "Creada",
    }
    form_args = {
        "position": {
            "description": "1 = imagen principal; 2, 3… = imágenes siguientes.",
        }
    }

    def on_model_change(self, form, model, is_created):
        image_file = form.image_file.data

        if image_file and image_file.filename:
            storage = get_cloudinary_storage()
            previous_storage_key = None if is_created else model.storage_key
            model.storage_key = storage.upload_image(image_file)
            form._uploaded_storage_key = model.storage_key
            form._previous_storage_key = previous_storage_key
        elif is_created:
            raise ValueError("Debe seleccionar un archivo de imagen.")

    def after_model_change(self, form, model, is_created):
        previous_storage_key = getattr(form, "_previous_storage_key", None)

        if previous_storage_key and previous_storage_key != model.storage_key:
            self._delete_asset_safely(previous_storage_key)

    def after_model_delete(self, model):
        self._delete_asset_safely(model.storage_key)

    def create_model(self, form):
        result = super().create_model(form)

        if result is False:
            self._delete_uploaded_asset_safely(form)

        return result

    def update_model(self, form, model):
        result = super().update_model(form, model)

        if not result:
            self._delete_uploaded_asset_safely(form)

        return result

    @staticmethod
    def _delete_asset_safely(storage_key):
        try:
            get_cloudinary_storage().delete_image(storage_key)
        except Exception:
            logger.exception("Cloudinary asset cleanup failed.")

    def _delete_uploaded_asset_safely(self, form):
        storage_key = getattr(form, "_uploaded_storage_key", None)

        if storage_key:
            self._delete_asset_safely(storage_key)


class UserAdmin(SecureModelView):
    """Read-only user administration with explicit administrator-access actions."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    column_list = ("name", "email", "account_type", "is_admin", "created_at", "admin_access_action")
    column_searchable_list = ("name", "email")
    column_filters = ("is_admin",)
    column_default_sort = ("created_at", True)
    column_details_list = ("name", "email", "account_type", "is_admin", "created_at", "admin_access_action")
    column_labels = {
        "name": "Nombre",
        "email": "Correo electrónico",
        "account_type": "Tipo de cuenta",
        "is_admin": "Administrador",
        "created_at": "Creado",
        "admin_access_action": "Acceso administrativo",
    }
    column_formatters = {
        "is_admin": lambda view, context, model, name: "Sí" if model.is_admin else "No",
        "admin_access_action": lambda view, context, model, name: view._access_action_link(model),
    }

    @staticmethod
    def _access_action_link(user: User):
        if user.is_admin:
            action_url = url_for(".revoke_admin_access", user_id=user.id)
            return Markup(f'<a class="btn btn-warning btn-xs" href="{action_url}">Retirar acceso</a>')

        action_url = url_for(".grant_admin_access", user_id=user.id)
        return Markup(f'<a class="btn btn-primary btn-xs" href="{action_url}">Dar acceso</a>')

    def _change_access(self, user_id: int, grant_access: bool):
        csrf_form = AdminCsrfForm(request.form)
        target = db.session.get(User, user_id)
        if target is None:
            flash("El usuario no existe.", "error")
            return redirect(url_for(".index_view"))

        if request.method == "POST":
            if not csrf_form.validate():
                abort(400)

            actor = get_current_user()
            actor_id = actor.id if actor is not None else None
            if actor_id is None:
                return redirect(url_for("admin_login"))

            # The service owns the transaction and locks the affected users.
            db.session.rollback()
            try:
                change_admin_access(actor_id, user_id, grant_access)
            except AdminAccessChangeError as error:
                flash(str(error), "error")
            else:
                flash(
                    "Acceso administrativo concedido."
                    if grant_access
                    else "Acceso administrativo retirado.",
                    "success",
                )

            return redirect(url_for(".details_view", id=user_id))

        return self.render(
            "admin/change_admin_access.html",
            target=target,
            grant_access=grant_access,
            csrf_form=csrf_form,
        )

    @expose("/grant-admin-access/<int:user_id>", methods=("GET", "POST"))
    def grant_admin_access(self, user_id: int):
        return self._change_access(user_id, grant_access=True)

    @expose("/revoke-admin-access/<int:user_id>", methods=("GET", "POST"))
    def revoke_admin_access(self, user_id: int):
        return self._change_access(user_id, grant_access=False)


class AccountAdminView(AdminAccessMixin, BaseView):
    """Allow the current administrator to set or change only their own password."""

    @expose("/", methods=("GET", "POST"))
    def index(self):
        user = get_current_user()
        if user is None:
            return redirect(url_for("admin_login"))

        form = ChangePasswordForm(request.form)
        requires_current_password = user.password_hash is not None
        if request.method == "POST":
            if not form.validate():
                abort(400)
            if form.new_password.data != form.confirm_password.data:
                flash("Las nuevas contraseñas no coinciden.", "error")
            elif not is_valid_password(form.new_password.data):
                flash("La nueva contraseña debe contener al menos 8 caracteres.", "error")
            elif requires_current_password and not check_password_hash(
                user.password_hash, form.current_password.data or ""
            ):
                flash("La contraseña actual no es correcta.", "error")
            else:
                user.password_hash = generate_password_hash(form.new_password.data)
                db.session.commit()
                flash("Contraseña actualizada.", "success")
                return redirect(url_for(".index"))

        return self.render(
            "admin/change_password.html",
            form=form,
            requires_current_password=requires_current_password,
        )


class ToolBlockAdmin(SecureModelView):
    """Administrative CRUD backed by the serialized ToolBlock domain service."""

    can_view_details = True
    column_select_related_list = (ToolBlock.tool,)
    column_list = ("tool", "start_date", "end_date", "reason", "created_at")
    column_filters = ("tool", "start_date", "end_date")
    column_searchable_list = ("reason",)
    column_default_sort = ("start_date", False)
    form_columns = ("tool", "start_date", "end_date", "reason")
    column_labels = {
        "tool": "Herramienta",
        "start_date": "Fecha inicio",
        "end_date": "Fecha fin",
        "reason": "Motivo",
        "created_at": "Creado",
        "updated_at": "Actualizado",
    }
    column_formatters = {
        "tool": lambda view, context, model, name: model.tool.name,
    }

    @staticmethod
    def _form_values(form):
        tool = form.tool.data
        if tool is None:
            raise ToolBlockValidationError("La herramienta es obligatoria.")

        return tool.id, form.start_date.data, form.end_date.data, form.reason.data

    @staticmethod
    def _flash_service_error(error: Exception) -> None:
        flash(str(error) or "No se ha podido guardar el bloqueo.", "error")

    def create_model(self, form):
        try:
            tool_id, start_date, end_date, reason = self._form_values(form)
            # The relationship field may have loaded its choices in the scoped
            # session. Start the domain operation with its own clean transaction.
            db.session.rollback()
            return create_tool_block(tool_id, start_date, end_date, reason)
        except (ToolBlockValidationError, ToolBlockConflictError, ToolBlockNotFoundError) as error:
            self._flash_service_error(error)
            return False

    def update_model(self, form, model):
        block_id = model.id
        try:
            tool_id, start_date, end_date, reason = self._form_values(form)
            # Flask-Admin loaded and populated the model in this scoped session. The
            # domain service owns the complete transaction, so discard that pending
            # generic mutation before it re-locks and validates the block.
            db.session.rollback()
            update_tool_block(block_id, tool_id, start_date, end_date, reason)
            return True
        except (ToolBlockValidationError, ToolBlockConflictError, ToolBlockNotFoundError) as error:
            self._flash_service_error(error)
            return False

    def delete_model(self, model):
        block_id = model.id
        # See update_model: deletion must use the controlled transaction too.
        db.session.rollback()
        try:
            delete_tool_block(block_id)
            return True
        except ToolBlockNotFoundError as error:
            self._flash_service_error(error)
            return False


class ReservationAdmin(SecureModelView):
    """Read-only reservation administration with controlled domain actions."""

    can_create = False
    can_delete = False
    can_edit = False
    can_view_details = True
    column_select_related_list = (Reservation.tool,)

    column_list = (
        "id",
        "tool",
        "start_date",
        "end_date",
        "customer_name",
        "customer_email",
        "customer_phone",
        "fulfillment_method",
        "status",
        "total_amount",
        "payment_expires_at",
        "created_at",
        "review_delivery_action",
        "cancel_action",
    )
    column_filters = ("status", "fulfillment_method", "tool", "start_date", "end_date")
    column_searchable_list = ("customer_name", "customer_email", "customer_phone")
    column_default_sort = ("created_at", True)
    column_labels = {
        "tool": "Herramienta",
        "customer_name": "Cliente",
        "customer_email": "Email",
        "customer_phone": "Teléfono",
        "start_date": "Fecha inicio",
        "end_date": "Fecha devolución",
        "fulfillment_method": "Modalidad",
        "status": "Estado",
        "payment_expires_at": "Límite de pago",
        "charged_days": "Días cobrados",
        "daily_price_snapshot": "Precio diario aplicado",
        "delivery_price_per_km_snapshot": "Tarifa transporte €/km aplicada",
        "billable_km": "Kilómetros facturables",
        "rental_amount": "Alquiler",
        "delivery_amount": "Transporte",
        "total_amount": "Total a pagar",
        "tool_deposit_amount": "Fianza configurada actualmente en la herramienta",
        "review_delivery_action": "Revisar transporte",
        "cancel_action": "Cancelar reserva",
    }
    column_details_list = (
        "id",
        "tool",
        "start_date",
        "end_date",
        "customer_name",
        "customer_email",
        "customer_phone",
        "fulfillment_method",
        "delivery_address",
        "status",
        "payment_expires_at",
        "charged_days",
        "daily_price_snapshot",
        "rental_amount",
        "billable_km",
        "delivery_price_per_km_snapshot",
        "delivery_amount",
        "total_amount",
        "tool_deposit_amount",
        "created_at",
        "updated_at",
        "review_delivery_action",
        "cancel_action",
    )
    column_formatters = {
        "tool": lambda view, context, model, name: model.tool.name,
        "status": lambda view, context, model, name: view._status_label(model),
        "daily_price_snapshot": lambda view, context, model, name: view._format_amount(
            model.daily_price_snapshot
        ),
        "delivery_price_per_km_snapshot": lambda view, context, model, name: view._format_amount(
            model.delivery_price_per_km_snapshot
        ),
        "rental_amount": lambda view, context, model, name: view._format_amount(model.rental_amount),
        "delivery_amount": lambda view, context, model, name: view._format_amount(model.delivery_amount),
        "total_amount": lambda view, context, model, name: view._format_amount(model.total_amount),
        "tool_deposit_amount": lambda view, context, model, name: view._format_amount(
            model.tool.deposit_amount
        ),
        "review_delivery_action": lambda view, context, model, name: view._review_delivery_link(model),
        "cancel_action": lambda view, context, model, name: view._cancel_reservation_link(model),
    }

    @staticmethod
    def _format_amount(value: Decimal | None) -> str:
        return "—" if value is None else f"{value:.2f} €"

    @staticmethod
    def _is_pending_delivery_review(reservation: Reservation) -> bool:
        return (
            reservation.status == "pending_review"
            and reservation.fulfillment_method == "delivery"
        )

    @classmethod
    def _status_label(cls, reservation: Reservation) -> str:
        return reservation_status_label(reservation)

    @staticmethod
    def _can_cancel(reservation: Reservation) -> bool:
        return reservation.status in {"pending_review", "pending_payment", "confirmed"}

    def _review_delivery_link(self, reservation: Reservation):
        if not self._is_pending_delivery_review(reservation):
            return "—"

        review_url = url_for(".review_delivery", reservation_id=reservation.id)
        return Markup(f'<a class="btn btn-primary btn-xs" href="{review_url}">Revisar transporte</a>')

    def _cancel_reservation_link(self, reservation: Reservation):
        if not self._can_cancel(reservation):
            return "—"

        cancel_url = url_for(".cancel_reservation", reservation_id=reservation.id)
        return Markup(f'<a class="btn btn-warning btn-xs" href="{cancel_url}">Cancelar reserva</a>')

    @staticmethod
    def _parse_billable_km(value: str | None) -> Decimal:
        if value is None or not value.strip():
            raise ValueError("Los kilómetros facturables son obligatorios.")

        try:
            billable_km = Decimal(value.strip())
        except InvalidOperation as error:
            raise ValueError("Los kilómetros facturables deben ser un número decimal válido.") from error

        if not billable_km.is_finite() or billable_km < 0:
            raise ValueError("Los kilómetros facturables deben ser un número decimal mayor o igual que cero.")

        if billable_km.as_tuple().exponent < -2:
            raise ValueError("Los kilómetros facturables admiten como máximo dos decimales.")

        return billable_km

    @expose("/review-delivery/<int:reservation_id>", methods=("GET", "POST"))
    def review_delivery(self, reservation_id: int):
        csrf_form = AdminCsrfForm(request.form)
        if request.method == "POST":
            if not csrf_form.validate():
                abort(400)
            try:
                billable_km = self._parse_billable_km(request.form.get("billable_km"))
                # Access control loaded the session user. The domain service owns the
                # transactional operation, so begin it with a clean session.
                db.session.rollback()
                review_delivery_reservation(reservation_id, billable_km)
            except ValueError as error:
                flash(str(error), "error")
            except ReservationReviewError:
                flash("La reserva ya no está pendiente de revisión de transporte.", "error")
            else:
                flash("Transporte revisado y presupuesto preparado para el pago.", "success")

            return redirect(url_for(".details_view", id=reservation_id))

        reservation = db.session.get(Reservation, reservation_id)
        if reservation is None:
            flash("La reserva no existe.", "error")
            return redirect(url_for(".index_view"))

        if not self._is_pending_delivery_review(reservation):
            flash("La reserva ya no está pendiente de revisión de transporte.", "error")
            return redirect(url_for(".details_view", id=reservation_id))

        return self.render(
            "admin/review_delivery.html", reservation=reservation, csrf_form=csrf_form
        )

    @expose("/cancel/<int:reservation_id>", methods=("GET", "POST"))
    def cancel_reservation(self, reservation_id: int):
        csrf_form = AdminCsrfForm(request.form)
        if request.method == "POST":
            if not csrf_form.validate():
                abort(400)
            try:
                # See review_delivery: cancellation owns its own transaction.
                db.session.rollback()
                cancel_reservation(reservation_id)
            except ReservationCancellationError:
                flash("La reserva ya no se puede cancelar.", "error")
            else:
                flash(
                    "Reserva cancelada. Esta acción no gestiona pagos, reembolsos ni fianzas.",
                    "success",
                )

            return redirect(url_for(".details_view", id=reservation_id))

        reservation = db.session.get(Reservation, reservation_id)
        if reservation is None:
            flash("La reserva no existe.", "error")
            return redirect(url_for(".index_view"))

        if not self._can_cancel(reservation):
            flash("La reserva ya no se puede cancelar.", "error")
            return redirect(url_for(".details_view", id=reservation_id))

        return self.render(
            "admin/cancel_reservation.html",
            reservation=reservation,
            status_label=self._status_label(reservation),
            csrf_form=csrf_form,
        )


class AgendaAdminView(AdminAccessMixin, BaseView):
    """Read-only agenda grouping operational events by tool."""

    @staticmethod
    def _current_month_range() -> tuple[date, date]:
        today = date.today()
        start_date = today.replace(day=1)
        return start_date, today.replace(day=monthrange(today.year, today.month)[1])

    @staticmethod
    def _parse_date(value: str | None, label: str) -> tuple[date | None, str | None]:
        if not value:
            return None, f"La fecha de {label} es obligatoria."
        try:
            return date.fromisoformat(value), None
        except ValueError:
            return None, f"La fecha de {label} debe usar el formato AAAA-MM-DD."

    @expose("/")
    def index(self):
        default_start_date, default_end_date = self._current_month_range()
        raw_start_date = request.args.get("start_date")
        raw_end_date = request.args.get("end_date")
        error_message = None

        if raw_start_date is None and raw_end_date is None:
            start_date, end_date = default_start_date, default_end_date
        else:
            start_date, start_error = self._parse_date(raw_start_date, "inicio")
            end_date, end_error = self._parse_date(raw_end_date, "fin")
            error_message = start_error or end_error
            if error_message is None and end_date < start_date:
                error_message = "La fecha de fin debe ser posterior o igual a la fecha de inicio."

        selected_tool_id = None
        raw_tool_id = request.args.get("tool_id")
        if error_message is None and raw_tool_id:
            try:
                selected_tool_id = int(raw_tool_id)
            except ValueError:
                error_message = "La herramienta seleccionada no es válida."
            else:
                if db.session.get(Tool, selected_tool_id) is None:
                    error_message = "La herramienta seleccionada no existe."

        tools = Tool.query.order_by(Tool.name.asc(), Tool.id.asc()).all()
        groups = []
        if error_message is None:
            groups = group_agenda_events(get_agenda_events(start_date, end_date, selected_tool_id))

        return self.render(
            "admin/agenda.html",
            start_date=start_date if error_message is None else raw_start_date,
            end_date=end_date if error_message is None else raw_end_date,
            selected_tool_id=selected_tool_id,
            tools=tools,
            groups=groups,
            error_message=error_message,
        )


def init_admin(app: Flask) -> Admin:
    admin = Admin(
        app,
        name="AUREA Administración",
        url="/admin",
        index_view=AuthenticatedAdminIndexView(name="Inicio", url="/admin"),
    )
    admin.add_view(ToolAdmin(Tool, db, name="Herramientas", category="Catálogo"))
    admin.add_view(ToolImageAdmin(ToolImage, db, name="Fotografías", category="Catálogo"))
    admin.add_view(ToolBlockAdmin(ToolBlock, db, name="Bloqueos", category="Reservas"))
    admin.add_view(ReservationAdmin(Reservation, db, name="Reservas", category="Reservas"))
    admin.add_view(AgendaAdminView(name="Agenda", endpoint="calendar", url="calendar", category="Reservas"))
    admin.add_view(UserAdmin(User, db, name="Usuarios", category="Usuarios"))
    admin.add_view(
        AccountAdminView(
            name="Cambiar contraseña",
            endpoint="admin_account",
            url="account",
            category="Cuenta",
        )
    )

    app.add_url_rule("/admin/login", endpoint="admin_login", view_func=admin_login, methods=("GET", "POST"))
    app.add_url_rule("/admin/logout", endpoint="admin_logout", view_func=admin_logout, methods=("POST",))

    @app.context_processor
    def inject_admin_logout_form():
        return {
            "admin_current_user": get_current_user(),
            "admin_logout_form": AdminCsrfForm(),
        }

    return admin
