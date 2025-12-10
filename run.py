from flask import Flask, render_template, flash, redirect, url_for, request
from markupsafe import Markup  # Änderung hier: Markup ist jetzt in markupsafe
from flask_login import LoginManager, current_user, login_required
from models import db, User, UserRole, Schedule, DutyType
from auth import auth
from datetime import datetime, date
from scheduling import AutoScheduler
import calendar as cal
import os
import sys

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dienstplan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SECRET_KEY aus Umgebungsvariable laden
SECRET_KEY = os.environ.get('SECRET_KEY')

# In Produktionsmodus (FLASK_ENV != 'development') muss SECRET_KEY gesetzt sein
flask_env = os.environ.get('FLASK_ENV', 'production')
if not SECRET_KEY and flask_env != 'development':
    print("FEHLER: SECRET_KEY ist nicht gesetzt!", file=sys.stderr)
    print("Bitte setzen Sie die Umgebungsvariable SECRET_KEY vor dem Start der Anwendung.", file=sys.stderr)
    print("Beispiel: export SECRET_KEY='ihr-geheimer-schluessel'", file=sys.stderr)
    sys.exit(1)

# Fallback für Development-Modus (nur zu Entwicklungszwecken!)
if not SECRET_KEY:
    SECRET_KEY = 'dev-key-only-for-development-DO-NOT-USE-IN-PRODUCTION'
    print("WARNUNG: Development-Modus - unsicherer SECRET_KEY wird verwendet!", file=sys.stderr)

app.config['SECRET_KEY'] = SECRET_KEY

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
    year = today.year if 'year' not in request.args else int(request.args.get('year'))
    month = today.month if 'month' not in request.args else int(request.args.get('month'))
    
    # Lade alle Dienste für den ausgewählten Monat
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, cal.monthrange(year, month)[1])
    
    duties = Schedule.query.filter(
        Schedule.date.between(start_date, end_date)
    ).all()
    
    # Debug-Ausgabe
    print(f"\nDienste für {month}/{year}:")
    for duty in duties:
        print(f"Tag {duty.date.day}: {duty.user.username} - {duty.duty_type.value}")
    
    # Organisiere Dienste nach Datum
    duty_dict = {}
    for duty in duties:
        day = duty.date.day
        if day not in duty_dict:
            duty_dict[day] = {}
        duty_dict[day][duty.duty_type.value] = duty.user.username
    
    # Debug-Ausgabe des duty_dict
    print("\nDuty Dictionary:")
    for day, day_duties in duty_dict.items():
        print(f"Tag {day}: {day_duties}")
    
    return render_template('calendar.html', 
                         year=year, 
                         month=month, 
                         duties=duty_dict,
                         current_user=current_user,
                         UserRole=UserRole,
                         DutyType=DutyType)

@app.route('/generate-schedule/<int:year>/<int:month>')
@login_required
def generate_schedule(year, month):
    if current_user.role != UserRole.PLANNER:
        flash('Keine Berechtigung für diese Aktion.')
        return redirect(url_for('calendar'))
    
    scheduler = AutoScheduler(year, month)
    duties = scheduler.distribute_duties()
    summary = scheduler.get_schedule_summary()
    
    # Zeige strukturierte Zusammenfassung
    flash(f'Dienstplan für {month}/{year} wurde erstellt.')
    flash('Dienstverteilung:')
    
    # Erstelle HTML-Tabelle für die Zusammenfassung
    table_html = """
    <table class="table table-striped">
        <thead>
            <tr>
                <th>Arzt</th>
                <th>Dienste</th>
                <th>Rufdienste</th>
                <th>Visiten</th>
                <th>Arbeitszeit</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for doc, stats in summary.items():
        table_html += f"""
            <tr>
                <td>{doc}</td>
                <td>{stats['dienst']}</td>
                <td>{stats['rufdienst']}</td>
                <td>{stats['visite']}</td>
                <td>{stats['work_percentage']}%</td>
            </tr>
        """
    
    table_html += """
        </tbody>
    </table>
    """
    
    flash(Markup(table_html))
    
    return redirect(url_for('calendar'))

@app.route('/make-planner/<username>')
@login_required
def make_planner(username):
    # Nur der erste registrierte Benutzer darf weitere Planner erstellen
    if current_user.id != 1:
        flash('Keine Berechtigung für diese Aktion.')
        return redirect(url_for('home'))
    
    user = User.query.filter_by(username=username).first()
    if user:
        user.role = UserRole.PLANNER
        db.session.commit()
        flash(f'Benutzer {username} wurde zum Planner ernannt.')
    else:
        flash(f'Benutzer {username} nicht gefunden.')
    
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)