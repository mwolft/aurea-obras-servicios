import logging
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_admin import Admin, AdminIndexView, BaseView
from flask_admin.base import expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import SecureForm
from markupsafe import Markup
from wtforms import FileField, PasswordField, StringField
from wtforms.validators import InputRequired

from app.extensions import db
from app.models import Reservation, Tool, ToolBlock, ToolImage
from app.services.authentication import authenticate_with_password, get_current_user, start_user_session
from app.services.admin_calendar import get_agenda_events, group_agenda_events
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


class AdminCsrfForm(SecureForm):
    pass


class AdminLoginForm(SecureForm):
    email = StringField("Correo electrónico", validators=[InputRequired()])
    password = PasswordField("Contraseña", validators=[InputRequired()])


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
    column_list = ("tool", "storage_key", "position", "created_at")
    column_searchable_list = ("storage_key",)
    column_default_sort = ("position", False)
    form_extra_fields = {"image_file": FileField("Archivo de imagen")}
    form_columns = ("tool", "image_file", "position")

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
    admin.add_view(ToolAdmin(Tool, db, category="Catálogo"))
    admin.add_view(ToolImageAdmin(ToolImage, db, category="Catálogo"))
    admin.add_view(ToolBlockAdmin(ToolBlock, db, category="Reservas"))
    admin.add_view(ReservationAdmin(Reservation, db, category="Reservas"))
    admin.add_view(AgendaAdminView(name="Agenda", endpoint="calendar", url="calendar", category="Reservas"))

    app.add_url_rule("/admin/login", endpoint="admin_login", view_func=admin_login, methods=("GET", "POST"))
    app.add_url_rule("/admin/logout", endpoint="admin_logout", view_func=admin_logout, methods=("POST",))

    @app.context_processor
    def inject_admin_logout_form():
        return {"admin_logout_form": AdminCsrfForm()}

    return admin
