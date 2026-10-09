# HACS: Installation, Upgrade und Rollback

## Verpackung und Version

Die Integration verwendet **direkte Installation aus dem Repository**: `content_in_root: false`, `zip_release: false`, genau eine Integration unter `custom_components/paradigma/`. Alle Laufzeitdateien und lokale Markenbilder liegen in diesem Verzeichnis. Es gibt keinen Build-Schritt und keine generierten Laufzeitdateien; ein zusätzliches ZIP würde nur eine zweite, potenziell abweichende Verpackung schaffen. Der bisherige ZIP-Dateiname entfällt. `render_readme` entfällt ebenfalls aus der HACS-Konfiguration.

Die Manifest-Version lautet **2.0.0-beta.1**. Die neue Hauptversion kennzeichnet den spezialisierten PELEO-Fork; die Vorabversion macht den noch ausstehenden HAOS-Test sichtbar. Die Mindestversion in HACS ist Core **2026.10.0**, entsprechend der Zielumgebung und der bestehenden PyModbus-Abhängigkeit.

Ohne GitHub-Releases verwendet HACS den Standardbranch. Deshalb sind nur dort veröffentlichte Dateien installierbar; lokale Änderungen auf `fix/peleo14-sensoren` sind noch keine HACS-Veröffentlichung. Für spätere reproduzierbare Updates empfiehlt sich ein unveränderlicher Git-Tag samt GitHub-Vorabrelease, passend zur Manifest-Version. HACS kann weiterhin die Dateien des Tags direkt laden; ein eigener ZIP-Anhang ist unnötig. Für Beta-Releases muss gegebenenfalls die Anzeige von Vorabversionen in HACS aktiviert werden. Die Installation setzt eine gesondert freigegebene Veröffentlichung voraus. P3 erstellt weder Commit noch Tag noch Release.

Das Repository muss öffentlich sein. GitHub-Beschreibung, Topics, Standardbranch und aktivierte Actions müssen vor Veröffentlichung separat geprüft werden; diese Remote-Einstellungen werden hier nicht verändert.

## Neue Installation

Zuerst [Lesebetrieb absichern](lesebetrieb.md). Schon das Konfigurationsformular prüft die TCP-Verbindung.

1. In HACS das Menü **Benutzerdefinierte Repositories / Custom repositories** öffnen.
2. `https://github.com/mattes1007/paradigma-peleo14-homeassistant` hinzufügen, Kategorie **Integration**.
3. **Paradigma PELEO 14** öffnen, die gewünschte veröffentlichte Version auswählen und herunterladen. Ohne Release wird der Standardbranch verwendet.
4. Home Assistant neu starten.
5. Unter **Einstellungen → Geräte & Dienste** die Integration **Paradigma PELEO 14** hinzufügen. Host, Port, Slave-ID und Abfrageintervall einstellen; nur vorhandene Zusatzkomponenten wählen.

HACS installiert nach `/config/custom_components/paradigma/`. Eine manuelle Installation derselben Domain oder die Originalintegration kann dort nicht parallel betrieben werden. Andere aktive Modbus-Integrationen und alte YAML-Abfragen vorher erfassen und auf doppelte Abfragen/Steuerungen prüfen; nicht ungeprüft löschen.

## Wechsel von einer bestehenden Originalintegration

**Domain `paradigma` und vorhandenen HA-Konfigurationseintrag erhalten.** Original und Fork belegen dasselbe Verzeichnis. Nicht beide HACS-Repositories gleichzeitig als installierte Integration derselben Domain verwenden.

