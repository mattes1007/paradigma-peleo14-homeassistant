# Update und Rollback

Config-Entry-Version **1 → 2** wird automatisch migriert. Vorhandene Daten und unbekannte Optionen bleiben erhalten. Die bisherige Sensorliste wird exakt aus den alten Baugruppenflags abgeleitet, einschließlich bisher unbedingt angelegter Kesselzähler/-status und Raumwerte. Neue Sollwertsensoren werden nicht automatisch hinzugefügt. Ein ungeprüftes Bestandsprofil verhindert neue Modellannahmen.

Das alte wörtliche `allow_control: true` wird auf die bisher tatsächlich freigegebenen HK1-/Warmwasserfunktionen sowie HK2 bei bestehendem HK2-Flag abgebildet. Keine Puffer-, Kessel- oder Coil-Schreibrechte werden hinzugefügt. Die vor der Migration tatsächlich angebotenen Freigaben werden separat in `legacy_control_functions` festgehalten (HK2 nur bei vorher vorhandenem HK2, Schreiben nur für Unit-ID 1). `legacy_control: true` allein ist keine Berechtigung. Die wirksamen Rechte sind die Schnittmenge der ursprünglichen Freigaben und der aktuellen Auswahl; Baugruppenänderungen erweitern die ursprüngliche Liste nicht. Sie können abgewählt, aber bei unverifiziertem Modell nicht erweitert werden. Falsch typisierte Freigaben erteilen keine Rechte.

Im geprüften Basiscommit und dessen Vorgängerversion wurden Optionsänderungen in `entry.data` angewendet und zusätzlich in `entry.options` gespiegelt; Setup und Plattformen lasen `entry.data`. Die Migration behält **beide Dictionaries**: wirksame Entry-Daten werden erweitert, `entry.options` wird unverändert erhalten und weder geleert noch als Vorrangkonfiguration eingemischt. So überschreiben abweichende/veraltete Spiegel weder Verbindung, Sensorwahl noch Schreibrechte. Auch unbekannte Optionsfelder bleiben erhalten. Der neue Options Flow speichert Änderungen in `entry.data` und gibt die unveränderten bisherigen Optionsdaten zurück, damit keine zusätzliche Optionsänderung einen zweiten Reload verursacht.

Bei bereits modularen Testeinträgen ohne `legacy_control_functions` lässt sich eine ursprüngliche Freigabe nicht sicher rekonstruieren. Im unverifizierten Profil bleiben diese Schreibzugriffe deshalb gesperrt; nach Bestätigung eines unterstützten Modells können Funktionen einzeln erneut freigegeben werden. Die echte Migration unveränderter v1-Einträge erfasst die ursprünglichen Rechte automatisch.

Domain, Entry-ID, Gerätekennung und sämtliche bisherigen Unique-ID-Formeln bleiben unverändert. Keine Entity-Registry-Migration, kein Umbenennen, kein Löschen von Recorderdaten. Der Modelltext des Geräts wird berichtigt; die Gerätekennung bleibt gleich.

## Vor produktiver Installation

1. Vollständiges Home-Assistant-Backup inklusive Konfiguration, `.storage` und Recorder erstellen und Wiederherstellbarkeit prüfen. Bisherige Integrationsdateien/Release-Version sichern.
2. Lokale Änderungen reviewen und echte HA-Config-/Options-Flow-, Migrations-, Reload- und Entity-Registry-Prüfung in einer getrennten HA-Testinstanz mit simuliertem Modbus durchführen. Hassfest und HACS-Validator ausführen. Die Offline-Stubs ersetzen diese Prüfung nicht.
3. Tatsächlichen Reglertyp/Firmware prüfen. Für die erste Anlagenprüfung ausdrücklich Lesemodus wählen; keine produktiven Schreibtests erforderlich.
4. Erst nach Freigabe Beta veröffentlichen; HACS auf genau dieses Release einstellen. Hier wurden keine Commits, Tags, Pushes oder Releases erstellt.
5. Nach Update prüfen: bisherige Entity-IDs und Historien, Verbindung, gewählte Sensoren, nur bewusst freigegebene Steuerfunktionen. Die drei neuen Sollwerte nach Modellprüfung in Optionen ergänzen.

## Rollback

Die alte Version kennt Entry-Version 2 nicht. **Nur alte Python-Dateien zurückkopieren reicht deshalb nicht.** Backup von vor dem Update wiederherstellen und passende bisherige Integrationsversion installieren; Home Assistant neu starten. Keine manuellen Registry-Resets und keine Neukonfiguration des Geräts. Eine komplette Wiederherstellung kann auch zwischenzeitliche Recorderdaten zurücksetzen; diese vorher sichern, falls benötigt. Ohne Vorabbackup ist ein zuverlässiger automatischer Downgrade nicht vorgesehen.

Die Integration verändert keine Reglerkonfiguration. Externe Vorgaben laufen gemäß Herstellerunterlage aus; der Rückfall wird vom Regler bestimmt.
