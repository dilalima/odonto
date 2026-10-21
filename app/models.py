from datetime import datetime

from sqlalchemy import UniqueConstraint

from app import db


class Appointment(db.Model):
    __table_args__ = (
        UniqueConstraint(
            "appointment_date",
            "appointment_time",
            name="uq_appointment_date_time",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(160), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    procedure = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=True, index=True)
    appointment_date = db.Column(db.Date, nullable=False, index=True)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="confirmado")
    source = db.Column(db.String(20), nullable=False, default="site")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Conversation(db.Model):
    phone = db.Column(db.String(30), primary_key=True)
    step = db.Column(db.String(30), nullable=False, default="name")
    data = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ContactRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(30), nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    procedure = db.Column(db.String(120), nullable=False)
    requested_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
