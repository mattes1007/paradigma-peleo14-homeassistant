# P1: Kommunikation und Lebenszyklus

Diese Dokumentation beschreibt den Stand von P1. Seit P3 ändern sich die
Steuerplattformen und Hub-Schreibmethoden; die aktuellen Sperren und
Rückleseprüfungen stehen in [P3-Steuerung](p3-steuerung.md).

## Auswirkungen auf die Plattformen

| Plattform | Sichere P1-Änderung | Bewusst beibehalten |
| --- | --- | --- |
| Sensor | Gemeinsamer Coordinator, konfiguriertes Intervall, Ausfallerkennung | P0-Register, Datentypen, Faktoren, Wortreihenfolge, Unique-IDs |
| Number | Verbesserter gemeinsamer Leseweg und geordneter Client-Lebenszyklus | Eigenes HA-Polling, Sollwert-Schreiblogik, bisherige Verfügbarkeit |
| Switch | Verbesserter Coil-Leseweg und geordneter Client-Lebenszyklus | Eigenes HA-Polling, Coil-Schreiblogik, bisherige Verfügbarkeit |
| Water Heater | Verbesserter gemeinsamer Leseweg und geordneter Client-Lebenszyklus | Eigenes HA-Polling, simulierte Sollwerte und bisherige An/Aus-Schreiblogik |

Der Hub bleibt unter `hass.data["paradigma"][entry_id]` erreichbar. Die
Steuerplattformen erhalten weiterhin denselben Hub und dieselben synchronen
Methoden. `number.py`, `switch.py` und `water_heater.py` bleiben unverändert;
auch die Hub-Methoden `write_register` und `write_coil` bleiben unverändert.
P1 führt keine Schreibzugriffe beim Setup, Polling oder Wiederverbinden ein.

## API und Transport

Das Manifest verlangt seit der Hassfest-Korrektur mindestens `pymodbus>=3.13.1`.
Home Assistant Core 2026.10.0 legt seinerseits `pymodbus==3.13.1` fest;
diese Version erfüllt unsere Mindestanforderung. Die Integration setzt keinen
eigenen exakten Pin gegen spätere Core-Abhängigkeitsupdates. Lesen verwendet ausschließlich die dokumentierte
Keyword-API `address=`, `count=`, `device_id=`. Die fehlerhaften Fallbacks auf
`slave`/`unit` entfallen. Andere PyModbus-Versionen sind hier nicht zugesichert.

Die Client-Vorgaben für Timeout und Wiederholungen werden nicht überschrieben,
weil der Client auch von den Schreibplattformen verwendet wird. PyModbus
3.13.1 verwendet standardmäßig drei Sekunden Timeout und drei Wiederholungen;
ein fehlgeschlagener Aufruf kann deshalb länger als drei Sekunden dauern.
Nach einem Transportfehler wird der Socket geschlossen und für mindestens fünf
Sekunden kein weiterer Lese-/Connect-Versuch unternommen. Der nächste normale
Poll kann wieder verbinden. Es gibt keinen eigenen Hintergrund-Reconnect-Task.
Die unveränderten Schreibmethoden verwenden diesen Lese-Backoff nicht.

Netzwerkfehler, fehlende Antworten und PyModbus-Transportausnahmen werden mit
Host, Port, Slave-ID beziehungsweise Funktion, Register und Anzahl protokolliert.
Modbus-Exception-Responses und fehlerhafte Nutzdaten werden separat behandelt.
Wiederholte Fehler desselben Registers werden auf DEBUG reduziert, erfolgreiche
Wiederherstellung auf INFO gemeldet. Ein vollständiger Sensorausfall wird zudem
vom HA-Coordinator protokolliert. PyModbus kann zusätzliche eigene Logs erzeugen.
Der bestehende Thread-Lock serialisiert alle Client-Zugriffe.

## Sensor-Polling und Verfügbarkeit

Der Leseplan wird aus den P0-Sensordefinitionen abgeleitet und nach Registertyp
und Startadresse dedupliziert. Es werden ausschließlich die durch aktive
Sensordefinitionen benötigten Register gelesen. Alle synchronen Lesezugriffe
eines Sensorzyklus laufen in einem Executor-Job außerhalb des Event-Loops.
Beim Plattform-Setup wird der zuvor initialisierte Coordinator wiederverwendet;
ein doppelter initialer Sensor-Refresh entfällt. Unveränderte Datensätze lösen
keine unnötigen Coordinator-Callbacks aus.

Antwortet kein konfiguriertes Sensorregister mit einer strukturell gültigen
Antwort, wird `UpdateFailed` ausgelöst: alle Coordinator-Sensoren sind dann
`unavailable`. Im nächsten erfolgreichen Poll werden sie wieder verfügbar.
Bei Teilfehlern enthält der neue Datensatz nur erhaltene Antworten; Sensoren
mit fehlender Antwort werden einzeln `unavailable`, ohne alte Messwerte als
aktuell darzustellen. Ein erfolgreich empfangener P0-Sentinel bleibt `unknown`
und zählt als Kommunikationserfolg. Auch ein Datensatz ausschließlich aus
Sentinels ist deshalb kein Verbindungsabbruch.

