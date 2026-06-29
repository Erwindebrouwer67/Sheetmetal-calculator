# Plaatwerk Calculator — Inno Mechatronics
## Installatie & Gebruik

### Vereisten
- Python 3.9 of hoger
- pip

---

### Stap 1 — Installeer Python-pakketten

Open een terminal in deze map en voer uit:

```
pip install -r requirements.txt
```

> Eerste keer duurt even — cadquery is een groot pakket (~500 MB).

---

### Stap 2 — Start de server

```
python server.py
```

Je ziet:
```
  Inno Mechatronics — Plaatwerk STEP Analyser
  Server draait op http://localhost:5050
```

Laat dit venster open staan zolang je de app gebruikt.

---

### Stap 3 — Open de app

Open `index.html` in Chrome (dubbelklik op het bestand).

Of installeer als PWA via GitHub Pages / Netlify (zie eerder).

---

### Stap 4 — STEP analyseren

1. Zorg dat de groene stip naast de server-URL brandt
2. Sleep een `.step` bestand op het upload-vlak
3. De velden worden automatisch ingevuld:
   - Materiaaldikte
   - Snijlengte (ontvouwde plaat)
   - Aantal buigingen
   - Insteekpunten

---

### Probleemoplossing

**Rode stip / server niet bereikbaar**
→ Controleer of `python server.py` nog draait

**"Analyse mislukt"**
→ Controleer of het bestand een plaatwerk onderdeel is (met buigingen)
→ Assemblages met meerdere onderdelen: exporteer onderdelen apart

**Poort 5050 al in gebruik**
→ Verander in `server.py` de laatste regel: `port=5051`
→ Pas ook de URL in de app aan

---

### Serveradres aanpassen

Draait de server op een andere pc in het netwerk?
Verander de URL in de app van `http://localhost:5050` naar het IP-adres van die pc,
bijv. `http://192.168.1.50:5050`.
