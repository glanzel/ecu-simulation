"""
Planetare Konstanten AG, VK, RZ pro Kontrollvariable.

VEJ = (AG − VK) / RZ  (siehe ecu.txt)

**Zu RZ:** In ecu.txt ist RZ als „Regenerationszeit“ gemeint. **CO₂:** Es gibt in der
Literatur **keinen** einzigen „richtigen“ Wert — ein CO₂-Puls wird über **Jahrzehnte bis
Jahrtausende** aus der Atmosphäre entfernt (IPCC Kohlenstoffzyklus-Kapitel; Archer 2009:
fossiles CO₂, Ozean- und Langzeitspeicher). Hier wird **RZ = CO2_REGENERATION_YEARS**
(Jahre) als **Größenordnung** einer wirksamen Anpassungs-/Abklingzeit gesetzt (Standard
**100 a**, vergleichbar dem üblichen GWP-Referenzhorizont; Alternativen in Studien oft
**50–300 a**). Daraus folgt **VEJ in Mt CO₂ a⁻¹** = (AG−VK)/RZ. **HANPP / N:** RZ=1
bleibt eine neutrale Skalierung (Anteil bzw. bereits jährlicher Fluss in AG/VK).

**Eingearbeitete Literatur (wo direkt aus PB-Update 2015):**

- **Klima / CO₂:** Literatur **350 ppm / ≈280 ppm** (Steffen et al. 2015, SRC „Ref Figure 3“).
  **AG und VK in diesem Modul in Mt CO₂** (atmosphärische CO₂-Masse proportional zur
  Konzentration, Faktor `MT_CO2_PER_ATMOSPHERIC_PPM` = 1000 × Gt pro ppm). **RZ** siehe
  `CO2_REGENERATION_YEARS`.
- **Stickstoff:** dieselbe Quelle — Literatur **69 Tg N a⁻¹**; im Modell **kt N a⁻¹**
  (**1 Tg = 1000 kt**), also **AG = 69 000 kt N a⁻¹** für dieselbe physikalische Grenze.
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
# Dieselbe physikalische Größe in **Megatonnen** pro ppm (Rechen- und Anzeigeeinheit im Modell).
MT_CO2_PER_ATMOSPHERIC_PPM: float = GT_CO2_PER_ATMOSPHERIC_PPM * 1000.0

# Charakteristische Zeitskala für ecu.txt: VEJ_CO2 = (AG−VK)/RZ [Mt CO₂ a⁻¹], AG/VK in Mt.
# Literatur: kein Einzelwert (IPCC: mehrere Entfernungsprozesse; Archer 2009 u. a.: Jahrhundert-
# bis Jahrtausend-Skalen). 100 a = übliche Größenordnungswahl / GWP-Referenz; bei Bedarf z. B. 200–300.
CO2_REGENERATION_YEARS: float = 100.0

# Stickstoff: Literatur meist Tg N a⁻¹; im Modell **kt N a⁻¹** (1 Tg = 1000 kt).
KT_N_PER_TG: float = 1000.0


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
        "AG/VK: Mt CO₂ (Masse in der Luft, linear mit ppm; Literatur 350/280 ppm). "
        "VEJ: Mt CO₂ a⁻¹ via (AG−VK)/RZ, RZ = CO2_REGENERATION_YEARS (Jahre)."
    ),
    # Literatur ppm → Masse in Mt: 1 Gt = 1000 Mt
    AG=350.0 * MT_CO2_PER_ATMOSPHERIC_PPM,
    VK=280.0 * MT_CO2_PER_ATMOSPHERIC_PPM,
    RZ=CO2_REGENERATION_YEARS,
    literature_note=(
        "Grenzen ppm: Steffen et al. (2015), SRC „Ref Figure 3.txt“ (Climate.change). "
        "Masse: ppm × MT_CO2_PER_ATMOSPHERIC_PPM (Mt; IPCC ~2,12 Pg C pro ppm → Gt, hier ×1000). "
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
    AG=5600,
    VK=0,
    RZ=1.0,
    literature_note=(
        "ca 20% Prozent der terrestrischen NPP in MT C (Kohlenstoff). https://www.science.org/doi/10.1126/sciadv.adh2458"
    ),
    is_example=True,
)

NITROGEN = BoundaryConstants(
    key="nitrogen",
    label_de="Stickstoff (anthropogene N₂-Fixierung)",
    unit_note="kt N pro Jahr (1 Tg = 1000 kt; PB-Grenze 69 Tg a⁻¹ → 69 000 kt a⁻¹).",
    AG=69.0 * KT_N_PER_TG,
    VK=0.0,
    RZ=5.0,
    literature_note=(
        "Literatur-Grenze 69 Tg N a⁻¹: Steffen et al. (2015); SRC „Ref Figure 3.txt“ "
        "(Biogeochemical.N). Im Modell kt N a⁻¹ (×1000). VK=0: kein nennenswerter "
        "anthropogener Haber-Bosch-Bezug vor Industrialisierung (Näherung)."
    ),
    is_example=False,
)

ALL_BOUNDARIES: tuple[BoundaryConstants, ...] = (CO2, HANPP, NITROGEN)
