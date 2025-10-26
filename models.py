from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from enum import Enum

db = SQLAlchemy()

class UserRole(Enum):
    USER = "user"
    PLANNER = "planner"

class DutyType(Enum):
    DIENST = "dienst"
    RUFDIENST = "rufdienst"
    VISITE = "visite"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.Enum(UserRole), default=UserRole.USER)
    work_percentage = db.Column(db.Integer, default=100)

    # Beziehungen
    duties = db.relationship('Schedule', backref='user', lazy=True)
    availabilities = db.relationship('Availability', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    duty_type = db.Column(db.Enum(DutyType), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))  # z.B. "Urlaub", "Fortbildung"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)