#!/bin/bash

# Prüfe ob venv existiert, wenn nicht erstelle es
if [ ! -d "venv" ]; then
    echo "Erstelle virtuelle Umgebung..."
    python -m venv venv
fi

# Aktiviere virtuelle Umgebung
source venv/bin/activate

# Installiere Abhängigkeiten
pip install -r requirements.txt

# Initialisiere Datenbank
python init_db.py

# Optional: Erstelle einen Admin-User
python - << EOF
from run import app
from models import db, User, UserRole
from werkzeug.security import generate_password_hash

with app.app_context():
    # Prüfe ob User bereits existiert
    user = User.query.filter_by(username='JuliaSchmeller').first()
    if not user:
        # Erstelle neuen User
        user = User(
            username='JuliaSchmeller',
            email='julia@example.com',
            role=UserRole.PLANNER,
            work_percentage=100
        )
        user.password_hash = generate_password_hash('IhrPasswort')  # Ändern Sie 'IhrPasswort' zu Ihrem gewünschten Passwort
        db.session.add(user)
        db.session.commit()
        print("Admin-User wurde erstellt!")
    else:
        # Update existierenden User zu Planner
        user.role = UserRole.PLANNER
        db.session.commit()
        print("Existierender User wurde zum Planner gemacht!")
EOF

echo "Setup abgeschlossen!"