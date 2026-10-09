# P3: Steuerfreigabe und Prüfung der Schreibpfade

## Auswirkungen auf die Plattformen

| Bereich | Änderung |
| --- | --- |
| Hub | Standardmäßig gesperrt, unveränderliche Adress-Allowlist, strikte Freigabe, Eingabe-/Antwortprüfungen; keine alten API-Fallbacks |
| Number | Nur freigegebene Heizkreis-Sollwerte; keine bedienbaren Regler für Holding 44/45; keine optimistischen Werte |
| Switch | Keine Schalter angelegt; alte Klassen/Unique-ID-Formate bleiben erhalten, Serviceaktionen sind gesperrt |
| Water Heater | Nur Solltemperatur, keine An/Aus-Funktion, keine simulierten 50 °C; Rücklesen nach bestätigtem Schreiben |
| Config/Options Flow | Übersetzte Freigabeoption mit Standard `False`; ungültige neue Eingaben abgewiesen; Endpunktwechsel sperren |
| Setup/Reload/Unload | Sensorplattform immer, Steuerplattformen nur bei Freigabe; tatsächlich geladene Plattformliste für Unload gespeichert; alte Runtime vor Reload/Unload gesperrt |
| Sensor | Produktiver Sensorcode unverändert; alle P0-Register und Sensoridentitäten erhalten |

## Belege und Einschränkung des Geltungsbereichs

