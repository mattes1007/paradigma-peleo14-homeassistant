# PELEO 14 mit SystaComfort: Sensorprofil

Dieser Fork verwendet ein festes PELEO-14-Sensorprofil; die Integration-Domain
bleibt `paradigma`. Die drei Kesselsensoren sind immer vorhanden. Die bestehende
Option `boiler_installed` steuert nur die optionalen Kesseltemperaturfühler.
Die frühere Option `wood_installed` wird nicht mehr angeboten und beim Lesen
ignoriert. Es werden keine Holzkessel- oder separaten Wodtke-Pelletsofen-Sensoren
angelegt und deren Register nicht abgefragt.

| Sensor-Schlüssel | Holding-Register / bisheriger PyModbus-Offset | Datentyp | Faktor | Unique-ID-Suffix |
| --- | --- | --- | --- | --- |
| `boiler_hours` | 27–28 | uint32 | 1 h | `holding_32_27` |
| `boiler_starts` | 29–30 | uint32 | 1 | `holding_32_29` |
| `status_boiler` | 41 | uint16 | bestehende Statustabelle | `holding_status_boiler_41` |

Die Adressen werden unverändert übergeben. Die Zähler werden jeweils in einer
Leseanforderung mit zwei Registern gelesen. Die bisherige Wortreihenfolge bleibt
**High Word zuerst**: `(erstes_register << 16) | zweites_register`.
Ihre Richtigkeit muss noch durch echte, bereits vorliegende Registerwerte oder
die passende Herstellerdokumentation bestätigt werden. `[0, 4294]` ergibt
4294 Stunden; `[4294, 0]` ergibt 281411584. Es gibt keine automatische Umkehrung
oder Plausibilitätskorrektur. Auch die Klartextzuordnung des Kesselstatus ist
weiterhin die bisherige, noch nicht gerätespezifisch bestätigte Tabelle.

## Ungültige Werte

Bei uint32 ist nur der vollständige Wert `0xFFFFFFFF` (4294967295) der bekannte
ungültige Zählerwert. Einzelne Wörter wie `0x7FFF`, `0x8000` oder `0xFFFF` sind
innerhalb eines gültigen uint32 zulässig. Unvollständige Registerpaare sowie
Wörter außerhalb von 0–65535 oder mit falschem Datentyp ergeben keinen Wert.
Bei 16-Bit-Sensoren bleibt die bisherige Sentinel-Liste `0x7FFF`, `0x8000`,
`0xFFFF` erhalten; zusätzlich werden falsche Datentypen und Werte außerhalb des
uint16-Bereichs verworfen. Diese 16-Bit-Sentinels müssen für weitere Register
noch anhand der Herstellerdokumentation geprüft werden. Null bleibt gültig.
Temperaturen werden weiterhin als vorzeichenbehaftete 16-Bit-Werte dekodiert.

## Bestehende Entity-Identitäten

Die Unique-IDs bleiben `<entry_id>_<suffix>` wie bisher. Domain, Sensor-Schlüssel
und Registertypen ändern sich nicht. Bestehende Entity-IDs und benutzerdefinierte
Namen werden nicht automatisch umbenannt. Die neuen Anzeigenamen gelten für
übersetzte Standardnamen. Bei neuen Installationen können daraus andere
Entity-IDs entstehen als im Ursprungsprojekt, abhängig von Sprache und
Gerätename. Bestehende Registry-Identitäten werden dadurch nicht ersetzt.

Die bisherigen `pellet_hours` und `pellet_starts` hatten exakt dieselben
Unique-IDs wie die Kesselzähler. Diese Doppeldefinitionen entfallen; es gibt
keine neuen Ersatz-IDs. Wurde früher nur die Holzoption verwendet, kann der
bestehende Registry-Eintrag deshalb weiterhin einen Pellet-Namen oder eine
Pellet-Entity-ID besitzen. Er wird unter derselben Identität als Kesselzähler
weiterverwendet. Eine optionale Umbenennung muss bewusst erfolgen und ihre
Referenzen in Automationen berücksichtigen. Es ist keine Unique-ID-Migration
nötig und der Integrationseintrag sollte nicht gelöscht und neu angelegt werden.

Frühere Entitäten für Register 42/43 und Holztemperaturen werden nicht mehr
bereitgestellt. Ihre Registry-Einträge können als nicht verfügbar zurückbleiben;
dieses Arbeitspaket löscht keine Registry-Einträge. Falls solche Entitäten
bereits verwendet wurden, müssen Referenzen später manuell geprüft werden.
Insbesondere wird ein ehemaliger Pelletsofenstatus nicht automatisch auf den
Kesselstatus von Register 41 umgeschrieben.

## Lokale Tests

`python3 -B -m unittest discover -s tests -v`

Die Tests laden den produktiven Sensorcode mit minimalen Home-Assistant-Stubs
und einem Fake-Hub. Sie installieren nichts, importieren weder den echten Hub
noch das Integrations-Setup und bauen keine Netzwerkverbindung auf. Sie prüfen
Zuordnung, Identitäten, Leseanforderungen, Wortreihenfolge und ungültige Werte;
sie ersetzen keinen vollständigen Home-Assistant-Laufzeittest.

Die Flow-Tests führen die produktiven Klassen mit ersetzten Framework-Imports
aus. Sie prüfen neue Formulare und das Speichern alter Optionen. Die
Identitätsprüfung kontrolliert Unique-IDs, Gerätekennung und den Verzicht auf
eine explizite Entity-ID-Zuweisung über Optionswechsel hinweg. Sie prüft nicht
die echte HA-Entity-Registry, das komplette Integrations-Setup oder dessen
Reload-Lebenszyklus. Die Sensorprüfung umfasst alle 64 booleschen Kombinationen
der sechs bisherigen Anlagenoptionen sowie einen Eintrag ohne diese Optionen.
