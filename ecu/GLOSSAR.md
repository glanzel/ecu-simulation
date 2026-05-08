# Kurzglossar Benennung (Domäne)

| Code / Variable | Bedeutung |
|-----------------|-----------|
| `vej_ziel` | Langfristiges planetares Ziel je Grenze (Jahres-Obergrenze, physische Verschmutzungseinheiten/a). |
| `vej_soll` | Kurzfristiges Soll (Jahr); im aktuellen Modell **identisch** zu `vej_ziel` — kein separates Datenfeld. |
| `vet_soll` | Kurzfristiges Soll pro Monat = `vej_ziel / 12` (Monats-Obergrenze je Grenze). |
| `vej_ist` | Beobachteter bzw. modellierter Verbrauch pro Monat (gleiche Einheit wie `vet_soll`). |
| `fraction_of_vej_ziel` | Anteil des VEJ-Ziels (Referenznachfrage / Startanker), dimensionslos 0…1. |

**UI / Tabellen:** Ausgeschriebene oder kurze Lesbare Labels ohne Unterstriche, z. B. „VEJ-Ist“, „VET-Soll“, „VEJ-Ziel“.
