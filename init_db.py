from run import app
from models import db, User, UserRole
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        # Erstellt alle Tabellen
        db.create_all()
        
        # Erstelle Admin-User falls nicht vorhanden
        admin = User.query.filter_by(username='JuliaSchmeller').first()
        if not admin:
            admin = User(
                username='JuliaSchmeller',
                email='julia@example.com',
                role=UserRole.PLANNER,
                work_percentage=100
            )
            admin.password_hash = generate_password_hash('IhrPasswort')
            db.session.add(admin)
            db.session.commit()
            print("Admin-User wurde erstellt!")
        else:
            admin.role = UserRole.PLANNER
            db.session.commit()
            print("Existierender User wurde zum Planner gemacht!")

if __name__ == '__main__':
    init_db()