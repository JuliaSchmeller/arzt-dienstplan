from datetime import datetime, timedelta
import calendar
from models import User, UserRole, Schedule, DutyType, db
from flask import current_app
from workalendar.europe import Germany  # Für Feiertage

class AutoScheduler:
    def __init__(self, year, month):
        self.year = year
        self.month = month
        self.cal = Germany()
        with current_app.app_context():
            self.doctors = User.query.filter_by(role=UserRole.USER).all()
            self.duty_points = {doc.id: 0 for doc in self.doctors}
            # Lade historische Daten für das ganze Jahr
            self.load_historical_duties()
            # Bestimme Visite-Ärzte für diesen Monat
            self.visite_doctors = self.get_visite_doctors()
    
    def load_historical_duties(self):
        """Lädt alle Dienste des aktuellen Jahres"""
        start_date = datetime(self.year, 1, 1)
        end_date = datetime(self.year, 12, 31)
        historical_duties = Schedule.query.filter(
            Schedule.date.between(start_date, end_date)
        ).all()
        
        print(f"\nGeladene historische Dienste von {start_date.date()} bis {end_date.date()}:")
        for duty in historical_duties:
            print(f"{duty.date}: {duty.user.username} - {duty.duty_type.value}")
            self.duty_points[duty.user.id] += self.calculate_duty_points(
                duty.duty_type,
                self.is_special_day(duty.date)
            )
    
    def get_days_in_month(self):
        """Ermittelt die Anzahl der Tage im Monat"""
        return calendar.monthrange(self.year, self.month)[1]
    
    def is_weekend(self, day):
        """Prüft ob ein Tag am Wochenende liegt"""
        date = datetime(self.year, self.month, day)
        return date.weekday() >= 5
    
    def is_special_day(self, date):
        """Prüft ob ein Tag ein Wochenende oder Feiertag ist"""
        return self.is_weekend(date.day) or self.cal.is_holiday(date)
    
    def calculate_duty_points(self, duty_type, is_special):
        """Berechnet Punktewert für verschiedene Diensttypen"""
        points = {
            DutyType.DIENST: 3,
            DutyType.RUFDIENST: 2,
            DutyType.VISITE: 1
        }
        base_points = points[duty_type]
        return base_points * 2 if is_special else base_points
    
    def get_doctor_duties(self, doctor_id, date):
        """Holt alle Dienste eines Arztes für ein bestimmtes Datum"""
        return Schedule.query.filter_by(
            user_id=doctor_id,
            date=date
        ).all()

    def get_weekend_count(self, doctor_id):
        """Ermittelt die Anzahl der Wochenenden, an denen ein Arzt Dienst oder Rufdienst hat"""
        start_date = datetime(self.year, self.month, 1)
        end_date = datetime(self.year, self.month, self.get_days_in_month())
        
        weekend_days = Schedule.query.filter(
            Schedule.user_id == doctor_id,
            Schedule.date.between(start_date, end_date),
            Schedule.duty_type.in_([DutyType.DIENST, DutyType.RUFDIENST])
        ).all()
        
        # Zähle nur Samstage als neue Wochenenden
        weekends = set()
        for duty in weekend_days:
            if duty.date.weekday() >= 5:  # Samstag oder Sonntag
                # Berechne den Samstag dieser Woche
                saturday = duty.date - timedelta(days=duty.date.weekday() - 5)
                weekends.add(saturday.date())
        
        return len(weekends)

    def get_duty_counts(self, doctor_id):
        """Ermittelt die Anzahl der verschiedenen Dienste eines Arztes"""
        start_date = datetime(self.year, self.month, 1)
        end_date = datetime(self.year, self.month, self.get_days_in_month())
        
        duties = Schedule.query.filter(
            Schedule.user_id == doctor_id,
            Schedule.date.between(start_date, end_date)
        ).all()
        
        counts = {
            'dienst': 0,
            'rufdienst': 0,
            'visite': 0
        }
        
        for duty in duties:
            if duty.duty_type == DutyType.DIENST:
                counts['dienst'] += 1
            elif duty.duty_type == DutyType.RUFDIENST:
                counts['rufdienst'] += 1
            elif duty.duty_type == DutyType.VISITE:
                counts['visite'] += 1
                
        return counts


    def get_last_visite_doctor(self, date):
        """Ermittelt welcher Arzt in der Vorwoche Visite hatte"""
        prev_date = date - timedelta(days=1)
        prev_duties = Schedule.query.filter_by(
            date=prev_date,
            duty_type=DutyType.VISITE
        ).first()
        return prev_duties.user_id if prev_duties else None

    def get_friday_rufdienst(self, weekend_date):
        """Ermittelt den Rufdienst vom Freitag für ein Wochenendatum"""
        friday_date = weekend_date - timedelta(days=weekend_date.weekday() - 4)
        friday_duty = Schedule.query.filter_by(
            date=friday_date,
            duty_type=DutyType.RUFDIENST
        ).first()
        return friday_duty

    def get_week_number(self, date):
        """Ermittelt die Kalenderwoche für ein Datum"""
        return date.isocalendar()[1]
        
    def is_visite_week(self, doctor_id, date):
        """Prüft ob ein Arzt in dieser Woche Visite hat"""
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)
        
        visite_duties = Schedule.query.filter(
            Schedule.date.between(week_start, week_end),
            Schedule.duty_type == DutyType.VISITE,
            Schedule.user_id == doctor_id
        ).all()
        
        return len(visite_duties) > 0

    def get_visite_doctors(self):
        """Ermittelt die Ärzte, die in diesem Monat bevorzugt Visite machen"""
        # Etwa ein Drittel der Ärzte soll Visite machen
        visite_count = max(len(self.doctors) // 3, 1)
        
        # Sortiere Ärzte nach bisherigen Visiten (aufsteigend)
        sorted_docs = sorted(self.doctors, 
                           key=lambda x: self.get_duty_counts(x.id)['visite'])
        
        return sorted_docs[:visite_count]
    
    def can_work_on_date(self, doctor_id, date, duty_type):
        """Prüft ob ein Arzt an einem bestimmten Tag arbeiten kann"""
        # Prüfe ob Dienstag und ob der Arzt Samstag Dienst hatte
        if date.weekday() == 1:  # Dienstag
            saturday = date - timedelta(days=3)  # 3 Tage zurück = Samstag
            saturday_duties = self.get_doctor_duties(doctor_id, saturday)
            for duty in saturday_duties:
                if duty.duty_type == DutyType.DIENST:
                    print(f"Arzt {doctor_id} hatte Samstag Dienst, hat diesen Dienstag frei")
                    return False
        
        # Wenn Visite, dann keine anderen Dienste in der Woche
        if self.is_visite_week(doctor_id, date):
            if duty_type != DutyType.VISITE:
                print(f"Arzt {doctor_id} hat diese Woche Visite, kann keine anderen Dienste machen")
                return False
        
        # Wenn andere Dienste in der Woche, dann keine Visite
        if duty_type == DutyType.VISITE:
            week_start = date - timedelta(days=date.weekday())
            week_end = week_start + timedelta(days=6)
            other_duties = Schedule.query.filter(
                Schedule.date.between(week_start, week_end),
                Schedule.user_id == doctor_id,
                Schedule.duty_type != DutyType.VISITE
            ).all()
            if other_duties:
                print(f"Arzt {doctor_id} hat diese Woche andere Dienste, kann keine Visite machen")
                return False
        
        # Prüfe vorherigen Tag auf Dienst
        prev_day = date - timedelta(days=1)
        prev_duties = self.get_doctor_duties(doctor_id, prev_day)
        
        for duty in prev_duties:
            if duty.duty_type == DutyType.DIENST:
                print(f"Arzt {doctor_id} hatte gestern Dienst, kann heute nicht arbeiten")
                return False
        
        # Prüfe Wochenend-Limit
        if self.is_weekend(date.day) and self.get_weekend_count(doctor_id) >= 2:
            print(f"Arzt {doctor_id} hat bereits 2 Wochenenden in diesem Monat")
            return False
        
        # Prüfe auf Rufdienst-Wochenende
        if duty_type == DutyType.RUFDIENST and date.weekday() >= 5:  # Samstag oder Sonntag
            friday_duty = self.get_friday_rufdienst(date)
            if friday_duty and friday_duty.user_id != doctor_id:
                print(f"Arzt {doctor_id} kann nicht Rufdienst am Wochenende haben, da anderer Arzt am Freitag Rufdienst hatte")
                return False
            elif friday_duty and friday_duty.user_id == doctor_id:
                return True
        
        return True
    
    def get_available_doctors(self, date, duty_type):
        """Ermittelt verfügbare Ärzte für ein Datum und Diensttyp"""
        available_docs = []
        for doc in self.doctors:
            try:
                existing_duty = Schedule.query.filter_by(
                    user_id=doc.id,
                    date=date
                ).first()
                
                if not existing_duty and self.can_work_on_date(doc.id, date, duty_type):
                    available_docs.append(doc)
            except Exception as e:
                print(f"Fehler beim Prüfen der Verfügbarkeit für {doc.username}: {e}")
                continue
        
        return available_docs
    
    def assign_duty(self, date, duty_type):
        """Weist einen Dienst einem Arzt zu"""
        # Wenn Samstag oder Sonntag und Rufdienst, dann MUSS es der Freitags-Rufdienst sein
        if duty_type == DutyType.RUFDIENST and date.weekday() >= 5:
            friday_duty = self.get_friday_rufdienst(date)
            if friday_duty:
                duty = Schedule(
                    date=date,
                    duty_type=duty_type,
                    user_id=friday_duty.user_id
                )
                print(f"Wochenend-Rufdienst automatisch zugewiesen: {friday_duty.user.username} - {date}")
                return duty
            else:
                print(f"Kein Freitags-Rufdienst gefunden für Wochenende {date}")
                return None

        available_docs = self.get_available_doctors(date, duty_type)
        if not available_docs:
            print(f"Keine verfügbaren Ärzte für {date} ({duty_type})")
            return None
        
        # Wähle Arzt basierend auf Diensttyp und Arbeitszeit
        if duty_type == DutyType.VISITE:
            # Wenn Montag, wähle bevorzugt aus Visite-Ärzten
            if date.weekday() == 0:  # Montag
                available_visite_docs = [doc for doc in available_docs if doc in self.visite_doctors]
                if available_visite_docs:
                    available_docs = available_visite_docs
            # An anderen Tagen, bevorzuge den Arzt vom Vortag
            else:
                last_visite_doc = self.get_last_visite_doctor(date)
                if last_visite_doc:
                    for doc in available_docs:
                        if doc.id == last_visite_doc:
                            chosen_doc = doc
                            break
                    else:
                        # Sortiere nach Visiten pro Arbeitszeit-Prozent
                        available_docs.sort(key=lambda x: (
                            self.get_duty_counts(x.id)['visite'] / (x.work_percentage/100),
                            self.duty_points[x.id] / (x.work_percentage/100)
                        ))
                        chosen_doc = available_docs[0]
                else:
                    # Sortiere nach Visiten pro Arbeitszeit-Prozent
                    available_docs.sort(key=lambda x: (
                        self.get_duty_counts(x.id)['visite'] / (x.work_percentage/100),
                        self.duty_points[x.id] / (x.work_percentage/100)
                    ))
                    chosen_doc = available_docs[0]
        else:
            # Bei anderen Diensten: Berücksichtige Dienstanzahl pro Arbeitszeit-Prozent
            available_docs.sort(key=lambda x: (
                self.get_duty_counts(x.id)[duty_type.value.lower()] / (x.work_percentage/100),
                self.duty_points[x.id] / (x.work_percentage/100)
            ))
            chosen_doc = available_docs[0]
        
        try:
            duty = Schedule(
                date=date,
                duty_type=duty_type,
                user_id=chosen_doc.id
            )
            
            # Aktualisiere Punktestand
            self.duty_points[chosen_doc.id] += self.calculate_duty_points(
                duty_type, 
                self.is_special_day(date)
            )
            
            print(f"Dienst zugewiesen: {chosen_doc.username} - {date} - {duty_type.value}")
            
            # Wenn Freitag-Rufdienst, gleich das ganze Wochenende zuweisen
            if duty_type == DutyType.RUFDIENST and date.weekday() == 4:  # Freitag
                print(f"Freitag-Rufdienst: Weise Wochenende für {chosen_doc.username} zu")
                for days_ahead in [1, 2]:  # Samstag und Sonntag
                    weekend_date = date + timedelta(days=days_ahead)
                    weekend_duty = Schedule(
                        date=weekend_date,
                        duty_type=DutyType.RUFDIENST,
                        user_id=chosen_doc.id
                    )
                    self.duty_points[chosen_doc.id] += self.calculate_duty_points(
                        DutyType.RUFDIENST, 
                        True  # Wochenende
                    )
                    db.session.add(weekend_duty)
                    print(f"Wochenend-Rufdienst zugewiesen: {chosen_doc.username} - {weekend_date}")
            
            return duty
            
        except Exception as e:
            print(f"Fehler bei der Dienstzuweisung: {e}")
            return None
    
    def distribute_duties(self):
        """Verteilt alle Dienste für den Monat"""
        days = self.get_days_in_month()
        duties = []
        
        try:
            # Lösche bestehende Einträge für diesen Monat
            start_date = datetime(self.year, self.month, 1)
            end_date = datetime(self.year, self.month, days)
            
            existing_duties = Schedule.query.filter(
                Schedule.date.between(start_date, end_date)
            ).all()
            
            for duty in existing_duties:
                db.session.delete(duty)
            
            print(f"\nStarte Dienstverteilung für {self.month}/{self.year}")
            
            # Verteile neue Dienste
            for day in range(1, days + 1):
                date = datetime(self.year, self.month, day)
                is_special = self.is_special_day(date)
                
                print(f"\nVerteilung für Tag {day} ({'Wochenende/Feiertag' if is_special else 'Werktag'}):")
                
                # Regulärer Dienst (jeden Tag)
                dienst = self.assign_duty(date, DutyType.DIENST)
                if dienst:
                    duties.append(dienst)
                    db.session.add(dienst)
                
                # Rufdienst (jeden Tag außer Samstag/Sonntag, da diese vom Freitag automatisch gesetzt werden)
                rufdienst = None
                if date.weekday() not in [5, 6]:  # Nicht Samstag oder Sonntag
                    rufdienst = self.assign_duty(date, DutyType.RUFDIENST)
                    if rufdienst:
                        duties.append(rufdienst)
                        db.session.add(rufdienst)
                else:  # Samstag oder Sonntag
                    rufdienst = self.assign_duty(date, DutyType.RUFDIENST)  # Wird automatisch vom Freitag übernommen
                    if rufdienst:
                        duties.append(rufdienst)
                        db.session.add(rufdienst)
                
                # Visite (Montag bis Freitag, außer an Feiertagen)
                if date.weekday() < 5 and not self.cal.is_holiday(date):  # Mo-Fr und kein Feiertag
                    visite = self.assign_duty(date, DutyType.VISITE)
                    if visite:
                        duties.append(visite)
                        db.session.add(visite)
            
            # Commit der Änderungen
            db.session.commit()
            print(f"\nDienstplan erfolgreich erstellt mit {len(duties)} Diensten")
            
        except Exception as e:
            print(f"Fehler bei der Dienstplanerstellung: {e}")
            db.session.rollback()
            return []
        
        return duties

    def get_schedule_summary(self):
        """Erstellt eine strukturierte Zusammenfassung der Dienstverteilung"""
        summary = {}
        for doc in self.doctors:
            summary[doc.username] = {
                'dienst': 0,
                'rufdienst': 0,
                'visite': 0,
                'work_percentage': doc.work_percentage,
                'dienst_pro_arbeitszeit': 0,
                'rufdienst_pro_arbeitszeit': 0,
                'visite_pro_arbeitszeit': 0
            }
        
        # Zähle alle Dienste des aktuellen Monats
        start_date = datetime(self.year, self.month, 1)
        end_date = datetime(self.year, self.month, self.get_days_in_month())
        
        current_duties = Schedule.query.filter(
            Schedule.date.between(start_date, end_date)
        ).all()
        
        for duty in current_duties:
            if duty.duty_type == DutyType.DIENST:
                summary[duty.user.username]['dienst'] += 1
            elif duty.duty_type == DutyType.RUFDIENST:
                summary[duty.user.username]['rufdienst'] += 1
            elif duty.duty_type == DutyType.VISITE:
                summary[duty.user.username]['visite'] += 1
        
        # Berechne Dienste pro Arbeitszeit
        for username, stats in summary.items():
            work_factor = stats['work_percentage'] / 100
            stats['dienst_pro_arbeitszeit'] = round(stats['dienst'] / work_factor, 2)
            stats['rufdienst_pro_arbeitszeit'] = round(stats['rufdienst'] / work_factor, 2)
            stats['visite_pro_arbeitszeit'] = round(stats['visite'] / work_factor, 2)
        
        return summary