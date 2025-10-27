from run import app
from models import db, User, UserRole
from werkzeug.security import generate_password_hash

test_users = [
    {
        "username": "DrMueller",
        "email": "mueller@klinik.de",
        "password": "test123",
        "work_percentage": 100
    },
    {
        "username": "DrSchmidt",
        "email": "schmidt@klinik.de",
        "password": "test123",
        "work_percentage": 80
    },
    {
        "username": "DrWeber",
        "email": "weber@klinik.de",
        "password": "test123",
        "work_percentage": 60
    },
    {
        "username": "DrBauer",
        "email": "bauer@klinik.de",
        "password": "test123",
        "work_percentage": 100
    },
    {
        "username": "DrKlein",
        "email": "klein@klinik.de",
        "password": "test123",
        "work_percentage": 90
    },
    {
        "username": "DrGross",
        "email": "gross@klinik.de",
        "password": "test123",
        "work_percentage": 75
    },
    {
        "username": "DrHoffmann",
        "email": "hoffmann@klinik.de",
        "password": "test123",
        "work_percentage": 100
    },
    {
        "username": "DrWagner",
        "email": "wagner@klinik.de",
        "password": "test123",
        "work_percentage": 85
    },
    {
        "username": "DrSchneider",
        "email": "schneider@klinik.de",
        "password": "test123",
        "work_percentage": 70
    }
]

def create_test_users():
    with app.app_context():
        for user_data in test_users:
            # Prüfen ob User bereits existiert
            if not User.query.filter_by(username=user_data["username"]).first():
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    role=UserRole.USER,  # Geändert von DOCTOR zu USER
                    work_percentage=user_data["work_percentage"]
                )
                new_user.set_password(user_data["password"])  # Nutze die set_password Methode
                db.session.add(new_user)
        
        db.session.commit()
        
        # Überprüfen der angelegten User
        print("\nAlle Benutzer im System:")
        print("-" * 50)
        all_users = User.query.all()
        for user in all_users:
            print(f"Username: {user.username:12} | Role: {user.role.value:7} | Work%: {user.work_percentage:3}%")

if __name__ == '__main__':
    create_test_users()