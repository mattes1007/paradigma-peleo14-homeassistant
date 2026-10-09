# Paradigma PELEO 14 für Home Assistant

Eigene Integration für die **Paradigma PELEO 14 mit SystaComfort-Regelung** über lokales Modbus TCP. Maintainer: [mattes1007](https://github.com/mattes1007). Installation als benutzerdefiniertes HACS-Repository; dieser Fork ist kein Eintrag im HACS-Standardkatalog.

![Paradigma Logo](logo.png)

## Stand und Voraussetzungen

Version **2.0.0-beta.1**, Domain **`paradigma`**. Zielversion: Home Assistant Core **2026.10.0**, mit `pymodbus==3.13.1`. Frühere Core-Versionen sind nicht freigegeben. HAOS 18.3 ist die vorgesehene Umgebung. Die lokalen Tests verwenden Framework-Stubs und Fake-Modbus-Clients; ein echter HAOS-Laufzeittest steht noch aus.

**Standardmäßig arbeitet die Integration ausschließlich lesend.** Die Option „Heizungssteuerung über Home Assistant erlauben“ ist deaktiviert, auch bei bestehenden Einträgen ohne diese Option. Eine zentrale Hub-Sperre verhindert Schreibzugriffe. Details zum ersten Test und zur Freigabe: [Nur-Lesen-Modus](docs/lesebetrieb.md).

## Sensoren und Kommunikation

Die drei PELEO-Kesselsensoren sind unabhängig von optionalen Komponenten immer vorhanden:

| Sensor | Holding-Register | Format |
| --- | --- | --- |
| Betriebsstunden | 27–28 | uint32, High Word zuerst |
| Kesselstarts | 29–30 | uint32, High Word zuerst |
| Kesselstatus | 41 | uint16, bestehende Statustabelle |

Ungültige Zählerwerte `4294967295` werden verworfen. Wortreihenfolge und Kesselstatus-Tabelle müssen noch anhand echter Registerwerte oder Herstellerunterlagen bestätigt werden. Es gibt keinen separaten Wodtke-Pelletsofen oder Holzkessel in diesem Profil.

Weitere Sensoren betreffen Heizkreis 1, Warmwasser, Puffer und Zirkulation. Solar, Heizkreis 2, Pool, Raumfühler sowie Kesseltemperaturfühler sind optional; ihre bisherigen Zuordnungen sind noch nicht unabhängig für diese Anlage bestätigt. Die Option für Kesseltemperaturfühler beeinflusst die drei Kesselsensoren nicht.

Das konfigurierte Sensor-Abfrageintervall beträgt 10–3600 Sekunden, standardmäßig 30 Sekunden. Alte gespeicherte Werte unter zehn Sekunden werden zur Laufzeit mit Warnung auf 30 Sekunden zurückgesetzt, ohne den gespeicherten Eintrag zu verändern. Bei vollständigem Ausfall werden Sensoren `unavailable`; erfolgreiche spätere Abfragen stellen die Daten automatisch wieder her. Details: [Register und Identitäten](docs/peleo14-register.md), [Kommunikation und Lebenszyklus](docs/p1-kommunikation.md).

Bei bewusst aktivierter Steuerfreigabe werden nur die belegten Heizkreis-Sollwerte und der Warmwasser-Sollwert angeboten. Sie prüfen Wertebereiche, Schreibantworten und Rücklesewerte. Puffer-/Kessel-Sollwertregler sowie Warmwasser-/Zirkulationsschalter bleiben gesperrt. Die geprüfte Herstellerunterlage bezeichnet Holding 44/45 als nur lesbar; Coil-Overrides benötigen eine gesonderte Freigabe ihrer Befehlssequenz. [P3-Schreibprüfung und Grenzen](docs/p3-steuerung.md).

## Installation und Aktualisierung

[HACS-Anleitung mit Backup, Wechsel von der Originalintegration und Rollback](docs/hacs-installation.md).

Repository: **`https://github.com/mattes1007/paradigma-peleo14-homeassistant`**, HACS-Kategorie **Integration**. Die Dateien liegen unter `custom_components/paradigma/`. HACS lädt direkt aus dem Repository; ein ZIP-Release ist nicht erforderlich. Diese lokalen Änderungen werden erst nach gesondert freigegebener Veröffentlichung über GitHub verfügbar.

Bei einer neuen Einrichtung unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **Paradigma PELEO 14** suchen. Verbindungsdaten für die vorgesehene Anlage: Host `192.168.1.42`, Port `502`, Slave-ID `1`. **Die Einrichtung prüft die Verbindung**, deshalb vor dem ersten Test die Hinweise zum Nur-Lesen-Modus prüfen. Die Steuerfreigabe dabei deaktiviert lassen. Nur tatsächlich installierte Zusatzkomponenten auswählen. Der bestehende Name und Integrationseintrag sollen bei einem Upgrade erhalten bleiben, damit die Entity-Identitäten erhalten bleiben.

## Entwicklung

Alle lokalen Tests ohne zusätzliche Pakete und ohne echte Netzwerkzugriffe:

```sh
python3 -B -m unittest discover -s tests -v
git diff --check
```

GitHub-Workflows prüfen zusätzlich HACS und Hassfest sowie die Offline-Tests unter Python 3.12 und 3.14. Die externen Validatoren sind nicht Teil des lokalen Testlaufs. [Verpackung und Versionsstrategie](docs/hacs-installation.md#verpackung-und-version).

## Herkunft

Fork von [nussfuellung/paradigma-homeassistant](https://github.com/nussfuellung/paradigma-homeassistant). Lizenz: [GPL-3.0](LICENSE). Dies ist ein privates Projekt und kein offizielles Produkt von Paradigma.
