# Hardware-Krisenindex (HKI)

Interaktives Hardware-Preis-Dashboard für RAM, SSD, GPUs und HDDs. Historische, auf September 2025 = 100 normierte 3DCenter-Gruppen und täglich erfasste Retailangebote werden **getrennt** dargestellt. Die Weboberfläche lädt `data/daily.json` bei jedem Besuch neu.

## Automatik
- Jeden Morgen startet GitHub Actions `Daily HKI collection and Pages` (Zeitplan in UTC; GitHub kann verzögert ausführen).
- Ein kostenloser oder kostenpflichtiger API-Zugang beim **unabhängigen** Anbieter Scrappa wird benötigt. Die Schnittstelle nutzt Geizhals-Produkt-IDs; sie ist **keine offizielle Geizhals-API**.
- Feste konkrete SKUs, Händler-Whitelist, Preise in EUR, bestätigte Lieferbarkeit, Neuware. Fehlende oder unsichere Preise ergeben eine Datenlücke, keine Schätzung.
- Min. 1/2 RAM, 1/2 SSD, 2/4 GPU, 1/2 HDD; anschließende Gewichtung 40/30/20/10.
- Der Ausgangspunkt 331,6 Punkte aus dem breiteren historischen Gruppenwarenkorb ist *nicht exakt vergleichbar* mit den anschließenden festen SKUs.
- Siebentages-Trend nur mit acht aufeinanderfolgenden ausreichend belegten Tagen **und gleicher SKU-Auswahl** berechnen.

## Zur Aktivierung
1. Im Repository **Settings → Pages → Build and deployment → Source: GitHub Actions** auswählen.
2. Bei https://scrappa.co einen API-Schlüssel für den Geizhals-Produkt-Endpunkt beschaffen. Bedingungen, Preis und Nutzungsrechte vorher prüfen.
3. Im Repository **Settings → Secrets and variables → Actions → New repository secret**: Name `SCRAPPA_API_KEY`, Wert: dein geheimer Schlüssel. Den Schlüssel niemals in Dateien oder Nachrichten eintragen.
4. Auf **Actions → Daily HKI collection and Pages → Run workflow** den ersten Lauf starten. Logs auf fehlende Händlerdaten und erfolgreiche Veröffentlichung prüfen.
5. Öffentliche Adresse nach erfolgreichem Deploy: https://ccanger.github.io/hardware-krisenindex/

Solange der Schlüssel fehlt, veröffentlicht der Workflow **nur** die historische Webseite und meldet die fehlenden Live-Daten ausdrücklich. Das verhindert vorgetäuschte Aktualität.

## Quellen
- https://www.3dcenter.org/artikel/speicherkrise-preisindex-september-2026
- https://scrappa.co/docs/geizhals-api/geizhals_product
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

Datenlieferant, Preise und Verfügbarkeit sind nicht amtlich; Händler- und API-Angaben können verzögert sein. Kein Anlageprodukt.
