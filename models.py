from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

db = SQLAlchemy()

class UserRole(Enum):
    USER = "user"
    PLANNER = "planner"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.Enum(UserRole), default=UserRole.USER)
    work_percentage = db.Column(db.Integer, default=100)  # Arbeitszeit in Prozent
    
class DutyType(Enum):
    DIENST = "dienst"
    RUFDIENST = "rufdienst"
    VISITE = "visite"

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    duty_type = db.Column(db.Enum(DutyType), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('duties', lazy=True))

class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))  # z.B. "Urlaub", "Fortbildung"
    user = db.relationship('User', backref=db.backref('availabilities', lazy=True))