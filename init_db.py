from run import app
from models import db, User, UserRole
from werkzeug.security import generate_password_hash
import os
import sys

def init_db():
    with app.app_context():
        # Erstellt alle Tabellen
        db.create_all()
        
        # Erstelle Admin-User falls nicht vorhanden
        # Das Admin-Passwort muss über die Umgebungsvariable ADMIN_PASSWORD gesetzt werden
        admin = User.query.filter_by(username='JuliaSchmeller').first()
        if not admin:
            admin_password = os.environ.get('ADMIN_PASSWORD')
            if not admin_password:
                print("WARNUNG: Kein Admin-User wurde erstellt!", file=sys.stderr)
                print("Um einen Admin-User zu erstellen, setzen Sie die Umgebungsvariable ADMIN_PASSWORD", file=sys.stderr)
                print("Beispiel: export ADMIN_PASSWORD='your-secure-password-here'", file=sys.stderr)
                print("Dann führen Sie 'python init_db.py' erneut aus.", file=sys.stderr)
            else:
                admin = User(
                    username='JuliaSchmeller',
                    email='julia@example.com',
                    role=UserRole.PLANNER,
                    work_percentage=100
                )
                admin.password_hash = generate_password_hash(admin_password)
                db.session.add(admin)
                db.session.commit()
                print("Admin-User wurde erstellt!")
        else:
            admin.role = UserRole.PLANNER
            db.session.commit()
            print("Existierender User wurde zum Planner gemacht!")

if __name__ == '__main__':
    init_db()