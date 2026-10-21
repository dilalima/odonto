import hashlib
import hmac
from datetime import date, time

import requests

from app import db
from app.models import ContactRequest, Conversation
from app.scheduling import (
    create_appointment,
    format_date,
    format_time,
    get_available_days,
    get_available_times,
)


def verify_signature(raw_body, signature, app_secret):
    if not app_secret or not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature[7:], expected)


def send_message(phone, message, config):
    token = config["WHATSAPP_ACCESS_TOKEN"]
    phone_number_id = config["WHATSAPP_PHONE_NUMBER_ID"]
    if not token or not phone_number_id:
        raise RuntimeError("Configure WHATSAPP_ACCESS_TOKEN e WHATSAPP_PHONE_NUMBER_ID.")

    response = requests.post(
        f"https://graph.facebook.com/{config['WHATSAPP_API_VERSION']}/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": message},
        },
        timeout=15,
    )
    response.raise_for_status()


def process_message(phone, text, config):
    text = text.strip()
    conversation = db.session.get(Conversation, phone)
    if conversation is None:
        conversation = Conversation(phone=phone, step="name", data={})
        db.session.add(conversation)
        db.session.commit()
        return "Olá! Vamos agendar seu procedimento. Qual é o seu nome completo?"

    data = dict(conversation.data or {})
    step = conversation.step

    if step == "name":
        if len(text.split()) < 2:
            return "Por favor, informe seu nome completo."
        data["full_name"] = text[:160]
        conversation.step = "age"
        answer = "Qual é a sua idade?"
    elif step == "age":
        if not text.isdigit() or not 1 <= int(text) <= 120:
            return "Informe sua idade em anos (de 1 a 120)."
        data["age"] = int(text)
        options = "\n".join(
            f"{index}. {name}"
            for index, name in enumerate(config["PROCEDURES"], start=1)
        )
        conversation.step = "procedure"
        answer = f"Escolha o procedimento respondendo com o número:\n{options}"
    elif step == "procedure":
        if not text.isdigit() or not 1 <= int(text) <= len(config["PROCEDURES"]):
            return "Escolha uma opção válida pelo número informado."
        data["procedure"] = config["PROCEDURES"][int(text) - 1]
        days = get_available_days(config, days_ahead=30)
        if not days:
            return (
                "No momento não há horários disponíveis nos dias de atendimento. "
                "A doutora entrará em contato para combinar outra data."
            )
        data["days"] = [day.isoformat() for day in days]
        conversation.step = "day"
        options = "\n".join(
            f"{index}. {format_date(day)}"
            for index, day in enumerate(days, start=1)
        )
        answer = f"Escolha o dia respondendo com o número:\n{options}"
    elif step == "day":
        days = [date.fromisoformat(value) for value in data.get("days", [])]
        if not text.isdigit() or not 1 <= int(text) <= len(days):
            return "Escolha um dia válido pelo número informado."
        selected_day = days[int(text) - 1]
        available = get_available_times(selected_day, config)
        if not available:
            db.session.add(
                ContactRequest(
                    phone=phone,
                    full_name=data["full_name"],
                    age=data["age"],
                    procedure=data["procedure"],
                    requested_date=selected_day,
                )
            )
            data.pop("days", None)
            conversation.step = "procedure"
            conversation.data = data
            db.session.commit()
            return (
                "Esse dia acabou de ser reservado. A doutora entrará em contato "
                "para combinar outra data. Envie uma nova mensagem se quiser "
                "escolher outro dia."
            )
        data["appointment_date"] = selected_day.isoformat()
        data["times"] = [slot.isoformat(timespec="minutes") for slot in available]
        conversation.step = "time"
        options = "\n".join(
            f"{index}. {format_time(slot)}"
            for index, slot in enumerate(available, start=1)
        )
        answer = f"Escolha o horário respondendo com o número:\n{options}"
    elif step == "time":
        times = data.get("times", [])
        if not text.isdigit() or not 1 <= int(text) <= len(times):
            return "Escolha um horário válido pelo número informado."
        data["appointment_time"] = times[int(text) - 1]
        conversation.step = "confirm"
        answer = (
            "Confira seu agendamento:\n"
            f"Nome: {data['full_name']}\n"
            f"Procedimento: {data['procedure']}\n"
            f"Data: {format_date(date.fromisoformat(data['appointment_date']))}\n"
            f"Horário: {format_time(time.fromisoformat(data['appointment_time']))}\n"
            "Responda 1 para confirmar ou 2 para cancelar."
        )
    elif step == "confirm":
        if text == "2":
            db.session.delete(conversation)
            db.session.commit()
            return "Agendamento cancelado. Se quiser recomeçar, envie uma nova mensagem."
        if text != "1":
            return "Responda 1 para confirmar ou 2 para cancelar."
        try:
            create_appointment(
                full_name=data["full_name"],
                age=data["age"],
                procedure=data["procedure"],
                phone=phone,
                appointment_date=data["appointment_date"],
                appointment_time=data["appointment_time"],
                source="whatsapp",
                config=config,
            )
        except ValueError:
            conversation.step = "procedure"
            data.pop("days", None)
            data.pop("times", None)
            conversation.data = data
            db.session.commit()
            return "Esse horário não está mais disponível. Envie uma nova mensagem para iniciar outro agendamento."
        db.session.delete(conversation)
        db.session.commit()
        return "Agendamento confirmado! A doutora Emille aguarda voce. Obrigada."
    else:
        conversation.step = "name"
        conversation.data = {}
        db.session.commit()
        return "Vamos recomeçar. Qual é o seu nome completo?"

    conversation.data = data
    db.session.commit()
    return answer
