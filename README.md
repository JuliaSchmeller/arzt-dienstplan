# Arzt-Dienstplan

Eine Flask-basierte Webanwendung zur Verwaltung und automatisierten Erstellung von Arztdienstplänen.

## Features

- Automatische Dienstplanerstellung mit fairer Verteilung
- Benutzerrollen (Planner und User)
- Kalenderview für Dienstübersicht
- Berücksichtigung verschiedener Diensttypen (Dienst, Rufdienst, Visite)
- Berücksichtigung von Arbeitszeit-Prozentsätzen

## Installation

1. Repository klonen:
```bash
git clone https://github.com/JuliaSchmeller/arzt-dienstplan.git
cd arzt-dienstplan
```

2. Virtuelle Umgebung erstellen und aktivieren:
```bash
python -m venv venv
source venv/bin/activate  # Auf Windows: venv\Scripts\activate
```

3. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

## Secrets / Configuration

### Umgebungsvariablen konfigurieren

Die Anwendung verwendet Umgebungsvariablen für sensible Konfigurationen wie SECRET_KEY und Passwörter.

1. Kopieren Sie die Beispieldatei:
```bash
cp .env.example .env
```

2. Bearbeiten Sie `.env` und setzen Sie die erforderlichen Werte:

#### SECRET_KEY (erforderlich)

Der SECRET_KEY wird für Session-Sicherheit und CSRF-Schutz verwendet.

**Generieren Sie einen sicheren Schlüssel:**
```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

**Setzen Sie den Schlüssel in der .env-Datei:**
```
SECRET_KEY=ihr-generierter-64-zeichen-hex-string
```

**Oder setzen Sie ihn direkt als Umgebungsvariable:**
```bash
export SECRET_KEY='ihr-generierter-64-zeichen-hex-string'
```

**WICHTIG:**
- Im Produktionsmodus (`FLASK_ENV != 'development'`) **muss** SECRET_KEY gesetzt sein
- Die Anwendung wird sich weigern zu starten, wenn SECRET_KEY in Produktion fehlt
- Verwenden Sie **niemals** den Beispielwert aus `.env.example` in Produktion
- Halten Sie den SECRET_KEY geheim und teilen Sie ihn nicht

#### ADMIN_PASSWORD (für initiale Einrichtung)

Das ADMIN_PASSWORD wird nur beim ersten Ausführen von `init_db.py` benötigt, um den ersten Admin-Benutzer zu erstellen.

```bash
export ADMIN_PASSWORD='ihr-sicheres-admin-passwort'
```

#### FLASK_ENV (optional)

```bash
export FLASK_ENV=production  # Für Produktion
export FLASK_ENV=development  # Für Entwicklung (Standard)
```

### Alternative: python-dotenv verwenden

Wenn Sie die `.env`-Datei verwenden möchten, können Sie `python-dotenv` installieren:

```bash
pip install python-dotenv
```

Dann laden Sie die Variablen automatisch, indem Sie am Anfang Ihrer Python-Skripte hinzufügen:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Datenbank initialisieren

**Stellen Sie sicher, dass SECRET_KEY und ADMIN_PASSWORD gesetzt sind:**

```bash
export SECRET_KEY='ihr-generierter-key'
export ADMIN_PASSWORD='ihr-admin-passwort'
python init_db.py
```

Dies erstellt:
- Alle notwendigen Datenbanktabellen
- Einen Admin-Benutzer (JuliaSchmeller) mit dem angegebenen Passwort

## Anwendung starten

**Produktionsmodus:**
```bash
export SECRET_KEY='ihr-generierter-key'
export FLASK_ENV=production
python run.py
```

**Entwicklungsmodus:**
```bash
export SECRET_KEY='dev-key'  # Oder lassen Sie es weg für automatischen Dev-Key
export FLASK_ENV=development
python run.py
```

Die Anwendung läuft standardmäßig auf `http://localhost:5001`

## Testdaten erstellen (optional)

Um Testbenutzer zu erstellen:
```bash
python create_test_user.py
```

## Sicherheitshinweise

1. **Niemals** echte Secrets in Git committen
2. Halten Sie `.env` geheim und teilen Sie sie nicht
3. Verwenden Sie starke, zufällig generierte Werte für SECRET_KEY
4. In Produktion: Setzen Sie `FLASK_ENV=production`
5. Ändern Sie regelmäßig Passwörter und Secrets
6. Verwenden Sie HTTPS in Produktionsumgebungen

## Migrationshinweise

Wenn Sie von einer älteren Version aktualisieren, die hardcodierte Secrets enthielt:

1. Generieren Sie einen neuen SECRET_KEY (siehe oben)
2. Setzen Sie die Umgebungsvariablen
3. Starten Sie die Anwendung neu
4. Alle Benutzer müssen sich neu anmelden (alte Sessions sind ungültig)

## Lizenz

[Bitte Lizenzinformationen einfügen]

## Kontakt

[Bitte Kontaktinformationen einfügen]
