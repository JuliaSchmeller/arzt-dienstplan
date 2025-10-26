from flask import Flask, render_template, flash
from flask_login import LoginManager, current_user
from models import db, User
from auth import auth

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dienstplan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # In Produktion sicher ändern!

# Initialisierung der Erweiterungen
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Bitte melden Sie sich an, um diese Seite zu sehen.'

# Blueprint registrieren
app.register_blueprint(auth)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/')
def home():
    return render_template('index.html')

@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Datenbank initialisiert!")

if __name__ == '__main__':
    app.run(debug=True, port=5001)