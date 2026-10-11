# Abschließende Integrations-QA – Paradigma Ultimate

Stand: 11.10.2026, lokaler Branch `feature/modular-ultimate`, Basis `9dde44a`.
Geprüft wurde der aktuelle uncommittete modulare Arbeitsstand einschließlich der
vorherigen Sicherheitskorrekturen. Keine neue Funktion, kein grundlegendes
Refactoring und keine Änderung am Integrationscode in diesem QA-Arbeitsgang.
Manifest unverändert `2.0.0-beta.1`; Freigabekandidat `2.0.0-beta.2`.

## Ergebnis

| Prüfung | Umgebung | Ergebnis |
|---|---|---|
| Echte HA-Python-Integrationsprüfung | Python 3.14.8, HA 2026.10.0, Testplugin 0.13.371, PyModbus 3.13.1 | 7 bestanden |
| Dieselben HA-Tests auf aktuellem Patchstand | Python 3.14.8, HA 2026.10.1, Testplugin 0.13.372, PyModbus 3.13.1 | 7 bestanden |
| Bestehende Offline-/Stub-Regressionen | System-Python 3.12.3 | 113 bestanden |
| Offizielles Hassfest | Unveränderter HA-Quellstand 2026.10.1; alle standardmäßigen Integrationsvalidatoren | 1 Integration, 0 ungültig, Exit 0 |
| Offizielle HACS-JSON-Schemas | Unveränderte Schemas aus `hacs/integration/main` | `hacs.json` und Manifest bestanden |
| Vollständige HACS-GitHub-Action | Nicht ausgeführt | Docker/Podman und Action-Token fehlen; lokale uncommittete Änderungen sind kein prüfbarer GitHub-Ref |
| Whitespaceprüfung | `git diff --check` | bestanden |

Es sind **sieben unterschiedliche echte HA-Testfälle**, jeweils auf zwei
HA-Versionen; nicht vierzehn verschiedene Szenarien. Die 113 älteren Tests bleiben
als Mock-/Stub-Prüfungen ausdrücklich separat ausgewiesen.

## Abgedeckte Integrationsprüfungen

1. **Erstinstallation:** Echter Config-Flow-Manager durchläuft Verbindung,
   unterstützte Modellwahl, alle angebotenen Baugruppen, gruppierte Sensorwahl,
   Steuerbereich und Zusammenfassung. SystaSmartC II wird abgewiesen, bevor ein
   Client angelegt wird. Neue Einträge beginnen ohne Schreibfunktionen. Der
   Verbindungstest-Client wird geschlossen, bevor der einzige Laufzeit-Client
   aktiv ist.
2. **Options Flow und Reload:** Sensoren werden über den echten Optionsmanager
   hinzugefügt und entfernt. Auswahl wird übernommen. Zwei Änderungen erzeugen
   genau zwei Reloads; jeweils bleibt nur ein verbundener Modbus-Client aktiv.
   Unique-IDs sind eindeutig, Gerätekennung und bestehende Entity-ID bleiben
   stabil. Entladen schließt alle Clients. Die HA-Fixtures melden keine
   zurückgelassenen Tasks/Timer.
3. **Migration v1 → v2:** Der echte Setup-Pfad ruft die Migration auf. Ein
   vorbestehendes Gerät und vorbestehende Sensor-, Number- und Water-Heater-
   Registryeinträge werden weiterverwendet. Wirksame alte Daten und abweichende
   Optionsdaten einschließlich unbekannter Felder bleiben erhalten. Das Modell
   bleibt `legacy_unverified`; neue Sollwertsensoren werden nicht automatisch
   aktiviert. Ursprünglich freigegebene HK1-/Warmwasserfunktionen bleiben erhalten,
   vorher nicht aktiviertes HK2 bleibt gesperrt – auch bei nachträglich erweiterter
   Auswahl.
