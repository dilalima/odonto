from datetime import date
from functools import wraps
import hmac
import logging

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from app import db
from app.models import Appointment, ContactRequest
from app.scheduling import (
    create_appointment,
    format_date,
    format_time,
    get_available_days,
    get_available_times,
    normalize_phone,
)
from app.whatsapp import process_message, send_message, verify_signature

main = Blueprint("main", __name__)


@main.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


def doctor_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("doctor_logged_in"):
            return redirect(url_for("main.doctor_login"))
        return view(*args, **kwargs)

    return wrapped


@main.get("/")
def index():
    config = current_app.config
    return render_template(
        "index.html",
        procedures=config["PROCEDURES"],
        available_days=get_available_days(config),
        weekday_names=[
            "Segunda-feira",
            "Terça-feira",
            "Quarta-feira",
            "Quinta-feira",
            "Sexta-feira",
            "Sábado",
            "Domingo",
        ],
    )


@main.get("/api/horarios")
def api_times():
    requested_day = request.args.get("data", "")
    try:
        day = date.fromisoformat(requested_day)
    except ValueError:
        return jsonify({"error": "Informe uma data válida."}), 400
    return jsonify(
        {
            "horarios": [
                format_time(slot)
                for slot in get_available_times(day, current_app.config)
            ]
        }
    )


@main.post("/agendar")
def book():
    full_name = request.form.get("full_name", "").strip()
    age_text = request.form.get("age", "").strip()
    procedure = request.form.get("procedure", "")
    appointment_date = request.form.get("appointment_date", "")
    appointment_time = request.form.get("appointment_time", "")
    phone = request.form.get("phone", "")

    if len(full_name.split()) < 2 or len(full_name) > 160:
        flash("Informe seu nome completo.", "error")
    elif not age_text.isdigit() or not 1 <= int(age_text) <= 120:
        flash("Informe uma idade válida, de 1 a 120 anos.", "error")
    else:
        try:
            phone = normalize_phone(phone)
        except ValueError:
            flash("Informe um WhatsApp válido com DDD, por exemplo (11) 99999-9999.", "error")
            return redirect(url_for("main.index"))
        try:
            appointment = create_appointment(
                full_name=full_name,
                age=int(age_text),
                procedure=procedure,
                phone=phone,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                source="site",
                config=current_app.config,
            )
        except ValueError as error:
            db.session.rollback()
            flash("Data ou horário indisponível. Escolha outro horário.", "error")
        except TypeError:
            db.session.rollback()
            flash("Data ou horário inválido. Escolha uma opção disponível.", "error")
        else:
            if (
                current_app.config["WHATSAPP_ENABLED"]
                and current_app.config["WHATSAPP_ACCESS_TOKEN"]
                and current_app.config["WHATSAPP_PHONE_NUMBER_ID"]
            ):
                try:
                    send_message(
                        phone,
                        f"Olá, {appointment.full_name}! Seu atendimento foi confirmado para "
                        f"{format_date(appointment.appointment_date)} às "
                        f"{format_time(appointment.appointment_time)}. Até lá!",
                        current_app.config,
                    )
                except Exception:
                    logging.getLogger(__name__).exception("Falha ao enviar confirmação pelo WhatsApp")
            flash(
                f"Agendamento confirmado para {appointment.full_name}, "
                f"{format_date(appointment.appointment_date)} às "
                f"{format_time(appointment.appointment_time)}.",
                "success",
            )
            return redirect(url_for("main.index"))
    return redirect(url_for("main.index"))


@main.route("/doutora/login", methods=["GET", "POST"])
def doctor_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        configured_password = current_app.config["DOCTOR_PASSWORD"]
        if (
            not configured_password
            or not hmac.compare_digest(username, current_app.config["DOCTOR_USERNAME"])
            or not hmac.compare_digest(password, configured_password)
        ):
            flash("Credenciais inválidas ou senha ainda não configurada.", "error")
        else:
            session.clear()
            session["doctor_logged_in"] = True
            return redirect(url_for("main.doctor_dashboard"))
    return render_template("doctor_login.html")


@main.post("/doutora/sair")
@doctor_required
def doctor_logout():
    session.clear()
    return redirect(url_for("main.doctor_login"))


@main.post("/doutora/agendar")
@doctor_required
def doctor_book():
    try:
        phone = normalize_phone(request.form.get("phone", ""))
        appointment = create_appointment(
            full_name=request.form.get("full_name", ""),
            age=int(request.form.get("age", "0")),
            procedure=request.form.get("procedure", ""),
            phone=phone,
            appointment_date=request.form.get("appointment_date", ""),
            appointment_time=request.form.get("appointment_time", ""),
            source="doutora",
            config=current_app.config,
        )
    except (ValueError, TypeError):
        db.session.rollback()
        flash("Não foi possível salvar: confira o WhatsApp, a data e o horário.", "error")
    else:
        flash(
            f"Agendamento salvo para {appointment.full_name}, "
                f"{format_date(appointment.appointment_date)} às "
            f"{format_time(appointment.appointment_time)}.",
            "success",
        )
    return redirect(url_for("main.doctor_dashboard"))


@main.post("/doutora/cancelar/<int:appointment_id>")
@doctor_required
def doctor_cancel(appointment_id):
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None or appointment.status != "confirmado":
        flash("Esse atendimento não está mais confirmado.", "error")
    else:
        appointment.status = "cancelado"
        db.session.commit()
        flash(
            f"Atendimento de {appointment.full_name} cancelado. "
            "O dia voltou a ficar disponível.",
            "success",
        )
    return redirect(url_for("main.doctor_dashboard"))


@main.get("/doutora")
@doctor_required
def doctor_dashboard():
    appointments = Appointment.query.filter_by(status="confirmado").order_by(
        Appointment.appointment_date, Appointment.appointment_time
    ).all()
    contact_requests = ContactRequest.query.filter_by(status="pendente").order_by(
        ContactRequest.created_at
    ).all()
    days = get_available_days(current_app.config, days_ahead=30)
    availability = [
        {
            "date": day,
            "times": get_available_times(day, current_app.config),
        }
        for day in days
    ]
    return render_template(
        "doctor_dashboard.html",
        appointments=appointments,
        contact_requests=contact_requests,
        availability=availability,
        procedures=current_app.config["PROCEDURES"],
        format_date=format_date,
        format_time=format_time,
    )


@main.get("/webhook/whatsapp")
def whatsapp_verify():
    if (
        request.args.get("hub.mode") == "subscribe"
        and request.args.get("hub.verify_token")
        == current_app.config["WHATSAPP_VERIFY_TOKEN"]
        and current_app.config["WHATSAPP_VERIFY_TOKEN"]
    ):
        return request.args.get("hub.challenge", ""), 200
    return "Verificação inválida", 403


@main.post("/webhook/whatsapp")
def whatsapp_webhook():
    config = current_app.config
    raw_body = request.get_data()
    if not verify_signature(
        raw_body, request.headers.get("X-Hub-Signature-256"), config["WHATSAPP_APP_SECRET"]
    ):
        return jsonify({"error": "Assinatura do webhook inválida."}), 401

    payload = request.get_json(silent=False)
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                phone = message.get("from")
                text = message.get("text", {}).get("body", "")
                reply = process_message(phone, text, config)
                send_message(phone, reply, config)
    return jsonify({"status": "ok"}), 200
