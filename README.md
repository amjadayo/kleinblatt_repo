# Kleinblatt - Microgreens Production Tracker

Eine umfassende Anwendung zur Verwaltung von Microgreens-Produktion, Lieferplänen und Kundenbestellungen.

## Funktionen
- Wöchentliche Ansichten für Lieferung, Produktion und Transfer
- Kundenverwaltungssystem mit Bestellhistorie
- Artikelverwaltung mit Wachstumsmetriken
- Automatisierte Abonnementbestellungen
- Druckfertige Wochenpläne für den täglichen Betrieb
- Detaillierte Analysen zu Kunden- und Produktleistung

## Installation

### Voraussetzungen
- Python 3.7 oder höher
- tkinter (für die GUI)
- ttkbootstrap (für erweiterte GUI-Styling-Optionen)
- Die erforderlichen Python-Pakete

### Installation der Abhängigkeiten
```bash
pip install -r requirements.txt
```

### Starten der Anwendung
```bash
python main.py
```

## Schnellstartanleitung
1. **Artikelverwaltung**: Fügen Sie zuerst Ihre Produkte im "Items"-Tab mit ihren Wachstumszeiten und Preisen hinzu
2. **Kunden hinzufügen**: Gehen Sie zum "Kunden"-Tab, um Ihre Kundeninformationen einzugeben
3. **Bestellungen erstellen**: Erstellen Sie neue Bestellungen mit Lieferterminen und optionalen Abonnement-Einstellungen
4. **Zeitpläne anzeigen**:
   - Nutzen Sie den "Lieferung"-Tab, um bevorstehende Kundenlieferungen zu sehen
   - Der "Produktion"-Tab zeigt, was wann gepflanzt werden muss
   - Der "Transfer"-Tab hilft bei der Verfolgung, wann Produkte zwischen Wachstumsstadien verschoben werden müssen

## Wochenansichten
- Navigieren Sie zwischen den Wochen mit den Pfeilen oben in jeder Zeitplanansicht
- Klicken Sie auf "Heute", um zur aktuellen Woche zurückzukehren
- Verwenden Sie den "+"-Button in der Lieferansicht, um neue Bestellungen direkt für bestimmte Tage hinzuzufügen

## Drucken von Zeitplänen
Jede Zeitplanansicht enthält eine "Drucken"-Schaltfläche, die ein PDF des aktuellen Wochenzeitplans erzeugt. Die PDFs werden im "output"-Ordner gespeichert.

## Datenbankstruktur
Die Anwendung verwendet eine lokale SQLite-Datenbank zur Speicherung aller Daten. Die wichtigsten Tabellen sind:
- `Customer`: Kundendaten
- `Item`: Produkte/Microgreens mit Wachstumszeiten und Preisen
- `Order`: Bestellungen mit Liefer- und Produktionsdaten
- `OrderItem`: Verbindungstabelle zwischen Bestellungen und Artikeln

## Entwicklung
Dieses Projekt ist in Python mit tkinter für die GUI entwickelt. Es verwendet peewee als ORM für die Datenbankinteraktion und FPDF für die PDF-Generierung.

### Projektstruktur
- `main.py`: Hauptanwendung und GUI
- `models.py`: Datenbankmodelle
- `database.py`: Datenbankfunktionen
- `weekly_view.py`: Wochenansichten für Lieferung, Produktion und Transfer
- `customers_view.py`: Kundenverwaltung
- `item_view.py`: Artikelverwaltung
- `print_schedules.py`: PDF-Generierung für Zeitpläne
- `widgets.py`: Benutzerdefinierte UI-Komponenten

## Version
Aktuelle Version: 0.9

## Support
Bei Fragen oder Problemen wenden Sie sich bitte an it@kleinblatt.de