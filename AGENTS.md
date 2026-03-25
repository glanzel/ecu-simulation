# AGENTS.md

## Zielbild
Konsequent objektorientiert: Domänenzustand und Verhalten gehören in Klassen.

## Regeln
- Logik in Klassenmethoden kapseln; Konstruktor/Fabriken setzen Abhängigkeiten, danach läuft das Verhalten über Methoden.
- Funktionale Programmierung vermeiden: keine „Pipeline“ aus vielen `map`/`filter`/Funktionsketten als Kernlogik.
- Hilfsfunktionen nur für generische Utilities; fachliche Entscheidungen als Methoden (ggf. `private`).
