# Paradigma PELEO 14 – modularer Anlagenbaukasten

Home-Assistant-Custom-Integration für Paradigma-Heizungsanlagen über eine gemeinsame Modbus-TCP-Verbindung. Weiterentwicklung des funktionierenden PELEO-14-Forks, Domain **`paradigma`**, Maintainer [mattes1007](https://github.com/mattes1007).

Manifest-Version **2.0.0-beta.1** bleibt bis zur Veröffentlichung unverändert. Für diesen modularen Entwicklungsstand wird **2.0.0-beta.2** empfohlen. Ziel: Home Assistant Core **2026.10.0**, HAOS 18.3, bestehende Abhängigkeit `pymodbus>=3.13.1`. Keine neue Abhängigkeit. Echte HA-Python-Tests auf Core 2026.10.0/2026.10.1 bestanden; HAOS-/Hardwareprüfung steht aus.

## Installation und Konfiguration

HACS → benutzerdefinierte Repositories → **`https://github.com/mattes1007/paradigma-peleo14-homeassistant`** → Kategorie **Integration**. Release installieren, HA neu starten und **Paradigma PELEO 14** hinzufügen. Einzelheiten: [HACS und Veröffentlichung](docs/hacs-installation.md).

Der offizielle HA-Assistent führt durch Verbindung/Reglermodell, Baugruppen, individuelle Sensorwahl pro Baugruppe, getrennte Steuerfreigaben und Zusammenfassung. Später dieselbe Auswahl über **Konfigurieren** ändern. Kein Dashboard-Installer, keine Lovelace-Änderungen.

Auswählbar: Allgemein/Außentemperatur, Kessel/Pelletheizung, Pufferspeicher, Heizkreis 1/2, Warmwasser, Zirkulation, Solarthermie, Schwimmbad und Raumfühler. Optional abgewählte Register werden nicht regelmäßig gelesen. Die bisherigen Entity- und Unique-IDs bleiben erhalten.

Verifiziertes Dokumentprofil: **SystaComfort II / Compact C ab Firmware 2.16**, TH-3000 V1.1. **SystaSmartC II ist noch nicht verifiziert und nicht für neue Einrichtungen freigegeben.** Bestehende Installationen behalten das bisherige Registerprofil als ungeprüftes Bestandsprofil. Es gibt keine automatische Erkennung von Modell/Firmware oder angeschlossener Hardware.

- [Konfiguration und Modelle](docs/KONFIGURATION.md)
- [Vollständiger implementierter Registerkatalog](docs/REGISTERKATALOG.md)
- [Steuerfunktionen und Voraussetzungen](docs/STEUERFUNKTIONEN.md)
- [Migration, Updateprüfung und Rollback](docs/MIGRATION.md)

## Lesemodus und Sollwerte

Standard ist ausschließlich Lesen. Neu optional: **Holding 2** externe Vorlauf-Sollwertvorgabe HK1, **Holding 44** Solltemperatur Puffer oben, **Holding 45** Kesselsolltemperatur. Faktor 0,1 °C, gemeinsame Coordinator-Aktualisierung, keine Schreibfreigabe notwendig. Holding 2 wird ausdrücklich nicht als intern berechneter Regler-Sollwert bezeichnet. Sentinel-Werte und fehlende Antworten werden unbekannt/nicht verfügbar.

Einzeln freigebbar: externe HK1-/HK2-Vorlaufvorgaben und Warmwasservorgabe. Vorhandene Hub-Schutzprüfungen, Grenzen, Live-Voraussetzungen und Rücklesen bleiben erhalten. Coil-Schalter, Schreiben auf 44/45 und dauerhafte Sollwerterneuerung bleiben gesperrt. Vorgaben können die interne Regelung für etwa fünf Minuten übersteuern. Keine Befehle beim Einrichten, Reload oder normalen Lesen.

## Migration und Prüfung

Entry-Version 1 wird auf 2 migriert: bisherige Sensoren, Einstellungen, Gerätekennung und bewusst freigegebene Steuerfunktionen bleiben erhalten. Neue Funktionen werden nicht automatisch aktiviert. **Vor Update vollständiges HA-Backup erstellen**; ein Rollback benötigt auch den alten Config Entry aus dem Backup.

Offlineprüfung:

```sh
python3 -m unittest discover -s tests
python3 -m compileall -q custom_components
```

113 lokale Mock-/Stub-Tests sowie sieben echte HA-Python-Tests jeweils auf Core 2026.10.0 und 2026.10.1 bestanden; keine Verbindung zur Heizung. Offizielles Hassfest und die offiziellen HACS-JSON-Schemas bestanden. Die vollständige HACS-GitHub-Action und Browser-/HAOS-/Hardwareprüfung bleiben offen. [Abschließender QA-Bericht](docs/QA-BERICHT.md). Lizenz, `hacs.json`, Manifest und `custom_components/paradigma/` sind vorhanden. Keine GitHub-Veröffentlichung wurde vorgenommen.

## Changelog – unveröffentlicht, empfohlen 2.0.0-beta.2

Zentraler Registerkatalog; Komponenten-/Sensor-/Steuerassistent mit deutschen und englischen Labels; drei neue optionale Sollwertsensoren; rückwärtskompatible Entry-Migration; ein gemeinsamer zyklischer Leseplan auch für Steuerentitäten; Modellgrenzen und TH-3000-Statusauswertung berichtigt. Dashboard-Baukasten, zusätzliche Heizkreise/Holzkessel/Pelletsofen und sichere Coil-Sequenzen bleiben spätere Arbeiten.

Historische technische Berichte: [P1-Kommunikation](docs/p1-kommunikation.md), [P3-Sicherheitsmodell](docs/p3-steuerung.md), [PELEO-Zähler](docs/peleo14-register.md). Die neuen Anleitungen ersetzen dort beschriebene globale Optionsfreigaben und unabhängige Plattform-Poller.

Fork von [nussfuellung/paradigma-homeassistant](https://github.com/nussfuellung/paradigma-homeassistant). [GPL-3.0](LICENSE). Privates Projekt, kein offizielles Paradigma-Produkt.