Geprüft wurde die von Paradigma verfasste Unterlage **TH-3000 V1.1, 03/2021**, für **SystaComfort II / Compact C ab Regler-Software V2.16**. Sie ist als [PDF-Kopie](https://forum.iobroker.net/assets/uploads/files/1674034323539-th-3000_v1.1_0321_systacomfort_ii_compactc_modbus_informationen_b_fhw.pdf) öffentlich abrufbar; die [Herstellerseite](https://www.paradigma.de/produkte/regelungen/systacomfortll/) verweist ebenfalls auf Modbus-Unterlagen. Das Dokument wird hier nicht vervielfältigt. Die ältere SystaSmartC-Unterlage TH-2833 ist kein ausreichender Nachweis für diese Regelung.

Die folgende Tabelle fasst die für die vorhandenen Schreibpfade relevanten Angaben zusammen. Adressen sind **nullbasiert**, keine Modicon-Registernummern:

| Funktion / bisheriger Code | Dokumentierter Zugriff | Entscheidung |
| --- | --- | --- |
| Heizkreis-Sollwert: Holding 2/3 | FC `0x10`, int16, Faktor 0,1; Rücklesen FC `0x03` | Mit ausdrücklicher Freigabe erlaubt |
| Warmwasser-Sollwert: Holding 8 | FC `0x10`, int16, Faktor 0,1; Rücklesen FC `0x03` | Nur bei bestätigtem Freigabe-Override erlaubt |
| Puffer oben: Holding 44 | Nur lesbar | Dauerhaft für dieses Profil gesperrt |
| Kessel: Holding 45 | Nur lesbar | Dauerhaft für dieses Profil gesperrt |
| Warmwasser: Coil 4/5 | Freigabe / Sperre, FC `0x05`; Rücklesen FC `0x01` | Gesperrt: sichere Paar-Sequenz noch nicht freigegeben |
| Zirkulation: Coil 6/7 | Freigabe / Sperre, FC `0x05`; Rücklesen FC `0x01` | Gesperrt: sichere Paar-Sequenz noch nicht freigegeben |

Quelle: TH-3000, Seiten 6, 11–12, 15 und 17–18. Die bisherige Switch-Logik schreibt nur das Freigabebit `False`, statt explizit die Sperre zu setzen. Das beendet allenfalls eine Freigabe; es garantiert kein Ausschalten. Das Verhalten bei beiden gleichzeitig gesetzten Bits, sichere Umschaltreihenfolge und Behandlung teilweise fehlgeschlagener Sequenzen sind für diese Integration noch offen. Deshalb gibt es keine freigegebenen Coil-Schreibpfade. Auch alte direkte Serviceaufrufe werden abgewiesen.

Die reale Firmware der Anlage wurde nicht ermittelt. Vor globaler Freigabe muss die Anwendbarkeit der Unterlage bestätigt werden. Schreibfreigaben gelten nur für Unit-ID 1; andere gültige Lese-IDs bleiben lesbar, aber schreibgesperrt. Die bisher bekannten P0-Zähler und Statusadressen werden nicht verändert. Die neue Unterlage stützt die bisherige High-Word-Reihenfolge, ersetzt aber keinen Vergleich mit realen Anlagenwerten.

## Grenzen und Voraussetzungen der Sollwerte

- Heizkreis 1/2: bisherige Anwendungsgrenzen **20–80 °C**, Schritt **1 °C**. Zusätzlich muss der Wert innerhalb der aus Holding 9/10 gelesenen maximalen Vorlauftemperatur liegen. Fehlende oder ungültige Maximalwerte sperren das Schreiben.
- Warmwasser: bisherige Anwendungsgrenzen **30–70 °C**, Schritt **0,1 °C**. Vor jedem Schreiben müssen Coil 4 aktiv und Coil 5 inaktiv gelesen werden. P3 setzt diese Bits selbst nicht; ohne eindeutigen Freigabe-Override bleibt der Sollwert gesperrt.
- Diese UI-Grenzen sind konservativ übernommene Anwendungsgrenzen, keine Zusicherung der Eignung für die konkrete Anlage. Sonderwerte zum Ausschalten/Beenden einer Steuerung werden nicht angeboten.
- Nicht endliche Zahlen, boolesche Werte, Zeichenketten, Bereichs- und Schrittverletzungen werden ohne Schreiben zurückgewiesen. Die Umrechnung in Zehntelgrade erfolgt ohne stilles Abschneiden.

## Bestätigung ist nicht Anlagenwirkung

Der Hub akzeptiert eine Schreibantwort nur, wenn sie keinen Modbus-Fehler meldet und FC `0x10`, Startadresse und Anzahl 1 bestätigt. Keine Antwort, Transportausnahme, Modbus-Exception oder unpassende Bestätigung gilt als Erfolg. Der dokumentierte PyModbus-3.13.1-Aufruf verwendet ausschließlich `address=`, `values=`, `device_id=`. Alte `slave`-/`unit`-Fallbacks entfallen.

Nach einer bestätigten Schreibantwort lesen Number und Water Heater den tatsächlichen Holding-Sollwert erneut aus. Bei Abweichung wird der gelesene Wert angezeigt und ein Fehler gemeldet; bei fehlendem Rücklesewert wird der Wert unbekannt beziehungsweise die Entität nicht verfügbar. Ein Schreibfehler erzeugt keinen gewünschten Ersatzwert und löscht auch den vorherigen Sollwert aus der aktuellen Anzeige, weil dessen Gültigkeit nach einem unbeantworteten Schreibversuch ungewiss ist. Beim nächsten erfolgreichen Poll wird ausschließlich der tatsächlich gelesene Registerwert angezeigt. Vorher gelesene Werte sind kein Beweis, dass ein fehlgeschlagener oder unbeantworteter Schreibversuch wirkungslos war.

Ein übereinstimmender Rücklesewert belegt den aktuellen Registerwert, **nicht** die tatsächliche Wärmeerzeugung, Pumpenwirkung oder erreichte Temperatur. Die Warmwasser-Betriebsart bleibt unbekannt, statt künstlich „an“ zu melden. Ein einzelnes sofortiges Rücklesen kann bei verzögerter Reglerübernahme abweichen; P3 führt dann keine automatische Wiederholung aus. Eine spätere normale Aktualisierung zeigt den aktuellen Wert.

Laut TH-3000 laufen Leitsystemvorgaben nach ungefähr fünf Minuten ohne Erneuerung aus. P3 sendet keine periodischen Erneuerungen und keine Befehle bei Setup, Polling, Reload, Unload oder Wiederverbindung. Die ursprünglichen sicheren Regler-Einstellungen für den Rückfall müssen vor Freigabe geprüft werden. Die unveränderten PyModbus-Timeout-/Retry-Vorgaben können eine Anfrage auf Protokollebene wiederholen; P3 fügt keine eigene Schreibwiederholung hinzu.

### Zeitlich begrenzte Rücklesebestätigung

Number und Water Heater veröffentlichen `setpoint_confirmation` und `last_requested_setpoint` als zusätzliche Attribute. Die mögliche Bestätigung ist konservativ auf **300 Sekunden ab Beginn des jeweiligen Schreibversuchs** begrenzt. Eine lange Anfrage verkürzt dieses Fenster; spätere zyklische Lesezugriffe verlängern es nicht. Auch nach Ablauf kann ein Register noch denselben Sollwert enthalten; dann bleibt dieser als Registerinhalt sichtbar, aber die Bestätigung ist `expired`.

| Attributwert | Bedeutung |
| --- | --- |
| `not_requested` | In dieser Entity-Laufzeit wurde kein Sollwert angefordert |
| `pending` / `acknowledged` | Angefordert / Schreibantwort bestätigt, noch kein passender Rücklesewert |
| `readback_matches` | Registerwert passt innerhalb des begrenzten Fensters zur Anforderung; kein Beweis für aktiven Heizbetrieb |
| `readback_mismatch` / `readback_failed` | Rücklesen weicht ab / nicht möglich |
| `write_failed` | Schreibversuch gesperrt oder fehlgeschlagen; keine Bestätigung |
| `expired` | Zeitfenster abgelaufen, auch bei weiterhin identischem Registerwert |

Die Entity-Laufzeit speichert diese Bestätigung nicht über einen Neustart oder Reload hinweg. Die Attributabfrage prüft die monotone Uhr ohne Modbus-Zugriff. Home Assistant veröffentlicht die Änderung beim nächsten regulären State-Update; es gibt keinen zusätzlichen Ablauf-Timer. Im normalen Betrieb kann die Frontend-Anzeige deshalb bis zum nächsten Number-/Water-Heater-Poll nachlaufen. Bei blockiertem HA-Event-Loop oder langen I/O-Aufrufen ist keine Echtzeit-Anzeige zugesichert. Die Attribute sind Rücklese-Evidenz, niemals ein bestätigter Anlagenzustand.

**Das Sperren weiterer Schreibzugriffe hebt bereits aktive Overrides nicht automatisch auf.** Sperren, Reload und Unload senden keine Rücksetz-Coils oder Sonderwerte. Bereits begonnene Requests einschließlich möglicher Bibliotheks-Retries können nicht zurückgerufen werden. Den lokalen Read-only-Status nicht mit dem geräteseitigen Ende einer zuvor gesetzten Vorgabe verwechseln.

## Identitäten und Konfiguration

`allow_control` wird wie die bestehenden Optionen in `entry.data` gespeichert; die redundanten `entry.options` bleiben erhalten, sind aber keine zusätzliche Berechtigungsquelle. Nur das literal boolesche `True` zählt. Alte fehlende oder ungültige Werte laden lesend, ohne die Sensoren zu blockieren. Neue ungültige Formulareingaben erzeugen einen übersetzten Feldfehler.

Eine Optionsübermittlung ohne Berechtigungsfeld sperrt die Steuerung. Ein Wechsel von Host, Port oder Slave-ID setzt die Berechtigung zurück, auch wenn die Checkbox dabei noch aktiv war; eine zweite bewusste Freigabe ist nötig. Ein identisches Speichern ohne Konfigurationsänderung entzieht eine bestehende Freigabe nicht unnötig. Geänderte Optionen und Reload sperren die bisherige Runtime dauerhaft; erst ein neues Setup kann eine noch ausdrücklich gespeicherte Freigabe anwenden.

Domain, Config-Entry-ID, Sensorschlüssel und Sensor-Unique-IDs bleiben unverändert. Aktive Regler behalten `<entry_id>_num_2`, `_num_3` und `_wh_ww`; gesperrte Altentitäten werden nicht auf andere Register umgebogen. Alte Puffer-, Kessel- und Switch-Einträge können nicht verfügbar in der Registry verbleiben. Sie werden nicht gelöscht. Vorhandene Automationen müssen die neue Sperre und gesperrten Funktionen berücksichtigen.

## Testumfang und verbleibende Prüfungen

Die Offline-Tests führen produktive Hub-, Sensor-, Flow-, Lebenszyklus- und Steuerklassen mit Fake-Clients und HA-Stubs aus. Sie prüfen strikte Berechtigungen, neue/alte Einträge, Endpunktwechsel, Freigabe/Entzug, fehlerhafte Antworten, Grenzen, Rücklesefehler/-abweichungen und unveränderte Sensoridentitäten. Ein kombinierter Test führt Setup, Refresh und Unload mit dem produktiven Hub aus. Es werden keine echten Modbus-Befehle oder HA-Serviceaufrufe ausgeführt.

Die echte HA-Entity-Registry, OptionsFlow-Benachrichtigungen, Frontend-Darstellung, Regler-Firmware, Verzögerungen und reale Anlagenwirkung sind noch nicht getestet. Keine zusätzliche Paketinstallation, kein Kontakt zur Heizung und keine HAOS-Installation wurden vorgenommen.

Seit dem abschließenden Sicherheitsreview liegt die Mindestabfragezeit bei **zehn Sekunden**, der Standard bleibt **30 Sekunden**. Neue Eingaben unter zehn Sekunden werden abgewiesen. Bereits gespeicherte kleinere, ungültige oder falsch typisierte Werte verwenden mit Warnung 30 Sekunden; die Daten werden nicht stillschweigend migriert. Nachträgliche Optionsänderungen verlangen einen gültigen Wert.

## Prüfung des vollständigen Abfragezyklus

Das konfigurierte Intervall gilt für **einen vollständigen Sensor-Coordinator-Zyklus**, nicht für jedes einzelne Register. Pro Zyklus wird der gesamte deduplizierte Leseplan einmal in einem Executor-Job abgearbeitet. Register werden innerhalb dieses Jobs nacheinander ohne Zehn-/Dreißig-Sekunden-Pause gelesen. Die Zyklusdauer hängt von Registeranzahl, Antworten und Timeouts ab. Der HA-Coordinator plant die normale nächste Aktualisierung nach Abschluss neu; 30 Sekunden sind kein garantierter maximaler Messwertabstand. HA-Timer sind nicht exakt und manuelle Aktualisierungen können zusätzliche Zyklen anfordern.

| Plattform | Zusätzliche zyklische Abfragen |
| --- | --- |
| Nur-Lesen-Modus | Nur der vollständige Sensorzyklus; keine Steuerplattform-Polls |
| Number mit Freigabe | Holding 2, optional 3, jeweils ein Register pro Entity-Update; HA-Core-Standard 30 Sekunden |
| Switch | Keine Entitäten angelegt, keine zusätzlichen zyklischen Coil-Abfragen |
| Water Heater mit Freigabe | Input 3 und Holding 8 pro Update; HA-Core-Standard 60 Sekunden |

Input 3 wird auch vom Sensor-Coordinator gelesen und ist deshalb eine verbleibende plattformübergreifende Doppelabfrage. Die Sollwerte 2/3/8 gehören nicht zum Sensor-Leseplan. Beim Warmwasser-Schreiben wurde die unnötige erneute Input-3-Abfrage entfernt: Nach Coil-Voraussetzung und Schreibantwort wird nur Holding 8 rückgelesen. Die dokumentierten Prüflesezugriffe und unmittelbaren Rücklesezugriffe nach Serviceaktionen sind zusätzliche ereignisbezogene Reads.

Die unabhängigen Plattform-Timer und der gemeinsame Hub-Lock wurden nicht umgebaut. Sie serialisieren I/O, bilden aber keinen gemeinsamen globalen Abfragezyklus und garantieren keine zehn Sekunden Pause zwischen Modbus-Telegrammen verschiedener Plattformen. Für die erste Prüfung bleibt Nur-Lesen empfohlen. Cache-/Coordinator-Zusammenführung und eine globale Lastbegrenzung sind getrennte spätere Arbeiten.

Framework-Belege für Core 2026.10.0: [Number-Intervall](https://raw.githubusercontent.com/home-assistant/core/2026.10.0/homeassistant/components/number/__init__.py), [Water-Heater-Intervall](https://raw.githubusercontent.com/home-assistant/core/2026.10.0/homeassistant/components/water_heater/__init__.py), [Coordinator-Terminierung](https://raw.githubusercontent.com/home-assistant/core/2026.10.0/homeassistant/helpers/update_coordinator.py). Die lokalen Tests prüfen Intervallparameter und konkrete Requests; sie führen den echten HA-Timer nicht aus.
