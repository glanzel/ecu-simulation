"""
Planetare Konstanten AG, VK, RZ sowie Start-Nachfrage und Wachstum — **durchgängig
literaturbelegt** oder aus tabellierten Beobachtungswerten **berechnet**.

**Hauptquelle für Istwerte / Grenzen (Tabelle 1):** Richardson, K. et al., „Earth beyond
six of nine planetary boundaries“, *Science Advances* **9**, eadh2458 (2023),
doi:10.1126/sciadv.adh2458 (PMC10499318). Abweichungen (z. B. CO₂-Fluss) sind im
jeweiligen ``default_params_note`` erklärt.

**CO₂-Emissionen:** Global Carbon Budget — Friedlingstein, P. et al., *Earth Syst. Sci. Data*
**17**, 965–1038, 2025 (GCB 2024; doi:10.5194/essd-17-965-2025): gesamt anthropogen
**41,6 Gt CO₂ a⁻¹** (2024), fossiler Anstieg **+0,8 %** (2023→2024, vorläufig).

**Weitere:** Ozon **284,6 DU** (global, Richardson T1, Ref. 96 = WMO/GAW-basierte
Schätzung im Paper); Aerosol **interhemisphärische AOD-Differenz** 0,076 (Ref. 55, 57, 68);
Ozean **Ω_arag 2,8** (Ref. 71); Stickstoff **190 Tg N a⁻¹** zu Landwirtschaft (Ref. 84 = FAO,
im Paper zitiert); Süßwasser **18,2 %** Landfläche mit Abweichung (Ref. 46 = Porkka et al.,
*Nature Water* 2024 u. a.); Kunststoffproduktion **+4,1 %** (2023→2024): PlasticsEurope
„The Fast Facts 2025“.

``start_demand_percent`` ist **100 × (Ist-Kontrollgröße) / (Modell-VEJ)**, sobald beide
dieselbe Einheit tragen; sonst **100 × Ist / (AG−VK)** bzw. dokumentierter Quotient
(z. B. Ozon: DU-Defizit relativ zum DU-Korridor).
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Physikalische Hilfsgrößen (IPCC Kohlenstoffzyklus, AR6-kompatibel) ------------
GT_CO2_PER_ATMOSPHERIC_PPM: float = 2.12 * (44.0 / 12.0)
MT_CO2_PER_ATMOSPHERIC_PPM: float = GT_CO2_PER_ATMOSPHERIC_PPM * 1000.0

# RZ CO₂: dokumentierte Modellwahl (kein Einzel-Literaturwert), vgl. Modulgeschichte.
CO2_REGENERATION_YEARS: float = 100.0
KT_N_PER_TG: float = 1000.0

# GCB 2024 (Friedlingstein et al. ESSD 2025): anthropogener Gesamt-CO₂-Fluss 2024.
ANTHROPOGENIC_CO2_TOTAL_GT_PER_YEAR_2024: float = 41.6

# Richardson et al. (2023) Sci. Adv. Tabelle 1 — Kontrollgrößen (Auszug). Suffixe: PI =
# präindustriell; BOUNDARY = planetare Grenze; CURRENT = aktueller Schätzwert.
CO2_PPM_BOUNDARY: float = 350.0
CO2_PPM_PI: float = 280.0

OZONE_DU_PI: float = 290.0
OZONE_DU_BOUNDARY: float = 276.0
OZONE_DU_CURRENT: float = 284.6

AOD_INTERHEM_DIFF_PI: float = 0.03
AOD_INTERHEM_DIFF_BOUNDARY: float = 0.1
AOD_INTERHEM_DIFF_CURRENT: float = 0.076

OMEGA_ARAG_PI: float = 3.44
OMEGA_ARAG_BOUNDARY: float = 2.75
OMEGA_ARAG_CURRENT: float = 2.8

N_AGRIC_FIXATION_TG_PER_YR_BOUNDARY: float = 62.0
N_AGRIC_FIXATION_TG_PER_YR_CURRENT: float = 190.0

FOREST_REMAINING_PCT_GLOBAL_CURRENT: float = 60.0
FOREST_REMAINING_PCT_GLOBAL_BOUNDARY: float = 75.0

BLUE_WATER_STRESS_PCT_LAND_BOUNDARY: float = 10.2
BLUE_WATER_STRESS_PCT_LAND_CURRENT: float = 18.2

HANPP_PCT_CURRENT: float = 30.0
HANPP_PCT_SAFE_TARGET: float = 10.0

# GCB: jährliche Änderung fossiler CO₂-Emissionen 2023→2024 (vorläufig, ±Unsicherheit).
GCB2024_FOSSIL_CO2_GROWTH_PCT_YR: float = 0.8

# Liu et al. ESSD 9, 181–192 (2017): globale N-Düngemittelnutzung stark gestiegen;
# langfristiger CAGR grob ~1–2 %/a — **1,0** % als konservative Jahresannahme (FAO/Landwirtschaft).
N_FERTILIZER_TREND_PCT_YR: float = 1.0

# PlasticsEurope „The Fast Facts 2025“: globale Kunststoffproduktion +4,1 % 2023→2024.
PLASTICS_PRODUCTION_GROWTH_PCT_YR: float = 4.1

# Feely et al. / Beobachtungen: Ω_arag Oberfläche ~**−0,08 pro Jahrzehnt** globales Mittel
# (z. B. Oceanography-Artikel; IPCC SROCC zu Ω-Trends) → **−0,8 % pro Jahrzehn** auf Ω 2,8
# entspricht grob **−0,29 %/a** relative Änderung (0,08/10 / 2,8 ≈ 0,0029).
OCEAN_OMEGA_ARAG_RELATIVE_DECLINE_PCT_YR: float = -0.29


def co2_vej_mt_per_year() -> float:
    """Jährliches VEJ (Mt CO₂/a) aus Steffen-Grenze 350 ppm, PI 280 ppm, RZ."""
    return (
        (CO2_PPM_BOUNDARY - CO2_PPM_PI)
        * MT_CO2_PER_ATMOSPHERIC_PPM
        / CO2_REGENERATION_YEARS
    )


def co2_start_demand_percent_from_gcb_emissions() -> float:
    """100 × GCB-Gesamtemissionen / Modell-VEJ (gleiche Einheit Mt/a)."""
    emissions_mt = ANTHROPOGENIC_CO2_TOTAL_GT_PER_YEAR_2024 * 1000.0
    return 100.0 * emissions_mt / co2_vej_mt_per_year()


def ozone_start_demand_percent_from_du_corridor() -> float:
    """DU-„Verbrauch“ relativ zum Korridor PI → Grenzwert (Richardson T1)."""
    corridor_du = OZONE_DU_PI - OZONE_DU_BOUNDARY
    depletion_du = OZONE_DU_PI - OZONE_DU_CURRENT
    return 100.0 * depletion_du / corridor_du


def aerosol_start_demand_percent_from_aod_diff() -> float:
    """Erhöhung der interhemisphärischen AOD-Differenz seit PI vs. Spielraum bis Grenzwert."""
    headroom = AOD_INTERHEM_DIFF_BOUNDARY - AOD_INTERHEM_DIFF_PI
    used = AOD_INTERHEM_DIFF_CURRENT - AOD_INTERHEM_DIFF_PI
    return 100.0 * used / headroom


def ocean_acid_start_demand_percent_from_omega() -> float:
    """Abnahme Ω seit PI relativ zum Abnahmekorridor PI → Grenze (Richardson T1)."""
    drop_pi_to_boundary = OMEGA_ARAG_PI - OMEGA_ARAG_BOUNDARY
    drop_pi_to_current = OMEGA_ARAG_PI - OMEGA_ARAG_CURRENT
    return 100.0 * drop_pi_to_current / drop_pi_to_boundary


def nitrogen_start_demand_percent_from_tg() -> float:
    return 100.0 * N_AGRIC_FIXATION_TG_PER_YR_CURRENT / N_AGRIC_FIXATION_TG_PER_YR_BOUNDARY


def freshwater_blue_start_demand_percent() -> float:
    """Störung % der Landfläche: Ist / planetare Schwelle (Richardson T1; Porkka et al.)."""
    return 100.0 * BLUE_WATER_STRESS_PCT_LAND_CURRENT / BLUE_WATER_STRESS_PCT_LAND_BOUNDARY


def land_system_start_demand_percent() -> float:
    """
    Waldfläche: Verlustanteil relativ zum im Modell erlaubten Maximalverlust (AG=0,25).
    Ist-Verlust = 1 − 0,60; „sicherer“ Maximalverlust = 1 − 0,75 = 0,25 (Richardson T1).
    """
    converted_current = 1.0 - (FOREST_REMAINING_PCT_GLOBAL_CURRENT / 100.0)
    converted_safe_cap = 1.0 - (FOREST_REMAINING_PCT_GLOBAL_BOUNDARY / 100.0)
    return 100.0 * converted_current / converted_safe_cap


def hanpp_start_demand_percent() -> float:
    return 100.0 * HANPP_PCT_CURRENT / HANPP_PCT_SAFE_TARGET


@dataclass(frozen=True)
class BoundaryConstants:
    """Eine planetare Grenze mit AG, VK, RZ und Simulations-Defaults (Prozent)."""

    key: str
    label_de: str
    unit_note: str
    consumption_unit_monthly: str
    AG: float # Grenzwert
    VK: float # Vorindustrieller Wert
    RZ: float # RZ = Regenerationszeit
    literature_note: str
    is_example: bool
    start_demand_percent: float
    annual_growth_percent: float
    default_params_note: str


CLIMATE_CO2 = BoundaryConstants(
    key="co2",
    label_de="Klima (atmosphärisches CO₂)",
    unit_note=(
        "AG/VK: Mt CO₂ (Masse in der Luft; Grenze 350 ppm, PI 280 ppm, Richardson et al. 2023 T1; "
        "Steffen et al. 2015). VEJ: Mt CO₂ a⁻¹ via (AG−VK)/RZ."
    ),
    consumption_unit_monthly="Mt CO₂ Monat⁻¹",
    AG=CO2_PPM_BOUNDARY * MT_CO2_PER_ATMOSPHERIC_PPM,
    VK=CO2_PPM_PI * MT_CO2_PER_ATMOSPHERIC_PPM,
    RZ=CO2_REGENERATION_YEARS,
    literature_note=(
        "350/280 ppm (Grenze/PI), atmosphärisch 417 ppm (2022, Richardson et al. 2023 T1); "
        "Masse: ppm × MT_CO2_PER_ATMOSPHERIC_PPM (IPCC ~2,12 Pg C/ppm)."
    ),
    is_example=False,
    start_demand_percent=co2_start_demand_percent_from_gcb_emissions(),
    annual_growth_percent=GCB2024_FOSSIL_CO2_GROWTH_PCT_YR,
    default_params_note=(
        "start_demand_percent: 100×(41,6 Gt CO₂/a) / VEJ; 41,6 aus GCB 2024 "
        "(Friedlingstein et al., ESSD 17, 965–1038, 2025). "
        "annual_growth_percent: +0,8 % fossile CO₂-Emissionen 2023→2024 (ebd.)."
    ),
)

STRATOSPHERIC_OZONE = BoundaryConstants(
    key="ozone",
    label_de="Stratosphärisches Ozon",
    unit_note="Globale mittlere Ozonsäule (DU); Richardson et al. (2023) T1 / WMO-GAW (Ref. 96).",
    consumption_unit_monthly="DU Monat⁻¹",
    AG=OZONE_DU_PI - OZONE_DU_BOUNDARY,
    VK=0.0,
    RZ=1.0,
    literature_note=(
        "290 DU PI, 276 DU Grenze (<5 % Reduktion), 284,6 DU aktuell: Richardson et al. (2023) T1."
    ),
    is_example=False,
    start_demand_percent=ozone_start_demand_percent_from_du_corridor(),
    annual_growth_percent=-0.15,
    default_params_note=(
        "start_demand_percent: 100×(290−284,6)/(290−276) nach Richardson T1. "
        "annual_growth_percent: −0,15 %/a grob aus Erholungstrend "
        "(WMO Scientific Assessment of Ozone Depletion 2022: leichter Anstieg der "
        "globalen Ozonsäule seit ~1996 — hier als **sinkender** modellierter "
        "Abbau-Druck interpretiert; keine exakte Ableitung aus Zeitreihe im Code)."
    ),
)

ATMOSPHERIC_AEROSOLS = BoundaryConstants(
    key="aerosol",
    label_de="Atmosphärische Aerosolbelastung",
    unit_note=(
        "Jährliche mittlere **interhemisphärische Differenz** der AOD (dimensionslos); "
        "Richardson et al. (2023) T1, Ref. 55, 57, 68."
    ),
    consumption_unit_monthly="ΔAOD_interhem. Monat⁻¹",
    AG=AOD_INTERHEM_DIFF_BOUNDARY,
    VK=AOD_INTERHEM_DIFF_PI,
    RZ=1.0,
    literature_note=(
        "PB 0,1, PI 0,03, aktuell 0,076: Richardson et al. (2023) T1; Satelliten/Multi-Source-AOD."
    ),
    is_example=False,
    start_demand_percent=aerosol_start_demand_percent_from_aod_diff(),
    annual_growth_percent=0.0,
    default_params_note=(
        "start_demand_percent: 100×(0,076−0,03)/(0,1−0,03) nach Richardson T1. "
        "annual_growth_percent: **0** — SAOD 2022 / Richardson diskutieren Trends, "
        "liefern aber **keine** einheitliche globale Jahres-Prozentänderung dieser Differenz "
        "(regional heterogen, Projektionen CMIP6 unsicher)."
    ),
)

OCEAN_ACIDIFICATION = BoundaryConstants(
    key="ocean_acid",
    label_de="Ozeanversauerung (Ω Aragonit)",
    unit_note="Globales mittleres Ω_arag Oberfläche; Richardson et al. (2023) T1.",
    consumption_unit_monthly="ΔΩ Monat⁻¹",
    AG=OMEGA_ARAG_PI - OMEGA_ARAG_BOUNDARY,
    VK=0.0,
    RZ=1.0,
    literature_note=(
        "PI 3,44, Grenze 2,75 (≥80 % von PI), aktuell 2,8: Richardson et al. (2023) T1, Ref. 71."
    ),
    is_example=False,
    start_demand_percent=ocean_acid_start_demand_percent_from_omega(),
    annual_growth_percent=OCEAN_OMEGA_ARAG_RELATIVE_DECLINE_PCT_YR,
    default_params_note=(
        "start_demand_percent: 100×(3,44−2,8)/(3,44−2,75) nach Richardson T1. "
        "annual_growth_percent: −0,29 %/a als Näherung aus **~0,08 Ω pro Jahrzehnt** "
        "globaler Oberflächenmittelwert (Beobachtungen, u. a. in IPCC SROCC Kap. 5 zu Ω-Trends; "
        "Feely et al., NOAA), umgerechnet auf relative Änderung bei Ω≈2,8."
    ),
)

NITROGEN = BoundaryConstants(
    key="nitrogen",
    label_de="Stickstoff (anthropogene Fixierung Landwirtschaft)",
    unit_note="Tg N a⁻¹; Grenze 62, Ist 190: Richardson et al. (2023) T1, Ref. 84 (FAO).",
    consumption_unit_monthly="kt N Monat⁻¹",
    AG=N_AGRIC_FIXATION_TG_PER_YR_BOUNDARY * KT_N_PER_TG,
    VK=0.0,
    RZ=1.0,
    literature_note=(
        "62 Tg N a⁻¹ Grenze, 190 Tg N a⁻¹ aktuell (anthropogen fixiert, landwirtschaftliches System): "
        "Richardson et al. (2023) T1; Zitat FAO im Original."
    ),
    is_example=False,
    start_demand_percent=nitrogen_start_demand_percent_from_tg(),
    annual_growth_percent=N_FERTILIZER_TREND_PCT_YR,
    default_params_note=(
        "start_demand_percent: 100×190/62 (Richardson T1). "
        "annual_growth_percent: +1,0 %/a als grobe Größenordnung langfristigen "
        "N-Düngemittelanstiegs (Liu & Tian, ESSD 9, 181–192, 2017; FAO-Zeitreihen)."
    ),
)

FRESHWATER = BoundaryConstants(
    key="freshwater",
    label_de="Süßwasser (blaue Wasser-Störung)",
    unit_note=(
        "Anteil der eisfreien Landfläche mit signifikanten Abweichungen der Abflüsse "
        "gegenüber präindustrieller Variabilität (%); Richardson et al. (2023) T1; "
        "Methodik Porkka et al. (2024) *Nature Water* (Ref. 46)."
    ),
    consumption_unit_monthly="% Landfläche (blue water) Monat⁻¹",
    AG=BLUE_WATER_STRESS_PCT_LAND_BOUNDARY,
    VK=0.0,
    RZ=1.0,
    literature_note=(
        "Grenze 10,2 % Landfläche, Ist 18,2 %: Richardson et al. (2023) T1; Basis Porkka et al."
    ),
    is_example=False,
    start_demand_percent=freshwater_blue_start_demand_percent(),
    annual_growth_percent=0.86,
    default_params_note=(
        "start_demand_percent: 100×18,2/10,2 (Richardson T1). "
        "annual_growth_percent: +0,86 %/a ≈ (1,09)^(1/10)−1 aus **+9 %** "
        "räumlich explizitem Konsum blauen+grünen Wassers für 46 Feldfrüchte "
        "2010→2020 (Tian et al., *Nature Food* 2025, doi:10.1038/s43016-025-01231-x); "
        "nicht identisch zur PB-%-Landflächen-Metrik, nur **Größenordnung** Wasserdruck."
    ),
)

LAND_SYSTEM = BoundaryConstants(
    key="land",
    label_de="Landnutzung (Waldfläche, global)",
    unit_note="Verbleibende Waldfläche % der potenziellen Waldbedeckung; Richardson et al. (2023) T1.",
    consumption_unit_monthly="Umwandlungsanteil Monat⁻¹",
    AG=1.0 - (FOREST_REMAINING_PCT_GLOBAL_BOUNDARY / 100.0),
    VK=0.0,
    RZ=1.0,
    literature_note=(
        "Global 60 % verbleibend, Grenze 75 % (gewichteter Durchschnitt der Biome): "
        "Richardson et al. (2023) T1; Satelliten-Landbedeckung (Ref. 72, 97)."
    ),
    is_example=False,
    start_demand_percent=land_system_start_demand_percent(),
    annual_growth_percent=-0.05,
    default_params_note=(
        "start_demand_percent: 100×(1−0,60)/(1−0,75) nach Richardson T1. "
        "annual_growth_percent: −0,05 %/a grob aus FAO Forest Resources Assessment "
        "(netto Waldverlust sinkend, aber regional ungleich; FRA 2020 Key Findings)."
    ),
)

HANPP = BoundaryConstants(
    key="hanpp",
    label_de="HANPP (funktionale Biosphären-Integrität)",
    unit_note="HANPP als % der holozänen NPP; Richardson et al. (2023) T1 (funktionale Komponente).",
    consumption_unit_monthly="HANPP-Anteil Monat⁻¹",
    AG=HANPP_PCT_SAFE_TARGET / 100.0,
    VK=0.0,
    RZ=1.0,
    literature_note=(
        "Aktuell 30 % HANPP, Zielgröße <10 % des holozänen NPP-Flusses (T1); "
        "HANPP-Methodik Haberl et al.; Running (2012) Science Diskussion."
    ),
    is_example=False,
    start_demand_percent=hanpp_start_demand_percent(),
    annual_growth_percent=0.69,
    default_params_note=(
        "start_demand_percent: 100×30/10 (Richardson T1: Ist 30 %, Ziel <10 %). "
        "annual_growth_percent: +0,69 %/a ≈ ln(25/13)/95 aus globalem HANPP-Anteil "
        "**~13 % (1910) → ~25 % (2005)** der potenziellen NPP (Krausmann et al., "
        "PMC3690849, 2013); extrapoliert, **kein** Post-2005-Fit."
    ),
)

NOVEL_ENTITIES = BoundaryConstants(
    key="novel",
    label_de="Neuartige Einträge (Chemikalien / Kunststoffe u. a.)",
    unit_note=(
        "Richardson et al. (2023) T1: **transgressed**, ohne skalaren „Current“-Wert in Tabelle. "
        "Proxy: global plastics production trend."
    ),
    consumption_unit_monthly="Index Monat⁻¹",
    AG=1.0,
    VK=0.0,
    RZ=1.0,
    literature_note=(
        "Persson et al. (2022) Environ. Sci. Technol. (überschritten); "
        "Richardson T1: qualitativ ohne Zahl — Modell-Index 1,0."
    ),
    is_example=True,
    start_demand_percent=100.0,
    annual_growth_percent=PLASTICS_PRODUCTION_GROWTH_PCT_YR,
    default_params_note=(
        "start_demand_percent: **100** — in Richardson T1 keine quantitative Current-Spalte; "
        "Wert markiert Überschreitung ohne Behauptung eines exakten VEJ-Verhältnisses. "
        "annual_growth_percent: **+4,1 %** globale Kunststoffproduktion 2023→2024 "
        "(PlasticsEurope, The Fast Facts 2025) als **einziger harter Jahrestrend** für diesen Proxy."
    ),
)


ALL_BOUNDARIES: tuple[BoundaryConstants, ...] = (
    CLIMATE_CO2,
    STRATOSPHERIC_OZONE,
    ATMOSPHERIC_AEROSOLS,
    OCEAN_ACIDIFICATION,
    NITROGEN,
    FRESHWATER,
    LAND_SYSTEM,
    HANPP,
    NOVEL_ENTITIES,
)


def default_start_demand_by_key() -> dict[str, float]:
    return {b.key: b.start_demand_percent / 100.0 for b in ALL_BOUNDARIES}


def default_growth_by_key() -> dict[str, float]:
    return {b.key: 1.0 + b.annual_growth_percent / 100.0 for b in ALL_BOUNDARIES}
