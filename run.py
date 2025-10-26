from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Schedule, Availability, DutyType, UserRole

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dienstplan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # In Produktion sicher ändern!

db.init_app(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Datenbank initialisiert!")

if __name__ == '__main__':
    app.run(debug=True)