# Empfehlung: erster Test ausschließlich mit Lesezugriffen

**Aktuell gibt es keine zuverlässige Read-only-Option in der Integration.** Die Plattformen `number`, `switch` und `water_heater` werden neben `sensor` geladen. Setup und Aktualisierungen lesen; Serviceaufrufe oder vorhandene Automationen können jedoch schreiben. P2 verändert diese Plattformen und die beiden Hub-Schreibmethoden nicht.

## Empfohlene nächste Umsetzung

Vor einem ersten Test mit erreichbarer Heizung einen standardmäßig aktiven Read-only-Modus entwickeln:

1. Beide Hub-Schreibmethoden vor jeder Client-Anforderung sperren und abgewiesene Aufrufe eindeutig melden. Das ist die zentrale Sicherung auch gegen versehentliche direkte Aufrufe.
2. Im Lesemodus nur die Sensorplattform laden. Steuerplattformen erst nach bewusster Freigabe laden; vorhandene Unique-IDs erhalten.
3. Neue und bestehende Konfigurationen standardmäßig lesend behandeln und Reload/Unload sowie alle Schreib-Einstiegspunkte mit Fake-Clients testen. Es darf keine Schreibanforderung den Client erreichen.

Das ist eine Empfehlung für ein separates Arbeitspaket, **keine bereits implementierte Funktion**. Der Wechsel der geladenen Plattformen und bestehende Automationen benötigen eigene Upgrade-Tests.

## Aktuelle Schreibpfade

| Plattform | Ziel | Hub-Methode / Modbus-Funktion |
| --- | --- | --- |
| Number | Holding 2, 3 (HK2 optional), 44, 45 | `write_register`, FC `0x10` |
| Switch | Coils 4 und 6 | `write_coil`, FC `0x05` |
| Water Heater | Holding 8; Einschalten Coil 4, Ausschalten Coil 5 | beide Methoden |

Diese Adressen beschreiben den vorhandenen Code, keine bestätigte Steuerfreigabe für die PELEO 14. Die Schreiblogik bleibt unverändert.

Entitäten auszublenden, optionale Komponenten abzuwählen oder Automationen zu pausieren garantiert keine Schreibsperre. Das Deaktivieren aller bekannten Steuerentitäten ist eine zusätzliche Vorsichtsmaßnahme, schützt aber nicht vor übersehenen oder neu angelegten Entitäten und direkten Schreibaufrufen.

Bis zur Umsetzung sind sichere Tests mit Fake-Modbus-Clients oder in einer Netzumgebung ohne erreichbare Heizung möglich. Für einen echten Lesetest wäre alternativ ein unabhängig geprüfter Modbus-Proxy erforderlich, der ausschließlich FC `0x03` und `0x04` zulässt und alle anderen Funktionen verwirft. Home Assistant darf dann keinen direkten Netzwerkpfad zur Heizung besitzen. Eine gewöhnliche TCP-Firewall auf Port 502 unterscheidet Lese- und Schreibfunktionen nicht.

**Ohne zentrale Schreibsperre oder eine solche geprüfte Netzwerksicherung wird ein erster Live-Test noch nicht empfohlen.** In P2 wurden weder Home Assistant noch die Heizung kontaktiert.
