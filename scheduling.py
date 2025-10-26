from datetime import datetime, timedelta
from calendar import monthrange
from models import User, Schedule, Availability, DutyType, db

class AutoScheduler:
    def __init__(self, year, month):
        self.year = year
        self.month = month
        self.num_days = monthrange(year, month)[1]
        
    def get_available_users(self, date):
        """Ermittelt verfügbare Ärzte für einen bestimmten Tag"""
        all_users = User.query.all()
        available_users = []
        
        for user in all_users:
            # Prüfe Verfügbarkeit (kein Urlaub, keine Fortbildung etc.)
            unavailable = Availability.query.filter(
                Availability.user_id == user.id,
                Availability.start_date <= date,
                Availability.end_date >= date
            ).first()
            
            if not unavailable:
                # Prüfe letzte Dienste (Mindestabstand)
                last_duty = Schedule.query.filter(
                    Schedule.user_id == user.id,
                    Schedule.date < date
                ).order_by(Schedule.date.desc()).first()
                
                if not last_duty or (date - last_duty.date).days >= 3:  # Mindestabstand 3 Tage
                    available_users.append(user)
        
        return available_users

    def calculate_fair_distribution(self, user):
        """Berechnet faire Dienstanzahl basierend auf Arbeitszeit"""
        base_duties = 4  # Basis: 4 Dienste pro Monat bei 100%
        return round(base_duties * (user.work_percentage / 100))

    def distribute_duties(self):
        """Verteilt die Dienste für den gesamten Monat"""
        start_date = datetime(self.year, self.month, 1).date()
        duties_assigned = {user.id: 0 for user in User.query.all()}
        
        for day in range(self.num_days):
            current_date = start_date + timedelta(days=day)
            available_users = self.get_available_users(current_date)
            
            if not available_users:
                continue
                
            # Sortiere Ärzte nach bisheriger Dienstanzahl und Arbeitszeit
            available_users.sort(key=lambda u: (
                duties_assigned[u.id] / self.calculate_fair_distribution(u),
                -u.work_percentage
            ))
            
            # Wähle den ersten verfügbaren Arzt
            selected_user = available_users[0]
            
            # Bestimme Diensttyp
            if current_date.weekday() >= 5:  # Wochenende
                duty_type = DutyType.DIENST
            else:  # Werktag
                duty_type = DutyType.RUFDIENST
            
            # Erstelle den Dienst
            new_duty = Schedule(
                date=current_date,
                duty_type=duty_type,
                user_id=selected_user.id
            )
            db.session.add(new_duty)
            duties_assigned[selected_user.id] += 1
        
        try:
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            return False

    def validate_schedule(self):
        """Überprüft den erstellten Dienstplan auf Regelkonformität"""
        all_duties = Schedule.query.filter(
            Schedule.date >= datetime(self.year, self.month, 1),
            Schedule.date < datetime(self.year, self.month + 1, 1)
        ).all()
        
        # Implementiere hier weitere Validierungsregeln
        return True