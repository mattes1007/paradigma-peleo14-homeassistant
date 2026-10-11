# Registerkatalog

Technische Quelle: `custom_components/paradigma/catalog.py`. Alle Adressen sind nullbasiert. Dieses Dokument enthält nur implementierte Sensoren und freigegebene Schreibfunktionen. Weitere Datenpunkte der Herstellerunterlage sind nicht automatisch implementiert.

Dokumentprofil: SystaComfort II / Compact C ab Firmware 2.16, [Paradigma TH-3000 V1.1, 03/2021](https://forum.iobroker.net/assets/uploads/files/1674034323539-th-3000_v1.1_0321_systacomfort_ii_compactc_modbus_informationen_b_fhw.pdf), Anhang A, Seiten 15–19. SystaSmartC II/TH-2833 ist kein gleichwertiges Profil; keine verifizierte Freigabe. Unverifizierte Bestandsprofile behalten ihre vorhandene Auswahl.

| Baugruppe | Entität / Schlüssel | Typ | Adresse | Datentyp | Faktor / Einheit | Lesen | Schreiben |
|---|---|---|---:|---|---|---|---|
| Allgemein / Außentemperatur | Außentemperatur (`outdoor_temp`) | input | 0 | int16 | 0.1 / °C | ja | nein |
| Heizkreis 1 | Vorlauf HK1 (`flow_hk1`) | input | 1 | int16 | 0.1 / °C | ja | nein |
| Heizkreis 1 | Rücklauf HK1 (`return_hk1`) | input | 2 | int16 | 0.1 / °C | ja | nein |
| Warmwasser | Warmwasser Temperatur (`dhw_temp`) | input | 3 | int16 | 0.1 / °C | ja | nein |
| Pufferspeicher | Puffer Oben (`buffer_top`) | input | 4 | int16 | 0.1 / °C | ja | nein |
| Pufferspeicher | Puffer Unten (`buffer_bottom`) | input | 5 | int16 | 0.1 / °C | ja | nein |
| Zirkulation | Rücklauf Zirkulation (`circ_return_temp`) | input | 6 | int16 | 0.1 / °C | ja | nein |
| Heizkreis 1 | Raumtemperatur HK1 (`room_temp_hk1`) | input | 9 | int16 | 0.1 / °C | ja | nein |
| Heizkreis 2 | Raumtemperatur HK2 (`room_temp_hk2`) | input | 10 | int16 | 0.1 / °C | ja | nein |
| Heizkreis 2 | Vorlauf HK2 (`flow_hk2`) | input | 7 | int16 | 0.1 / °C | ja | nein |
| Heizkreis 2 | Rücklauf HK2 (`return_hk2`) | input | 8 | int16 | 0.1 / °C | ja | nein |
| Kessel / Pelletheizung | Kessel Vorlauf (`boiler_flow`) | input | 12 | int16 | 0.1 / °C | ja | nein |
| Kessel / Pelletheizung | Kessel Rücklauf (`boiler_return`) | input | 13 | int16 | 0.1 / °C | ja | nein |
| Kessel / Pelletheizung | PELEO 14 Betriebsstunden (`boiler_hours`) | holding | 27 | uint32 | 1 / h | ja | nein |
| Kessel / Pelletheizung | PELEO 14 Kesselstarts (`boiler_starts`) | holding | 29 | uint32 | 1 / — | ja | nein |
| Solarthermie | Kollektortemperatur (`collector_temp`) | input | 11 | int16 | 0.1 / °C | ja | nein |
| Solarthermie | Solar Leistung (`solar_power`) | holding | 19 | uint16 | 0.1 / kW | ja | nein |
| Solarthermie | Solar Tagesertrag (`solar_day`) | holding | 20 | uint16 | 0.1 / kWh | ja | nein |
| Solarthermie | Solar Gesamtertrag (`solar_total`) | holding | 21 | uint32 | 0.1 / kWh | ja | nein |
| Schwimmbad | Pool Temperatur (`pool_temp`) | input | 19 | int16 | 0.1 / °C | ja | nein |
| Schwimmbad | Pool Vorlauf (`pool_flow`) | input | 20 | int16 | 0.1 / °C | ja | nein |
| Schwimmbad | Pool Rücklauf (`pool_return`) | input | 21 | int16 | 0.1 / °C | ja | nein |
| Warmwasser | Status Warmwasser (`status_ww`) | holding | 34 | uint16 | 1 / — | ja | nein |
| Zirkulation | Status Zirkulation (`status_circ`) | holding | 35 | uint16 | 1 / — | ja | nein |
| Heizkreis 1 | Status Heizkreis 1 (`status_hk1`) | holding | 36 | uint16 | 1 / — | ja | nein |
| Heizkreis 2 | Status Heizkreis 2 (`status_hk2`) | holding | 37 | uint16 | 1 / — | ja | nein |
| Solarthermie | Status Solar (`status_solar`) | holding | 39 | uint16 | 1 / — | ja | nein |
| Schwimmbad | Status Pool (`status_pool`) | holding | 40 | uint16 | 1 / — | ja | nein |
| Kessel / Pelletheizung | PELEO 14 Kesselstatus (`status_boiler`) | holding | 41 | uint16 | 1 / — | ja | nein |
| Heizkreis 1 | Externe Vorlauf-Sollwertvorgabe HK1 (`external_flow_hk1`) | holding | 2 | int16 | 0.1 / °C | ja | separate HK1-Freigabe; nie durch Sensorwahl |
| Pufferspeicher | Solltemperatur Puffer oben (`target_buffer_top`) | holding | 44 | int16 | 0.1 / °C | ja | nein |
| Kessel / Pelletheizung | Kesselsolltemperatur (`target_boiler`) | holding | 45 | int16 | 0.1 / °C | ja | nein |

## Rohregister und Voraussetzungen

| Funktion | Schreibregister | Raw-Grenzen / Schritt | Voraussetzung |
|---|---:|---|---|
| HK1 | Holding 2 | 200–800 / 10 | Holding 9: gültige maximale Vorlauftemperatur |
| HK2 | Holding 3 | 200–800 / 10 | Holding 10: gültige maximale Vorlauftemperatur |
| Warmwasser | Holding 8 | 300–700 / 1 | Coil 4 aktiv, Coil 5 inaktiv |

Holding 3/8 und Input 3 werden bei entsprechender Steuerfreigabe ebenfalls im gemeinsamen Leseplan berücksichtigt. Holding 9/10 und Coil 4/5 werden als Rohvoraussetzungen live vor dem Schreiben geprüft; sie sind keine automatisch angelegten Sensoren. Coil-Schreibfunktionen sind nicht freigegeben.

## Sollwerte und Gültigkeit

**Holding 2 ist die externe, zeitlich begrenzte Vorlauf-Sollwertvorgabe HK1.** Es ist kein nachgewiesener intern berechneter aktueller Regler-Sollwert. Holding 44/45 sind Solltemperatur Puffer oben/Kessel und ausschließlich lesbar. Alle drei: int16, Faktor 0,1 °C. Die historische uint16-YAML-Konfiguration beschreibt den Rohtransport; Temperaturen werden gemäß TH-3000 vorzeichenbehaftet interpretiert.

Fehlende Antworten sind unbekannt, kein Ersatzwert 0 °C. Für vorhandene 16-Bit-Messwerte werden 0x8000, 0x7FFF und 0xFFFF konservativ verworfen. Diese fortgeführte Invalid-Policy ist nicht auf beliebige Fehlerregister übertragbar (dort kann etwa 0xFFFF „keine Störung“ bedeuten). uint32 ist High-Word zuerst; nur das gesamte 0xFFFFFFFF wird verworfen, einzelne Sentinel-Wörter können gültige Zählerbestandteile sein. Der Typ begrenzt den Rohwert; keine erfundenen physikalischen Herstellergrenzen für Lesesensoren.

Raumtemperaturen benötigen aktivierte Raumfühler und den zugehörigen Heizkreis. Zusatzregler/Fühler müssen tatsächlich vorhanden sein; es gibt keine automatische Hardwareerkennung. Unbekannte Statuscodes bleiben numerisch erkennbar. Bestätigte TH-3000-Profile nutzen korrigierte HK-/Kessel-/Pool-Statuszuordnungen; unverifizierte Bestandsprofile behalten die alte Zuordnung. IDs bleiben dabei gleich.

Noch nicht implementiert: HK3, Holzkessel, Wodtke-Pelletsofen, Kaskade, weitere Solar-/Frischwasserstation-Daten, dauerhafte Steuerung und Coil-Paarbefehle. Dokumentierte Existenz allein bedeutet keine Integrationsunterstützung.
