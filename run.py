from flask import Flask, render_template, flash, redirect, url_for
from flask_login import LoginManager, current_user, login_required
from models import db, User, UserRole
from auth import auth
from datetime import datetime, date
from scheduling import AutoScheduler

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

@app.route('/calendar')
@login_required
def calendar():
    # Aktuelles Datum für die initiale Anzeige
    today = date.today()
    year = today.year
    month = today.month
    
    # Hier später: Logik für das Abrufen der Dienste
    
    return render_template('calendar.html', 
                         year=year, 
                         month=month, 
                         current_user=current_user,
                         UserRole=UserRole)

@app.route('/generate-schedule/<int:year>/<int:month>')
@login_required
def generate_schedule(year, month):
    # Nur Planer dürfen Dienstpläne erstellen
    if current_user.role != UserRole.PLANNER:
        flash('Keine Berechtigung für diese Aktion.')
        return redirect(url_for('calendar'))
    
    scheduler = AutoScheduler(year, month)
    if scheduler.distribute_duties():
        flash(f'Dienstplan für {month}/{year} wurde erfolgreich erstellt.')
    else:
        flash('Fehler bei der Erstellung des Dienstplans.')
    
    return redirect(url_for('calendar'))

@app.route('/make-planner/<username>')
@login_required
def make_planner(username):
    # Nur der erste registrierte Benutzer darf weitere Planer erstellen
    if current_user.id != 1:  # Annahme: der erste Benutzer hat ID 1
        flash('Keine Berechtigung für diese Aktion.')
        return redirect(url_for('home'))
    
    user = User.query.filter_by(username=username).first()
    if user:
        user.role = UserRole.PLANNER
        db.session.commit()
        flash(f'Benutzer {username} wurde zum Planer ernannt.')
    else:
        flash(f'Benutzer {username} nicht gefunden.')
    
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)