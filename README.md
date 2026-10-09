# Paradigma PELEO 14 für Home Assistant

Eigene Integration für die **Paradigma PELEO 14 mit SystaComfort-Regelung** über lokales Modbus TCP. Maintainer: [mattes1007](https://github.com/mattes1007). Installation als benutzerdefiniertes HACS-Repository; dieser Fork ist kein Eintrag im HACS-Standardkatalog.

![Paradigma Logo](logo.png)

## Stand und Voraussetzungen

Version **2.0.0-beta.1**, Domain **`paradigma`**. Zielversion: Home Assistant Core **2026.10.0**, mit `pymodbus==3.13.1`. Frühere Core-Versionen sind nicht freigegeben. HAOS 18.3 ist die vorgesehene Umgebung. Die lokalen Tests verwenden Framework-Stubs und Fake-Modbus-Clients; ein echter HAOS-Laufzeittest steht noch aus.

**Die Integration enthält aktive Steuerplattformen und hat derzeit keinen Read-only-Schalter. Vor einem Test mit erreichbarer Heizung die [Empfehlung zum sicheren Lesebetrieb](docs/lesebetrieb.md) beachten.** P2 bereitet Installation und Verpackung vor, aktiviert aber keine Schreibsperre.

## Sensoren und Kommunikation

Die drei PELEO-Kesselsensoren sind unabhängig von optionalen Komponenten immer vorhanden:

| Sensor | Holding-Register | Format |
| --- | --- | --- |
| Betriebsstunden | 27–28 | uint32, High Word zuerst |
| Kesselstarts | 29–30 | uint32, High Word zuerst |
| Kesselstatus | 41 | uint16, bestehende Statustabelle |

Ungültige Zählerwerte `4294967295` werden verworfen. Wortreihenfolge und Kesselstatus-Tabelle müssen noch anhand echter Registerwerte oder Herstellerunterlagen bestätigt werden. Es gibt keinen separaten Wodtke-Pelletsofen oder Holzkessel in diesem Profil.

Weitere Sensoren betreffen Heizkreis 1, Warmwasser, Puffer und Zirkulation. Solar, Heizkreis 2, Pool, Raumfühler sowie Kesseltemperaturfühler sind optional; ihre bisherigen Zuordnungen sind noch nicht unabhängig für diese Anlage bestätigt. Die Option für Kesseltemperaturfühler beeinflusst die drei Kesselsensoren nicht.

Das konfigurierte Sensor-Abfrageintervall beträgt 5–3600 Sekunden, standardmäßig 30 Sekunden. Bei vollständigem Ausfall werden Sensoren `unavailable`; erfolgreiche spätere Abfragen stellen die Daten automatisch wieder her. Details: [Register und Identitäten](docs/peleo14-register.md), [Kommunikation und Lebenszyklus](docs/p1-kommunikation.md).

Die unveränderten Plattformen Number, Switch und Water Heater können Solltemperaturen, Warmwasser und Zirkulation steuern. Sie verwenden weiterhin eigene Abfragen und haben noch nicht die Ausfallbehandlung der Sensoren. Ihre Schreibsemantik wurde nicht für die PELEO 14 bestätigt.

## Installation und Aktualisierung

[HACS-Anleitung mit Backup, Wechsel von der Originalintegration und Rollback](docs/hacs-installation.md).

Repository: **`https://github.com/mattes1007/paradigma-peleo14-homeassistant`**, HACS-Kategorie **Integration**. Die Dateien liegen unter `custom_components/paradigma/`. HACS lädt direkt aus dem Repository; ein ZIP-Release ist nicht erforderlich. Diese lokalen P2-Änderungen werden erst nach gesondert freigegebener Veröffentlichung über GitHub verfügbar.

Bei einer neuen Einrichtung unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **Paradigma PELEO 14** suchen. Verbindungsdaten für die vorgesehene Anlage: Host `192.168.1.42`, Port `502`, Slave-ID `1`. **Die Einrichtung prüft die Verbindung**, deshalb erst mit abgesichertem Netzwerk durchführen. Nur tatsächlich installierte Zusatzkomponenten auswählen. Der bestehende Name und Integrationseintrag sollen bei einem Upgrade erhalten bleiben, damit die Entity-Identitäten erhalten bleiben.

## Entwicklung

Alle lokalen Tests ohne zusätzliche Pakete und ohne echte Netzwerkzugriffe:

```sh
python3 -B -m unittest discover -s tests -v
git diff --check
```

GitHub-Workflows prüfen zusätzlich HACS und Hassfest sowie die Offline-Tests unter Python 3.12 und 3.14. Die externen Validatoren sind nicht Teil des lokalen Testlaufs. [Verpackung und Versionsstrategie](docs/hacs-installation.md#verpackung-und-version).

## Herkunft

Fork von [nussfuellung/paradigma-homeassistant](https://github.com/nussfuellung/paradigma-homeassistant). Lizenz: [GPL-3.0](LICENSE). Dies ist ein privates Projekt und kein offizielles Produkt von Paradigma.