1. Ein vollständiges HA-Backup erstellen, herunterladen und Wiederherstellungszugang sichern. Prüfen, dass Konfiguration, `custom_components`, HACS-Daten und Entity-/Device-Registry enthalten sind; bei Bedarf auch Historie sichern. Zusätzlich Originalversion, Dateien, Optionen, Gerätenamen, Entity-IDs und verwendete Automationen dokumentieren.
2. Steuerautomationen und externe Serviceaufrufe stoppen. Beim Fork die Option „Heizungssteuerung über Home Assistant erlauben“ deaktiviert lassen; alte Einträge ohne diese Option starten automatisch lesend. Die zentrale Schreibsperre gilt erst, sobald der neue Code geladen ist. Die vorherige Originalintegration hat diese Sperre nicht. [Hinweise zum ersten Test](lesebetrieb.md).
3. Die Zuordnung zum Originalrepository in **HACS** entfernen beziehungsweise deinstallieren, wenn HACS einen Domainkonflikt meldet. Eine HACS-Deinstallation kann die Integrationsdateien entfernen. **Den bestehenden Integrationseintrag unter Geräte & Dienste nicht löschen.** Vor dem nächsten Neustart die Dateien des Forks installieren.
4. Den Fork als benutzerdefiniertes Repository hinzufügen und herunterladen. Sicherstellen, dass nur die gewünschten Fork-Dateien in `custom_components/paradigma/` liegen; keine Mischung alter und neuer Dateien.
5. Home Assistant neu starten. Den bestehenden Integrationseintrag verwenden, keine zweite Instanz anlegen. Optionen, Logs, verfügbare Sensoren und Entity-Referenzen kontrollieren.

Die erhaltene `entry_id` ist Bestandteil der Unique-IDs. Bei den drei Kesselsensoren bleiben die Suffixe `holding_32_27`, `holding_32_29` und `holding_status_boiler_41` unverändert. Dadurch können bestehende Registry-Einträge und Entity-IDs weiterverwendet werden. Löschen und Neuanlegen des HA-Eintrags erzeugt eine neue `entry_id` und gefährdet diese Zuordnung.

Früher doppelt definierte Pelletzähler können weiterhin einen Pellet-Namen oder eine entsprechende Entity-ID tragen. Sie werden unter derselben Identität als Kesselzähler verwendet. Eine Umbenennung ist optional und erfordert eine Prüfung aller Referenzen. Entfernte Holz-/Ofen-Sensoren können als nicht verfügbare Registry-Einträge verbleiben; sie werden nicht automatisch gelöscht oder auf Register 41 umgebogen. Details stehen in [P0-Registerdokumentation](peleo14-register.md).

Neue Installationen können wegen übersetzter Namen andere Entity-IDs erhalten. Die Kompatibilität gilt für die im Fork erhaltenen Identitäten; beliebige ältere Originalversionen oder schon manuell geänderte Registries sind damit nicht pauschal geprüft. Keine manuelle Bearbeitung von `.storage` vornehmen.

## Rollback

Bei Problemen die Heizung weiterhin gegen Schreibzugriffe absichern. Logs sichern und zunächst die vorherige Integrationsversion beziehungsweise die gesicherten Originaldateien vollständig nach `custom_components/paradigma/` zurückbringen, die HACS-Repository-Zuordnung passend korrigieren und Home Assistant neu starten. Den bestehenden HA-Eintrag erhalten. Ein Dateirücktausch stellt gelöschte Konfigurationseinträge oder Registry-Daten nicht wieder her.

Wurden Konfiguration, Registry oder andere Daten verändert, das vollständige Backup wiederherstellen. Abhängigkeiten über Home Assistant verwalten lassen; keine manuellen Paketinstallationen auf HAOS. Nach dem Rollback Sensoridentitäten, Automationen und ursprüngliche Optionen erneut prüfen. Auch die Originalintegration enthält Schreibfunktionen.

## Prüfungen und Grenzen

Lokale Tests prüfen JSON-Metadaten, Verzeichnisstruktur, Markenbilder, konsistente Übersetzungsschlüssel, Dokumentationsverweise sowie die P0-/P1-Regressionen. CI ergänzt HACS-Validierung, Hassfest und Offline-Tests unter Python 3.12/3.14. Die externen Actions werden erst nach Veröffentlichung ausgeführt. Ein lokaler Erfolg ersetzt weder diese Validatoren noch einen echten HACS-/HAOS-Installations- und Upgrade-Test.

Offizielle Grundlagen: [HACS Integration](https://www.hacs.xyz/docs/publish/integration/), [HACS-Konfiguration](https://www.hacs.xyz/docs/publish/start/), [lokale Markenbilder](https://developers.home-assistant.io/docs/core/integration/brand_images/), [HAOS-Backups](https://www.home-assistant.io/common-tasks/os/#backups).
