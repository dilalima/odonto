import hmac
import secrets

from flask import Flask, abort, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
import pymysql

db = SQLAlchemy()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object("config.Config")

    if test_config:
        app.config.update(test_config)
    else:
        _validate_config(app.config)

    _ensure_mysql_database(app.config["SQLALCHEMY_DATABASE_URI"])
    db.init_app(app)

    @app.before_request
    def protect_forms():
        if request.method != "POST" or request.path.startswith("/webhook/whatsapp"):
            return None
        expected = session.get("csrf_token", "")
        received = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(received, expected):
            abort(400, description="Token CSRF inválido.")
        return None

    @app.context_processor
    def csrf_context():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return {"csrf_token": token}

    from app.routes import main

    app.register_blueprint(main)

    with app.app_context():
        from app import models  # noqa: F401

        db.create_all()
        _ensure_legacy_columns()

    return app


def _validate_config(config):
    required = {
        "SECRET_KEY": config.get("SECRET_KEY"),
        "DATABASE_URL": config.get("SQLALCHEMY_DATABASE_URI"),
        "DOCTOR_PASSWORD": config.get("DOCTOR_PASSWORD"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("Configure no arquivo .env: " + ", ".join(missing))
    if config["SECRET_KEY"] == "desenvolvimento-altere-esta-chave":
        raise RuntimeError("SECRET_KEY não pode usar o valor padrão.")


def _ensure_mysql_database(database_uri):
    """Create the configured MySQL database before SQLAlchemy creates tables."""
    url = make_url(database_uri)
    if url.get_backend_name() != "mysql":
        return

    database_name = url.database
    if not database_name:
        raise RuntimeError("DATABASE_URL precisa informar o nome do banco.")

    safe_database_name = database_name.replace("`", "``")
    connection = pymysql.connect(
        host=url.host,
        port=url.port or 3306,
        user=url.username,
        password=url.password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{safe_database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


def _ensure_legacy_columns():
    columns = {column["name"] for column in inspect(db.engine).get_columns("appointment")}
    if "phone" not in columns:
        db.session.execute(text("ALTER TABLE appointment ADD COLUMN phone VARCHAR(30) NULL"))
        db.session.commit()
    _ensure_appointment_time_constraint()


def _ensure_appointment_time_constraint():
    if db.engine.dialect.name != "mysql":
        return

    inspector = inspect(db.engine)
    unique_constraints = inspector.get_unique_constraints("appointment")
    unique_indexes = inspector.get_indexes("appointment")
    unique_entries = unique_constraints + [
        index for index in unique_indexes if index.get("unique")
    ]

    if any(
        entry.get("column_names") == ["appointment_date", "appointment_time"]
        for entry in unique_entries
    ):
        return

    date_only_entries = {
        entry.get("name"): entry
        for entry in unique_entries
        if entry.get("name")
        and entry.get("column_names") == ["appointment_date"]
    }
    preparer = db.engine.dialect.identifier_preparer
    with db.engine.begin() as connection:
        for index_name in date_only_entries:
            connection.execute(
                text(f"ALTER TABLE appointment DROP INDEX {preparer.quote(index_name)}")
            )
        connection.execute(
            text(
                "ALTER TABLE appointment ADD CONSTRAINT "
                "uq_appointment_date_time UNIQUE (appointment_date, appointment_time)"
            )
        )