4. **Holding 2/44/45:** Alle drei werden nach ausdrücklicher unterstützter
   Modellwahl angelegt und vom vorhandenen Coordinator aktualisiert. Geprüfte
   Umrechnung: 543 → 54,3 °C, 600 → 60,0 °C, 720 → 72,0 °C. Je Register werden
   `0x8000`, `0x7FFF` und `0xFFFF` nicht verfügbar. Ein tatsächlich gelesener Wert
   0 bleibt gültige 0,0 °C. Ein fehlendes optionales Register macht die übrigen
   Sensoren nicht unbrauchbar.
5. **Schreibsicherheit:** Direkte Hub-Aufrufe im Lesemodus sind gesperrt. Der
   echte Options Flow verlangt die ausdrückliche Sicherheitsbestätigung. Nach
   alleiniger HK1-Freigabe existiert nur die passende Number-Steuerentität;
   HK2, Warmwasser, 44/45 und Coils bleiben schreibgesperrt. Ein zulässiger
   Testbefehl erreicht ausschließlich den simulierten Client; ein Wert außerhalb
   der Grenzen wird abgewiesen. Kein Setup, Refresh, Reload oder Unload schreibt.
6. **HA-Plattformen und Übersetzungen:** Echte Sensor-/Number-/Switch-/Water-Heater-
   Plattformen werden über HA registriert. Gesperrte Schalter werden nicht als
   Entitäten angelegt. Deutsche und englische Konfigurations-, Options-, Selector-
   und Entity-Übersetzungen werden durch den echten HA-Übersetzungsloader geladen.
   Formularfelder, Zusammenfassung und die drei Sollwertlabels sind vorhanden.
7. **Optionsbearbeitung nach Migration:** Alte Optionsdaten bleiben auch beim
   Speichern unverändert. Wirksames Intervall und individuelle Steuerwahl ändern
   sich in Entry-Daten. Genau ein Reload, ein aktiver Client, unveränderte
   Geräte-/Sensoridentität und keine Modbus-Schreibbefehle.

Zusätzliche Einzelrechte-, Modellwechsel-, fehlerhafte Callback-,
Grenzwert- und Freigabeentzugsprüfungen bleiben in den 113 Offline-Regressionen.

## Offizielle Validatoren und Umfang

