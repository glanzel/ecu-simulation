# AGENTS.md

## Zielbild
Konsequent objektorientiert: Domänenzustand und Verhalten gehören in Klassen.

## Fachliche Anforderungen (Simulation)

- **Konsum ist unveränderbar.** Ein Konsum wird einmal gesetzt (Beobachtung pro Periode). Sobald daraus die **folgenden** Schattenpreise berechnet wurden, darf dieser gespeicherte Konsum **nicht** mehr verändert werden. Kein nachträgliches Überschreiben oder „zweites Einkaufen“ mit neuen Preisen auf derselben Beobachtung: aus neuen Preisen entsteht **immer erst** der nächste Konsum.

- **Preislogik kennt keinen Demand.** Funktionen zur Preisbildung (`logic.prices`, u. a. Schätzung aus der Timeline) dürfen **nicht** auf die Nachfragefunktion, aktuelle Referenznachfrage oder Elastizitäten zugreifen. Sie arbeiten **ausschließlich** auf der Grundlage **historischer** Daten (z. B. gespeicherte Konsumintervalle, VEJ, ECU-Boden, Konfiguration für Preisschritte). Nachfrage und Konsum gehören in die Simulationsschicht; die Preisschicht sieht nur die **Beobachtungshistorie**.

## Regeln
- Logik in Klassenmethoden kapseln; Konstruktor/Fabriken setzen Abhängigkeiten, danach läuft das Verhalten über Methoden.
- Funktionale Programmierung vermeiden: keine „Pipeline“ aus vielen `map`/`filter`/Funktionsketten als Kernlogik.
- Hilfsfunktionen nur für generische Utilities; fachliche Entscheidungen als Methoden (ggf. `private`).
- **Funktionsaufrufe:** Wo möglich in einer Zeile. Bei sehr langen Zeilen darf der Aufruf eingerückt umbrochen werden (Fortsetzung in der nächsten Zeile). 
- **Funktionsdefinition:** Wo möglich in einer Zeile. Bei sehr langen Zeilen darf der Aufruf eingerückt umbrochen werden (Fortsetzung in der nächsten Zeile). **Nicht** die „eine Zeile pro Argument/Variable“-Formatierung — keine vertikal gestapelte Argumentliste.


