# FitTrainer - Deine Trainingsbegleitung am Desktop

FitTrainer ist eine einfach zu bedienende Desktop-App, die dich von der Trainingsplanung
bis zum Abschluss einer Einheit begleitet. Du bekommst passende Vorschlaege, kannst dein
Workout frei anpassen und siehst am Ende eine klare Zusammenfassung.

## Was du damit machen kannst

- Uebungen durchsuchen und nach Ziel, Muskelgruppe oder Ausruestung filtern
- Trainingsempfehlungen erhalten, die zu deinem Ziel und deiner Zeit passen
- Im Live-Modus trainieren: Timer, Pausen und Tempo-Hinweise inklusive
- Deinen Trainingsverlauf ansehen und Fortschritte nachvollziehen

## So laeuft eine Einheit ab

1. Benutzername waehlen (damit dein Verlauf gespeichert wird)
2. Ziel und Trainingszeit angeben
3. Vorschlaege pruefen, Uebungen auswaehlen und Reihenfolge anpassen
4. Training starten und Schritt fuer Schritt durchfuehren
5. Zusammenfassung am Ende speichern

## Workout erstellen (Schritt fuer Schritt)

1. Im Hauptmenue auf "Trainingsempfehlung" gehen
2. Ziel auswaehlen (z. B. Muskelaufbau oder Ausdauer) und die Wunschdauer angeben
3. Vorschlaege ansehen und Uebungen nach Bedarf hinzufuegen/entfernen
4. Reihenfolge anpassen, damit das Workout zu dir passt
5. Mit "Start" in den Live-Modus wechseln

## Live-Modus bedienen

- Die App fuehrt dich automatisch durch die Uebungen in der festgelegten Reihenfolge
- Timer und Pausen zeigen dir, wann es weitergeht
- Du kannst eine Uebung ueberspringen oder das Training pausieren/fortsetzen
- Am Ende bekommst du eine Zusammenfassung und der Verlauf wird gespeichert

## Daten & Datenschutz

- Alles bleibt lokal auf deinem Rechner
- Die Uebungs- und Trainingsdaten werden in einer SQLite-Datei gespeichert

## Technik (kurz)

- Programmiert in Python
- Benutzeroberflaeche mit Kivy
- Lokale Speicherung mit SQLite
- Tests mit pytest (fuer die Entwicklung)

## Schnellstart

Voraussetzungen: Python 3.10 oder neuer.

```bash
python -m pip install .
python main.py
```

Wenn du die App nur ausprobieren willst, reicht es, das Projekt zu entpacken und
`python main.py` auszufuehren.