Hassfest wurde direkt aus dem offiziellen [HA-Tag 2026.10.1](https://github.com/home-assistant/core/tree/2026.10.1/script/hassfest)
mit folgendem Aufruf im HA-Quellverzeichnis ausgeführt:

```sh
python -m script.hassfest --action validate --integration-path /absolute/path/custom_components/paradigma
```

Der offizielle [Hassfest-Action-Einstieg](https://github.com/home-assistant/actions/blob/master/hassfest/action.yml)
startet normalerweise einen Docker-Container. Hier wurde stattdessen dessen
unveränderter Python-Validator mit ruff 0.16.9 und der benötigten Infrared-Bibliothek
10.1.0 in der isolierten Umgebung verwendet. Ergebnis: alle Standardvalidatoren
inklusive Manifest, Anforderungen, Übersetzungen, Abhängigkeiten und Config Flow
liefen durch. Der zusätzliche, nicht standardmäßige `--requirements`-Modus wurde
nicht ausgeführt; alle Abhängigkeiten sämtlicher HA-Integrationen wurden nicht
installiert. Die echte Paradigma-Laufzeit wurde mit PyModbus 3.13.1 geprüft.

Die lokale HACS-Prüfung verwendet exakt
[`HACS_MANIFEST_JSON_SCHEMA` und `INTEGRATION_MANIFEST_JSON_SCHEMA`](https://github.com/hacs/integration/blob/main/custom_components/hacs/utils/validate.py).
Nur der HACS-Package-Initializer wird beim Laden umgangen, damit keine HACS-
Integration gestartet wird; die Schemas werden nicht kopiert oder nachgebaut.
Dies ist **keine vollständige HACS-Repository-/GitHub-Action-Validierung**. Die
[offizielle Action](https://github.com/hacs/integration/blob/main/action/action.py)
benötigt GitHub-Zugriff, Token und einen veröffentlichten Ref. Beschreibung,
Topics, Archivstatus, GitHub-Lizenz-/Brand-Prüfung, Releaseauflösung und tatsächlicher
HACS-Download wurden damit nicht geprüft. Die vorhandenen CI-Workflows wurden
nicht ausgelöst.

Quellarchive zur Zuordnung dieser QA-Ausführung (SHA-256):

- HA 2026.10.1: `de1de677c0e39926d7dde504d4d2a68760b589c66880376b275f4550faed4a4b`
- HACS `main`, heruntergeladen am 11.10.2026: `696241dc38e07a095e6239d52f49f1c89c65bad2ee17f84205d5696a87736fb4`

## Fehlgeschlagene Vorläufe und tatsächliche Korrekturen

Anfangs fehlten Python 3.14, pip/venv und HA-Testbibliotheken. Sie wurden in
isolierten `/tmp`-Umgebungen bereitgestellt, ohne Integrationsabhängigkeiten zu
ändern. Die Sandbox blockierte Unix-Socket-Kommunikation des asyncio-Eventloops
und der Hassfest-Prozessverwaltung. Die Läufe wurden außerhalb dieser Sandbox
wiederholt; pytest blockierte weiterhin Netzwerk-Sockets und erlaubte nur die
notwendigen lokalen Unix-Sockets.

Die ersten HA-Läufe deckten Fehler **im neu angelegten Testaufbau** auf:
DeviceRegistry wurde zunächst mit alten Mapping-Annahmen bedient, ein nicht
vorhandenes privates Config-Entry-Feld wurde gepatcht, der Optionsdialog erhielt
irrtümlich das dort nicht zulässige Feld `name`, und eine Prüfung unterstellte
verzögerte statt sofort wirksamer Freigabeentziehung durch den HA-Update-Listener.
Diese Testannahmen wurden an die echten HA-APIs angepasst. Die abschließenden
Läufe bestanden vollständig. Es wurde in diesem QA-Arbeitsgang **kein zusätzlicher
Produktfehler bestätigt und keine Integrationsdatei korrigiert**.

Ein von uv angelegter Benutzer-Symlink zur temporären Python-Version wurde wieder
entfernt. System-Python und Shell-Konfiguration bleiben unverändert.

## Grenzen und Freigabeempfehlung

Nicht geprüft: Browserdarstellung der Formulare, HACS-/HAOS-Installation,
physische Regler/Firmware, reale Modbus-Telegramme oder Heizwirkung, reale
Recorder-Historien und die Wiederherstellung eines vollständigen HA-Backups.
Die Tests verwenden echte HA-Registries mit den offiziellen In-Memory-Storage-
Fixtures; sie sind kein Langzeit-/Hardwaretest. Die offenen Grenzen der
Modellunterstützung und zeitlich begrenzten Steuerung bleiben unverändert.
Außerdem ist im Manifest weiterhin die PyModbus-Untergrenze statt einer exakten
Version angegeben; spätere Bibliotheksversionen sind durch diesen Test nicht
freigegeben.

**Empfehlung: `2.0.0-beta.2` als kontrollierte Test-Beta freigeben**, sobald Review
und die vollständigen GitHub-HACS-/Hassfest-CI-Läufe auf dem später ausdrücklich
freigegebenen Veröffentlichungsstand grün sind. Vor dem Release Manifestversion
auf beta.2 setzen; dieser QA-Auftrag ändert sie nicht. Kein pauschales produktives
Update daraus ableiten. Vor einem später genehmigten Anlagenupdate vollständiges
Backup samt Rollback-Prüfung erstellen und zunächst im Lesemodus die bisherigen
Entity-IDs, Historien und ausgewählten Werte kontrollieren.

Keine Kontakte zu `192.168.1.42` oder `192.168.1.70`, keine produktiven
Modbus-Zugriffe, HAOS-/Dashboard-Änderungen, Commits, Pushes, Tags oder Releases.

Reproduzierbare Tests: [tests/ha_runtime](../tests/ha_runtime/README.md).
