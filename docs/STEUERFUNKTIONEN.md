# Einzeln freigegebene Steuerfunktionen

Auswählbar sind externe Vorlaufvorgaben HK1 (Holding 2), HK2 (Holding 3) und externe Warmwasservorgabe (Holding 8). Keine Freigabe folgt aus der Sensorwahl. Bei neuen Freigaben ist das bestätigte TH-3000-Profil SystaComfort II/Compact C ab 2.16 erforderlich. Unit-ID muss zum Schreiben 1 sein.

HK1/HK2: 20–80 °C, Schritt 1 °C, zusätzlich live geprüfte maximale Vorlauftemperatur aus Holding 9/10. Warmwasser: 30–70 °C, Schritt 0,1 °C; vor jedem Schreiben müssen Coil 4 aktiv und Coil 5 inaktiv zurückgelesen werden. Die Integration setzt diese Freigabe-Coils selbst nicht. Die Grenzen sind konservative Anwendungsgrenzen, keine Garantie für die konkrete Anlage.

Eine Legacy-Freigabe gilt nur für die separat gespeicherten ursprünglichen Funktionen. Eine spätere Auswahl zusätzlicher Baugruppen oder Funktionen erweitert sie nicht. Modell-/Verbindungswechsel verwerfen die Legacy-Freigabe im Entwurf; neue Rechte verlangen die separate Sicherheitsbestätigung.

Der vorhandene Hub prüft pro Adresse Freigabe, Datentyp, Grenzen, Schritt und Voraussetzungen unter dem gemeinsamen Verbindungsschloss. Es gibt keine freien Schreibadressen und keinen zweiten Client. Fehlt die individuelle Berechtigungsprüfung, liefert sie keinen wörtlichen booleschen Wert `True` oder schlägt sie fehl, bleibt der Zugriff gesperrt. Die Rechte werden nach den Live-Voraussetzungen unmittelbar vor jedem Schreibtelegramm erneut geprüft, auch bei direkten Hub-Aufrufen. Nur FC 0x10 wird verwendet. Eine Quittung allein ist keine Erfolgsmeldung: sofortiges Rücklesen muss zum angeforderten Wert passen; sonst wird ein Fehler gemeldet. Registerbestätigung beweist keine Heizwirkung.

Vorgaben gelten laut TH-3000 etwa **fünf Minuten**. Keine periodischen Schreibbefehle oder automatische Erneuerung, keine Befehle bei Setup, Reload oder Unload. Sichere Rückfalleinstellungen müssen am Regler vor Freigabe geprüft werden. Die zeitlich begrenzten Bestätigungsattribute aus P3 bleiben erhalten. Der Modbus-Client behält seine bisherigen Timeout-/Retry-Einstellungen; es gibt keine zusätzlichen Anwendungsschreibwiederholungen.

Holding 44/45 bleiben ausschließlich lesbar. Warmwasser-/Zirkulationsschalter und Warmwasser-Ein/Aus bleiben gesperrt; sichere Coil-Paarsequenzen sind noch nicht freigegeben. Keine dauerhafte Steuerung, keine Schwimmbadsteuerung oder Steuerung zusätzlicher Heizkreise.

Zyklische Werte der Number- und Water-Heater-Entitäten kommen nun aus **dem gemeinsamen Sensor-Coordinator**. Eigene Plattform-Poller sind deaktiviert. Prüf- und Rücklesezugriffe nach einem ausdrücklichen Befehl bleiben ereignisbezogen. Details des übernommenen Sicherheitsmodells: [P3](p3-steuerung.md); dessen früherer globaler Optionsdialog und unabhängige Poller sind durch diese modulare Version ersetzt.
