"""
Planetare Konstanten AG, VK, RZ pro Kontrollvariable.

VEJ = (AG − VK) / RZ  (siehe ecu.txt)

**Zu RZ:** In ecu.txt ist RZ als „Regenerationszeit“ gemeint. **CO₂:** Es gibt in der
Literatur **keinen** einzigen „richtigen“ Wert — ein CO₂-Puls wird über **Jahrzehnte bis
Jahrtausende** aus der Atmosphäre entfernt (IPCC Kohlenstoffzyklus-Kapitel; Archer 2009:
fossiles CO₂, Ozean- und Langzeitspeicher). Hier wird **RZ = CO2_REGENERATION_YEARS**
(Jahre) als **Größenordnung** einer wirksamen Anpassungs-/Abklingzeit gesetzt (Standard
**100 a**, vergleichbar dem üblichen GWP-Referenzhorizont; Alternativen in Studien oft
**50–300 a**). Daraus folgt **VEJ in Gt CO₂ a⁻¹** = (AG−VK)/RZ. **HANPP / N:** RZ=1
bleibt eine neutrale Skalierung (Anteil bzw. bereits jährlicher Fluss in AG/VK).

**Eingearbeitete Literatur (wo direkt aus PB-Update 2015):**

- **Klima / CO₂:** Literatur **350 ppm / ≈280 ppm** (Steffen et al. 2015, SRC „Ref Figure 3“).
  **AG und VK in diesem Modul in Gt CO₂** (atmosphärische CO₂-Masse proportional zur
  Konzentration, Faktor `GT_CO2_PER_ATMOSPHERIC_PPM`). **RZ** siehe
  `CO2_REGENERATION_YEARS`.
- **Stickstoff:** dieselbe Quelle — biogeochemische Flüsse N, Grenzwert **69 Tg N a⁻¹**
  (industrielle N₂-Fixierung u. a. je nach Definition; Zahlenfolge Boundary /
  Unsicherheitszone / Ist in der SRC-Tabelle). Vorindustriell wird der **zusätzliche**
  anthropogene Fixierungsstrom oft gegen **0** gesetzt (Rockström et al. 2009).
- **HANPP:** In Steffen et al. (2015) ist die Land-System-Grenze u. a. über
  **Waldbestand** (%) formuliert, nicht über HANPP. Hier: **Proxy** aus Literatur zur
  menschlichen Inanspruchnahme der NPP (Haberl et al., u. a. PNAS 2007, globale
  Größenordnung ~24 % der NPP; Holozän-Baseline und „sicherer“ Deckel grob
  abgeschätzt) — siehe `literature_note` bei `HANPP`.

Hinweis Realität: In der Praxis sind mehrere planetare Grenzen bereits überschritten
(Ist-Werte oberhalb des sicheren Grenzbereichs). Dieses Projekt modelliert das nicht:
Es werden nur AG/VK/RZ zur Ableitung von VEJ als Rechen-Obergrenze genutzt — ohne
Abbildung aktueller globaler Ist-Verläufe oder Transgressions-Status.
"""

from __future__ import annotations

from dataclasses import dataclass

# Umrechnung Atmosphäre: Zuwachs der CO₂-Masse in der Luft pro 1 ppm Erhöhung.
# Übliche Größenordnung (IPCC / Erdsystem-Literatur): ~2,12 Pg C pro ppm
# → 2,12 × (44/12) ≈ 7,8 Gt CO₂ pro ppm (nicht Jahres-Emission, sondern Masse in der Luft).
# Quelle z. B. IPCC AR5 WGI (Kohlenstoffzyklus); exakter Wert leicht modellabhängig.
GT_CO2_PER_ATMOSPHERIC_PPM: float = 2.12 * (44.0 / 12.0)

# Charakteristische Zeitskala für ecu.txt: VEJ_CO2 = (AG−VK)/RZ [Gt CO₂ a⁻¹], AG/VK in Gt.
# Literatur: kein Einzelwert (IPCC: mehrere Entfernungsprozesse; Archer 2009 u. a.: Jahrhundert-
# bis Jahrtausend-Skalen). 100 a = übliche Größenordnungswahl / GWP-Referenz; bei Bedarf z. B. 200–300.
CO2_REGENERATION_YEARS: float = 100.0


