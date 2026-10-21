import re
from datetime import date, time, timedelta

import pytest

from app import create_app, db
from app.models import Appointment
from app.scheduling import create_appointment, get_available_times


@pytest.fixture
def client():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DOCTOR_USERNAME": "emille",
            "DOCTOR_PASSWORD": "senha-teste",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )
    return app.test_client()


def csrf_token(client):
    response = client.get("/")
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


def test_homepage_has_csrf_token(client):
    assert csrf_token(client)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_form_without_csrf_is_rejected(client):
    response = client.post(
        "/doutora/login",
        data={"username": "emille", "password": "senha-teste"},
    )
    assert response.status_code == 400


def test_login_accepts_valid_csrf(client):
    token = csrf_token(client)
    response = client.post(
        "/doutora/login",
        data={
            "username": "emille",
            "password": "senha-teste",
            "csrf_token": token,
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/doutora")


def test_booking_blocks_the_rest_of_the_day(client):
    app = client.application
    appointment_day = date.today() + timedelta(days=1)
    slots = [time(9, 0), time(14, 0)]
    app.config["WORKING_HOURS"] = {appointment_day.weekday(): slots}

    with app.app_context():
        assert get_available_times(appointment_day, app.config) == slots

        create_appointment(
            full_name="Maria Silva",
            age=35,
            procedure=app.config["PROCEDURES"][0],
            phone="5511999999999",
            appointment_date=appointment_day.isoformat(),
            appointment_time="09:00",
            source="site",
            config=app.config,
        )

        assert get_available_times(appointment_day, app.config) == []
        assert Appointment.query.filter_by(appointment_date=appointment_day).count() == 1

        with pytest.raises(ValueError, match="Escolha outro"):
            create_appointment(
                full_name="Ana Costa",
                age=31,
                procedure=app.config["PROCEDURES"][0],
                phone="5511777777777",
                appointment_date=appointment_day.isoformat(),
                appointment_time="09:00",
                source="site",
                config=app.config,
            )
        db.session.rollback()


def test_booking_route_blocks_second_booking_on_the_same_day(client):
    app = client.application
    appointment_day = date.today() + timedelta(days=1)
    slots = [time(9, 0), time(14, 0)]
    app.config["WORKING_HOURS"] = {appointment_day.weekday(): slots}
    token = csrf_token(client)

    available_response = client.get(
        f"/api/horarios?data={appointment_day.isoformat()}"
    )
    assert available_response.status_code == 200
    assert available_response.get_json() == {"horarios": ["09:00", "14:00"]}

    response = client.post(
        "/agendar",
        data={
            "csrf_token": token,
            "full_name": "Maria Silva",
            "age": "30",
            "phone": "(11) 99999-9999",
            "procedure": app.config["PROCEDURES"][0],
            "appointment_date": appointment_day.isoformat(),
            "appointment_time": "09:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Agendamento confirmado" in response.get_data(as_text=True)

    response = client.post(
        "/agendar",
        data={
            "csrf_token": token,
            "full_name": "Joana Souza",
            "age": "30",
            "phone": "(11) 88888-8888",
            "procedure": app.config["PROCEDURES"][0],
            "appointment_date": appointment_day.isoformat(),
            "appointment_time": "14:00",
        },
        follow_redirects=True,
    )
    assert "horário indisponível" in response.get_data(as_text=True)

    with app.app_context():
        assert Appointment.query.filter_by(appointment_date=appointment_day).count() == 1


def test_doctor_can_cancel_and_reopen_the_day(client):
    app = client.application
    appointment_day = date.today() + timedelta(days=2)
    slots = [time(9, 0)]
    app.config["WORKING_HOURS"] = {appointment_day.weekday(): slots}

    with app.app_context():
        appointment = create_appointment(
            full_name="Maria Silva",
            age=35,
            procedure=app.config["PROCEDURES"][0],
            phone="5511999999999",
            appointment_date=appointment_day.isoformat(),
            appointment_time="09:00",
            source="site",
            config=app.config,
        )
        appointment_id = appointment.id

    token = csrf_token(client)
    with client.session_transaction() as session:
        session["doctor_logged_in"] = True

    response = client.post(
        f"/doutora/cancelar/{appointment_id}",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "voltou a ficar disponível" in response.get_data(as_text=True)

    with app.app_context():
        assert db.session.get(Appointment, appointment_id).status == "cancelado"
        assert get_available_times(appointment_day, app.config) == slots
