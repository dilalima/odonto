from datetime import date, datetime, time, timedelta
import re

from app import db
from app.models import Appointment
from sqlalchemy.exc import IntegrityError


def get_available_times(day, config):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    if day < date.today():
        return []

    working_hours = config["WORKING_HOURS"].get(day.weekday(), [])
    if not working_hours:
        return []

    booked = Appointment.query.filter_by(
        appointment_date=day, status="confirmado"
    ).first()
    if booked:
        return []
    now = datetime.now().time()
    return [
        slot
        for slot in working_hours
        if day != date.today() or slot > now
    ]


def get_available_procedures(day, config):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    procedures_by_weekday = config.get("PROCEDURES_BY_WEEKDAY")
    if procedures_by_weekday is None:
        return list(config["PROCEDURES"])
    return list(
        procedures_by_weekday.get(day.weekday(), config["PROCEDURES"])
    )


def get_available_days(config, days_ahead=30):
    today = date.today()
    return [
        today + timedelta(days=offset)
        for offset in range(days_ahead + 1)
        if get_available_times(today + timedelta(days=offset), config)
    ]


def get_available_days_for_procedure(procedure, config, days_ahead=30):
    return [
        day
        for day in get_available_days(config, days_ahead=days_ahead)
        if procedure in get_available_procedures(day, config)
    ]


def create_appointment(
    *, full_name, age, procedure, phone, appointment_date, appointment_time, source, config
):
    full_name = full_name.strip()
    if len(full_name.split()) < 2 or len(full_name) > 160:
        raise ValueError("Informe o nome completo.")
    if not isinstance(age, int) or not 1 <= age <= 120:
        raise ValueError("Informe uma idade válida.")
    phone = normalize_phone(phone)
    day = date.fromisoformat(appointment_date)
    slot = time.fromisoformat(appointment_time)

    if procedure not in get_available_procedures(day, config):
        raise ValueError("O procedimento selecionado não está disponível.")
    if slot not in get_available_times(day, config):
        raise ValueError("Esse horário acabou de ficar indisponível. Escolha outro.")

    appointment = Appointment(
        full_name=full_name,
        age=age,
        procedure=procedure,
        phone=phone,
        appointment_date=day,
        appointment_time=slot,
        source=source,
    )
    db.session.add(appointment)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ValueError(
            "Esse horário acabou de ficar indisponível. Escolha outro."
        ) from error
    return appointment


def normalize_phone(phone):
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) in (10, 11):
        digits = "55" + digits
    if not 12 <= len(digits) <= 15 or not digits.startswith("55"):
        raise ValueError("Informe um WhatsApp válido com DDD.")
    return digits


def format_date(day):
    return day.strftime("%d/%m/%Y")


def format_time(slot):
    return slot.strftime("%H:%M")