@dataclass(frozen=True)
class BoundaryConstants:
    """Eine planetare Grenze mit Kontrollvariablen AG, VK, RZ."""

    key: str
    label_de: str
    unit_note: str
    # Absolute Grenzmenge (Kontrollvariable, Grenzzustand)
    AG: float
    # Vorindustrieller Referenzwert VK
    VK: float
    # Divisor im ecu.txt-Sinne (hier oft 1: keine extra Skalierung, s. Modul-Doku)
    RZ: float
    literature_note: str
    is_example: bool


# --- Werte: Klima + N aus Steffen et al. 2015 (SRC „Ref Figure 3“); HANPP als Proxy ---

CO2 = BoundaryConstants(
    key="co2",
    label_de="Klima (atmosphärisches CO₂)",
    unit_note=(
        "AG/VK: Gt CO₂ (Masse in der Luft, linear mit ppm; Literatur 350/280 ppm). "
        "VEJ: Gt CO₂ a⁻¹ via (AG−VK)/RZ, RZ = CO2_REGENERATION_YEARS (Jahre)."
    ),
    # Literatur ppm → Masse: AG = 350 ppm × (Gt CO₂ pro ppm), VK = 280 ppm × …
    AG=350.0 * GT_CO2_PER_ATMOSPHERIC_PPM,
    VK=280.0 * GT_CO2_PER_ATMOSPHERIC_PPM,
    RZ=CO2_REGENERATION_YEARS,
    literature_note=(
        "Grenzen ppm: Steffen et al. (2015), SRC „Ref Figure 3.txt“ (Climate.change). "
        "Masse: ppm × GT_CO2_PER_ATMOSPHERIC_PPM (IPCC-Größenordnung ~2,12 Pg C pro ppm). "
        "RZ=CO2_REGENERATION_YEARS: IPCC betont **keine** einzelne CO₂-Lebensdauer; Entfernung "
        "über sehr unterschiedliche Zeiten (u. a. Archer, D., 2009, Annu. Rev. Earth Planet. Sci., "
        "fossiles CO₂ über Jahrhunderte bis sehr lang). Hier 100 a als dokumentierte "
        "Größenordnung (u. a. Referenz für GWP100); Werte 50–300 a in anderen Vereinfachungen üblich."
    ),
    is_example=False,
)

HANPP = BoundaryConstants(
    key="hanpp",
    label_de="HANPP (Proxy)",
    unit_note="Anteil der terrestrischen NPP (0–1)",
    AG=0.15,
    VK=0.08,
    RZ=1.0,
    literature_note=(
        "Kein direkter Eintrag in Steffen et al. 2015 „Fig. 3“-Tabelle (dort u. a. "
        "Land-System über Waldbestand %). Proxy: Deckel 0,15 und Baseline ~0,08 "
        "orientiert an Diskussion menschlicher NPP-Inanspruchnahme (z. B. Haberl et al. 2007 "
        "~24 % global; Rockström et al. 2009 Landnutzungs-Obergrenzen anders definiert). "
        "Bei Bedarf durch forest-cover-Metrik aus PB ersetzen."
    ),
    is_example=True,
)

NITROGEN = BoundaryConstants(
    key="nitrogen",
    label_de="Stickstoff (anthropogene N₂-Fixierung)",
    unit_note="Tg N pro Jahr (Kontrollvariable N-Fluss, PB-Update 2015)",
    AG=69.0,
    VK=0.0,
    RZ=5.0,
    literature_note=(
        "Grenze 69 Tg N a⁻¹: Steffen et al. (2015); SRC „Ref Figure 3.txt“ "
        "(Biogeochemical.N, Spalte Boundary). VK=0: kein nennenswerter "
        "anthropogener Haber-Bosch-Bezug vor Industrialisierung (Naherung)."
    ),
    is_example=False,
)

ALL_BOUNDARIES: tuple[BoundaryConstants, ...] = (CO2, HANPP, NITROGEN)
