# Modular konfigurieren

Installation: [HACS-Anleitung](hacs-installation.md). Nach Installation die Integration **Paradigma PELEO 14** hinzufügen. Keine YAML- oder Lovelace-Konfiguration nötig.

1. Name, Host, Port, Unit-ID, Modell und Intervall eingeben. Standard: Port 502, Unit 1, 30 Sekunden; Minimum 10 Sekunden. Der Erstassistent prüft ausschließlich die Verbindung, schreibt nichts.
2. Vorhandene Baugruppen auswählen: Allgemein/Außentemperatur, Kessel/Pelletheizung, Puffer, HK1, HK2, Warmwasser, Zirkulation, Solar, Schwimmbad und Raumfühler. Raumfühler schalten Raumtemperaturen in der jeweiligen Heizkreisauswahl frei.
3. Pro Baugruppe erscheint ein eigenes Sensorformular mit verständlichen, übersetzten Mehrfachauswahlen. Bei neuen Anlagen sind die bisherigen üblichen Sensoren vorausgewählt; die drei neuen Sollwerte sind optional. Register werden nur für gewählte Sensoren oder ausdrücklich freigegebene Steuerentitäten zyklisch gelesen.
4. Steuerfunktionen einzeln auswählen und Modell, Voraussetzungen sowie sichere Rückfalleinstellungen bestätigen. Standard: keine. Sensorwahl erteilt keine Schreibrechte.
5. Zusammenfassung prüfen und übernehmen. Erst dieser Schritt speichert. Abbrechen lässt die Konfiguration unverändert.

Spätere Änderungen: **Einstellungen → Geräte & Dienste → Paradigma → Konfigurieren**. Derselbe Assistent übernimmt bestehende Werte. Speichern lädt die Integration neu; der alte Hub wird gesperrt, die Plattformen entladen, der Coordinator gestoppt und die gemeinsame Verbindung geschlossen. Es entsteht kein zusätzliches Gerät. Abgewählte Entitäten werden nicht aus der Registry oder dem Recorder gelöscht; sie können nicht verfügbar bleiben und bei erneuter Auswahl dieselbe Identität erhalten.

## Modelle

Verifiziertes Dokumentprofil: **SystaComfort II / Compact C ab Firmware 2.16**, TH-3000 V1.1 (03/2021). Die Auswahl ist eine Bestätigung durch den Nutzer, keine automatische Firmwareerkennung. Angeschlossene Zusatzregler und Fühler müssen tatsächlich vorhanden sein.

**SystaSmartC II ist nicht neu unterstützt.** Eine passende, verifizierte Registerunterlage fehlt. Es wird ausdrücklich als nicht unterstützt beschriftet und bei neuen Einträgen abgewiesen. Bestehende Einträge werden ohne Modellbehauptung als `legacy_unverified` erhalten. Dort bleiben bisherige Leseregister und vorhandene ausdrückliche Schreibfreigaben erhalten; neue Sollwertsensoren oder neue Steuerfreigaben werden nicht angeboten. Nach Prüfung des tatsächlichen Reglers kann das bestätigte Modell in Optionen gewählt werden. Ein Wechsel von Modell oder Verbindung löscht die bisherigen Steuerfreigaben im Entwurf; eine erneute ausdrückliche Auswahl und Sicherheitsbestätigung ist erforderlich.

## Daten und künftige Dashboards

Entry-Daten enthalten `model`, `components`, `sensors` und `controls` als einzige maßgebliche Auswahl. Sensorattribute `component` und `register_key` verbinden die bestehenden HA-Entitäten mit dem Katalog. Gerätekennung und Unique-IDs bleiben unverändert. Es gibt keinen Dashboard-Installer und keine zweite Anlagenkonfiguration.

Fehlende Antworten und ungültige Werte werden unbekannt/nicht verfügbar. Ein einzelnes fehlendes optionales Register blockiert andere Werte nicht. Antworten alle gewählten Register nicht, meldet der gemeinsame Coordinator einen Kommunikationsfehler. Eine leere Auswahl erzeugt keine regelmäßigen Modbus-Lesezugriffe.
