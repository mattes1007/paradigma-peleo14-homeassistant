# Echte HA-Python-Integrationsprüfung

Diese sieben Tests verwenden echte HA-Klassen, Config-/Options-Flow-Manager,
Config Entries, Entity-/Device-Registry, Plattformen und Coordinator. Nur der
Modbus-Transport ist simuliert. Die üblichen offiziellen HA-Testfixtures
simulieren auch Storage und HA-Umgebungsdienste; es handelt sich nicht um einen
HAOS-/Browser-/Hardware-Test. Keine alten AST-/HA-Stubs werden importiert.

Python 3.14 wird benötigt. Eine isolierte Umgebung erstellen und
`requirements.txt` aus diesem Verzeichnis installieren. Beispielsweise mit uv:

```sh
uv venv --python /path/to/python3.14 /tmp/paradigma-ha-qa-env
uv pip install --python /tmp/paradigma-ha-qa-env/bin/python -r tests/ha_runtime/requirements.txt
PYTHONDONTWRITEBYTECODE=1 /tmp/paradigma-ha-qa-env/bin/python -m pytest tests/ha_runtime \
  -o asyncio_mode=auto --disable-socket --allow-unix-socket --timeout=30 \
  -q -p no:cacheprovider
```

Im Repository-Wurzelverzeichnis ausführen. Die globale pytest-Pluginerkennung
lädt `pytest_homeassistant_custom_component.plugins` automatisch. Netzwerk-Sockets
sind gesperrt; lokale Unix-Sockets sind für asyncio/Fixtures nötig. Eine Sandbox,
die auch Unix-Socket-Kommunikation verbietet, verhindert diesen Lauf.

Für HA 2026.10.1 in einer zweiten Umgebung stattdessen
`pytest-homeassistant-custom-component==0.13.372` installieren. Beide Kombinationen
wurden geprüft. PyModbus bleibt auf 3.13.1 festgelegt. Die Integration selbst
bekommt keine neue Laufzeitabhängigkeit.

Für lokale HACS-Schemavalidierung mit einem separat heruntergeladenen offiziellen
`hacs/integration`-Checkout:

```sh
/tmp/paradigma-ha-qa-env/bin/python tests/ha_runtime/check_hacs_metadata.py /path/to/hacs-integration
```

Das führt die unveränderten offiziellen JSON-Schemas aus und ersetzt ausdrücklich
nicht die vollständige GitHub-HACS-Action.

Ergebnis und Einschränkungen: [QA-Bericht](../../docs/QA-BERICHT.md).
