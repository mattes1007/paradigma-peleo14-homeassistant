# Nur-Lesen-Modus und erster Test

Seit P3 ist die Steuerung standardmäßig gesperrt. Die Option **„Heizungssteuerung über Home Assistant erlauben“** ist bei neuen Einträgen deaktiviert; bestehende Einträge ohne diese Option starten ebenfalls lesend. Im Nur-Lesen-Modus wird ausschließlich die Sensorplattform geladen. Keine Number-, Switch- oder Water-Heater-Entität wird als bedienbare Steuerung angelegt.

Die Sperre sitzt zusätzlich in beiden Hub-Schreibmethoden. Nur ein echter boolescher Wert `True` in den maßgeblichen Konfigurationsdaten erlaubt überhaupt eine Prüfung freigegebener Schreibfunktionen. Fehlende/ungültige Werte, beispielsweise `1` oder `"true"`, bleiben gesperrt. Redundante alte `entry.options`-Werte können keine Freigabe bewirken. Eine alte Laufzeit wird vor geänderten Optionen, Reload und Unload sofort gesperrt und kann sich nicht selbst wieder freischalten. Endpunktwechsel setzen die gespeicherte Freigabe zurück.

## Erster Test auf HAOS

1. Backup und sichere Wiederherstellung gemäß [HACS-Anleitung](hacs-installation.md) vorbereiten. Bestehende Steuerautomationen pausieren, die vorherige Integration und andere Modbus-Clients berücksichtigen.
2. Nach einem Neustart sicherstellen, dass der P3-Code geladen ist. Die Steuerfreigabe deaktiviert lassen. Die Sperre existiert nicht in älteren Original-/P0-/P1-/P2-Versionen.
3. Nur Sensorwerte, Verfügbarkeit, Logs und Wiederverbindung prüfen. Die Einrichtung selbst verwendet einen gesonderten, ebenfalls nicht schreibberechtigten Test-Hub.
4. Falls die installierte SystaComfort-Version dies unterstützt, am Hauptbedienteil zusätzlich den Modbus-Zugriff auf **lesen** begrenzen. Menübezeichnung und Voraussetzungen anhand der passenden Herstellerunterlage prüfen; P3 verändert keine Einstellung am Regler.

Die zentrale Sperre gilt für diese Integration. Sie schützt nicht vor anderen Integrationen, externen Modbus-Clients oder bereits zuvor gesendeten Befehlen. Ein bereits begonnener oder übertragener Schreibzugriff lässt sich bei einem Optionswechsel nicht zurückrufen. Bereits aktive Override-Werte können bis zu ihrem geräteseitigen Ablauf wirksam bleiben; Sperren, Unload und Read-only-Setup senden ausdrücklich keine Rücksetzbefehle.

## Bewusste Freigabe

Nur nach Prüfung von Regler-/Firmware-Version, Herstellerunterlage, Anlagenkonfiguration und Rückfallverhalten die Option aktivieren. Danach sind ausschließlich die in [P3-Steuerung](p3-steuerung.md) geprüften Sollwerte bedienbar. Puffer-/Kessel-Sollwerte und alle Coil-Schalter bleiben auch dann gesperrt.

Zum erneuten Sperren die Option deaktivieren. Die bisherige Runtime wird sofort gesperrt, danach neu geladen; vorhandene Steuerentitäten werden entfernt und können als nicht verfügbare Registry-Einträge verbleiben. Sensoridentitäten bleiben erhalten. Bei einem gescheiterten Reload/Unload bleibt die alte Runtime gesperrt.

Die lokalen Tests verwenden ausschließlich Fake-Clients. Ein echter HAOS-/Heizungstest wurde nicht durchgeführt.