Größere Registerblöcke, ein gemeinsamer Cache mit den Steuerplattformen und
deren komplette Umstellung auf den Coordinator werden zunächst nicht umgesetzt:
Gerätespezifische Blockgrenzen sind unbekannt; ein Cache könnte Sollwertanzeigen
nach Schreibaktionen verzögern. Insbesondere bleibt das zusätzliche Lesen der
Warmwassertemperatur durch den Water Heater bestehen.

## Setup, Reload und Unload

Setup prüft Konfiguration, Verbindung und den ersten Sensor-Refresh, bevor
Plattformen geladen werden. Verbindungs-/Gesamtausfälle führen zu
`ConfigEntryNotReady`; Home Assistant übernimmt die erneuten Setup-Versuche.
Bei initialen Fehlern und Abbruch werden Coordinator und Client freigegeben.
Der Verbindungstest im Config Flow schließt seinen Testclient im Executor auch
bei Ausnahmen.

Unload entfernt zuerst die Plattformen. Nur bei Erfolg werden Coordinator und
Client beendet und die Runtime-Daten entfernt. Bei fehlgeschlagenem Unload
bleibt der gemeinsame Client erhalten. Schlägt das Laden von Plattformen fehl,
wird deren Unload versucht. Scheitert auch diese Bereinigung, bleiben die
Runtime-Daten erhalten und ein weiterer Setup-Versuch darf sie nicht mit einem
zweiten Client überschreiben. Dieser seltene Zustand benötigt eine erfolgreiche
Bereinigung oder einen HA-Neustart; er wird ausdrücklich protokolliert.
Optionsänderungen verwenden weiterhin HA-Reload und dieselbe Config-Entry-ID.

## Konfigurationsbereiche und Altoptionen

- Host: nicht leer, keine Leerzeichen; IP-Adressen (auch IPv6) oder Hostnamen.
  Es erfolgt keine DNS-Auflösung bei der Validierung.
- Port: ganzzahlig 1–65535.
- Slave-ID: ganzzahlig 1–255; Broadcast-ID 0 wird nicht angeboten.
- Sensor-Abfrageintervall: seit dem P3-Sicherheitsreview ganzzahlig 10–3600 Sekunden, Standard 30 Sekunden.

Neue Eingaben und Änderungen werden vor dem Speichern geprüft. Bei alten,
früher ignorierten ungültigen Intervallen wird zur Laufzeit mit Warnung auf
30 Sekunden zurückgefallen, ohne den Eintrag zu verändern. Der Optionsdialog
verlangt vor dem Speichern einen gültigen Wert. Fehlendes Intervall verwendet
30 Sekunden. Ungültige alte Verbindungseinstellungen führen zu einem klaren
Setup-Fehler und müssen über die Optionen korrigiert werden.
Die alte Holzoption bleibt ignoriert. Das vorhandene Speichermodell mit
`entry.data` und redundanten `entry.options` bleibt zur Vermeidung einer
Konfigurationsmigration unverändert. Endpunktwechsel werden beim nächsten
Setup geprüft; der Optionsdialog baut keine Testverbindung auf.

## Grenzen der Verifikation

Die Tests verwenden ausschließlich Standardbibliothek, HA-Stubs und Fake-Clients.
Der echte PyModbus-Client wird im Test nicht importiert. Sie prüfen produktive
Lese-/Coordinator-Funktionen, Flow-Klassen und Setup-/Unload-Funktionen; ein Test
führt Sensor-I/O mit einem echten lokalen Executor-Thread aus. HA-Timer,
Config-Entry-State-Machine, echte Entity-Registry und reale Geräteantworten sind
nicht Bestandteil dieser Tests. Eine tatsächliche Laufzeitfreigabe für Core
2026.10 ist damit noch nicht erfolgt. Es wurden keine Pakete installiert.

Die P0-Vorbehalte für Register-Wortreihenfolge, Statusbedeutungen und
16-Bit-Sentinels gelten weiter. Die Steuerplattformen melden weiterhin ihre
alten Zustände und haben keine eigene `unavailable`-Logik. HACS-Release- und
Gerätemetadaten bleiben außerhalb dieses Arbeitspakets.

Quellen:

- [Core 2026.10.0: Modbus-Abhängigkeiten](https://raw.githubusercontent.com/home-assistant/core/2026.10.0/homeassistant/components/modbus/manifest.json)
- [PyModbus 3.13.1: Client, Keyword-API und Standardwerte](https://pymodbus.readthedocs.io/en/v3.13.1/source/client.html)
- [HA: Coordinator und UpdateFailed](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [HA: Setup-Wiederholungen](https://developers.home-assistant.io/docs/integration_setup_failures/)

Lokale Prüfung: `python3 -B -m unittest discover -s tests -v`.
