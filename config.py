import os
from datetime import time

from dotenv import load_dotenv

load_dotenv()


class Config:
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

    DOCTOR_USERNAME = os.getenv("DOCTOR_USERNAME", "emille")
    DOCTOR_PASSWORD = os.getenv("DOCTOR_PASSWORD", "")

    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v20.0")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
    WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "0") == "1"

    # Edite esta lista com os procedimentos oferecidos pela clinica.
    PROCEDURES = [
        "Raspagem",
        "Limpeza",
        "Extração",
        "Restauração",
    ]

    # Dias da semana: 0 = segunda-feira, 6 = domingo.
    # Edite os dias e horários de atendimento conforme a agenda da doutora.
    WORKING_HOURS = {
        0: [time(9, 0)],
        1: [time(14, 0)],
        3: [time(14, 0)],
        4: [time(9, 0)],
    }
