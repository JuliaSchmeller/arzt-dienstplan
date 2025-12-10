# Arzt Dienstplan

Eine Flask-Anwendung zur automatischen Erstellung und Verwaltung von Arztdienstplänen.

## Features

- Automatische Dienstplanverteilung basierend auf Arbeitszeit-Prozentsätzen
- Berücksichtigung von Wochenenden und Feiertagen
- Benutzer- und Rollenverwaltung (Planer und Ärzte)
- Interaktiver Kalender zur Anzeige der Dienste

## Installation

1. Repository klonen:
```bash
git clone https://github.com/JuliaSchmeller/arzt-dienstplan.git
cd arzt-dienstplan
```

2. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

3. Datenbank initialisieren:
```bash
python init_db.py
```

## Ausführung

Starte die Anwendung mit:
```bash
python run.py
```

Die Anwendung ist dann unter `http://localhost:5001` erreichbar.

## Logging-Konfiguration

Das Logging-Level kann über die Umgebungsvariable `LOG_LEVEL` gesteuert werden.

### Verfügbare Log-Level

- `DEBUG`: Detaillierte Informationen, hauptsächlich für Diagnose-Zwecke
- `INFO`: Bestätigungen, dass alles wie erwartet funktioniert
- `WARNING`: Hinweise auf potenzielle Probleme
- `ERROR`: Fehler, die behoben werden sollten

### Verwendung

**Linux/macOS:**
```bash
export LOG_LEVEL=DEBUG
python run.py
```

**Windows (CMD):**
```cmd
set LOG_LEVEL=DEBUG
python run.py
```

**Windows (PowerShell):**
```powershell
$env:LOG_LEVEL="DEBUG"
python run.py
```

Wenn `LOG_LEVEL` nicht gesetzt ist, wird standardmäßig `INFO` verwendet.

### Beispiele

Debug-Modus mit detaillierter Ausgabe:
```bash
LOG_LEVEL=DEBUG python run.py
```

Nur Fehler und Warnungen anzeigen:
```bash
LOG_LEVEL=WARNING python run.py
```

## Entwicklung

### Test-Benutzer erstellen
```bash
python create_test_user.py
```

## Lizenz

Dieses Projekt ist für den internen Gebrauch bestimmt.
