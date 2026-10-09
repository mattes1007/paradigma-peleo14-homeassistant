# Paradigma Heating Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/github/v/release/nussfuellung/paradigma-homeassistant?include_prereleases)](https://github.com/nussfuellung/paradigma-homeassistant/releases)
[![Downloads](https://img.shields.io/github/downloads/nussfuellung/paradigma-homeassistant/total.svg?style=flat)](https://github.com/nussfuellung/paradigma-homeassistant/releases)
[![Stars](https://img.shields.io/github/stars/nussfuellung/paradigma-homeassistant.svg?style=flat)](https://github.com/nussfuellung/paradigma-homeassistant/stargazers)
[![Issues](https://img.shields.io/github/issues/nussfuellung/paradigma-homeassistant.svg?style=flat)](https://github.com/nussfuellung/paradigma-homeassistant/issues)
[![Last Commit](https://img.shields.io/github/last-commit/nussfuellung/paradigma-homeassistant.svg?style=flat)](https://github.com/nussfuellung/paradigma-homeassistant/commits/main)

![Paradigma Integration Logo](logo.png)

> [!TIP]
> **For this fork, add its GitHub repository as a custom integration repository in HACS. The upstream default-store entry refers to the original project.**

This fork targets the **Paradigma PELEO 14 with SystaComfort** and communicates locally via **Modbus TCP**. The fixed boiler sensor profile and identity compatibility are documented in [PELEO 14 registers](docs/peleo14-register.md). Polling, recovery and platform limitations are documented in [P1 communication](docs/p1-kommunikation.md).


> [!IMPORTANT]
> **If you previously added your heating system manually via YAML, make sure to remove all old Modbus files/entries from your `configuration.yaml`. Otherwise, the system may block the Modbus communication.**

[🇩🇪 Zur deutschen Beschreibung springen](#german)

---

## 🇬🇧 English Description

### Compatible Devices
This integration is designed for Paradigma controllers that support the "Modbus-Schnittstelle für das Smarthome-System" protocol (Protocol Version 1.1).

* **PELEO 14 with SystaComfort**
* Optional solar, second heating circuit, pool and room sensors retain their previous register mappings; these have not been independently verified for this system.

### Features

The integration connects to the heating controller (Unit ID 1) and provides a fully modular setup. You can enable or disable specific components during configuration.

#### 🌡️ Sensors (Read-Only)
* **Standard:** Outdoor Temp, Flow/Return (HK1), DHW Temp, Buffer (Top/Bottom), Circulation Return.
* **Status:** Clear-text status messages (fully translated) for Heating Circuits, DHW, Circulation, and Boiler.
* **Optional Components (Selectable):**
    * **Solar:** Collector Temp, Current Power, Daily Yield, Total Yield.
    * **Heating Circuit 2 (HK2):** Flow/Return, Room Temp, Status.
    * **PELEO 14:** Operating hours, starts and boiler status are always enabled. Boiler flow/return temperature sensors are optional.
    * **Pool:** Temp, Flow/Return, Status.
    * **Room Sensors:** Room temperatures for HK1 and HK2.

#### 🎛️ Controls (Read/Write)
* **Heating Circuits:** Set target **Flow Temperature** (Vorlauf) via Number entities for HK1 and HK2.
* **Domestic Hot Water:** Set target water temperature and toggle On/Off via a **Water Heater** entity.
* **Buffer/Boiler:** Set target temperatures for Buffer Top and Boiler.

#### 🔘 Switches
* **DHW Enable:** Enable/Disable hot water preparation globally.
* **Circulation Enable:** Enable/Disable circulation pump globally.

### Installation via HACS

1.  Open **HACS** in Home Assistant.
2.  Go to **Integrations** and click on **Explore & Download Repositories** (or use the search bar).
3.  Add this fork as a **custom repository**, category **Integration**, and select it.
4.  Click **Download** / **Install**.
5.  Restart Home Assistant.

### Configuration

1.  Go to **Settings** > **Devices & Services**.
2.  Click **Add Integration** and search for **Paradigma**.
3.  Enter the connection details:
    * **Host:** IP address of your SystaSmartC/Comfort.
    * **Port:** Default is `502`.
    * **Unit ID:** Default is `1`.
4.  **Select your installed components:**
    * Check the boxes for **Solar**, **Heating Circuit 2**, **Pool**, **Room Sensors**, **Boiler temperature sensors** to enable the respective sensors.

> **Note:** You can change these settings at any time by clicking **"Configure"** on the integration entry.

---

<a name="german"></a>
## 🇩🇪 Deutsche Beschreibung

### Kompatible Geräte

Dieser Fork verwendet ein festes **PELEO-14-Profil mit SystaComfort**.
Register, Wortreihenfolge und Hinweise zu bestehenden Entity-IDs stehen in der
[PELEO-14-Registerdokumentation](docs/peleo14-register.md).
Abfrageintervall, Wiederverbindung und Plattformgrenzen stehen in der
[P1-Kommunikationsdokumentation](docs/p1-kommunikation.md).

Diese Integration unterstützt Paradigma Regelungen, die das Protokoll "Modbus-Schnittstelle für das Smarthome-System" (Protokoll V1.1) unterstützen.

* **PELEO 14 mit SystaComfort**
* Optionale Solar-, Heizkreis-2-, Pool- und Raumfühlersensoren behalten ihre bisherigen Registerzuordnungen; diese sind für diese Anlage noch nicht unabhängig bestätigt.

### Funktionen

Die Integration verbindet sich mit dem Heizungsregler (Unit ID 1) und bietet einen modularen Aufbau. Komponenten können bei der Einrichtung an- oder abgewählt werden.

#### 🌡️ Sensoren (Nur Lesen)
* **Standard:** Außentemperatur, Vorlauf/Rücklauf (HK1), Warmwasser, Puffer (Oben/Unten), Zirkulation Rücklauf.
* **Status:** Klartext-Statusmeldungen (mehrsprachig) für Heizkreise, Warmwasser, Zirkulation und Kessel (z. B. "Heizbetrieb", "Vorhaltezeit", "Ladung läuft").
* **Optionale Komponenten (Wählbar):**
    * **Solar:** Kollektor-Temp, Leistung, Tagesertrag, Gesamtertrag.
    * **Heizkreis 2 (HK2):** Vorlauf/Rücklauf, Raumtemperatur, Status.
    * **PELEO 14:** Betriebsstunden, Kesselstarts und Kesselstatus sind immer aktiv. Kessel-Vorlauf/Rücklauf sind optional.
    * **Pool:** Temp, Vorlauf/Rücklauf, Status.
    * **Raumfühler:** Raumtemperaturen für HK1 und HK2 (falls Fernbedienung vorhanden).

#### 🎛️ Steuerung (Lesen/Schreiben)
* **Heizkreise:** Einstellen der **Soll-Vorlauftemperatur** über Zahlen-Entitäten (Number) für HK1 und HK2.
* **Warmwasser:** Einstellen der Warmwasser-Solltemperatur und An/Aus über eine **Wassererwärmer** (Water Heater) Entität.
* **Puffer/Kessel:** Einstellen der Solltemperaturen für Puffer Oben und den Kessel.

#### 🔘 Schalter
* **Warmwasser Freigabe:** Ein-/Ausschalten der Warmwasserbereitung (DHW Enable).
* **Zirkulation Freigabe:** Ein-/Ausschalten der Zirkulationspumpe (Circ Enable).

### Installation über HACS

1.  Öffnen Sie **HACS** in Home Assistant.
2.  Gehen Sie zu **Integrationen** und klicken Sie auf **Durchsuchen & Herunterladen** (oder nutzen Sie die Suchfunktion).
3.  Fügen Sie diesen Fork als **benutzerdefiniertes Repository**, Kategorie **Integration**, hinzu und wählen Sie ihn aus.
4.  Klicken Sie auf **Herunterladen**.
5.  Starten Sie Home Assistant neu.

### Konfiguration

1.  Gehen Sie zu **Einstellungen** > **Geräte & Dienste**.
2.  Klicken Sie auf **Integration hinzufügen** und suchen Sie nach **Paradigma**.
3.  Geben Sie die Verbindungsdaten ein:
    * **IP-Adresse:** Die IP Ihrer SystaSmartC/Comfort im Netzwerk.
    * **Port:** Standard ist `502`.
    * **Unit ID:** Standard ist `1`.
4.  **Wählen Sie Ihre installierten Komponenten:**
    * Setzen Sie Haken bei **Solar**, **Heizkreis 2**, **Pool**, **Raumfühler**, **Kesseltemperaturfühler**, um die entsprechenden Sensoren zu aktivieren.

> **Hinweis:** Sie können diese Einstellungen jederzeit nachträglich ändern, indem Sie bei der Integration auf **"Konfigurieren"** klicken.

---

### Disclaimer / Haftungsausschluss

This is a private open-source project and **not** an official product of Ritter Energie- und Umwelttechnik GmbH & Co. KG or Paradigma. Use at your own risk.

Dies ist ein privates Open-Source-Projekt und **kein** offizielles Produkt der Ritter Energie- und Umwelttechnik GmbH & Co. KG oder Paradigma. Benutzung auf eigene Gefahr.
