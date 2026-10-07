#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IL SEGRETO DEL CARBONARO — versione 3D finale
Escape room in prima persona ambientata a Torino, 4 maggio 1860.

Installazione:   pip install -r requirements.txt
Avvio:           python il_segreto_del_carbonaro_finale.py

Stesso gioco della versione 3D della radice, con in più il menu Grafica nella schermata di pausa
(Esc): quattro livelli, Bassa / Media / Alta / Max, con un clic o con i tasti 1-4. La scelta viene
ricordata in ~/.il_segreto_del_carbonaro.json. Si parte da Media; Max è identico alla versione 3D originale.

Tutto (stanza, oggetti, texture, luci e suoni) è generato via codice:
nessuna immagine, modello 3D o file audio esterno.

Comandi:  WASD / frecce = muoviti · mouse = guarda · clic = esamina
          Invio = conferma · Esc = chiudi / pausa (in pausa: 1-4 = grafica) · M = audio · F11 = schermo intero
          R = rigioca (a fine partita)
          Mappamondo: trascina (o A-D / frecce) per girarlo · W-S = inclina · rotellina = zoom · Esc = esci

La parola d'ordine OBBEDISCO è formata da nove frammenti, una lettera ciascuno (O·B·B·E·D·I·S·C·O):
  - sette enigmi nello studio (pianoforte, spartito, mappa, mappamondo, camino, ritratto, scrivania);
    il mappamondo non ha una finestra: ci si avvicina, lo si gira col mouse e si clicca la città giusta;
  - risolti i sette, la libreria di destra scorre di lato e rivela l'archivio segreto, con
      · "Analizza fascicoli": i quattro fascicoli a terra, da mettere in ordine cronologico; il codice
        che ne esce (8690) va inserito nel Quadro di Comando Ferroviario, che solo allora si accende;
      · il Quadro di Comando Ferroviario apre il minigioco "Il Treno Diplomatico":
        si ruotano gli scambi con il mouse (o coi tasti 1-7) e si porta Cavour da Torino a Plombières
        (Invio / leva verde = parti · R = ripristina gli scambi · C = mostra/nascondi la pianta).
  - con tutti e nove i frammenti la porta d'uscita si sblocca.
"""

from ursina import *                         # noqa: F401,F403  (stile tipico di Ursina)
from ursina.shaders import unlit_shader

import bisect
import json
import math
import os
import random
import re
import shutil
import sys
import tempfile
import time
import unicodedata
import wave
from array import array
from pathlib import Path

from direct.filter.FilterManager import FilterManager
from panda3d.core import (ColorBlendAttrib, Filename, LVecBase3f, PTA_LVecBase3f, SamplerState,
                          TransparencyAttrib, loadPrcFileData)
from panda3d.core import Shader as ShaderPanda       # `Shader` e `Texture` di Ursina sono altre classi
from panda3d.core import Texture as TexturaPanda
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Su Windows i percorsi non distinguono maiuscole e minuscole (C:\WINDOWS = C:\Windows),
# ma Panda3D di default sì: senza questa riga rifiuta file che esistono davvero.
loadPrcFileData("", "vfs-case-sensitive 0")

# --------------------------------------------------------------------------
# Configurazione
# --------------------------------------------------------------------------
TEMPO_TOTALE = 25 * 60          # 25:00
DISTANZA_INTERAZIONE = 4.2      # metri
DISTANZA_INTERAZIONE_ARCHIVIO = 8.0   # nell'archivio tutto è a grandezza di ferrovia: scambi e leve si azionano da lontano
BONUS_VELOCITA_ARCHIVIO = 1.5   # nell'archivio (sala enorme) si cammina più svelti
ALTEZZA_OCCHI = 1.62
SCALINO = .35                      # dislivello che si sale camminando
SALTO = 5.8                        # velocità iniziale del salto (m/s): scavalca circa 1,5 m, abbastanza per salire sull'impalcato
GRAVITA = 9.8
VELOCITA = 2.4
SENSIBILITA_MOUSE = 40
MAX_INPUT = 32
# tastiera del computer -> note (Do4 = 60): riga centrale tasti bianchi, riga sopra tasti neri
TASTI_PIANO = {"a": 60, "w": 61, "s": 62, "e": 63, "d": 64, "f": 65, "t": 66, "g": 67, "y": 68,
               "h": 69, "u": 70, "j": 71, "k": 72, "o": 73, "l": 74, "p": 75}
N_LUCI = 36                     # 6 nello studio + 30 nell'archivio segreto (23 lanterne, 4 lampioni, candelabro, lampada del Quadro)

# Livelli di grafica (menu nella schermata di pausa, tasti 1-4).
#   luci        = quante luci contano per ogni pixel: le più vicine alla telecamera (Max: tutte, come nell'originale)
#   raggio      = oltre questa distanza in metri una luce è ignorata (0 = nessun limite)
#   riflessi    = 1 se i materiali lucidi (catene, cornici, pianoforte...) riflettono la luce, 0 se no
#   risoluzione = quota della risoluzione della finestra con cui si disegna la scena 3D (l'interfaccia resta nitida)
#   polvere     = quanti granelli di polvere fluttuano nello studio
LIVELLI_GRAFICA = [
    {"nome": "Bassa", "luci": 6, "raggio": 14.0, "riflessi": 0.0, "risoluzione": .65, "polvere": 12},
    {"nome": "Media", "luci": 10, "raggio": 20.0, "riflessi": 0.0, "risoluzione": .85, "polvere": 40},
    {"nome": "Alta", "luci": 16, "raggio": 28.0, "riflessi": 1.0, "risoluzione": 1.0, "polvere": 40},
    {"nome": "Max", "luci": N_LUCI, "raggio": 0.0, "riflessi": 1.0, "risoluzione": 1.0, "polvere": 40},
]
GRAFICA_PREDEFINITA = 1         # Media
FILE_IMPOSTAZIONI = Path.home() / ".il_segreto_del_carbonaro.json"


def carica_grafica():
    """Indice del livello salvato nel file delle impostazioni (Media se manca o è illeggibile)."""
    try:
        nome = json.loads(FILE_IMPOSTAZIONI.read_text(encoding="utf-8-sig")).get("grafica")
        for i, livello in enumerate(LIVELLI_GRAFICA):
            if livello["nome"] == nome:
                return i
    except Exception:
        pass
    return GRAFICA_PREDEFINITA


def salva_grafica(indice):
    try:
        try:
            dati = json.loads(FILE_IMPOSTAZIONI.read_text(encoding="utf-8-sig"))
            if not isinstance(dati, dict):
                dati = {}
        except Exception:
            dati = {}
        dati["grafica"] = LIVELLI_GRAFICA[indice]["nome"]
        FILE_IMPOSTAZIONI.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as ex:
        print("Impostazioni non salvate:", ex)

# --------------------------------------------------------------------------
# Contenuti del gioco
# --------------------------------------------------------------------------
# L'elenco è in "ordine di parola": i frammenti, letti da sinistra a destra, formano
# OBBEDISCO, una lettera per enigma.  I primi sette enigmi (fase 1) si risolvono nello studio; quando sono
# tutti risolti la libreria scorre di lato e si entra nell'archivio segreto, dove
# aspettano gli ultimi due (fase 2): i fascicoli (il cui codice si digita nel Quadro) e il Treno Diplomatico.
ENIGMI = [
    {
        "id": "pianoforte",
        "nome": "Pianoforte",
        "titolo": "Il Pianoforte",
        "domanda": ("I patrioti scrivono sui muri un nome per ingannare gli "
                    "austriaci, lodando un compositore. Ma è l'acronimo del "
                    "futuro Re d'Italia. Chi è il musicista?"),
        "soluzioni": ["verdi", "giuseppe verdi", "viva verdi"],
        "frammento": "O",
        "curiosita": ("La polizia austriaca mandava ogni notte agenti a cancellare le scritte "
                      "«Viva V.E.R.D.I.», ma il giorno dopo ricomparivano: non si poteva "
                      "vietare di inneggiare a un compositore amatissimo."),
    },
    {
        "id": "inno",
        "nome": "Inno",
        "titolo": "Il Canto degli Italiani",
        "domanda": "Siediti al pianoforte e suona lo spartito sul leggio.",
        "soluzioni": [],
        "frammento": "B",
        "curiosita": ("Goffredo Mameli scrisse il testo a Genova e Michele Novaro lo mise in musica "
                      "proprio qui a Torino, nel novembre del 1847. Diventò inno nazionale "
                      "provvisorio nel 1946 e ufficiale soltanto nel 2017."),
    },
    {
        "id": "mappa",
        "nome": "Mappa",
        "titolo": "La Mappa",
        "domanda": ("La storia li ricorderà come 'I Mille', ma quanti "
                    "volontari salparono davvero da Quarto? "
                    "(Tra loro c'era una donna)."),
        "soluzioni": ["1089", "1 089"],
        "frammento": "B",
        "curiosita": ("La donna era Rose Montmasson, moglie di Francesco Crispi: unica donna "
                      "della spedizione, curò i feriti e fu soprannominata «l'angelo di "
                      "Calatafimi». Compare nell'elenco ufficiale dei 1089."),
    },
    {
        "id": "globo",
        "nome": "Mappamondo",
        "nome_hud": "Globo",
        "tipo": "globo",                # niente finestra: ci si avvicina al globo e si clicca uno spillo
        "titolo": "Il Mappamondo",
        "domanda": ("Cavour ha fatto una rinuncia dolorosa per l'alleanza francese: ha ceduto "
                    "la Savoia e quale città? Gira il mappamondo e indicala."),
        "soluzioni": [],
        "frammento": "E",
        "curiosita": ("Promesse a Napoleone III a Plombières (1858) in cambio dell'aiuto contro l'Austria, "
                      "Nizza e la Savoia furono cedute alla Francia con il Trattato di Torino del 24 marzo "
                      "1860: dopo l'armistizio di Villafranca, che aveva lasciato il Veneto all'Austria, "
                      "furono il prezzo dell'assenso francese all'annessione di Toscana ed Emilia. Nizza era "
                      "la città natale di Garibaldi, che non perdonò mai a Cavour quella cessione."),
    },
    {
        "id": "camino",
        "nome": "Camino",
        "titolo": "La Lettera Bruciata",
        "domanda": ("Tra le braci c'è una lettera mezza bruciata, scritta col cifrario di Cesare: "
                    "ogni lettera è spostata di tre posti in avanti nell'alfabeto di 26 lettere "
                    "(A diventa D, B diventa E, C diventa F…). Decifrala: come si chiamavano tra loro i carbonari? "
                    "EXRQL FXJLQL"),
        "soluzioni": ["buoni cugini", "i buoni cugini", "cugini"],
        "frammento": "D",
        "curiosita": ("I carbonari si chiamavano tra loro \"buoni cugini\" e chiamavano \"pagani\" chi "
                      "non era affiliato. Le loro cellule si dicevano \"vendite\", come le botteghe dei "
                      "carbonai da cui la società prese nome e simboli."),
    },
    {
        "id": "libreria",
        "nome": "Analizza fascicoli",
        "nome_hud": "Fascicoli",
        "nome_nascosto": "???",
        "fase": 2,
        "tipo": "fascicoli",
        "titolo": "Analizza fascicoli",
        "domanda": ("La storia deve seguire il suo corso naturale. Prendi l'ultimo "
                    "frammento di ogni anno per formare il codice."),
        "istruzione_quadro": ("Il Quadro di Comando è bloccato da un codice di quattro cifre. "
                              "Inseriscilo: lo trovi analizzando i fascicoli a terra."),
        "soluzioni": ["8690", "8 6 9 0"],
        "frammento": "I",
        "curiosita": ("Dalle Cinque Giornate di Milano del 1848 al Trattato di Torino del 1860: in "
                      "dodici anni Cavour portò la questione italiana al Congresso di Parigi "
                      "(1856), la Seconda guerra d'indipendenza (1859) fu vinta con l'alleanza francese "
                      "a Magenta e Solferino e il Piemonte annesse Lombardia, Emilia e Toscana, "
                      "cedendo Nizza e la Savoia."),
    },
    {
        "id": "ritratto",
        "nome": "Ritratto",
        "titolo": "Il Ritratto",
        "domanda": ("Sono il Re di Sardegna e un giorno sarò il Primo Re dell'Italia "
                    "unita, ma la mia firma porta un numero romano ereditato dalla "
                    "mia casata. Qual è il numero in cifre?"),
        "soluzioni": ["2", "ii", "due"],
        "frammento": "S",
        "curiosita": ("Nel 1861 Vittorio Emanuele II mantenne il numero 2 invece di ripartire da I: "
                      "a molti patrioti parve l'annessione al Piemonte più che la nascita "
                      "di una nazione nuova."),
    },
    {
        "id": "scrivania",
        "nome": "Scrivania",
        "titolo": "La Scrivania",
        "domanda": ("Cavour pensava nella lingua della nazione che ci aiutò "
                    "contro gli austriaci. Quali sono i colori di quella "
                    "bandiera? (es: verde bianco rosso)"),
        "soluzioni": ["blu bianco rosso", "bleu blanc rouge"],
        "ordine_libero": True,          # i tre colori valgono in qualunque ordine
        "frammento": "C",
        "curiosita": ("Cavour, nato a Torino nel 1810, era di madrelingua francese e scrisse in "
                      "francese gran parte della sua corrispondenza privata."),
    },
    {
        "id": "treno",
        "nome": "Treno",
        "nome_nascosto": "???",
        "fase": 2,
        "tipo": "minigioco",
        "titolo": "Il Treno Diplomatico",
        "domanda": ("Porta Cavour in gran segreto da Torino a Plombières, "
                    "dove lo attende Napoleone III."),
        "soluzioni": [],
        "frammento": "O",
        "curiosita": ("Il 20 e 21 luglio 1858 Cavour incontrò in segreto Napoleone III a "
                      "Plombières. La Francia avrebbe aiutato il Piemonte contro l'Austria "
                      "in cambio di Nizza e della Savoia: l'intesa, formalizzata nel gennaio "
                      "1859, portò alla Seconda guerra d'indipendenza."),
    },
]
ENIGMI_PER_ID = {e["id"]: e for e in ENIGMI}
N_ENIGMI = len(ENIGMI)
ID_FASE1 = [e["id"] for e in ENIGMI if e.get("fase", 1) == 1]
N_FASE1 = len(ID_FASE1)
# Fascicoli sparsi a terra nell'archivio, mescolati: il giocatore deve rimetterli in ordine cronologico.
FASCICOLI = [("Il Trattato di Torino", 1860), ("Il Congresso di Parigi", 1856), ("I Moti Milanesi", 1848),
             ("Seconda guerra d'indipendenza", 1859)]
DATE_AMMESSE = {1848, 1849, 1854, 1856, 1858, 1859, 1860, 1861, 1864, 1866, 1870}     # le date importanti da programma
assert all(anno in DATE_AMMESSE for _, anno in FASCICOLI), "un fascicolo ha una data non ammessa"
CODICE_FASCICOLI = "".join(str(anno)[-1] for _, anno in sorted(FASCICOLI, key=lambda f: f[1]))     # ultima cifra, in ordine cronologico: 8690
# "Fratelli d'Italia, l'Italia s'è desta…" (M. Novaro, 1847), in Sol maggiore
INNO = [("Re", 62), ("Re", 62), ("Mi", 64), ("Re", 62), ("Si", 71), ("Si", 71), ("Do", 72), ("Si", 71),
        ("Si", 71), ("Re", 74), ("Do", 72), ("Si", 71), ("La", 69), ("Si", 71), ("La", 69), ("Sol", 67)]
assert ENIGMI_PER_ID["libreria"]["soluzioni"][0] == CODICE_FASCICOLI, "il codice dei fascicoli non corrisponde"
PAROLA_ORDINE = "obbedisco"
assert "".join(e["frammento"] for e in ENIGMI) == PAROLA_ORDINE.upper(), "i frammenti non formano la parola d'ordine"

TRAMA = ("4 maggio 1860. Sei un corriere della Carboneria, nascosto nello studio "
         "segreto di un patriota torinese. Porti un messaggio che deve raggiungere "
         "Garibaldi prima che salpi da Quarto. Ma qualcuno ha parlato: i gendarmi "
         "hanno circondato il palazzo e stanno forzando l'ingresso.\n"
         "Il patriota ha nascosto la parola d'ordine dell'uscita segreta in nove "
         "frammenti: sette custoditi dagli oggetti della stanza, gli ultimi due "
         "in un luogo che solo un vero patriota saprebbe trovare. Hai 25 minuti per "
         "decifrare i codici, ricomporre la chiave e fuggire.")

CURIOSITA_FINALE = ("Sei anni dopo, il 9 agosto 1866, durante la Terza guerra "
                    "d'indipendenza, Garibaldi aveva appena battuto gli austriaci a "
                    "Bezzecca e marciava verso Trento. Dal generale La Marmora arrivò "
                    "l'ordine di sgomberare il Trentino: erano in corso le trattative "
                    "di armistizio con l'Austria. Garibaldi, a malincuore, rispose con "
                    "un telegramma di una sola parola, entrato nella storia: "
                    "«Obbedisco».")


# --------------------------------------------------------------------------
# Utilità
# --------------------------------------------------------------------------
def normalizza(testo):
    """Minuscole, senza accenti, punteggiatura e spazi superflui.
    La congiunzione 'e' viene ignorata ("blu, bianco e rosso")."""
    testo = unicodedata.normalize("NFKD", str(testo))
    testo = "".join(c for c in testo if not unicodedata.combining(c))
    testo = re.sub(r"[^a-z0-9]+", " ", testo.lower())
    return " ".join(p for p in testo.split() if p != "e")


def risposta_corretta(enigma, risposta):
    r = normalizza(risposta)
    if not r:
        return False
    if enigma.get("ordine_libero"):
        return sorted(r.split()) in [sorted(normalizza(s).split()) for s in enigma["soluzioni"]]
    return r in {normalizza(s) for s in enigma["soluzioni"]}


def formatta_tempo(secondi):
    secondi = max(0, int(math.ceil(secondi)))
    return "%02d:%02d" % (secondi // 60, secondi % 60)


def C(r, g, b, a=255):
    return color.rgba32(r, g, b, a)


# Palette "Dark Academia / Risorgimento"
ORO = C(212, 175, 55)
ORO_CHIARO = C(244, 218, 138)
ORO_SCURO = C(140, 108, 30)
PERGAMENA = C(238, 225, 194)
PERGAMENA_SCURA = C(206, 186, 146)
INCHIOSTRO = C(44, 30, 22)
BORDEAUX = C(120, 24, 40)
BORDEAUX_SCURO = C(68, 12, 24)
BORDEAUX_CHIARO = C(160, 40, 58)
VERDE_CHIARO = C(120, 200, 130)
VERDE_SCURO = C(20, 70, 40)
ROSSO_ALLARME = C(236, 70, 58)
LEGNO = C(96, 60, 36)
LEGNO_SCURO = C(52, 32, 20)
NERO_LACCA = C(14, 12, 14)
FERRO = C(58, 58, 64)
CERA = C(236, 226, 200)
TRICOLORE = [C(0, 146, 70), C(244, 245, 240), C(206, 43, 55)]


# --------------------------------------------------------------------------
# Logica del Treno Diplomatico (Python puro: niente grafica, quindi testabile da sola)
# --------------------------------------------------------------------------
# Direzioni come maschere di bit: una tessera di binario ha le sue "aperture" in una maschera.
# N è verso l'alto della mappa (z crescente), E verso destra (x crescente).
DIR_N, DIR_E, DIR_S, DIR_O = 1, 2, 4, 8
VETTORE_DIR = {DIR_N: (0, 1), DIR_E: (1, 0), DIR_S: (0, -1), DIR_O: (-1, 0)}
_OPPOSTA = {DIR_N: DIR_S, DIR_E: DIR_O, DIR_S: DIR_N, DIR_O: DIR_E}
CURVA_BASE = DIR_N | DIR_E              # la curva "canonica": ruotata di 90° alla volta dà le altre tre
DRITTO_BASE = DIR_N | DIR_S


def opposta(d):
    return _OPPOSTA[d]


def ruota_cw(maschera, volte=1):
    """Ruota una maschera di aperture di 90° in senso orario (N→E→S→O→N), 'volte' volte."""
    for _ in range(volte % 4):
        maschera = ((maschera << 1) | (maschera >> 3)) & 15
    return maschera


def lati(maschera):
    return [d for d in (DIR_N, DIR_E, DIR_S, DIR_O) if maschera & d]


# La mappa, dall'alto (z = 8) al basso (z = 0), 13 colonne (x = 0..12).
#   .  erba                              T  Torino (partenza, il treno parte verso nord)
#   |  -  binario dritto (N-S / E-O)     Q  Plombières (arrivo giusto, si entra da est)   P  idem, da sud
#   a b c d  curve fisse N-E / E-S / S-O / O-N     V  Vienna (arrivo sbagliato, si entra da ovest)
#   1..7  nodi di scambio: pezzi che ruotano di 90° a ogni clic (curve; i numeri in SCAMBI_DRITTI sono rettilinei)
#   h  v  ponte sopraelevato: l'impalcato corre in direzione E-O (h) o N-S (v) e sotto passa l'altro binario
#   r  rampa: sale verso il ponte accanto (la direzione si ricava da lì)
#   x  z  passaggio a livello: binario N-S (x) o E-O (z) che attraversa una strada
#   ,  ;  +  strada E-O / N-S / incrocio di strade (solo scenografia: non portano il treno da nessuna parte)
MAPPA_TRENO = [
    "...Q-7--b---V",
    ",,,,,x,,x,,+,",
    "..b-rhr-4..;.",
    "..|..|..r..;.",
    "..3..|--v-c;.",
    "..|..|..r.|;.",
    "..|..6--5-|;.",
    "..2---1---d;.",
    "..|...T....;.",
]
# Binari "rossi" ('#'): zone pattugliate dalle spie austriache, portano a Vienna.
MAPPA_ROSSI = [
    "......##.###.",
    ".......#.....",
    ".............",
    ".............",
    ".......#.#...",
    ".............",
    ".............",
    ".............",
    ".............",
]
SCAMBI_DRITTI = {"3"}                    # gli altri scambi sono curve
# Quanti quarti di giro in senso orario ha già ogni scambio all'inizio (la partenza non è mai risolta).
GIRI_INIZIALI_TRENO = {"1": 1, "2": 2, "3": 1, "4": 1, "5": 1, "6": 3, "7": 0}
# Dopo quante tessere rosse il treno viene fermato dalle spie.
ROSSE_PRIMA_DELLO_STOP = 2


class Tessera:
    """Una cella della ferrovia. Gli scambi sono pezzi che si possono ruotare."""

    def __init__(self, tipo, maschera, rosso=False, sigla=None, giri=0, strada=None, alta=None, asse_alto=0):
        self.tipo = tipo        # erba | binario | scambio | partenza | arrivo | vienna | ponte | rampa
        self.base = maschera
        self.rosso = rosso
        self.sigla = sigla
        self.giri_iniziali = giri
        self.giri = giri        # quarti di giro orari rispetto alla maschera base
        self.strada = strada    # None | "eo" | "ns" | "inc": strada che passa nella tessera (scenografia)
        self.alta = alta        # rampa: il lato dove si arriva all'altezza dell'impalcato
        self.asse_alto = asse_alto   # ponte: le due direzioni (maschera) in cui corre l'impalcato

    @property
    def maschera(self):
        if self.tipo == "scambio":
            return ruota_cw(self.base, self.giri)
        if self.tipo == "ponte":
            return DIR_N | DIR_E | DIR_S | DIR_O
        return self.base

    @property
    def ruotabile(self):
        return self.tipo == "scambio"

    def ruota(self):
        if self.ruotabile:
            self.giri = (self.giri + 1) % 4
        return self.maschera

    def ripristina(self):
        self.giri = self.giri_iniziali

    def esce_da(self, entra):
        """Da quale lato esce un treno entrato dal lato 'entra' (None = non può proseguire)."""
        if not (self.maschera & entra):
            return None
        if self.tipo == "ponte":
            return opposta(entra)             # il ponte si attraversa sempre dritti, sopra o sotto
        resto = self.maschera & ~entra
        return resto if resto in (DIR_N, DIR_E, DIR_S, DIR_O) else None

    def quota(self, lato):
        """Altezza (0 = terra, 1 = impalcato) al bordo 'lato' della tessera, per un treno che la percorre."""
        if self.tipo == "rampa":
            return 1.0 if lato == self.alta else 0.0
        if self.tipo == "ponte":
            return 1.0 if self.asse_alto & lato else 0.0
        return 0.0


class Tratto:
    """Un passaggio del treno in una tessera: da quale lato entra e da quale esce."""

    def __init__(self, cella, entra_da, esce_verso, ferma_al_centro=False):
        self.cella = cella
        self.entra_da = entra_da             # None = la tessera di partenza (il treno parte dal centro)
        self.esce_verso = esce_verso         # None = il treno si ferma al centro della tessera
        self.ferma_al_centro = ferma_al_centro


class Corsa:
    """Risultato della simulazione: i tratti percorsi e come va a finire."""
    PLOMBIERES, INTERCETTATO, DERAGLIATO = "plombieres", "intercettato", "deragliato"

    def __init__(self, tratti, esito, motivo, fuori=None):
        self.tratti = tratti
        self.esito = esito
        self.motivo = motivo
        self.fuori = fuori                   # direzione in cui il treno lascia i binari (se deraglia)

    @property
    def vittoria(self):
        return self.esito == self.PLOMBIERES


class Griglia:
    """La rete ferroviaria: costruisce le tessere dalla mappa e simula la corsa del treno."""

    def __init__(self, righe=None, rossi=None, giri_iniziali=None):
        righe = righe or MAPPA_TRENO
        rossi = MAPPA_ROSSI if rossi is None else rossi
        giri_iniziali = GIRI_INIZIALI_TRENO if giri_iniziali is None else giri_iniziali
        self.righe = len(righe)
        self.colonne = len(righe[0])
        assert all(len(r) == self.colonne for r in righe) and len(rossi) == self.righe
        self.tessere = {}
        self.scambi = {}                     # sigla -> Tessera
        self.partenza = self.arrivo = self.vienna = None
        fisse = {"|": DIR_N | DIR_S, "-": DIR_E | DIR_O, "a": DIR_N | DIR_E, "b": DIR_E | DIR_S,
                 "c": DIR_S | DIR_O, "d": DIR_O | DIR_N}
        strade = {",": "eo", ";": "ns", "+": "inc"}
        celle_ponte, celle_rampa = {}, []
        for riga_txt, riga in enumerate(righe):
            z = self.righe - 1 - riga_txt
            for x, ch in enumerate(riga):
                cella = (x, z)
                rosso = rossi[riga_txt][x] == "#"
                if ch in fisse:
                    self.tessere[cella] = Tessera("binario", fisse[ch], rosso)
                elif ch in "1234567":
                    base = DRITTO_BASE if ch in SCAMBI_DRITTI else CURVA_BASE
                    t = Tessera("scambio", base, rosso, ch, giri_iniziali.get(ch, 0))
                    self.tessere[cella] = t
                    self.scambi[ch] = t
                elif ch == "T":
                    self.tessere[cella] = Tessera("partenza", DIR_N, rosso)
                    self.partenza = cella
                elif ch in "PQ":
                    self.tessere[cella] = Tessera("arrivo", DIR_S if ch == "P" else DIR_E, rosso)
                    self.arrivo = cella
                elif ch == "V":
                    self.tessere[cella] = Tessera("vienna", DIR_O, True)
                    self.vienna = cella
                elif ch in "hv":
                    alto = (DIR_E | DIR_O) if ch == "h" else (DIR_N | DIR_S)
                    t = Tessera("ponte", 15, rosso, asse_alto=alto)
                    self.tessere[cella] = t
                    celle_ponte[cella] = alto
                elif ch == "r":
                    celle_rampa.append(cella)
                elif ch in "xz":
                    base = (DIR_N | DIR_S) if ch == "x" else (DIR_E | DIR_O)
                    self.tessere[cella] = Tessera("binario", base, rosso, strada="eo" if ch == "x" else "ns")
                elif ch in strade:
                    self.tessere[cella] = Tessera("erba", 0, False, strada=strade[ch])
        for (x, z) in celle_rampa:             # ogni rampa guarda il ponte accanto, lungo l'asse dell'impalcato
            trovata = None
            for d in (DIR_N, DIR_E, DIR_S, DIR_O):
                vx, vz = VETTORE_DIR[d]
                alto = celle_ponte.get((x + vx, z + vz))
                if alto and alto & d:
                    trovata = d
            assert trovata, "la rampa in %s non è accanto a un ponte" % ((x, z),)
            rosso = rossi[self.righe - 1 - z][x] == "#"
            self.tessere[(x, z)] = Tessera("rampa", trovata | opposta(trovata), rosso, alta=trovata)
        assert self.partenza and self.arrivo, "la mappa deve avere una partenza e un arrivo"

    def tessera(self, x, z):
        return self.tessere.get((x, z))

    def ripristina(self):
        for t in self.scambi.values():
            t.ripristina()

    def configurazione(self):
        return {sigla: t.giri for sigla, t in self.scambi.items()}

    def imposta(self, giri):
        for sigla, n in giri.items():
            self.scambi[sigla].giri = n % 4

    def simula(self):
        """Fa partire il treno dalla stazione di Torino e segue i binari così come sono ora."""
        x, z = self.partenza
        tratti = [Tratto((x, z), None, DIR_N)]
        esce = DIR_N
        rosse = 0
        visti = set()
        for _ in range(4 * self.righe * self.colonne):
            dx, dz = VETTORE_DIR[esce]
            x, z = x + dx, z + dz
            entra = opposta(esce)
            t = self.tessere.get((x, z))
            if t is None or not (t.maschera & entra):
                if rosse:
                    return Corsa(tratti, Corsa.INTERCETTATO,
                                 "Le spie austriache ti aspettavano sui binari rossi!", fuori=esce)
                return Corsa(tratti, Corsa.DERAGLIATO, "Il treno è uscito dai binari!", fuori=esce)
            if t.rosso:
                rosse += 1
            if t.tipo == "arrivo":
                tratti.append(Tratto((x, z), entra, None, True))
                return Corsa(tratti, Corsa.PLOMBIERES, "Il treno è arrivato a Plombières!")
            if t.tipo == "vienna" or (t.rosso and rosse >= ROSSE_PRIMA_DELLO_STOP):
                tratti.append(Tratto((x, z), entra, None, True))
                return Corsa(tratti, Corsa.INTERCETTATO,
                             "Hai imboccato i binari rossi: portano dritti a Vienna!")
            chiave = ((x, z), entra)
            if chiave in visti:
                tratti.append(Tratto((x, z), entra, None, True))
                return Corsa(tratti, Corsa.INTERCETTATO, "Il treno gira in tondo: le spie lo hanno notato!")
            visti.add(chiave)
            resto = t.esce_da(entra)
            if resto is None:                                      # vicolo cieco
                tratti.append(Tratto((x, z), entra, None, True))
                esito = Corsa.INTERCETTATO if rosse else Corsa.DERAGLIATO
                return Corsa(tratti, esito, "Il binario finisce nel nulla!")
            tratti.append(Tratto((x, z), entra, resto))
            esce = resto
        return Corsa(tratti, Corsa.DERAGLIATO, "Il treno si è perso!")

    # ---- geometria del percorso (coordinate locali della mappa) ----
    def centro(self, x, z, lato):
        return ((x - (self.colonne - 1) / 2) * lato, (z - (self.righe - 1) / 2) * lato)

    def polilinea(self, corsa, lato, quota_ponte=0.0, passi_curva=8):
        """Punti (x, z, y) che il treno percorre. Restituisce (punti, indice_fine_binari).
        quota_ponte è l'altezza dell'impalcato dei ponti, nella stessa unità di 'lato'."""
        pts = []

        def aggiungi(p):
            if not pts or math.dist(p, pts[-1]) > 1e-6:
                pts.append(p)

        def bordo(c, d, y):
            vx, vz = VETTORE_DIR[d]
            return (c[0] + vx * lato / 2, c[1] + vz * lato / 2, y)

        for t in corsa.tratti:
            c = self.centro(t.cella[0], t.cella[1], lato)
            tess = self.tessere[t.cella]
            if t.entra_da is None:
                aggiungi((c[0], c[1], 0.0))
                aggiungi(bordo(c, t.esce_verso, 0.0))
            elif t.esce_verso is None:
                y_in = tess.quota(t.entra_da) * quota_ponte
                aggiungi(bordo(c, t.entra_da, y_in))
                aggiungi((c[0], c[1], y_in))
            elif t.esce_verso == opposta(t.entra_da):
                aggiungi(bordo(c, t.entra_da, tess.quota(t.entra_da) * quota_ponte))
                aggiungi(bordo(c, t.esce_verso, tess.quota(t.esce_verso) * quota_ponte))
            else:                                   # curva: quarto di cerchio attorno allo spigolo
                ve, vu = VETTORE_DIR[t.entra_da], VETTORE_DIR[t.esce_verso]
                k = (c[0] + (ve[0] + vu[0]) * lato / 2, c[1] + (ve[1] + vu[1]) * lato / 2)
                r = lato / 2
                for i in range(passi_curva + 1):
                    f = (math.pi / 2) * i / passi_curva
                    aggiungi((k[0] - vu[0] * r * math.cos(f) - ve[0] * r * math.sin(f),
                              k[1] - vu[1] * r * math.cos(f) - ve[1] * r * math.sin(f), 0.0))
        fine = len(pts) - 1
        if corsa.fuori is not None:               # deraglia: prosegue dritto sull'erba per un po'
            vx, vz = VETTORE_DIR[corsa.fuori]
            ultimo = pts[-1]
            aggiungi((ultimo[0] + vx * lato * .55, ultimo[1] + vz * lato * .55, 0.0))
        return pts, fine


# --------------------------------------------------------------------------
# Font di sistema (con ripiego automatico)
# --------------------------------------------------------------------------
def _trova_font(tipo):
    win = os.environ.get("WINDIR", "C:/Windows") + "/Fonts/"
    mac = "/System/Library/Fonts/Supplemental/"
    dj = "/usr/share/fonts/truetype/dejavu/"
    lib = "/usr/share/fonts/truetype/liberation/"
    free = "/usr/share/fonts/truetype/freefont/"
    candidati = {
        "r": [win + "georgia.ttf", mac + "Georgia.ttf", "/Library/Fonts/Georgia.ttf", win + "times.ttf",
              mac + "Times New Roman.ttf", dj + "DejaVuSerif.ttf", lib + "LiberationSerif-Regular.ttf",
              "/usr/share/fonts/TTF/DejaVuSerif.ttf", "/usr/share/fonts/dejavu/DejaVuSerif.ttf", free + "FreeSerif.ttf"],
        "b": [win + "georgiab.ttf", mac + "Georgia Bold.ttf", "/Library/Fonts/Georgia Bold.ttf", win + "timesbd.ttf",
              mac + "Times New Roman Bold.ttf", dj + "DejaVuSerif-Bold.ttf", lib + "LiberationSerif-Bold.ttf",
              "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSerif-Bold.ttf",
              free + "FreeSerifBold.ttf"],
        "i": [win + "georgiai.ttf", mac + "Georgia Italic.ttf", "/Library/Fonts/Georgia Italic.ttf", win + "timesi.ttf",
              mac + "Times New Roman Italic.ttf", dj + "DejaVuSerif-Italic.ttf", lib + "LiberationSerif-Italic.ttf",
              "/usr/share/fonts/TTF/DejaVuSerif-Italic.ttf", "/usr/share/fonts/dejavu/DejaVuSerif-Italic.ttf",
              free + "FreeSerifItalic.ttf"],
    }
    for p in candidati[tipo]:
        if os.path.isfile(p):
            return p
    return None


FONT_FILE = {k: _trova_font(k) for k in "rbi"}


_FONT_UI = {}


class RigheCentrate(Entity):
    """Testo su più righe, ciascuna centrata (un solo Text a più righe le allinea a sinistra e il blocco risulta sfasato).
    Ha 'text' e 'width' come un Text, così si fa adattare allo stesso modo."""

    def __init__(self, parent, pos, scala, col, tipo="r", z=0):
        super().__init__(parent=parent, position=(pos[0], pos[1], z), scale=scala)
        self.col, self.tipo = col, tipo
        self.righe = []
        self._testo = ""

    @property
    def text(self):
        return self._testo

    @text.setter
    def text(self, valore):
        self._testo = valore
        for r in self.righe:
            r.enabled = False
            destroy(r)
        self.righe = []
        parti = str(valore).split("\n") if valore else []
        for i, riga in enumerate(parti):
            y = ((len(parti) - 1) / 2 - i) * ALTEZZA_RIGA
            self.righe.append(testo_ui(self, riga, (0, y), 1.0, self.col, self.tipo))

    @property
    def width(self):
        return max((r.width for r in self.righe), default=0)


def font_ui(tipo):
    """Percorso del font per Ursina, già verificato (None = font predefinito di Ursina)."""
    if tipo not in _FONT_UI:
        _FONT_UI[tipo] = None
        for p in (FONT_FILE[tipo], FONT_FILE["r"]):
            if not p:
                continue
            try:
                # realpath restituisce il percorso con le maiuscole corrette
                percorso = Filename.fromOsSpecific(os.path.realpath(p)).getFullpath()
                loader.loadFont(percorso)          # solleva un errore se Panda3D non riesce a leggerlo
                _FONT_UI[tipo] = percorso
                break
            except Exception as ex:
                print("Font non caricabile, uso un ripiego:", p, ex)
    return _FONT_UI[tipo]


_PIL_FONT = {}


def font_pil(tipo, size):
    key = (tipo, size)
    if key not in _PIL_FONT:
        p = FONT_FILE[tipo] or FONT_FILE["r"]
        try:
            _PIL_FONT[key] = ImageFont.truetype(p, size) if p else ImageFont.load_default(size)
        except Exception:
            _PIL_FONT[key] = ImageFont.load_default()
    return _PIL_FONT[key]


# --------------------------------------------------------------------------
# Texture procedurali (PIL)
# --------------------------------------------------------------------------
def tex(img, filtering="mipmap"):
    return Texture(img.convert("RGBA"), filtering=filtering)


def _mescola(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _gradiente(w, h, alto, basso):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_mescola(alto, basso, y / max(1, h - 1)))
    return img


def _macchie(img, n, col, rmin, rmax, alpha, seme):
    rnd = random.Random(seme)
    strato = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(strato)
    for _ in range(n):
        r = rnd.randint(rmin, rmax)
        x, y = rnd.randint(0, img.size[0]), rnd.randint(0, img.size[1])
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (alpha,))
    strato = strato.filter(ImageFilter.GaussianBlur(max(2, rmin // 2)))
    base = img.convert("RGBA")
    base.alpha_composite(strato)
    return base


def _rumore(img, forza, seme):
    rnd = random.Random(seme)
    px = img.load()
    w, h = img.size
    for _ in range(w * h // 3):
        x, y = rnd.randrange(w), rnd.randrange(h)
        c = px[x, y]
        k = rnd.randint(-forza, forza)
        px[x, y] = tuple(max(0, min(255, v + k)) for v in c[:3]) + tuple(c[3:])
    return img


def img_carta_da_parati():
    w = h = 256
    img = Image.new("RGB", (w, h), (84, 20, 32))
    d = ImageDraw.Draw(img)
    for x in range(0, w, 32):
        d.line([(x, 0), (x, h)], fill=(90, 23, 36), width=10)
    for cx, cy in ((64, 64), (192, 192), (192, 64), (64, 192)):
        grande = (cx, cy) in ((64, 64), (192, 192))
        s = 46 if grande else 22
        d.polygon([(cx, cy - s), (cx + s * 0.62, cy), (cx, cy + s), (cx - s * 0.62, cy)], fill=(106, 28, 42))
        d.polygon([(cx, cy - s), (cx + s * 0.62, cy), (cx, cy + s), (cx - s * 0.62, cy)], outline=(140, 104, 40))
        if grande:
            for dx in (-1, 1):
                d.ellipse((cx + dx * 18 - 9, cy - 22, cx + dx * 18 + 9, cy - 4), fill=(118, 34, 48))
                d.ellipse((cx + dx * 18 - 9, cy + 4, cx + dx * 18 + 9, cy + 22), fill=(118, 34, 48))
            d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=(150, 112, 42))
        else:
            d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(150, 112, 42))
    return _rumore(img, 8, 1)


def img_parquet():
    w = h = 512
    rnd = random.Random(11)
    img = Image.new("RGB", (w, h), (70, 44, 26))
    d = ImageDraw.Draw(img)
    for riga in range(8):
        y0 = riga * 64
        x = -rnd.randint(0, 200)
        while x < w:
            lung = rnd.randint(140, 280)
            base = (rnd.randint(78, 104), rnd.randint(48, 64), rnd.randint(28, 38))
            d.rectangle((x, y0, x + lung, y0 + 63), fill=base)
            for k in range(14):
                yy = y0 + 3 + k * 4 + rnd.randint(-1, 1)
                scuro = tuple(max(0, v - rnd.randint(8, 22)) for v in base)
                pts = [(xx, yy + 1.5 * math.sin(xx / rnd.uniform(18, 40) + k)) for xx in range(x, x + lung, 8)]
                if len(pts) > 1:
                    d.line(pts, fill=scuro, width=1)
            d.line([(x, y0), (x, y0 + 63)], fill=(26, 16, 10), width=2)
            x += lung
        d.line([(0, y0), (w, y0)], fill=(24, 14, 8), width=2)
    return _rumore(img, 10, 2)


def img_legno(base=(64, 38, 22), seme=3):
    w = h = 256
    rnd = random.Random(seme)
    img = Image.new("RGB", (w, h), base)
    d = ImageDraw.Draw(img)
    for _ in range(120):
        x = rnd.randint(0, w)
        k = rnd.randint(6, 26)
        col = tuple(max(0, v - k) for v in base)
        pts = [(x + 3 * math.sin(y / rnd.uniform(14, 30)), y) for y in range(0, h + 8, 8)]
        d.line(pts, fill=col, width=rnd.choice((1, 1, 2)))
    return _rumore(img, 6, seme)


def img_boiserie():
    w, h = 512, 256
    img = img_legno((74, 46, 27), 5).resize((w, h))
    d = ImageDraw.Draw(img)
    for x0 in (24, 280):
        r = (x0, 30, x0 + 208, 226)
        d.rectangle(r, outline=(40, 24, 14), width=4)
        d.line([(r[0] + 6, r[1] + 6), (r[2] - 6, r[1] + 6)], fill=(112, 76, 46), width=3)
        d.line([(r[0] + 6, r[1] + 6), (r[0] + 6, r[3] - 6)], fill=(112, 76, 46), width=3)
        d.line([(r[0] + 6, r[3] - 6), (r[2] - 6, r[3] - 6)], fill=(36, 20, 12), width=3)
        d.line([(r[2] - 6, r[1] + 6), (r[2] - 6, r[3] - 6)], fill=(36, 20, 12), width=3)
    return img


def img_pietra():
    w = h = 256
    rnd = random.Random(21)
    img = Image.new("RGB", (w, h), (60, 58, 58))
    d = ImageDraw.Draw(img)
    for riga in range(6):
        y0 = riga * 43
        off = 0 if riga % 2 else -40
        for x0 in range(off, w, 80):
            t = rnd.randint(-14, 14)
            d.rectangle((x0 + 2, y0 + 2, x0 + 78, y0 + 41), fill=(112 + t, 108 + t, 104 + t))
    return _rumore(img, 16, 22)


def img_pergamena(w, h, bordo=True, seme=1860):
    img = _gradiente(w, h, (240, 228, 198), (206, 186, 146))
    img = _macchie(img, 26, (150, 116, 70), w // 40, w // 12, 40, seme)
    # bordi bruciati
    strato = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(strato)
    for i in range(22):
        d.rectangle((i, i, w - 1 - i, h - 1 - i), outline=(96, 60, 24, int(90 * (1 - i / 22) ** 2)))
    img.alpha_composite(strato)
    if bordo:
        d = ImageDraw.Draw(img)
        d.rectangle((10, 10, w - 11, h - 11), outline=(120, 24, 40), width=6)
        d.rectangle((24, 24, w - 25, h - 25), outline=(140, 108, 30), width=2)
        for (x, y, sx, sy) in ((34, 34, 1, 1), (w - 35, 34, -1, 1), (34, h - 35, 1, -1), (w - 35, h - 35, -1, -1)):
            d.line([(x, y), (x + sx * 40, y)], fill=(120, 24, 40), width=4)
            d.line([(x, y), (x, y + sy * 40)], fill=(120, 24, 40), width=4)
            d.ellipse((x + sx * 10 - 4, y + sy * 10 - 4, x + sx * 10 + 4, y + sy * 10 + 4), fill=(120, 24, 40))
    return img


ITALIA = [(0.18, 0.12), (0.30, 0.06), (0.45, 0.09), (0.58, 0.05), (0.67, 0.10), (0.62, 0.17),
          (0.60, 0.23), (0.63, 0.31), (0.70, 0.42), (0.79, 0.51), (0.86, 0.55), (0.90, 0.54),
          (0.89, 0.60), (0.96, 0.67), (0.99, 0.74), (0.93, 0.72), (0.85, 0.66), (0.81, 0.69),
          (0.83, 0.77), (0.77, 0.87), (0.72, 0.84), (0.74, 0.75), (0.67, 0.65), (0.57, 0.57),
          (0.47, 0.47), (0.39, 0.37), (0.33, 0.29), (0.27, 0.24), (0.22, 0.25), (0.15, 0.27),
          (0.12, 0.20)]
SICILIA = [(0.56, 0.86), (0.66, 0.87), (0.75, 0.86), (0.72, 0.96), (0.60, 0.92)]
SARDEGNA = [(0.26, 0.51), (0.32, 0.51), (0.34, 0.60), (0.32, 0.72), (0.27, 0.71), (0.25, 0.61)]
CORSICA = [(0.28, 0.38), (0.31, 0.37), (0.32, 0.44), (0.29, 0.48), (0.27, 0.43)]


def img_mappa():
    w, h = 1024, 720
    img = img_pergamena(w, h, bordo=False, seme=7)
    d = ImageDraw.Draw(img)
    area = (40, 40, 680, 680)

    def P(pts):
        return [(area[0] + x * (area[2] - area[0]), area[1] + y * (area[3] - area[1])) for x, y in pts]

    for isola in (ITALIA, SICILIA, SARDEGNA, CORSICA):
        for k in range(4, 0, -1):     # tratteggio costiero
            d.polygon(P(isola), outline=(150, 136, 110))
        d.polygon(P(isola), fill=(200, 172, 122), outline=(60, 40, 26))
    for nome, (x, y) in (("Torino", (0.14, 0.17)), ("Genova", (0.22, 0.25)), ("Roma", (0.50, 0.45)),
                         ("Napoli", (0.62, 0.56)), ("Palermo", (0.64, 0.87)), ("Marsala", (0.565, 0.885))):
        px, py = P([(x, y)])[0]
        d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(60, 40, 26))
        d.text((px + 8, py - 10), nome, font=font_pil("i", 20), fill=(60, 40, 26))
    # rotta dei Mille: Quarto -> Talamone -> Marsala
    tappe = P([(0.23, 0.27), (0.36, 0.33), (0.41, 0.39), (0.42, 0.55), (0.47, 0.72), (0.54, 0.84), (0.565, 0.88)])
    punti = []
    for i in range(len(tappe) - 1):
        for s in range(12):
            u = s / 12
            punti.append((tappe[i][0] + (tappe[i + 1][0] - tappe[i][0]) * u,
                          tappe[i][1] + (tappe[i + 1][1] - tappe[i][1]) * u))
    for i in range(0, len(punti) - 1, 2):
        d.line([punti[i], punti[i + 1]], fill=(150, 24, 36), width=4)
    qx, qy = tappe[0]
    d.ellipse((qx - 9, qy - 9, qx + 9, qy + 9), outline=(150, 24, 36), width=3)
    d.text((qx - 90, qy + 4), "Quarto", font=font_pil("b", 22), fill=(150, 24, 36))
    d.text(P([(0.08, 0.55)])[0], "Mar Tirreno", font=font_pil("i", 24), fill=(90, 80, 70))
    d.text(P([(0.74, 0.30)])[0], "Mar\nAdriatico", font=font_pil("i", 22), fill=(90, 80, 70))
    # cartiglio
    d.rectangle((712, 60, 990, 300), outline=(120, 24, 40), width=4)
    d.rectangle((722, 70, 980, 290), outline=(140, 108, 30), width=1)
    d.text((851, 110), "ITALIA", font=font_pil("b", 44), fill=(68, 12, 24), anchor="mm")
    d.text((851, 160), "Anno 1860", font=font_pil("i", 28), fill=(60, 40, 26), anchor="mm")
    d.text((851, 215), "La Spedizione", font=font_pil("r", 24), fill=(60, 40, 26), anchor="mm")
    d.text((851, 248), "dei Mille", font=font_pil("r", 24), fill=(60, 40, 26), anchor="mm")
    # nave
    nx, ny = 850, 420
    d.polygon([(nx - 80, ny), (nx + 80, ny), (nx + 55, ny + 34), (nx - 55, ny + 34)], fill=(60, 40, 26))
    for mx in (nx - 30, nx + 30):
        d.line([(mx, ny), (mx, ny - 110)], fill=(60, 40, 26), width=4)
        d.polygon([(mx + 3, ny - 104), (mx + 48, ny - 60), (mx + 3, ny - 30)], fill=(236, 226, 200), outline=(60, 40, 26))
    d.line([(nx - 30, ny - 110), (nx - 30, ny - 130)], fill=(60, 40, 26), width=2)
    for i, c in enumerate(((0, 146, 70), (244, 245, 240), (206, 43, 55))):
        d.rectangle((nx - 30 + i * 10, ny - 132, nx - 20 + i * 10, ny - 118), fill=c)
    d.text((nx, ny + 64), "Piroscafi «Piemonte» e «Lombardo»", font=font_pil("i", 19), fill=(60, 40, 26), anchor="mm")
    # rosa dei venti
    rc = (860, 590)
    for k in range(8):
        ang = k * math.pi / 4
        lung = 70 if k % 2 == 0 else 38
        punta = (rc[0] + math.cos(ang) * lung, rc[1] + math.sin(ang) * lung)
        l1 = (rc[0] + math.cos(ang + 0.35) * 14, rc[1] + math.sin(ang + 0.35) * 14)
        l2 = (rc[0] + math.cos(ang - 0.35) * 14, rc[1] + math.sin(ang - 0.35) * 14)
        d.polygon([punta, l1, rc, l2], fill=(150, 24, 36) if k == 6 else (60, 40, 26))
    d.text((rc[0], rc[1] - 90), "N", font=font_pil("b", 26), fill=(150, 24, 36), anchor="mm")
    d.rectangle((12, 12, w - 13, h - 13), outline=(60, 40, 26), width=5)
    d.rectangle((24, 24, w - 25, h - 25), outline=(60, 40, 26), width=1)
    return img


def img_ritratto():
    w, h = 512, 640
    img = _gradiente(w, h, (74, 44, 34), (22, 14, 14))
    d = ImageDraw.Draw(img)
    # drappo
    d.polygon([(0, 0), (150, 0), (110, 260), (40, 640), (0, 640)], fill=(96, 18, 30))
    for k in range(6):
        d.line([(20 + k * 22, 0), (10 + k * 14, 640)], fill=(70, 10, 20), width=5)
    cx = w // 2
    # busto in uniforme
    d.ellipse((cx - 230, 470, cx + 230, 900), fill=(28, 34, 66))
    d.polygon([(cx - 150, 520), (cx + 170, 700), (cx + 120, 720), (cx - 170, 560)], fill=(110, 160, 220))  # fascia azzurra
    for sx in (-1, 1):
        d.ellipse((cx + sx * 170 - 55, 470, cx + sx * 170 + 55, 520), fill=(212, 175, 55))
        for k in range(7):
            d.line([(cx + sx * 170 - 48 + k * 16, 505), (cx + sx * 170 - 52 + k * 16, 548)], fill=(212, 175, 55), width=4)
    d.polygon([(cx - 36, 450), (cx + 36, 450), (cx, 540)], fill=(236, 232, 220))
    for i, mx in enumerate((cx - 110, cx - 70, cx + 60)):
        d.ellipse((mx - 13, 600, mx + 13, 626), fill=(212, 175, 55) if i != 1 else (200, 200, 210))
        d.rectangle((mx - 8, 580, mx + 8, 600), fill=(206, 43, 55) if i != 1 else (0, 120, 70))
    # collo e testa
    d.rectangle((cx - 40, 380, cx + 40, 470), fill=(170, 124, 94))
    d.ellipse((cx - 100, 170, cx + 100, 430), fill=(198, 152, 116))
    d.ellipse((cx - 70, 190, cx + 40, 330), fill=(212, 170, 134))
    d.ellipse((cx - 108, 140, cx + 108, 250), fill=(42, 30, 22))          # capelli
    d.rectangle((cx - 108, 196, cx - 88, 300), fill=(42, 30, 22))
    d.rectangle((cx + 88, 196, cx + 108, 300), fill=(42, 30, 22))
    for sx in (-1, 1):
        d.ellipse((cx + sx * 42 - 16, 268, cx + sx * 42 + 16, 286), fill=(250, 244, 236))
        d.ellipse((cx + sx * 42 - 7, 270, cx + sx * 42 + 7, 284), fill=(40, 28, 20))
        d.line([(cx + sx * 20, 250), (cx + sx * 66, 246)], fill=(42, 30, 22), width=7)
    d.polygon([(cx - 8, 290), (cx + 8, 290), (cx + 18, 340), (cx - 16, 340)], fill=(176, 128, 96))
    # i celebri baffoni all'insù e il pizzetto
    for sx in (-1, 1):
        d.polygon([(cx, 352), (cx + sx * 40, 344), (cx + sx * 110, 318), (cx + sx * 150, 270),
                   (cx + sx * 138, 316), (cx + sx * 80, 366), (cx + sx * 20, 372)], fill=(40, 28, 20))
    d.polygon([(cx - 26, 380), (cx + 26, 380), (cx + 12, 440), (cx, 456), (cx - 12, 440)], fill=(40, 28, 20))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    # pennellate e craquelure
    rnd = random.Random(1849)
    strato = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ds = ImageDraw.Draw(strato)
    for _ in range(900):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        ang = rnd.uniform(0, math.pi)
        l = rnd.randint(6, 18)
        ds.line([(x, y), (x + math.cos(ang) * l, y + math.sin(ang) * l)],
                fill=(255, 240, 210, 12) if rnd.random() < .5 else (0, 0, 0, 16), width=2)
    for _ in range(60):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        pts = [(x, y)]
        for _ in range(4):
            x += rnd.randint(-22, 22)
            y += rnd.randint(-22, 22)
            pts.append((x, y))
        ds.line(pts, fill=(20, 12, 8, 40), width=1)
    img = img.convert("RGBA")
    img.alpha_composite(strato)
    # vignettatura
    v = Image.new("L", (w, h), 0)
    ImageDraw.Draw(v).ellipse((-60, -40, w + 60, h + 40), fill=255)
    v = v.filter(ImageFilter.GaussianBlur(70))
    nero = Image.new("RGBA", (w, h), (8, 4, 4, 255))
    return Image.composite(img, nero, v)


def img_spartito():
    """Spartito dell'inizio del Canto degli Italiani, con il nome di ogni nota."""
    w, h = 768, 512
    img = img_pergamena(w, h, bordo=False, seme=3)
    d = ImageDraw.Draw(img)
    ink = (30, 20, 14)
    d.text((w // 2, 44), "Il Canto degli Italiani", font=font_pil("i", 50), fill=ink, anchor="mm")
    d.text((w // 2, 92), "M. Novaro  ·  Torino, 1847", font=font_pil("r", 24), fill=(90, 60, 40), anchor="mm")
    gradini = {62: -1, 64: 0, 67: 2, 69: 3, 71: 4, 72: 5, 74: 6}     # posizione sul rigo (Mi4 = 1ª riga)
    passo = 11
    for riga in range(2):
        base = 250 + riga * 190                                     # y della riga più bassa
        for k in range(5):
            d.line([(40, base - k * 2 * passo), (w - 40, base - k * 2 * passo)], fill=(80, 60, 44), width=2)
        d.text((56, base - 8 * passo), "#", font=font_pil("b", 30), fill=ink, anchor="mm")   # Fa diesis
        for b in (4,):
            x = 110 + b * 78 - 39
            d.line([(x, base), (x, base - 8 * passo)], fill=(80, 60, 44), width=2)
        d.line([(w - 42, base), (w - 42, base - 8 * passo)], fill=(80, 60, 44), width=3)
        for k in range(8):
            nome, midi = INNO[riga * 8 + k]
            x = 110 + k * 78 + (20 if k >= 4 else 0)
            y = base - gradini[midi] * passo
            if gradini[midi] < 0:
                d.line([(x - 20, base + 2 * passo), (x + 20, base + 2 * passo)], fill=ink, width=2)
            d.ellipse((x - 13, y - 10, x + 13, y + 10), fill=ink)
            if gradini[midi] < 4:
                d.line([(x + 12, y), (x + 12, y - 70)], fill=ink, width=3)
            else:
                d.line([(x - 12, y), (x - 12, y + 70)], fill=ink, width=3)
            d.text((x, base + 58), nome, font=font_pil("b", 28), fill=(120, 24, 40), anchor="mm")
    return img


def img_lettera():
    w, h = 320, 420
    img = img_pergamena(w, h, bordo=False, seme=9)
    d = ImageDraw.Draw(img)
    d.text((34, 40), "Mon cher ami,", font=font_pil("i", 30), fill=(40, 30, 50))
    rnd = random.Random(8)
    for r in range(10):
        y = 100 + r * 26
        x = 34 + (30 if r == 0 else 0)
        fine = w - 34 - rnd.randint(0, 60)
        pts = []
        while x < fine:
            pts.append((x, y + 5 * math.sin(x * 0.35 + r) + rnd.uniform(-1.5, 1.5)))
            x += 4
        d.line(pts, fill=(50, 40, 70), width=2)
    d.text((w - 50, h - 60), "C.", font=font_pil("i", 34), fill=(40, 30, 50), anchor="mm")
    d.ellipse((40, h - 90, 100, h - 30), fill=(130, 20, 36))
    d.ellipse((52, h - 78, 88, h - 42), outline=(90, 10, 22), width=3)
    return img


# --- Mappamondo -------------------------------------------------------------
# Coste semplificate in (longitudine, latitudine): l'Europa e il Mediterraneo sono più dettagliati del resto del mondo.
COSTA_EURASIA = [
    # Gibilterra -> costa mediterranea di Spagna e Francia
    (-5.6, 36.0), (-4.4, 36.7), (-2.1, 36.7), (-0.7, 37.6), (0.2, 38.8), (-0.3, 39.5), (0.9, 40.8), (2.2, 41.4),
    (3.2, 42.2), (3.0, 43.2), (4.2, 43.5), (4.8, 43.4), (5.4, 43.25), (6.2, 43.1), (7.3, 43.7),
    # Liguria e Italia tirrenica
    (7.8, 43.8), (8.8, 44.4), (9.8, 44.05), (10.3, 43.5), (10.6, 42.95), (11.1, 42.4), (12.2, 41.75), (13.5, 41.2),
    (14.25, 40.83), (14.75, 40.6), (15.0, 40.0), (15.7, 39.5), (15.8, 38.9), (15.65, 38.2), (16.1, 37.95),
    # Calabria ionica, golfo di Taranto, Salento, Puglia, Adriatico
    (16.6, 38.4), (17.15, 39.0), (16.6, 39.7), (16.6, 40.1), (17.2, 40.45), (18.0, 40.1), (18.4, 39.8),
    (18.5, 40.15), (17.9, 40.65), (16.9, 41.1), (16.0, 41.45), (16.2, 41.9), (15.2, 41.95), (14.2, 42.5),
    (13.6, 43.55), (12.6, 44.1), (12.3, 44.9), (12.35, 45.45), (13.1, 45.75), (13.75, 45.65),
    # Istria, Dalmazia, Albania, Grecia
    (13.6, 45.2), (13.9, 44.8), (14.5, 45.3), (15.2, 44.2), (16.4, 43.5), (17.5, 43.0), (18.1, 42.65), (18.7, 42.3),
    (19.4, 41.9), (19.4, 41.3), (19.4, 40.4), (20.0, 39.7), (20.7, 39.0), (21.1, 38.3), (21.6, 37.9), (21.7, 36.8),
    (22.4, 36.4), (22.8, 36.8), (23.2, 36.4), (23.1, 37.3), (23.7, 37.9), (24.05, 37.7), (24.1, 38.2),
    (23.0, 39.0), (22.6, 40.0), (22.9, 40.6), (23.7, 40.2), (23.9, 40.7), (24.4, 40.9), (26.0, 40.8),
    (26.2, 40.35),
    # Dardanelli -> costa egea e meridionale della Turchia, Levante, Sinai
    (26.4, 40.1), (26.1, 39.5), (26.9, 39.3), (26.3, 38.3), (27.1, 38.4), (27.3, 37.0), (28.2, 36.7), (29.6, 36.2),
    (30.6, 36.8), (32.3, 36.1), (34.0, 36.3), (34.6, 36.8), (36.0, 36.6), (35.8, 35.5), (35.5, 34.0),
    (34.8, 32.1), (34.3, 31.3), (32.6, 31.05), (32.5, 29.9), (33.6, 28.3), (34.3, 27.8), (34.95, 29.5),
    # Penisola arabica
    (35.2, 28.0), (37.2, 24.2), (39.2, 21.5), (40.8, 19.0), (42.7, 15.5), (43.4, 12.7), (45.0, 12.8), (48.5, 14.0),
    (52.2, 15.6), (55.0, 17.0), (57.8, 19.0), (59.8, 22.5), (58.6, 23.6), (56.6, 24.5), (56.4, 26.3), (56.0, 25.0),
    (54.4, 24.3), (51.6, 24.2), (51.6, 25.9), (50.6, 25.0), (50.1, 26.3), (48.6, 27.9), (47.9, 29.4), (48.5, 30.0),
    # Iran, Pakistan, India
    (50.8, 28.9), (51.4, 27.9), (54.0, 26.6), (56.3, 27.2), (57.3, 25.8), (61.6, 25.2), (66.5, 25.4), (67.0, 24.8),
    (68.4, 23.6), (69.0, 22.4), (70.3, 20.9), (72.6, 21.2), (72.8, 19.0), (73.8, 15.5), (74.8, 12.9), (76.3, 9.9),
    (77.5, 8.1), (78.2, 8.9), (79.8, 10.3), (80.2, 13.1), (82.3, 16.9), (84.9, 19.2), (86.5, 20.0), (87.9, 21.7),
    (90.5, 22.0), (92.3, 21.0), (94.2, 18.8), (94.3, 16.0), (97.6, 16.5), (98.5, 13.0), (98.3, 9.5), (98.5, 8.0),
    # Indocina, Cina, Corea
    (100.3, 6.0), (101.3, 2.8), (103.8, 1.3), (103.4, 4.0), (102.2, 6.2), (100.5, 7.0), (99.2, 10.0), (100.5, 13.5),
    (101.0, 12.6), (103.0, 11.0), (104.8, 8.6), (106.7, 10.3), (109.3, 12.0), (108.9, 15.3), (106.0, 18.0),
    (106.7, 20.0), (108.0, 21.5), (109.8, 21.5), (110.5, 21.2), (114.2, 22.3), (117.0, 23.5), (119.5, 26.0),
    (121.5, 28.5), (121.9, 31.0), (120.3, 34.0), (119.2, 34.6), (120.3, 36.0), (122.6, 37.4), (119.5, 37.1),
    (117.7, 38.9), (118.0, 39.2), (121.2, 38.8), (121.6, 40.0), (124.0, 39.8), (125.1, 39.6), (126.6, 37.5),
    (126.5, 34.5), (129.0, 35.1), (129.5, 36.0), (129.4, 37.5), (128.4, 38.8), (129.7, 41.0), (130.7, 42.3),
    # Siberia orientale, Kamchatka, Chukotka
    (131.9, 43.1), (135.4, 43.8), (138.0, 45.5), (140.5, 48.5), (141.0, 52.9), (137.5, 54.0), (135.1, 54.5),
    (138.5, 56.5), (143.0, 59.3), (148.0, 59.4), (152.0, 59.2), (156.0, 57.5), (156.7, 51.0), (158.5, 52.9),
    (162.0, 56.0), (163.0, 59.5), (166.0, 60.3), (172.0, 61.0), (177.0, 62.5), (179.9, 64.5),
    # costa artica (da est a ovest)
    (179.9, 68.9), (170.0, 70.0), (160.0, 69.5), (150.0, 71.5), (140.0, 72.5), (130.0, 71.0), (113.0, 73.5),
    (105.0, 77.5), (95.0, 76.0), (87.0, 74.0), (80.0, 73.5), (73.0, 72.5), (68.0, 69.0), (60.0, 69.0), (53.0, 68.0),
    (44.0, 68.5), (43.5, 66.3), (40.0, 64.6), (37.5, 64.0), (35.0, 64.5), (34.5, 66.0), (37.0, 66.2), (41.0, 67.8),
    (33.0, 69.3), (28.5, 70.9), (25.8, 71.1),
    # Norvegia, Svezia, golfo di Botnia, Finlandia, Baltico
    (21.0, 70.2), (18.9, 69.8), (16.0, 68.6), (14.4, 67.3), (13.0, 66.0), (11.0, 64.5), (10.4, 63.4), (7.0, 62.7),
    (5.0, 62.0), (5.3, 60.4), (5.6, 58.9), (6.5, 58.1), (8.0, 58.0), (9.5, 58.9), (10.7, 59.9), (11.2, 59.1),
    (11.9, 57.7), (12.6, 56.1), (12.9, 55.6), (14.3, 55.6), (14.6, 56.1), (16.4, 56.7), (16.6, 57.8), (18.1, 59.3),
    (18.7, 60.0), (17.1, 61.0), (17.3, 62.4), (20.3, 63.8), (22.2, 65.6), (24.2, 65.8), (25.4, 65.0), (21.6, 63.1),
    (21.5, 61.0), (22.3, 60.0), (25.0, 60.2), (28.0, 60.5), (30.3, 59.9), (28.0, 59.5), (24.7, 59.4), (23.6, 58.9),
    (24.1, 57.0), (22.0, 57.6), (21.0, 56.5), (21.1, 55.7), (21.0, 55.3), (19.9, 54.9), (18.6, 54.4), (16.0, 54.3),
    (14.2, 53.9), (12.1, 54.2), (10.9, 54.0),
    # Danimarca, Mare del Nord, Francia atlantica, Spagna e Portogallo
    (10.9, 56.4), (10.6, 57.7), (8.2, 56.7), (8.6, 55.5), (8.9, 54.0), (8.5, 53.6), (7.0, 53.6), (5.5, 53.4),
    (4.7, 52.9), (4.2, 51.9), (3.2, 51.3), (1.6, 50.9), (1.6, 50.2), (0.2, 49.5), (-1.2, 49.4), (-1.9, 49.7),
    (-1.6, 48.6), (-3.5, 48.8), (-4.8, 48.4), (-4.5, 47.8), (-2.2, 47.2), (-1.2, 46.0), (-1.2, 44.6), (-1.8, 43.4),
    (-3.8, 43.5), (-5.8, 43.6), (-8.0, 43.7), (-9.3, 43.0), (-8.8, 41.0), (-9.5, 38.8), (-8.8, 37.0), (-7.4, 37.2),
    (-6.3, 36.8),
]
COSTA_AFRICA = [
    (-5.8, 35.8), (-5.3, 35.9), (-2.0, 35.1), (-0.6, 35.7), (1.5, 36.5), (3.0, 36.8), (5.0, 36.7), (6.9, 36.9),
    (8.6, 36.9), (9.9, 37.3), (10.2, 36.8), (11.0, 37.1), (10.6, 36.4), (11.1, 35.2), (10.8, 34.7), (10.1, 33.9),
    (11.1, 33.2), (13.2, 32.9), (15.1, 32.4), (15.6, 31.4), (17.5, 31.0), (19.0, 30.3), (20.1, 31.0), (20.1, 32.1),
    (21.6, 32.9), (23.0, 32.6), (24.0, 32.1), (25.2, 31.6), (27.3, 31.4), (29.9, 31.2), (31.0, 31.6), (32.3, 31.3),
    (32.5, 29.9), (33.6, 27.2), (34.6, 25.5), (35.6, 23.9), (37.2, 21.0), (37.4, 19.0), (38.6, 18.0), (39.5, 15.6),
    (41.5, 13.9), (43.3, 12.5), (43.1, 11.6), (44.5, 10.4), (48.0, 11.2), (51.2, 11.8), (51.3, 10.4), (50.8, 9.0),
    (49.0, 6.0), (47.0, 4.0), (44.0, 1.5), (42.0, -1.0), (40.0, -3.0), (39.7, -4.0), (39.3, -6.8), (40.4, -10.4),
    (40.7, -14.5), (39.0, -17.0), (34.8, -19.8), (35.5, -22.0), (35.5, -24.0), (32.9, -26.0), (32.5, -28.6),
    (31.0, -29.9), (28.0, -32.7), (25.6, -34.0), (20.0, -34.8), (18.4, -34.0), (17.9, -32.0), (16.5, -28.6),
    (15.2, -26.6), (14.5, -22.9), (12.0, -18.5), (11.8, -17.0), (13.4, -12.0), (13.3, -8.8), (12.2, -6.0),
    (11.8, -4.8), (9.3, -1.0), (9.6, 2.5), (9.4, 3.9), (8.5, 4.5), (6.0, 4.3), (3.4, 6.4), (1.2, 6.1), (-2.0, 4.8),
    (-4.0, 5.2), (-7.5, 4.4), (-9.5, 5.5), (-11.5, 6.9), (-13.2, 8.5), (-15.0, 11.0), (-16.8, 12.5), (-17.5, 14.7),
    (-16.5, 16.0), (-16.0, 18.0), (-17.1, 21.0), (-16.0, 23.7), (-14.5, 26.1), (-13.2, 27.7), (-11.0, 28.6),
    (-9.8, 29.9), (-9.6, 30.4), (-9.8, 31.5), (-8.5, 33.3), (-7.6, 33.6), (-6.8, 34.0), (-6.2, 35.1),
]
COSTA_NORD_AMERICA = [
    (-168.0, 65.6), (-166.0, 68.9), (-156.8, 71.3), (-141.0, 69.6), (-128.0, 70.0), (-115.0, 68.5), (-95.0, 68.0),
    (-90.0, 69.0), (-82.0, 68.0), (-81.0, 64.0), (-77.0, 62.5), (-70.0, 60.0), (-64.5, 60.3), (-61.0, 56.0),
    (-56.0, 52.0), (-59.0, 48.0), (-64.2, 48.8), (-66.0, 45.0), (-70.0, 43.8), (-70.6, 42.6), (-70.0, 41.6),
    (-74.0, 40.6), (-75.5, 38.5), (-75.5, 35.2), (-81.0, 31.8), (-80.1, 26.5), (-80.4, 25.2), (-81.8, 26.5),
    (-82.8, 28.0), (-84.5, 30.0), (-89.0, 30.2), (-90.0, 29.0), (-94.0, 29.6), (-97.2, 27.6), (-97.5, 22.0),
    (-96.0, 19.0), (-94.5, 18.2), (-91.0, 19.0), (-90.4, 21.0), (-87.0, 21.5), (-88.0, 18.5), (-88.2, 16.0),
    (-84.0, 15.8), (-83.3, 10.5), (-79.5, 9.6), (-77.5, 8.5), (-78.5, 7.5), (-80.0, 7.4), (-83.0, 8.2), (-85.7, 10.0),
    (-87.5, 13.0), (-91.0, 13.9), (-94.5, 16.0), (-96.5, 15.7), (-100.0, 17.0), (-105.5, 20.5), (-105.6, 23.0),
    (-108.5, 25.5), (-112.0, 29.0), (-114.8, 31.8), (-114.0, 29.0), (-112.0, 26.0), (-109.9, 23.0), (-112.0, 24.8),
    (-115.0, 29.5), (-117.1, 32.6), (-120.6, 34.5), (-122.5, 37.8), (-124.2, 40.4), (-124.5, 43.0), (-124.0, 46.3),
    (-124.7, 48.4), (-123.0, 49.0), (-127.0, 50.5), (-130.0, 54.5), (-134.0, 58.0), (-139.0, 59.5), (-146.0, 60.5),
    (-152.0, 59.0), (-154.0, 57.5), (-162.0, 55.0), (-165.0, 54.5), (-158.0, 56.5), (-157.0, 58.8), (-162.0, 58.6),
    (-165.0, 60.5), (-164.5, 63.0), (-161.0, 64.5), (-166.0, 64.6),
]
COSTA_SUD_AMERICA = [
    (-77.5, 8.5), (-75.5, 10.5), (-71.5, 12.4), (-68.0, 10.5), (-64.0, 10.6), (-61.5, 10.0), (-60.0, 8.5),
    (-57.0, 6.0), (-52.0, 5.0), (-50.0, 1.8), (-49.0, 0.0), (-44.0, -2.5), (-39.0, -3.5), (-35.2, -5.5), (-35.0, -9.0),
    (-38.5, -13.0), (-39.0, -17.5), (-41.0, -22.0), (-43.2, -22.9), (-48.5, -26.0), (-48.6, -28.5), (-51.0, -31.0),
    (-53.4, -33.7), (-56.0, -34.9), (-58.0, -34.5), (-57.0, -36.5), (-58.0, -38.5), (-62.0, -39.0), (-62.5, -41.0),
    (-65.0, -42.5), (-67.5, -46.0), (-65.8, -47.8), (-68.3, -50.2), (-68.4, -52.4), (-67.0, -54.8), (-71.0, -55.0),
    (-74.0, -52.5), (-75.5, -48.0), (-74.0, -43.0), (-73.5, -37.0), (-71.6, -33.0), (-71.4, -28.0), (-70.4, -23.6),
    (-70.3, -18.5), (-76.3, -13.8), (-77.1, -12.0), (-79.6, -7.0), (-81.3, -4.6), (-80.5, -1.0), (-79.8, 1.5),
    (-77.3, 4.0), (-77.7, 7.5),
]
COSTA_AUSTRALIA = [
    (114.0, -22.0), (114.0, -26.5), (115.0, -34.0), (118.0, -35.0), (123.5, -34.0), (129.0, -31.6), (134.0, -33.0),
    (137.5, -35.5), (140.0, -37.8), (144.0, -38.4), (146.3, -39.1), (150.0, -37.5), (151.2, -33.9), (153.5, -28.5),
    (153.0, -25.0), (149.0, -21.0), (146.0, -18.5), (145.4, -15.0), (142.5, -10.7), (141.5, -12.5), (141.5, -17.0),
    (139.5, -17.5), (136.5, -15.5), (136.8, -12.3), (132.5, -11.5), (130.8, -12.4), (129.3, -15.0), (126.0, -14.0),
    (122.0, -17.0), (121.0, -19.5), (116.7, -20.6),
]
COSTA_GROENLANDIA = [(-73.0, 78.0), (-60.0, 82.0), (-35.0, 83.5), (-20.0, 82.0), (-18.0, 77.0), (-22.0, 70.0), (-32.0, 68.0),
               (-40.0, 65.0), (-43.5, 60.0), (-48.0, 61.0), (-52.0, 64.0), (-54.0, 67.0), (-55.0, 70.0), (-58.0, 75.5),
               (-68.0, 77.0)]
COSTA_ISOLE = [
    # Mediterraneo
    [(12.4, 37.8), (13.3, 38.2), (14.5, 38.05), (15.6, 38.25), (15.1, 37.5), (15.3, 37.0), (15.1, 36.65), (14.3, 36.8),
     (12.9, 37.5)],                                                                                  # Sicilia
    [(8.2, 41.0), (9.2, 41.25), (9.8, 40.9), (9.7, 40.0), (9.6, 39.2), (9.0, 39.1), (8.4, 38.9), (8.4, 39.5),
     (8.5, 40.6)],                                                                                   # Sardegna
    [(9.4, 43.0), (9.55, 42.0), (9.2, 41.4), (8.6, 41.7), (8.7, 42.6)],                              # Corsica
    [(23.5, 35.3), (24.5, 35.4), (26.3, 35.2), (25.8, 35.0), (24.0, 35.0)],                         # Creta
    [(32.3, 35.0), (33.0, 35.3), (34.6, 35.7), (34.0, 34.9), (33.0, 34.6), (32.4, 34.7)],           # Cipro
    [(2.3, 39.6), (3.5, 39.8), (3.2, 39.3), (2.5, 39.4)],                                            # Maiorca
    [(23.4, 38.9), (24.6, 38.1), (24.2, 38.1), (23.3, 38.6)],                                        # Eubea
    # Atlantico e Mare del Nord
    [(-5.7, 50.1), (-4.2, 50.4), (-3.0, 50.7), (-1.3, 50.7), (0.3, 50.8), (1.4, 51.2), (0.9, 51.6), (1.75, 52.6),
     (0.4, 52.9), (0.1, 53.6), (-1.1, 54.6), (-1.6, 55.6), (-2.5, 56.1), (-2.1, 57.15), (-1.8, 57.6), (-3.1, 58.6),
     (-5.0, 58.6), (-5.7, 57.5), (-5.6, 56.4), (-5.6, 55.3), (-4.9, 54.8), (-3.4, 54.9), (-3.4, 54.3), (-3.0, 53.4),
     (-4.6, 53.3), (-4.1, 52.8), (-4.4, 52.2), (-5.3, 51.8), (-4.0, 51.6), (-3.0, 51.4), (-4.2, 51.2),
     (-5.0, 50.4)],                                                                                  # Gran Bretagna
    [(-6.2, 53.35), (-5.9, 54.6), (-6.2, 55.2), (-7.3, 55.4), (-8.5, 54.9), (-8.6, 54.2), (-10.0, 54.2), (-9.9, 53.5),
     (-9.4, 52.6), (-10.4, 51.8), (-9.8, 51.5), (-8.5, 51.6), (-6.4, 52.2)],                         # Irlanda
    [(-22.0, 64.0), (-24.0, 65.5), (-22.0, 66.4), (-16.0, 66.5), (-13.6, 65.2), (-15.0, 64.2), (-18.5, 63.4),
     (-22.0, 63.8)],                                                                                 # Islanda
    [(10.0, 55.0), (12.6, 55.7), (12.2, 56.1), (10.6, 55.5)],                                        # Selandia e Fionia
    # resto del mondo
    [(49.3, -12.0), (50.3, -15.5), (49.5, -17.0), (48.0, -22.0), (47.0, -25.0), (45.2, -25.5), (43.7, -23.0),
     (44.0, -20.0), (44.4, -17.0), (46.3, -15.7), (48.0, -13.5)],                                    # Madagascar
    [(79.8, 6.5), (80.0, 9.7), (81.3, 8.5), (81.8, 7.0), (80.6, 5.9)],                               # Sri Lanka
    [(95.3, 5.6), (97.5, 5.2), (100.4, 2.2), (103.6, -1.0), (106.0, -3.2), (105.8, -5.8), (104.5, -5.9),
     (101.5, -3.0), (98.7, 0.0), (96.0, 2.8)],                                                       # Sumatra
    [(105.2, -6.8), (108.0, -6.3), (111.0, -6.4), (114.5, -7.7), (114.4, -8.7), (111.0, -8.2), (106.5, -7.4)],  # Giava
    [(109.0, 1.5), (110.0, -1.0), (110.5, -3.0), (114.5, -4.0), (116.3, -3.5), (117.5, 0.0), (118.9, 1.0),
     (119.0, 5.0), (117.0, 7.0), (115.5, 5.0), (113.0, 3.2), (111.0, 1.7)],                          # Borneo
    [(119.5, -5.5), (120.5, 0.5), (124.8, 1.5), (121.5, -1.0), (123.0, -4.5), (121.2, -2.5)],       # Sulawesi
    [(131.0, -1.0), (135.0, -3.3), (138.0, -1.6), (141.0, -2.6), (144.0, -3.8), (147.5, -6.0), (150.0, -10.5),
     (147.0, -10.0), (144.0, -8.0), (141.0, -9.0), (138.0, -8.3), (137.5, -5.0), (133.0, -4.0), (132.0, -2.6)],  # N. Guinea
    [(120.5, 18.5), (122.2, 18.4), (122.0, 16.0), (124.0, 13.0), (120.8, 13.8), (120.0, 16.0)],     # Luzon
    [(122.0, 8.0), (126.5, 7.0), (125.5, 9.5), (123.5, 8.0)],                                        # Mindanao
    [(120.2, 22.5), (121.9, 25.2), (121.5, 23.0)],                                                   # Taiwan
    [(108.6, 19.2), (110.5, 20.1), (111.0, 19.6), (109.6, 18.2)],                                    # Hainan
    [(130.9, 34.0), (132.0, 33.9), (135.0, 33.5), (137.0, 34.5), (139.8, 34.9), (140.9, 36.0), (141.6, 38.3),
     (142.0, 39.6), (141.4, 41.4), (140.0, 40.6), (139.8, 38.5), (138.5, 37.4), (136.8, 37.3), (135.7, 35.5),
     (133.0, 35.5), (131.0, 34.4)],                                                                  # Honshu
    [(130.0, 32.0), (130.7, 31.0), (131.7, 31.5), (131.9, 33.2), (130.0, 33.8), (129.5, 33.0)],     # Kyushu
    [(140.0, 42.0), (141.0, 43.3), (141.7, 45.4), (143.5, 44.3), (145.6, 43.3), (143.3, 42.0), (141.0, 41.6)],  # Hokkaido
    [(142.0, 46.0), (143.5, 49.0), (143.0, 54.0), (142.2, 54.0), (142.0, 50.0)],                     # Sachalin
    [(144.6, -40.7), (148.3, -40.9), (148.0, -43.2), (146.0, -43.6), (145.0, -42.0)],               # Tasmania
    [(172.7, -34.4), (175.0, -36.8), (178.5, -37.7), (177.0, -39.3), (176.0, -41.3), (174.8, -41.3), (174.0, -39.0),
     (173.0, -35.5)],                                                                                # N. Zelanda nord
    [(172.5, -40.5), (174.3, -41.7), (173.0, -43.5), (171.2, -44.4), (169.0, -46.6), (166.5, -46.0), (168.0, -44.0),
     (171.0, -42.0)],                                                                                # N. Zelanda sud
    [(-80.0, 73.0), (-62.0, 66.5), (-65.0, 63.0), (-75.0, 64.5), (-85.0, 70.0)],                    # Baffin
    [(-120.0, 76.0), (-95.0, 81.0), (-70.0, 82.5), (-80.0, 76.0), (-100.0, 73.0), (-118.0, 71.0)],  # arcipelago artico
    [(-85.0, 22.0), (-80.0, 23.2), (-74.2, 20.2), (-77.5, 19.9), (-82.0, 21.6)],                    # Cuba
    [(-74.4, 18.5), (-68.4, 18.6), (-69.9, 19.9), (-72.8, 19.9)],                                    # Hispaniola
    [(-53.5, 46.6), (-52.6, 47.6), (-55.5, 51.6), (-59.4, 47.6)],                                    # Terranova
    [(52.0, 71.5), (55.0, 73.5), (60.0, 76.5), (68.0, 77.0), (57.0, 71.5)],                          # Novaja Zemlja
    [(11.0, 78.5), (17.0, 80.2), (27.0, 80.0), (22.0, 77.5), (16.0, 76.6)],                          # Svalbard
]
COSTA_MARI_INTERNI = [
    [(29.0, 41.15), (28.0, 41.9), (27.9, 42.7), (28.0, 43.3), (28.6, 43.8), (29.7, 45.2), (30.7, 46.5), (31.7, 46.6),
     (33.5, 46.0), (32.5, 45.4), (33.6, 44.5), (35.0, 44.8), (36.4, 45.25), (35.3, 45.5), (35.4, 46.5), (37.5, 47.1),
     (39.2, 47.2), (38.2, 46.2), (37.6, 45.6), (36.9, 45.3), (37.0, 45.0), (37.8, 44.7), (39.7, 43.6), (41.6, 41.6),
     (39.7, 41.0), (36.3, 41.3), (34.9, 42.0), (33.0, 41.9), (31.0, 41.1)],                          # Mar Nero e d'Azov
    [(26.6, 40.4), (27.5, 40.3), (29.0, 41.0), (28.0, 41.0)],                                        # Mar di Marmara
    [(47.2, 44.2), (47.8, 45.8), (49.0, 46.5), (51.5, 47.0), (53.0, 46.8), (53.2, 45.3), (51.3, 44.5), (51.5, 43.2),
     (52.8, 41.8), (53.0, 40.0), (53.9, 38.5), (53.9, 37.3), (51.0, 36.8), (49.0, 37.6), (48.9, 38.4), (49.5, 40.3),
     (48.6, 41.8), (47.5, 43.0)],                                                                    # Mar Caspio
    [(-95.0, 58.8), (-92.0, 57.0), (-87.0, 55.5), (-82.3, 52.9), (-79.5, 51.5), (-78.8, 54.5), (-77.0, 58.0),
     (-78.0, 62.3), (-82.0, 64.5), (-86.0, 64.0), (-90.5, 63.5), (-94.0, 61.0)],                    # Baia di Hudson
    [(-88.0, 48.3), (-84.5, 46.5), (-82.5, 43.0), (-79.0, 43.4), (-81.5, 45.0), (-87.5, 45.5)],     # Grandi Laghi
]

# Gli spilli sul mappamondo (lat, lon), senza nome: chi gioca deve sapere dov'è Nizza. Torino, Genova e Marsiglia sono
# escluse apposta: a questa scala distano 1-2 gradi da Nizza e i loro spilli si sovrapporrebbero.
CITTA_GLOBO = [("Nizza", 43.70, 7.27), ("Venezia", 45.44, 12.33), ("Roma", 41.90, 12.50), ("Napoli", 40.85, 14.27),
               ("Parigi", 48.86, 2.35), ("Vienna", 48.21, 16.37), ("Madrid", 40.42, -3.70), ("Londra", 51.51, -0.13)]
CITTA_GIUSTA = "Nizza"


def img_globo(w=2048, h=1024):
    """Texture equirettangolare del mappamondo: x = longitudine (-180 a sinistra), y = latitudine (nord in alto).
    Si disegna a dimensione doppia e poi si riduce: così le coste non sono seghettate."""
    finale = (w, h)
    w, h = 2 * w, 2 * h
    mare, mare_basso, terra, costa = (150, 178, 172), (184, 204, 190), (222, 202, 154), (92, 66, 40)

    def P(pts):
        return [((lon + 180) / 360 * w, (90 - lat) / 180 * h) for lon, lat in pts]

    rnd = random.Random(5)
    antartide = ([(-180, -90)] + [(lon, -70 + 4 * math.sin(lon * .05) + rnd.uniform(-1.5, 1.5))
                                  for lon in range(-180, 181, 6)] + [(180, -90)])
    terre = [COSTA_EURASIA, COSTA_AFRICA, COSTA_NORD_AMERICA, COSTA_SUD_AMERICA, COSTA_AUSTRALIA, COSTA_GROENLANDIA,
             antartide] + COSTA_ISOLE
    # bassi fondali: un alone più chiaro lungo le coste
    alone = Image.new("L", (w, h), 0)
    da = ImageDraw.Draw(alone)
    for t in terre:
        da.polygon(P(t), fill=255)
    alone = alone.resize((w // 4, h // 4)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(3))
    img = Image.composite(Image.new("RGB", (w, h), mare_basso), Image.new("RGB", (w, h), mare), alone.resize((w, h)))
    d = ImageDraw.Draw(img)
    for t in terre:
        d.polygon(P(t), fill=terra)
        d.line(P(t) + P(t[:1]), fill=costa, width=3)
    for m in COSTA_MARI_INTERNI:
        d.polygon(P(m), fill=mare)
        d.line(P(m) + P(m[:1]), fill=costa, width=3)
    # meridiani e paralleli ogni 15 gradi, equatore in rosso
    for lon in range(-180, 181, 15):
        x = (lon + 180) / 360 * w
        d.line([(x, 0), (x, h)], fill=(120, 100, 80), width=2)
    for lat in range(-75, 76, 15):
        y = (90 - lat) / 180 * h
        d.line([(0, y), (w, y)], fill=(140, 40, 40) if lat == 0 else (120, 100, 80), width=4 if lat == 0 else 2)
    img = img.resize(finale, Image.LANCZOS)
    return _macchie(img, 40, (150, 116, 70), finale[0] // 60, finale[0] // 20, 26, 1860)     # carta un po' ingiallita


def img_lettera_bruciata(w=512, h=360):
    """La lettera mezza bruciata del camino: pergamena con i bordi anneriti, un angolo mangiato dal fuoco
    e il messaggio cifrato ben leggibile al centro."""
    img = img_pergamena(w, h, bordo=False, seme=33)
    d = ImageDraw.Draw(img)
    rnd = random.Random(1821)
    for r in range(4):                              # righe di testo illeggibile, in parte bruciate
        y = 48 + r * 26
        x, fine = 46 + (36 if r == 0 else 0), w - 50 - rnd.randint(0, 80)
        pts = []
        while x < fine:
            pts.append((x, y + 4 * math.sin(x * .3 + r) + rnd.uniform(-1.2, 1.2)))
            x += 4
        d.line(pts, fill=(60, 44, 40), width=2)
    corpo = 58
    while corpo > 20 and d.textlength("EXRQL FXJLQL", font=font_pil("b", corpo)) > w * .7:
        corpo -= 2
    d.text((w // 2, h * .62), "EXRQL FXJLQL", font=font_pil("b", corpo), fill=(34, 20, 16), anchor="mm")
    d.line([(w * .18, h * .74), (w * .82, h * .74)], fill=(110, 30, 34), width=3)
    # contorno frastagliato: un angolo in alto a destra se l'è preso il fuoco
    contorno = []
    for i in range(60):                             # lato sinistro, dal basso verso l'alto, poi in alto
        contorno.append((10 + rnd.uniform(0, 10), h - 10 - (h - 20) * i / 59))
    for i in range(40):
        u = i / 39
        x, y = 10 + (w * .6 - 10) * u, 10 + rnd.uniform(0, 10)
        contorno.append((x, y))
    for i in range(50):                             # la bruciatura: una curva dall'alto fino al lato destro
        u = i / 49
        x = w * .6 + (w - 10 - w * .6) * u
        y = h * .42 * math.sin(u * math.pi / 2) ** 1.4 + rnd.uniform(-9, 9) + 6
        contorno.append((x, max(4, y)))
    for i in range(50):                             # lato destro e lato inferiore
        contorno.append((w - 10 - rnd.uniform(0, 10), h * .45 + (h * .55 - 10) * i / 49))
    for i in range(60):
        contorno.append((w - 10 - (w - 20) * i / 59, h - 10 - rnd.uniform(0, 10)))
    maschera = Image.new("L", (w, h), 0)
    ImageDraw.Draw(maschera).polygon(contorno, fill=255)
    sfuma = maschera.filter(ImageFilter.GaussianBlur(16))
    # verso il bordo la carta passa al bruno, al nero e, sul filo, a un'ombra di brace
    nero = sfuma.point(lambda v: 255 if v < 150 else max(0, int((235 - v) * 3)))
    img = Image.composite(Image.new("RGBA", (w, h), (26, 14, 8, 255)), img, nero)
    brace = sfuma.point(lambda v: 150 if 70 < v < 120 else 0).filter(ImageFilter.GaussianBlur(3))
    img = Image.composite(Image.new("RGBA", (w, h), (170, 70, 24, 255)), img, brace)
    img.putalpha(maschera)
    return img


def img_tappeto():
    w, h = 640, 440
    img = Image.new("RGB", (w, h), (92, 18, 30))
    d = ImageDraw.Draw(img)
    for i, (c, lw) in enumerate((((22, 18, 20), 34), ((170, 128, 50), 8), ((40, 22, 26), 20), ((170, 128, 50), 4))):
        o = sum(x[1] for x in (((22, 18, 20), 34), ((170, 128, 50), 8), ((40, 22, 26), 20), ((170, 128, 50), 4))[:i])
        d.rectangle((o, o, w - 1 - o, h - 1 - o), outline=c, width=lw)
    for x in range(40, w - 40, 36):
        d.polygon([(x, 12), (x + 12, 24), (x, 36), (x - 12, 24)], fill=(150, 110, 44))
        d.polygon([(x, h - 36), (x + 12, h - 24), (x, h - 12), (x - 12, h - 24)], fill=(150, 110, 44))
    cx, cy = w // 2, h // 2
    for k, c in enumerate(((170, 128, 50), (40, 22, 26), (120, 30, 44), (170, 128, 50))):
        s = 140 - k * 30
        d.polygon([(cx, cy - s * 0.8), (cx + s * 1.3, cy), (cx, cy + s * 0.8), (cx - s * 1.3, cy)], fill=c)
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = cx + sx * 220, cy + sy * 120
            d.ellipse((px - 22, py - 22, px + 22, py + 22), fill=(170, 128, 50))
            d.ellipse((px - 12, py - 12, px + 12, py + 12), fill=(40, 22, 26))
    return _rumore(img, 14, 4)


def img_quadrante():
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, s - 4, s - 4), fill=(236, 226, 200), outline=(140, 108, 30), width=12)
    romani = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    for i, r in enumerate(romani):
        a = i * math.pi / 6 - math.pi / 2
        d.text((s / 2 + math.cos(a) * 92, s / 2 + math.sin(a) * 92), r, font=font_pil("r", 22),
               fill=(44, 30, 22), anchor="mm")
    return img


def img_radiale(s, col=(255, 255, 255), esponente=1.8, forza=1.0):
    img = Image.new("RGBA", (s, s), col + (0,))
    px = img.load()
    c = (s - 1) / 2
    for y in range(s):
        for x in range(s):
            d = math.hypot(x - c, y - c) / c
            a = max(0.0, 1 - d) ** esponente
            px[x, y] = col + (int(255 * a * forza),)
    return img


def img_fiamma():
    w, h = 64, 128
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            u = (x - w / 2) / (w / 2)
            v = y / h                         # 0 = punta, 1 = base
            largh = 0.15 + 0.85 * math.sin(min(1.0, v * 1.1) * math.pi * 0.62)
            d = abs(u) / max(0.01, largh)
            if d < 1 and v > 0.02:
                a = (1 - d ** 2) * min(1.0, (1 - v) * 6) * min(1.0, v * 3)
                t = min(1.0, d + (1 - v) * 0.5)
                col = _mescola((255, 250, 210), (255, 120, 20), t)
                px[x, y] = col + (int(255 * max(0.0, a)),)
    return img


def img_vignetta():
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    px = img.load()
    c = (s - 1) / 2
    for y in range(s):
        for x in range(s):
            d = math.hypot((x - c) / c, (y - c) / c) / 1.25
            px[x, y] = (0, 0, 0, int(235 * min(1.0, max(0.0, (d - 0.35) / 0.65)) ** 1.6))
    return img


def img_titolo_oro(testo, w, h):
    """Scritta dorata con ombra e bagliore, come immagine con trasparenza."""
    f = font_pil("b", int(h * .78))
    # FIX: Calcola dinamicamente la larghezza per non tagliare le scritte lunghe
    dummy = Image.new("L", (1, 1))
    lw = int(ImageDraw.Draw(dummy).textlength(testo, font=f))
    w = max(w, lw + 40)
    
    maschera = Image.new("L", (w, h), 0)
    ImageDraw.Draw(maschera).text((w / 2, h / 2), testo, font=f, fill=255, anchor="mm")
    oro = _gradiente(w, h, (255, 236, 160), (176, 120, 30)).convert("RGBA")
    oro.putalpha(maschera)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bagliore = Image.new("RGBA", (w, h), (255, 220, 130, 0))
    bagliore.putalpha(maschera.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * .8)))
    img.alpha_composite(bagliore)
    ombra = Image.new("RGBA", (w, h), (30, 16, 4, 0))
    ombra.putalpha(maschera.filter(ImageFilter.GaussianBlur(3)).point(lambda v: int(v * .7)))
    img.alpha_composite(ombra, (5, 6))
    img.alpha_composite(oro)
    return img


def img_targa():
    w, h = 512, 112
    img = _gradiente(w, h, (240, 210, 130), (150, 110, 36))
    d = ImageDraw.Draw(img)
    d.rectangle((4, 4, w - 5, h - 5), outline=(96, 70, 20), width=5)
    d.rectangle((14, 14, w - 15, h - 15), outline=(200, 160, 70), width=2)
    for x in (30, w - 30):
        d.ellipse((x - 7, h / 2 - 7, x + 7, h / 2 + 7), fill=(110, 80, 26))
    d.text((w / 2 + 2, h / 2 + 2), "PORTA USCITA", font=font_pil("b", 54), fill=(250, 226, 150), anchor="mm")
    d.text((w / 2, h / 2), "PORTA USCITA", font=font_pil("b", 54), fill=(52, 34, 10), anchor="mm")
    return img


def img_sigillo(spunta=False):
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(24):
        a = i * math.tau / 24
        r = 118 * (1 + 0.06 * math.sin(i * 2.7))
        pts.append((s / 2 + math.cos(a) * r, s / 2 + math.sin(a) * r))
    d.polygon(pts, fill=(78, 12, 24))
    d.ellipse((24, 24, s - 24, s - 24), fill=(128, 22, 40))
    d.ellipse((40, 40, s - 40, s - 40), outline=(92, 14, 28), width=5)
    d.ellipse((60, 52, 100, 92), fill=(170, 50, 66))
    if spunta:
        d.line([(80, 132), (114, 168), (180, 88)], fill=(244, 218, 138), width=18, joint="curve")
    return img.filter(ImageFilter.GaussianBlur(0.8))


def img_coccarda():
    s = 128
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, s - 2, s - 2), fill=(212, 175, 55))
    d.ellipse((7, 7, s - 7, s - 7), fill=(206, 43, 55))
    d.ellipse((24, 24, s - 24, s - 24), fill=(244, 245, 240))
    d.ellipse((42, 42, s - 42, s - 42), fill=(0, 146, 70))
    return img


def img_pannello(w, h, alto=(30, 22, 26), basso=(8, 6, 8), bordo=(212, 175, 55)):
    img = _gradiente(w, h, alto, basso).convert("RGBA")
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 6, fill=255)
    img.putalpha(m)
    ImageDraw.Draw(img).rounded_rectangle((3, 3, w - 4, h - 4), radius=h // 6, outline=bordo, width=4)
    return img


def img_raggi():
    s = 512
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    for k in range(18):
        a = k * math.tau / 18
        d.polygon([(c, c), (c + math.cos(a - 0.08) * s, c + math.sin(a - 0.08) * s),
                   (c + math.cos(a + 0.08) * s, c + math.sin(a + 0.08) * s)], fill=(255, 214, 120, 60))
    return img.filter(ImageFilter.GaussianBlur(3))


# --- texture dell'archivio segreto e del Treno Diplomatico ------------------
def img_pixel(colori, seme, dim=16, scala=8, righe=None, colonne=None):
    """Texture 'alla Minecraft': dim x dim pixel colorati a caso, ingranditi senza sfumature.
    righe / colonne = (periodo, colore) per aggiungere linee (assi di legno, mattoni, tronchi)."""
    rnd = random.Random(seme)
    img = Image.new("RGB", (dim, dim))
    px = img.load()
    for y in range(dim):
        for x in range(dim):
            px[x, y] = rnd.choice(colori)
    if righe:
        for y in range(0, dim, righe[0]):
            for x in range(dim):
                px[x, y] = righe[1]
    if colonne:
        for x in range(0, dim, colonne[0]):
            for y in range(dim):
                px[x, y] = colonne[1]
    return img.resize((dim * scala, dim * scala), Image.NEAREST)


PIXEL_ERBA = [(92, 150, 54), (84, 138, 48), (104, 162, 62), (78, 128, 44)]
PIXEL_TERRA = [(122, 86, 54), (112, 78, 48), (134, 96, 60), (100, 70, 44)]
PIXEL_PIETRA = [(128, 128, 128), (118, 118, 120), (140, 140, 140), (106, 106, 108)]
PIXEL_NEVE = [(246, 249, 252), (232, 238, 246), (252, 253, 254)]
PIXEL_FOGLIE = [(52, 122, 44), (44, 104, 38), (66, 138, 52), (36, 90, 32)]
PIXEL_TRONCO = [(98, 70, 42), (86, 60, 36), (108, 78, 48)]
PIXEL_ASSI = [(164, 124, 72), (152, 112, 64), (174, 132, 80)]
PIXEL_MATTONI = [(158, 76, 56), (146, 68, 50), (168, 84, 62)]
PIXEL_ARDESIA = [(70, 74, 92), (62, 66, 84), (78, 82, 100)]


def img_erba():
    return img_pixel(PIXEL_ERBA, 1)


def img_terra():
    return img_pixel(PIXEL_TERRA, 2)


def img_roccia():
    return img_pixel(PIXEL_PIETRA, 3)


def img_neve():
    return img_pixel(PIXEL_NEVE, 4)


def img_foglie():
    return img_pixel(PIXEL_FOGLIE, 5)


def img_tronco():
    return img_pixel(PIXEL_TRONCO, 6, colonne=(4, (70, 48, 28)))


def img_assi_mc():
    return img_pixel(PIXEL_ASSI, 7, righe=(4, (120, 86, 48)))


def img_mattoni_mc():
    return img_pixel(PIXEL_MATTONI, 8, righe=(4, (196, 186, 170)))


def img_tetto_mc():
    return img_pixel(PIXEL_ARDESIA, 9, righe=(4, (44, 46, 60)))


def img_cartello(testo, fondo, bordo=(244, 236, 214), colore=(255, 255, 255), w=384, h=112):
    """Insegna di stazione per il plastico: scritta grande su fondo pieno con doppio bordo."""
    img = Image.new("RGBA", (w, h), fondo + (255,))
    d = ImageDraw.Draw(img)
    d.rectangle((3, 3, w - 4, h - 4), outline=bordo, width=5)
    d.rectangle((13, 13, w - 14, h - 14), outline=bordo, width=2)
    size = int(h * .52)
    f = font_pil("b", size)
    while d.textlength(testo, font=f) > w - 44 and size > 12:
        size -= 2
        f = font_pil("b", size)
    d.text((w / 2 + 2, h / 2 + 3), testo, font=f, fill=(0, 0, 0), anchor="mm")
    d.text((w / 2, h / 2), testo, font=f, fill=colore, anchor="mm")
    return img


def img_lucchetto(aperto=False):
    """Lucchetto dorato per il campo del codice (chiuso / aperto)."""
    s = 128
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ferro = (190, 190, 200)
    if aperto:                                   # archetto sollevato e spostato di lato
        d.arc((46, 4, 108, 66), 180, 360, fill=ferro, width=11)
        d.line([(108, 35), (108, 52)], fill=ferro, width=11)
        d.line([(47, 35), (47, 44)], fill=ferro, width=11)
    else:
        d.arc((30, 8, 98, 76), 180, 360, fill=ferro, width=12)
        d.line([(31, 42), (31, 66)], fill=ferro, width=12)
        d.line([(97, 42), (97, 66)], fill=ferro, width=12)
    d.rounded_rectangle((20, 60, 108, 118), radius=10, fill=(212, 175, 55), outline=(120, 88, 20), width=4)
    d.rounded_rectangle((28, 68, 100, 110), radius=7, outline=(244, 218, 138), width=2)
    d.ellipse((57, 76, 71, 90), fill=(40, 26, 10))
    d.polygon([(61, 88), (67, 88), (69, 104), (59, 104)], fill=(40, 26, 10))
    return img


def img_fascicolo(titolo, anno, w=320, h=224, seme=1, scritta=True):
    """Copertina di un fascicolo (cartella di cartone) con etichetta: titolo e anno.
    Con scritta=False l'etichetta ha solo righe di pennino (per i fascicoli a terra, visti di sbieco)."""
    rnd = random.Random(seme)
    img = _gradiente(w, h, (206, 168, 108), (176, 136, 82))
    img = _macchie(img, 14, (120, 84, 44), w // 30, w // 10, 40, seme)
    d = ImageDraw.Draw(img)
    d.rectangle((2, 2, w - 3, h - 3), outline=(104, 72, 36), width=4)
    d.line([(10, 12), (w - 10, 12)], fill=(228, 196, 140), width=2)
    for _ in range(40):                          # piccole macchie di inchiostro e polvere
        x, y = rnd.randint(8, w - 8), rnd.randint(8, h - 8)
        d.point((x, y), fill=(96, 66, 34))
    d.rectangle((26, 52, w - 27, h - 52), fill=(244, 236, 212), outline=(120, 24, 40), width=4)
    if scritta:
        size = 30
        f = font_pil("b", size)
        while d.textlength(titolo, font=f) > w - 84 and size > 12:
            size -= 2
            f = font_pil("b", size)
        d.text((w / 2, 84), titolo, font=f, fill=(60, 24, 24), anchor="mm")
        d.text((w / 2, h - 82), str(anno), font=font_pil("b", 44), fill=(120, 24, 40), anchor="mm")
    else:
        for riga in range(4):
            y = 74 + riga * 22
            pts = [(x, y + 4 * math.sin(x * .3 + riga + seme)) for x in range(44, w - 44, 6)]
            d.line(pts, fill=(80, 56, 44), width=2)
    d.ellipse((w - 62, 14, w - 24, 52), fill=(130, 20, 36))              # ceralacca
    return img


def img_scheda(w=420, h=270, seme=1):
    """Scheda del fascicolo mostrata nella finestra dell'enigma (cartoncino con linguetta)."""
    img = _gradiente(w, h, (232, 214, 172), (206, 180, 128)).convert("RGBA")
    img = _macchie(img, 16, (150, 112, 62), w // 30, w // 9, 36, seme)
    d = ImageDraw.Draw(img)
    d.rectangle((3, 3, w - 4, h - 4), outline=(120, 24, 40), width=6)
    d.rectangle((14, 14, w - 15, h - 15), outline=(140, 108, 30), width=2)
    return img


def img_targa_quadro():
    w, h = 640, 96
    img = _gradiente(w, h, (240, 210, 130), (150, 110, 36))
    d = ImageDraw.Draw(img)
    d.rectangle((4, 4, w - 5, h - 5), outline=(96, 70, 20), width=5)
    d.rectangle((14, 14, w - 15, h - 15), outline=(200, 160, 70), width=2)
    testo = "QUADRO DI COMANDO FERROVIARIO"
    size = 40
    f = font_pil("b", size)
    while d.textlength(testo, font=f) > w - 56 and size > 12:
        size -= 2
        f = font_pil("b", size)
    d.text((w / 2 + 2, h / 2 + 2), testo, font=f, fill=(250, 226, 150), anchor="mm")
    d.text((w / 2, h / 2), testo, font=f, fill=(52, 34, 10), anchor="mm")
    return img


def img_numero(n, s=128):
    """Targa numerata dello scambio: cifra d'oro su fondo scuro, con doppio bordo."""
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((3, 3, s - 4, s - 4), radius=s // 6, fill=(26, 18, 14, 255), outline=(212, 175, 55, 255), width=6)
    d.rounded_rectangle((13, 13, s - 14, s - 14), radius=s // 8, outline=(140, 108, 30, 255), width=2)
    f = font_pil("b", int(s * .66))
    d.text((s / 2 + 2, s / 2 + 5), str(n), font=f, fill=(0, 0, 0, 255), anchor="mm")
    d.text((s / 2, s / 2 + 2), str(n), font=f, fill=(244, 218, 138, 255), anchor="mm")
    return img


def img_istruzioni_quadro(w=640, h=250):
    """Targa di istruzioni sul Quadro di Comando (sul piano, rivolta verso chi guarda)."""
    img = _gradiente(w, h, (36, 26, 20), (18, 12, 10))
    d = ImageDraw.Draw(img)
    d.rectangle((4, 4, w - 5, h - 5), outline=(212, 175, 55), width=5)
    d.rectangle((14, 14, w - 15, h - 15), outline=(140, 108, 30), width=2)
    righe = [("1", "Gira gli scambi: clic, o i tasti 1-7 da qui"),
             ("2", "Leva verde (o Invio): il treno parte da Torino"),
             ("3", "Porta Cavour a Plombières. R: ripristina gli scambi")]
    f = font_pil("i", 25)
    for i, (n, t) in enumerate(righe):
        y = 62 + i * 62
        d.ellipse((34, y - 22, 78, y + 22), fill=(120, 24, 40), outline=(212, 175, 55), width=3)
        d.text((56, y + 1), n, font=font_pil("b", 28), fill=(244, 218, 138), anchor="mm")
        size = 25
        while d.textlength(t, font=f) > w - 140 and size > 12:
            size -= 1
            f = font_pil("i", size)
        d.text((98, y), t, font=f, fill=(238, 225, 194), anchor="lm")
    return img


# Minimappa dell'archivio: la stessa pianta della ferrovia, vista dall'alto, per orientarsi (e per leggere gli scambi)
MM_CELLA = 40


def _mm_segmento(d, cx, cz, lato, larghezza, col, y0):
    """Un braccio di binario dal centro della cella verso il lato 'lato' (disegnato sull'immagine, y verso il basso)."""
    vx, vz = VETTORE_DIR[lato]
    x1, y1 = cx + vx * MM_CELLA / 2, cz - vz * MM_CELLA / 2
    d.line([(cx, cz), (x1, y1)], fill=col, width=larghezza)


def _mm_binario(d, cx, cz, maschera, rosso, ponte=False):
    traversa = (150, 40, 40) if rosso else (96, 66, 40)
    rotaia = (255, 150, 130) if rosso else (226, 226, 236)
    if ponte:
        traversa, rotaia = (70, 70, 80), (200, 200, 214)
    for l in lati(maschera):
        _mm_segmento(d, cx, cz, l, 11, traversa, 0)
    r = 5
    d.ellipse((cx - r, cz - r, cx + r, cz + r), fill=traversa)
    for l in lati(maschera):
        _mm_segmento(d, cx, cz, l, 3, rotaia, 0)
    d.ellipse((cx - 2, cz - 2, cx + 2, cz + 2), fill=rotaia)


def img_minimappa(griglia):
    """Pianta statica: erba, strade, binari (rossi quelli delle spie), ponti con il binario che passa sotto, rampe,
    stazioni e le caselle degli scambi (le braccia correnti le disegna MiniMappa sopra, via via)."""
    c = MM_CELLA
    w, h = griglia.colonne * c, griglia.righe * c
    img = Image.new("RGBA", (w, h), (52, 112, 58, 255))
    d = ImageDraw.Draw(img)
    rnd = random.Random(5)
    for _ in range(w * h // 90):                                  # zolle d'erba
        x, y = rnd.randrange(w), rnd.randrange(h)
        k = rnd.randint(-12, 12)
        d.rectangle((x, y, x + 2, y + 2), fill=(56 + k, 118 + k, 62 + k, 255))
    for (x, z), t in griglia.tessere.items():
        x0, y0 = x * c, (griglia.righe - 1 - z) * c
        cx, cz = x0 + c / 2, y0 + c / 2
        if t.strada:                                              # strada: asfalto con la riga tratteggiata
            grigio = (92, 92, 100, 255)
            if t.strada in ("eo", "inc"):
                d.rectangle((x0, cz - 11, x0 + c, cz + 11), fill=grigio)
            if t.strada in ("ns", "inc"):
                d.rectangle((cx - 11, y0, cx + 11, y0 + c), fill=grigio)
            if t.strada == "eo":
                for k in range(0, c, 14):
                    d.rectangle((x0 + k, cz - 1, x0 + k + 7, cz + 1), fill=(230, 224, 180, 255))
            elif t.strada == "ns":
                for k in range(0, c, 14):
                    d.rectangle((cx - 1, y0 + k, cx + 1, y0 + k + 7), fill=(230, 224, 180, 255))
        if t.tipo == "ponte":
            _mm_binario(d, cx, cz, DIR_N | DIR_S if t.asse_alto & DIR_E else DIR_E | DIR_O, t.rosso)   # sotto
            if t.asse_alto & DIR_E:
                d.rectangle((x0, cz - 12, x0 + c, cz + 12), fill=(176, 170, 160, 255), outline=(40, 40, 50, 255), width=2)
            else:
                d.rectangle((cx - 12, y0, cx + 12, y0 + c), fill=(176, 170, 160, 255), outline=(40, 40, 50, 255), width=2)
            _mm_binario(d, cx, cz, t.asse_alto, t.rosso, ponte=True)
        elif t.tipo == "rampa":
            _mm_binario(d, cx, cz, t.base, t.rosso)
            vx, vz = VETTORE_DIR[t.alta]
            # un quadratino arancione dal lato dove la rampa arriva all'altezza del ponte
            d.rectangle((cx - 4 + vx * 12, cz - 4 - vz * 12, cx + 4 + vx * 12, cz + 4 - vz * 12), fill=(250, 200, 80, 255))
        elif t.tipo == "scambio":
            d.rectangle((x0 + 2, y0 + 2, x0 + c - 3, y0 + c - 3), fill=(52, 38, 22, 255), outline=(212, 175, 55, 255), width=3)
            d.text((x0 + 6, y0 + 4), t.sigla, font=font_pil("b", 14), fill=(255, 232, 150, 255), anchor="lt")
        elif t.tipo in ("arrivo", "vienna", "partenza"):
            fondo = {"arrivo": (22, 130, 70), "vienna": (170, 34, 34), "partenza": (36, 92, 170)}[t.tipo]
            d.rectangle((x0 + 2, y0 + 2, x0 + c - 3, y0 + c - 3), fill=fondo + (255,), outline=(244, 236, 214, 255), width=2)
            _mm_binario(d, cx, cz, t.base, t.tipo == "vienna")
            lettera = {"arrivo": "P", "vienna": "V", "partenza": "T"}[t.tipo]
            d.text((x0 + c - 7, y0 + 5), lettera, font=font_pil("b", 15), fill=(255, 255, 255, 255), anchor="rt")
        elif t.tipo == "binario":
            _mm_binario(d, cx, cz, t.maschera, t.rosso)
            if t.strada:                                          # passaggio a livello: segnale rosso-bianco
                d.rectangle((x0 + 3, y0 + 3, x0 + 11, y0 + 11), fill=(235, 235, 235, 255), outline=(200, 30, 30, 255), width=2)
    return img


def img_mm_scambio(maschera):
    """Le braccia di uno scambio (nell'orientamento attuale), in giallo vivo su fondo trasparente."""
    c = MM_CELLA
    img = Image.new("RGBA", (c, c), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for l in lati(maschera):
        _mm_segmento(d, c / 2, c / 2, l, 9, (30, 20, 8, 255), 0)
    d.ellipse((c / 2 - 6, c / 2 - 6, c / 2 + 6, c / 2 + 6), fill=(30, 20, 8, 255))
    for l in lati(maschera):
        _mm_segmento(d, c / 2, c / 2, l, 5, (255, 214, 70, 255), 0)
    d.ellipse((c / 2 - 4, c / 2 - 4, c / 2 + 4, c / 2 + 4), fill=(255, 214, 70, 255))
    return img


# --------------------------------------------------------------------------
# Shader con più luci di candela (GLSL)
# --------------------------------------------------------------------------
_VERTEX = """#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
out vec2 uv;
out vec3 wpos;
out vec3 wnorm;
out vec4 vcol;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    wpos = (p3d_ModelMatrix * p3d_Vertex).xyz;
    wnorm = transpose(inverse(mat3(p3d_ModelMatrix))) * p3d_Normal;
    uv = p3d_MultiTexCoord0 * texture_scale + texture_offset;
    vcol = p3d_Color;
}
"""

_FRAGMENT = """#version 150
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 luci_pos[%d];
uniform vec3 luci_col[%d];
uniform vec3 ambiente;
uniform vec3 cam_pos;
uniform vec2 nebbia;
uniform float lucido;
uniform vec3 emissione;
uniform int n_luci;          // quante luci contare: le prime n_luci dell'array, gia ordinate dalla piu vicina alla camera
uniform float raggio_max;    // oltre questa distanza una luce e ignorata (0 = nessun limite)
uniform float riflessi;      // 1 = riflessi lucidi accesi, 0 = spenti
in vec2 uv;
in vec3 wpos;
in vec3 wnorm;
in vec4 vcol;
out vec4 fragColor;
void main() {
    vec4 base = texture(p3d_Texture0, uv) * vcol * p3d_ColorScale;
    if (base.a < 0.02) discard;
    vec3 V = normalize(cam_pos - wpos);

    // FIX LUCI: Usa la normale reale ed elimina l'inversione ottica che causava il taglio
    vec3 n = length(wnorm) > 0.0001 ? normalize(wnorm) : vec3(0.0, 1.0, 0.0);

    vec3 diff = ambiente;
    vec3 spec = vec3(0.0);
    float zf = step(wpos.z, -4.1);
    float inVarco = step(1.6, wpos.x) * step(wpos.x, 3.2) * step(-5.5, wpos.z) * step(wpos.z, -3.2);
    float rifl = lucido * riflessi;
    float r2max = raggio_max * raggio_max;
    for (int i = 0; i < %d; i++) {
        if (i >= n_luci) break;
        vec3 L = luci_pos[i] - wpos;
        float d2 = dot(L, L);
        if (raggio_max > 0.0 && d2 > r2max) continue;
        float zl = step(luci_pos[i].z, -4.1);
        if (abs(zl - zf) > 0.5 && inVarco < 0.5 && luci_pos[i].y > -50.0) continue;
        float d = sqrt(d2);
        L /= d;
        float att = 1.0 / (1.0 + 0.10 * d + 0.28 * d2);
        float nd = max(dot(n, L), 0.0);
        diff += luci_col[i] * nd * att;
        if (rifl > 0.001) {
            vec3 H = normalize(L + V);
            spec += luci_col[i] * pow(max(dot(n, H), 0.0), 40.0) * att * rifl;
        }
    }
    vec3 col = base.rgb * diff + spec + emissione * base.rgb;
    float dist = length(cam_pos - wpos);
    col *= 1.0 - smoothstep(nebbia.x, nebbia.y, dist) * 0.5;
    col = vec3(1.0) - exp(-col * 1.35);
    fragColor = vec4(col, base.a);
}
""" % (N_LUCI, N_LUCI, N_LUCI)


def crea_shader_stanza():
    return Shader(language=Shader.GLSL, vertex=_VERTEX, fragment=_FRAGMENT,
                  default_input={"texture_scale": Vec2(1, 1), "texture_offset": Vec2(0, 0)})


# Il quadrato che mostra la scena ridotta: passa i colori così come sono (il quadrato di base del FilterManager è tinto di rosa)
_VERTEX_QUAD = """#version 150
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
}
"""
_FRAGMENT_QUAD = """#version 150
uniform sampler2D p3d_Texture0;
in vec2 uv;
out vec4 fragColor;
void main() {
    fragColor = vec4(texture(p3d_Texture0, uv).rgb, 1.0);
}
"""


class RisoluzioneScena(FilterManager):
    """Disegna la scena 3D in un buffer più piccolo della finestra (scala = quota della risoluzione) e lo stende a
    tutta finestra. L'interfaccia di Ursina ha una telecamera sua, sopra a tutto: resta alla risoluzione piena e nitida.
    Se la finestra cambia dimensione (F11, ridimensionamento) il buffer la segue da solo."""

    def __init__(self, win, cam, scala):
        super().__init__(win, cam)
        self.scala = scala

    def getScaledSize(self, mul, div, align):
        return (max(160, int(round(self.win.getXSize() * self.scala * mul / div))),
                max(90, int(round(self.win.getYSize() * self.scala * mul / div))))


# --------------------------------------------------------------------------
# Audio sintetizzato (WAV generati al volo in una cartella temporanea)
# --------------------------------------------------------------------------
def componi_musica(FR=22050):
    """Brano in loop di leggera suspense (Re minore, 92 bpm, 8 battute)."""
    bpm = 92
    beat = 60.0 / bpm
    L = int(FR * beat * 32)
    buf = [0.0] * L
    rnd = random.Random(1860)

    def nota(n):                       # numero MIDI -> Hz
        return 440.0 * 2 ** ((n - 69) / 12)

    def pizzico(t0, midi, dur, amp, smorz=.996, morbido=2):
        f = nota(midi)
        N = max(2, int(FR / f))
        tab = [rnd.uniform(-1, 1) for _ in range(N)]
        for _ in range(morbido):       # attacco più morbido (meno brillante)
            tab = [(tab[i] + tab[i - 1]) * .5 for i in range(N)]
        s = int(t0 * FR)
        n = int(dur * FR)
        coda = int(.03 * FR)
        for k in range(n):
            i = k % N
            v = tab[i]
            tab[i] = smorz * .5 * (v + tab[(i + 1) % N])
            g = amp if k < n - coda else amp * (n - k) / coda
            buf[(s + k) % L] += v * g

    def sinusoide(t0, f, dur, amp, attacco, rilascio, decad=1.0):
        w = 2 * math.pi * f / FR
        c2 = 2 * math.cos(w)
        y1, y2 = math.sin(-w), math.sin(-2 * w)
        s = int(t0 * FR)
        n = int(dur * FR)
        na, nr = max(1, int(attacco * FR)), max(1, int(rilascio * FR))
        e = 1.0
        for k in range(n):
            y0 = c2 * y1 - y2
            y2, y1 = y1, y0
            if k < na:
                g = k / na
            elif k > n - nr:
                g = (n - k) / nr
            else:
                g = 1.0
            e *= decad
            buf[(s + k) % L] += y0 * amp * g * e

    # i - VI - iv - V  (Rem, Sib, Solm, La7): due battute ciascuno
    accordi = [(50, [62, 65, 69]), (46, [58, 62, 65]), (43, [55, 58, 62]), (45, [57, 61, 64, 67])]
    for a, (basso, voci) in enumerate(accordi):
        t_acc = a * 8 * beat
        # tappeto d'archi morbido
        for v in voci[:3]:
            sinusoide(t_acc, nota(v - 12), 8 * beat, .035, 1.2, 1.4)
            sinusoide(t_acc, nota(v - 12) * 2.003, 8 * beat, .012, 1.6, 1.4)
        # basso pizzicato: 1° e 3° tempo
        for b in range(8):
            if b % 2 == 0:
                pizzico(t_acc + b * beat, basso - 12 if b % 4 == 0 else basso - 5, beat * 1.6, .42, .993, 3)
        # ostinato di pizzicati in crome
        schema = [0, 1, 2, 1, 0, 1, 2, 1]
        for b in range(16):
            v = voci[schema[b % 8]] + (12 if b % 8 == 2 else 0)
            accento = .2 if b % 2 == 0 else .13
            pizzico(t_acc + b * beat / 2, v, beat * .9, accento, .989, 5)
    # carillon: brevi frasi nelle battute pari
    frasi = [(1, [(0, 81), (1.5, 77), (2, 76), (3, 74)]),
             (3, [(0, 86), (1, 84), (2, 82), (3, 81)]),
             (5, [(0, 79), (1, 82), (2, 81), (3, 79)]),
             (7, [(0, 76), (1.5, 73), (2.5, 69)])]
    for battuta, note in frasi:
        for (b, m) in note:
            t = (battuta * 4 + b) * beat
            sinusoide(t, nota(m), 1.6, .07, .004, .3, .99985)
            sinusoide(t, nota(m) * 4.01, .5, .005, .004, .2, .9997)
    # tic-tac leggerissimo sui tempi
    for b in range(32):
        f = 1500 if b % 2 == 0 else 1200
        sinusoide(b * beat, f, .03, .014, .002, .02, .9993)
    # leggero filtro passa-basso sul mix: suono più tondo (a giro sul loop, senza stacchi)
    y = 0.0
    for giro in range(2):
        for i in range(L):
            y += .6 * (buf[i] - y)
            if giro:
                buf[i] = y
    picco = max(abs(v) for v in buf) or 1.0
    return [v * .9 / picco for v in buf]


def tono_pianoforte(midi, FR=22050, durata=1.8):
    """Nota di pianoforte: armoniche leggermente inarmoniche che si spengono a velocità diverse."""
    f = 440.0 * 2 ** ((midi - 69) / 12)
    n = int(FR * durata)
    out = [0.0] * n
    for k, amp in enumerate((1.0, .5, .28, .16, .08), start=1):
        fk = k * f * math.sqrt(1 + .0003 * k * k)
        if fk > FR * .45:
            break
        w = 2 * math.pi * fk / FR
        c2 = 2 * math.cos(w)
        y1, y2 = math.sin(-w), math.sin(-2 * w)
        e = amp
        smorz = math.exp(-(1.3 + .9 * k) * (1 + (midi - 60) / 48) / FR)
        for i in range(n):
            y0 = c2 * y1 - y2
            y2, y1 = y1, y0
            e *= smorz
            out[i] += y0 * e
    attacco = int(.004 * FR)
    for i in range(attacco):
        out[i] *= i / attacco
    picco = max(abs(v) for v in out) or 1.0
    return [v * .8 / picco for v in out]


class Suoni:
    FREQ = 22050

    def __init__(self):
        self.attivo = True
        self.sfx = {}
        self.cartella = tempfile.mkdtemp(prefix="carbonaro_")
        try:
            self._genera()
        except Exception as ex:          # l'audio non è indispensabile
            print("Audio non disponibile:", ex)
            self.sfx = {}

    def _scrivi(self, nome, durata, f, volume=0.55, loop=False):
        """f è una funzione del tempo oppure direttamente la lista dei campioni."""
        campioni = f if isinstance(f, list) else [f(i / self.FREQ) for i in range(int(self.FREQ * durata))]
        n = len(campioni)
        dati = array("h")
        for i, v in enumerate(campioni):
            v = max(-1.0, min(1.0, v)) * volume
            fade = 1.0 if loop else min(1.0, (n - i) / (self.FREQ * 0.01))
            dati.append(int(v * fade * 32767))
        percorso = os.path.join(self.cartella, nome + ".wav")
        with wave.open(percorso, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.FREQ)
            w.writeframes(dati.tobytes())
        suono = loader.loadSfx(Filename.fromOsSpecific(percorso))
        self.sfx[nome] = suono
        return suono

    def _genera(self):
        tau = math.tau
        rnd = random.Random(1860)

        def note(seq, decad=5.0, timbro=1.0):
            def f(t):
                v = 0.0
                for inizio, fr, vol in seq:
                    if t >= inizio:
                        dt = t - inizio
                        env = math.exp(-dt * decad) * min(1.0, dt * 200)
                        v += vol * env * (math.sin(tau * fr * dt) + timbro * 0.35 * math.sin(tau * 2 * fr * dt)
                                          + timbro * 0.15 * math.sin(tau * 3 * fr * dt))
                return v
            return f

        self._scrivi("click", 0.06, lambda t: 0.5 * math.sin(tau * 880 * t) * math.exp(-t * 70))
        self._scrivi("giusto", 1.2, note([(0.0, 523.25, .3), (.11, 659.25, .3), (.22, 783.99, .3), (.33, 1046.5, .35)]))
        self._scrivi("sbagliato", 0.38, lambda t: math.exp(-t * 7) * (
            0.35 * (1 if math.sin(tau * 98 * t) > 0 else -1) + 0.3 * math.sin(tau * 104 * t)))
        self._scrivi("bloccato", 0.5, lambda t: (
            (rnd.random() * 2 - 1) * 0.5 * math.exp(-t * 30) + 0.45 * math.sin(tau * 196 * t) * math.exp(-t * 9)
            + 0.3 * math.sin(tau * 587 * t) * math.exp(-t * 14) + 0.2 * math.sin(tau * 1244 * t) * math.exp(-t * 18)))
        self._scrivi("catene", 1.3, lambda t: sum(
            0.35 * math.sin(tau * f0 * (t - s)) * math.exp(-(t - s) * 16) if t > s else 0.0
            for s, f0 in ((0.0, 1480), (0.12, 1210), (0.25, 1660), (0.4, 990), (0.62, 1320), (0.85, 1100), (1.0, 180))))
        self._scrivi("tick", 0.05, lambda t: 0.5 * math.sin(tau * 1760 * t) * math.exp(-t * 110))
        self._scrivi("vittoria", 2.8, note([(0.0, 392.0, .25), (.16, 523.25, .25), (.32, 659.25, .25), (.48, 783.99, .28),
                                            (.72, 1046.5, .3), (.72, 523.25, .2), (.72, 659.25, .18)], decad=1.6))
        self._scrivi("porta", 2.0, lambda t: 0.3 * math.sin(tau * (140 + 90 * t + 12 * math.sin(t * 30)) * t)
                     * min(1.0, t * 4) * math.exp(-t * 0.8) + (rnd.random() * 2 - 1) * 0.06)
        self._scrivi("sconfitta", 1.8, lambda t: (
            (rnd.random() * 2 - 1) * 0.9 * math.exp(-t * 7) + 0.5 * math.sin(tau * (70 - 18 * t) * t) * math.exp(-t * 1.5)
            + (0.25 * math.sin(tau * 233 * (t - .5)) * math.exp(-(t - .5) * 3) if t > .5 else 0)
            + (0.25 * math.sin(tau * 220 * (t - .9)) * math.exp(-(t - .9) * 2) if t > .9 else 0)))
        # archivio segreto e treno: libreria che scorre, scambio, fischio, sbuffo, incidente
        def inviluppo(t, durata, attacco=.15, rilascio=.4):
            return min(1.0, t / attacco) * min(1.0, max(0.0, (durata - t) / rilascio))

        self._scrivi("scorrimento", 2.6, lambda t: inviluppo(t, 2.6) * (
            (rnd.random() * 2 - 1) * 0.22 * (0.6 + 0.4 * math.sin(tau * 7 * t))
            + 0.35 * math.sin(tau * (52 + 6 * math.sin(t * 5)) * t) + 0.12 * math.sin(tau * 31 * t)))
        self._scrivi("scambio", 0.2, lambda t: (
            0.45 * math.sin(tau * 420 * t) * math.exp(-t * 60) + (rnd.random() * 2 - 1) * 0.3 * math.exp(-t * 90)
            + (0.4 * math.sin(tau * 640 * (t - .07)) * math.exp(-(t - .07) * 70) if t > .07 else 0)))
        self._scrivi("fischio", 1.1, lambda t: inviluppo(t, 1.1, .04, .25) * 0.3 * (
            math.sin(tau * (780 + 6 * math.sin(t * 40)) * t) + 0.8 * math.sin(tau * (1040 + 6 * math.sin(t * 40)) * t)))
        self._scrivi("sbuffo", 0.16, lambda t: math.exp(-t * 28) * (
            (rnd.random() * 2 - 1) * 0.35 + 0.35 * math.sin(tau * 85 * t)))
        self._scrivi("incidente", 1.2, lambda t: (
            (rnd.random() * 2 - 1) * 0.7 * math.exp(-t * 9) + 0.45 * math.sin(tau * (110 - 50 * t) * t) * math.exp(-t * 2.5)
            + (0.3 * math.sin(tau * 196 * (t - .35)) * math.exp(-(t - .35) * 5) if t > .35 else 0)))
        # camino: brusio morbido (rumore filtrato) e pochi scoppiettii attutiti
        n = int(self.FREQ * 6)
        fuoco = [0.0] * n
        lp = 0.0
        for i in range(n):
            lp += .02 * (rnd.uniform(-1, 1) - lp)
            fuoco[i] = lp
        for _ in range(26):
            inizio = rnd.randrange(n)
            durata = rnd.randint(250, 700)
            amp = rnd.uniform(.08, .22)
            f = 0.0
            for k in range(durata):
                f += .3 * (rnd.uniform(-1, 1) - f)
                fuoco[(inizio + k) % n] += f * amp * math.exp(-k / (durata * .25))
        picco = max(abs(v) for v in fuoco) or 1.0
        amb = self._scrivi("fuoco", 0, [v * .5 / picco for v in fuoco], volume=1.0, loop=True)
        amb.setLoop(True)
        amb.setVolume(0.1)
        # pianoforte suonabile: quattro campioni (Do3..Do6) trasposti con la velocità
        self.voci_piano = {}
        for base_midi in (48, 60, 72, 84):
            self._scrivi("piano_%d" % base_midi, 0, tono_pianoforte(base_midi, self.FREQ), volume=.9)
            percorso = os.path.join(self.cartella, "piano_%d.wav" % base_midi)
            self.voci_piano[base_midi] = [loader.loadSfx(Filename.fromOsSpecific(percorso)) for _ in range(3)]
        self.turno_voce = 0
        # musica di sottofondo: leggera suspense, in loop
        mus = self._scrivi("musica", 0, componi_musica(self.FREQ), volume=1.0, loop=True)
        mus.setLoop(True)
        mus.setVolume(0.38)

    def suona(self, nome):
        if self.attivo and nome in self.sfx:
            self.sfx[nome].play()

    def ambiente(self, acceso, musica=True):
        """Accende/spegne il camino e la musica di sottofondo."""
        for nome, on in (("fuoco", acceso), ("musica", acceso and musica)):
            s = self.sfx.get(nome)
            if s is None:
                continue
            if on and self.attivo:
                if s.status() != s.PLAYING:
                    s.play()
            else:
                s.stop()

    def nota_piano(self, midi):
        if not self.attivo or not getattr(self, "voci_piano", None):
            return
        base_midi = max(48, min(84, 48 + 12 * ((midi - 48) // 12)))
        voci = self.voci_piano[base_midi]
        self.turno_voce = (self.turno_voce + 1) % len(voci)
        v = voci[self.turno_voce]
        v.stop()
        v.setPlayRate(2 ** ((midi - base_midi) / 12))
        v.play()

    def volume_musica(self, volume):
        s = self.sfx.get("musica")
        if s is not None:
            s.setVolume(volume)

    def volume_camino(self, distanza):
        """Il fuoco si sente bene solo quando ci si avvicina al camino."""
        s = self.sfx.get("fuoco")
        if s is not None:
            s.setVolume(.04 + .22 * max(0.0, min(1.0, 1 - (distanza - 1.0) / 5.0)))

    def pulisci(self):
        shutil.rmtree(self.cartella, ignore_errors=True)


# --------------------------------------------------------------------------
# Aiuti per costruire la scena
# --------------------------------------------------------------------------
def cilindro(risoluzione=12, start=-.5, direction=(0, 1, 0)):
    """Cilindro di Ursina con le normali (senza, l'illuminazione risulta piatta)."""
    m = Cylinder(risoluzione, start=start, direction=direction)
    asse = Vec3(*direction).normalized()
    v = list(m.vertices)
    normali = []
    for i in range(0, len(v) - 2, 3):              # la mesh è una lista di triangoli
        a, b, c = Vec3(*v[i]), Vec3(*v[i + 1]), Vec3(*v[i + 2])
        fn = (b - a).cross(c - a)
        fn = fn.normalized() if fn.length() > 1e-9 else asse
        if abs(fn.dot(asse)) > .9:                  # tappi: normale piatta
            normali += [fn, fn, fn]
        else:                                       # fianco: normale radiale (superficie liscia)
            for p in (a, b, c):
                r = p - asse * p.dot(asse)
                normali.append(r.normalized() if r.length() > 1e-9 else fn)
    m.normals = normali
    m.generate()
    return m


def blocco(parent, pos, scala, col=None, texture=None, rot=(0, 0, 0), tex_scale=None, model="cube"):
    e = Entity(parent=parent, model=model, position=pos, scale=scala, rotation=rot)
    if texture is not None:
        e.texture = texture
    if col is not None:
        e.color = col
    if tex_scale is not None:
        e.texture_scale = tex_scale
    return e


_SPRITE_FRAG = """#version 150
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec2 recinto;
in vec2 uv;
in vec3 wpos;
in vec4 vcol;
out vec4 fragColor;
void main() {
    if (recinto.x * (wpos.z - recinto.y) < 0.0) discard;
    fragColor = texture(p3d_Texture0, uv) * p3d_ColorScale * vcol;
}
"""
_SHADER_SPRITE = []


def shader_sprite():
    if not _SHADER_SPRITE:
        _SHADER_SPRITE.append(Shader(language=Shader.GLSL, vertex=_VERTEX, fragment=_SPRITE_FRAG,
                                     default_input={"texture_scale": Vec2(1, 1), "texture_offset": Vec2(0, 0),
                                                    "recinto": Vec2(0, 0)}))
    return _SHADER_SPRITE[0]


def sprite_luminoso(parent, pos, scala, texture, col):
    """Quad sempre rivolto alla camera, in fusione additiva (fiamme, aloni). Gli aloni sono ritagliati contro il muro
    tra studio e archivio: un quad rivolto alla camera sporge dal suo centro e altrimenti si vedrebbe attraverso il muro."""
    e = Entity(parent=parent, model="quad", texture=texture, position=pos, scale=scala,
               color=col, shader=shader_sprite(), billboard=True)
    try:
        studio = e.world_position.z > -4.1
    except Exception:
        studio = False
    e.set_shader_input("recinto", Vec2(1, -4.0) if studio else Vec2(-1, -4.2))
    e.setTransparency(TransparencyAttrib.MAlpha)
    e.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    e.setDepthWrite(False)
    e.setBin("fixed", 20)
    return e


def avvolgi(testo, caratteri):
    """Va a capo ogni ~'caratteri' caratteri senza spezzare le parole."""
    righe = []
    for paragrafo in testo.split("\n"):
        riga = ""
        for parola in paragrafo.split(" "):
            if riga and len(riga) + 1 + len(parola) > caratteri:
                righe.append(riga)
                riga = parola
            else:
                riga = (riga + " " + parola).strip()
        righe.append(riga)
    return "\n".join(righe)


def testo_ui(parent, t, pos=(0, 0), scala=1.0, col=PERGAMENA, tipo="r", origin=(0, 0), wordwrap=0, z=0):
    if wordwrap:
        t = avvolgi(t, wordwrap)
    kw = dict(parent=parent, text=t, position=pos, scale=scala, color=col, origin=origin, z=z)
    f = font_ui(tipo)
    return Text(**kw)


def quad_ui(parent, pos, scala, col=color.white, texture=None, z=0):
    e = Entity(parent=parent, model="quad", position=pos, scale=scala, color=col, z=z)
    if texture is not None:
        e.texture = texture
    return e


def pulsante(parent, etichetta, pos, scala, primario=True, azione=None):
    b = Button(parent=parent, text=etichetta, position=pos, scale=scala,
               color=BORDEAUX if primario else C(34, 32, 38),
               highlight_color=BORDEAUX_CHIARO if primario else C(60, 56, 64),
               pressed_color=BORDEAUX_SCURO if primario else C(20, 18, 22),
               text_color=ORO_CHIARO if primario else PERGAMENA)
    b.text_entity.scale *= 1.1
    b.on_click = azione
    return b

ALTEZZA_RIGA = .045                      # interlinea di RigheCentrate (una riga = un Text a parte)
ALTEZZA_RIGA_TESTO = .0185               # altezza reale di una riga di un Text a più righe, a scala 1 (misurata)

def adatta_testo(t, scala_base, larg_max, alt_max=None):
    k = scala_base
    # FIX: Stima più generosa per le lettere, evita rimpicciolimenti anomali
    w = max(t.width, max((len(r) for r in str(t.text).split("\n")), default=0) * .016)
    if w > 0 and w * k > larg_max:
        k = larg_max / w
    if alt_max:
        riga = ALTEZZA_RIGA if isinstance(t, RigheCentrate) else ALTEZZA_RIGA_TESTO
        righe = str(t.text).count("\n") + 1
        if righe * riga * k > alt_max:
            k = alt_max / (righe * riga)
    t.scale = k
    return k

class TestiAdattivi:
    def __init__(self):
        self.voci = []

    def aggiungi(self, t, scala, limite, altezza=None):
        self.voci.append((t, scala, limite, altezza))
        return t

    def adatta(self, a):
        for t, scala, limite, altezza in self.voci:
            adatta_testo(t, scala, limite(a), altezza)


def font_ui(tipo):
    if tipo == "b":
        return "garabd.ttf" # File per il Grassetto
    elif tipo == "i":
        return "garai.ttf"  # File per il Corsivo
    else:
        return "gara.ttf"   # File per il font Regolare

# --------------------------------------------------------------------------
# Campo di testo per le risposte
# --------------------------------------------------------------------------
class CampoTesto(Entity):
    def __init__(self, parent, pos, larghezza, su_invio):
        super().__init__(parent=parent, position=pos)
        self.valore = ""
        self.attivo = False
        self.su_invio = su_invio
        self.larghezza = larghezza
        quad_ui(self, (0, 0), (larghezza + .012, .082), BORDEAUX, z=.01)
        self.sfondo = quad_ui(self, (0, 0), (larghezza, .07), C(252, 246, 232))
        self.etichetta = testo_ui(self, "La tua risposta:", (-larghezza / 2, .062), .9, C(110, 84, 60), "i", (-.5, 0))
        self.segnaposto = testo_ui(self, "Scrivi qui la risposta…", (-larghezza / 2 + .02, 0), 1.3,
                                   C(170, 150, 128), "i", (-.5, 0), z=-.01)
        self.testo = testo_ui(self, "", (-larghezza / 2 + .02, 0), 1.45, INCHIOSTRO, "r", (-.5, 0), z=-.01)
        self.cursore = quad_ui(self, (-larghezza / 2 + .02, 0), (.003, .045), INCHIOSTRO, z=-.01)

    def svuota(self):
        self.valore = ""
        self._aggiorna()

    def _aggiorna(self):
        self.testo.text = self.valore
        self.segnaposto.enabled = not self.valore
        # Text.width non tiene conto della scala dell'entità: la applichiamo noi.
        # Se la risposta è lunga, il testo si rimpicciolisce per restare nella casella.
        larghezza_base = self.testo.width if self.valore else 0
        spazio = self.larghezza - .05
        scala = 1.45 if larghezza_base * 1.45 <= spazio else spazio / larghezza_base
        self.testo.scale = scala
        self.cursore.x = -self.larghezza / 2 + .024 + larghezza_base * scala

    def text_input(self, key):
        if self.attivo and len(self.valore) < MAX_INPUT and key.isprintable():
            self.valore += key
            self._aggiorna()

    def input(self, key):
        if not self.attivo:
            return
        if key in ("backspace", "backspace hold"):
            self.valore = self.valore[:-1]
            self._aggiorna()
        elif key in ("enter", "numpad enter"):
            self.su_invio()

    def update(self):
        self.cursore.visible = self.attivo and int(time.monotonic() * 2) % 2 == 0


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# L'archivio segreto dietro la libreria
# --------------------------------------------------------------------------
# Le coordinate sono quelle del mondo. La libreria di destra (x = 2.5) scorre verso l'angolo
# e libera un varco nella parete nord dello studio (z = -4.1): oltre c'è una sala enorme, con la
# ferrovia a grandezza d'uomo sul pavimento.
APERTURA_X0, APERTURA_X1, APERTURA_ALTEZZA = 1.75, 3.0, 2.4
SCORRIMENTO_LIBRERIA = 1.25
OSTACOLO_LIBRERIA_CHIUSA = (1.7, -4.2, 3.3, -3.5)
SPAZIO_INGRESSO = 2.0                                           # metri in più tra l'ingresso e tutto il resto dell'archivio
ARC_X0, ARC_X1, ARC_Z0, ARC_Z1 = -17.05, 21.85, -27.4 - SPAZIO_INGRESSO, -4.2   # interno dell'archivio
ARC_ALTEZZA = 7.5                                               # soffitto molto più alto di quello dello studio
ALTEZZA_STUDIO = 3.4
RAGGIO_GIOCATORE = .28
LARGHEZZA_FRAMMENTI = 1.5            # la pergamena dei frammenti in basso: nove slot a distanza PASSO_SLOT
PASSO_SLOT = .155
RAGGIO_GLOBO = .18                    # il mappamondo: 36 cm di diametro
GLOBO_DISTANZA = (.32, .78, .55)      # modalità globo: distanza della visuale (minima con lo zoom, massima, iniziale)
GLOBO_BECCHEGGIO = 45                 # quanto si inclina il globo con W-S (gradi, in su e in giù)
GLOBO_INCLINAZIONE_INIZIALE = -25     # il nord è un po' rivolto verso chi guarda, come un mappamondo visto dall'alto
LANTERNE_ARCHIVIO = ([(x, -6.2) for x in (-5.6, 2.4, 10.4)]                  # nella fascia d'ingresso, dove sta il Quadro
                     + [(x, z - SPAZIO_INGRESSO) for z in (-8.4, -14.1, -19.8, -25.5)
                        for x in (-13.6, -5.6, 2.4, 10.4, 18.4)])
QUOTA_LANTERNE = 4.7                      # le lanterne pendono basse: la sala è alta, la luce deve arrivare a terra


class StanzaSegreta:
    """Geometria dell'archivio, libreria scorrevole, luci e zone in cui ci si può muovere."""

    def __init__(self, gioco):
        self.g = gioco
        self.aperta = False
        self.luminosita = 0.0                 # le luci dell'archivio si accendono quando il passaggio si apre
        self.luminosita_obiettivo = 0.0
        self.progresso = self.progresso_obiettivo = 0.0
        self.durata_apertura = 2.6
        self.luci = []
        self.libreria = None
        self.libreria_x_chiusa = None
        self.ostacolo_aperto = (APERTURA_X1, -4.2, APERTURA_X1 + 1.5, -3.5)
        self.nodi_archivio = []               # tutto ciò che sta dentro l'archivio (lo riempie Gioco._costruisci_stanza)

    def mostra_archivio(self, si):
        """A passaggio chiuso l'archivio è nascosto: dietro il muro non si vede, ma Panda3D lo disegnerebbe lo stesso
        (non sa che il muro lo copre) ogni volta che nello studio si guarda a nord. Così si risparmiano centinaia di oggetti."""
        for n in self.nodi_archivio:
            if si:
                n.show()
            else:
                n.hide()

    # ------------------------------------------------------------------ costruzione
    def costruisci_parete_nord(self):
        """Parete nord dello studio con il varco (al posto del cubo unico di prima)."""
        m, g = self.g.mondo, self.g
        spess = .2
        pezzi = [((-4.2 + APERTURA_X0) / 2, 1.7, APERTURA_X0 + 4.2, 3.4),                 # a sinistra del varco
                 ((APERTURA_X1 + 4.2) / 2, 1.7, 4.2 - APERTURA_X1, 3.4),                  # a destra del varco
                 ((APERTURA_X0 + APERTURA_X1) / 2, (APERTURA_ALTEZZA + 3.4) / 2,
                  APERTURA_X1 - APERTURA_X0, 3.4 - APERTURA_ALTEZZA)]                     # architrave
        for cx, cy, larg, alt in pezzi:
            blocco(m, (cx, cy, -4.1), (larg, alt, spess), texture=g.t_parati,
                   tex_scale=(10 * larg / 8.4, 4 * alt / 3.4))

    def costruisci(self):
        g, m = self.g, self.g.mondo
        larg, prof = ARC_X1 - ARC_X0, ARC_Z1 - ARC_Z0
        cx, cz = (ARC_X0 + ARC_X1) / 2, (ARC_Z0 + ARC_Z1) / 2
        alto = ARC_ALTEZZA
        pietra = C(150, 142, 136)
        # pavimento in pietra e soffitto a travi
        blocco(m, (cx, 0, cz), (larg, 1, prof), col=C(120, 112, 106), texture=g.t_pietra,
               tex_scale=(larg / 1.4, prof / 1.4), model="plane")
        blocco(m, (cx, alto, cz), (larg, 1, prof), col=C(36, 24, 18), texture=g.t_legno,
               tex_scale=(larg / 1.6, prof / 1.6), model="plane", rot=(180, 0, 0))
        for i in range(6):
            blocco(m, (ARC_X0 + 1.6 + i * (larg - 3.2) / 5, alto - .15, cz), (.26, .3, prof),
                   col=C(70, 44, 26), texture=g.t_legno)
        for z in (-9.8, -15.8, -21.8, -27.8):
            blocco(m, (cx, alto - .12, z), (larg, .22, .2), col=C(60, 38, 22), texture=g.t_legno)
        # muri: ovest, est, fondo; a sud la parete dello studio continua a destra e a sinistra e si alza sopra di essa
        lungo = prof + .4
        zc = (ARC_Z0 + ARC_Z1) / 2
        muri = [(ARC_X0 - .1, alto / 2, zc, .2, alto, lungo),
                (ARC_X1 + .1, alto / 2, zc, .2, alto, lungo),
                (cx, alto / 2, ARC_Z0 - .1, larg + .4, alto, .2),
                ((ARC_X0 - .2 - 4.2) / 2, alto / 2, ARC_Z1 + .1, -4.2 - (ARC_X0 - .2), alto, .2),
                ((4.2 + ARC_X1 + .2) / 2, alto / 2, ARC_Z1 + .1, ARC_X1 + .2 - 4.2, alto, .2),
                (0, (ALTEZZA_STUDIO + alto) / 2, ARC_Z1 + .1, 8.4, alto - ALTEZZA_STUDIO, .2)]
        for (x, y, z, sx, sy, sz) in muri:
            blocco(m, (x, y, z), (sx, sy, sz), col=pietra, texture=g.t_pietra, tex_scale=(max(sx, sz) * .7, sy * .7))
        # rivestimento in pietra, dal lato dell'archivio, della parete dello studio (con il varco)
        for (x0, x1, y0, y1) in ((-4.2, APERTURA_X0, 0, ALTEZZA_STUDIO), (APERTURA_X1, 4.2, 0, ALTEZZA_STUDIO),
                                 (APERTURA_X0, APERTURA_X1, APERTURA_ALTEZZA, ALTEZZA_STUDIO)):
            blocco(m, ((x0 + x1) / 2, (y0 + y1) / 2, ARC_Z1 - .02), (x1 - x0, y1 - y0, .04), col=pietra,
                   texture=g.t_pietra, tex_scale=((x1 - x0) * .7, (y1 - y0) * .7))
        # zoccolo scuro lungo l'interno
        legno = LEGNO_SCURO
        blocco(m, (ARC_X0 + .03, .07, zc), (.06, .14, prof), col=legno)
        blocco(m, (ARC_X1 - .03, .07, zc), (.06, .14, prof), col=legno)
        blocco(m, (cx, .07, ARC_Z0 + .03), (larg, .14, .06), col=legno)
        # lesene di pietra lungo i muri lunghi
        for z in (-7.0, -10.6, -14.2, -17.8, -21.4, -25.0, -28.6):
            self._lesena(ARC_X0 + .26, z)
            self._lesena(ARC_X1 - .26, z)
        # sei librerie sul fondo, con gli stendardi tricolori tra l'una e l'altra
        for i in range(12):
            x = 2.4 + (i - 5.5) * 3.2
            g._costruisci_libreria((x, 0, ARC_Z0 + .22))
            g.ostacoli.append((x - .8, ARC_Z0, x + .8, ARC_Z0 + .55))
        for x in (-13.6, -7.2, -.8, 5.6, 12.0, 18.4):
            self._stendardo(x, ARC_Z0 + .06)
        # lanterne appese: la luce dell'archivio
        for (x, z) in LANTERNE_ARCHIVIO:
            self._lanterna(x, z, Vec3(6.0, 3.8, 1.9))
        # la libreria scorrevole è quella di destra dello studio
        self.libreria = g.libreria_scorrevole
        self.libreria_x_chiusa = self.libreria.x

    def _lesena(self, x, z):
        g, m = self.g, self.g.mondo
        blocco(m, (x, .12, z), (.62, .24, .62), col=C(150, 142, 136), texture=g.t_pietra)
        blocco(m, (x, ARC_ALTEZZA / 2, z), (.46, ARC_ALTEZZA - .5, .46), col=C(150, 142, 136), texture=g.t_pietra,
               tex_scale=(1, 3))
        blocco(m, (x, ARC_ALTEZZA - .12, z), (.62, .24, .62), col=C(150, 142, 136), texture=g.t_pietra)
        g.ostacoli.append((x - .31, z - .31, x + .31, z + .31))

    def _stendardo(self, x, z):
        m = self.g.mondo
        for i, c in enumerate(TRICOLORE):
            blocco(m, (x + (i - 1) * .52, 2.1, z), (.5, 1.5, .03), col=c)
        blocco(m, (x, 2.9, z), (1.7, .06, .05), col=ORO_SCURO)

    def _lanterna(self, x, z, col):
        """Lanterna con lume grande, appesa al soffitto con una catena: ogni lanterna è una luce della scena."""
        g, m = self.g, self.g.mondo
        y = QUOTA_LANTERNE
        blocco(m, (x, (ARC_ALTEZZA + y) / 2, z), (.035, ARC_ALTEZZA - y, .035), col=FERRO)                    # catena
        blocco(m, (x, y - .25, z), (.34, .05, .34), col=ORO_SCURO)                              # fondo
        blocco(m, (x, y + .22, z), (.40, .05, .40), col=ORO_SCURO)                              # coperchio
        for dx, dz in ((.16, .16), (-.16, .16), (.16, -.16), (-.16, -.16)):
            blocco(m, (x + dx, y - .015, z + dz), (.03, .5, .03), col=ORO_SCURO)               # montanti
        luce = {"col": Vec3(0, 0, 0), "piena": col, "tremolio": .16}
        g._candela(m, (x, y - .22, z), .22, 3.2, luce)
        self.luci.append(luce)

    def lampione(self, x, z):
        """Lampione a candela sul bordo del prato: una luce vera, bassa, per illuminare gli ultimi binari."""
        g, m = self.g, self.g.mondo
        blocco(m, (x, .06, z), (.34, .12, .34), col=FERRO, model=cilindro(10, start=-.5))
        blocco(m, (x, 1.3, z), (.07, 2.6, .07), col=FERRO)
        blocco(m, (x, 2.5, z), (.34, .05, .34), col=ORO_SCURO)
        blocco(m, (x, 2.95, z), (.4, .05, .4), col=ORO_SCURO)
        for dx, dz in ((.15, .15), (-.15, .15), (.15, -.15), (-.15, -.15)):
            blocco(m, (x + dx, 2.73, z + dz), (.03, .46, .03), col=ORO_SCURO)
        luce = {"col": Vec3(0, 0, 0), "piena": Vec3(5.2, 3.7, 1.8), "tremolio": .14}
        g._candela(m, (x, 2.53, z), .2, 2.0, luce)
        self.luci.append(luce)
        g.ostacoli.append((x - .15, z - .15, x + .15, z + .15))

    def candelabro(self, pos, col):
        """Candelabro d'oro accanto ai fascicoli (una luce)."""
        g, m = self.g, self.g.mondo
        x, y, z = pos
        blocco(m, (x, .03, z), (.3, .06, .3), col=ORO_SCURO, model=cilindro(12, start=-.5))
        blocco(m, (x, .62, z), (.04, 1.2, .04), col=ORO)
        blocco(m, (x, 1.22, z), (.4, .03, .04), col=ORO)
        blocco(m, (x, 1.22, z), (.04, .03, .4), col=ORO)
        for dx, dz in ((.2, 0), (-.2, 0), (0, .2), (0, -.2)):
            luce = {"col": Vec3(0, 0, 0), "piena": col, "tremolio": .3} if (dx, dz) == (.2, 0) else None
            g._candela(m, (x + dx, 1.23, z + dz), .13, .9, luce)
            if luce is not None:
                self.luci.append(luce)
        g.ostacoli.append((x - .22, z - .22, x + .22, z + .22))

    # ------------------------------------------------------------------ passaggio
    def apri(self, durata=2.6):
        if self.aperta:
            return
        self.aperta = True
        self.durata_apertura = durata
        self.progresso_obiettivo = 1.0
        self.luminosita_obiettivo = 1.0
        self.mostra_archivio(True)
        ostacoli = self.g.ostacoli
        if OSTACOLO_LIBRERIA_CHIUSA in ostacoli:
            ostacoli.remove(OSTACOLO_LIBRERIA_CHIUSA)
        ostacoli.append(self.ostacolo_aperto)

    def chiudi_subito(self):
        self.aperta = False
        self.progresso = self.progresso_obiettivo = 0.0
        self.luminosita = self.luminosita_obiettivo = 0.0
        self.mostra_archivio(False)
        ostacoli = self.g.ostacoli
        if self.ostacolo_aperto in ostacoli:
            ostacoli.remove(self.ostacolo_aperto)
        if OSTACOLO_LIBRERIA_CHIUSA not in ostacoli:
            ostacoli.append(OSTACOLO_LIBRERIA_CHIUSA)
        self._applica()

    @property
    def punto_libreria(self):
        """Dove guardare mentre la libreria scorre."""
        return Vec3(self.libreria_x_chiusa + .6, 1.3, -3.8)

    def aggiorna(self, dt):
        """Fa scorrere la libreria e accende (o spegne) piano piano le luci dell'archivio."""
        self.progresso = self._verso(self.progresso, self.progresso_obiettivo, dt / self.durata_apertura)
        self.luminosita = self._verso(self.luminosita, self.luminosita_obiettivo, dt * .5)
        self._applica()

    @staticmethod
    def _verso(valore, obiettivo, passo):
        if valore < obiettivo:
            return min(obiettivo, valore + passo)
        return max(obiettivo, valore - passo)

    def _applica(self):
        u = self.progresso
        u = u * u * (3 - 2 * u)                              # partenza e arrivo dolci
        if self.libreria is not None:
            self.libreria.x = self.libreria_x_chiusa + SCORRIMENTO_LIBRERIA * u
        for l in self.luci:
            l["base"] = l["piena"] * self.luminosita

    # ------------------------------------------------------------------ dove si cammina
    def zone_agibili(self):
        """Rettangoli (x0, z0, x1, z1) per il CENTRO del giocatore, già ristretti del suo raggio."""
        if not self.aperta:
            return []
        r = RAGGIO_GIOCATORE
        return [(APERTURA_X0 + r, ARC_Z1 - .4, APERTURA_X1 - r, -3.4),           # il varco
                (ARC_X0 + r, ARC_Z0 + r, ARC_X1 - r, ARC_Z1 - r)]               # l'archivio

    def nell_archivio(self, x, z):
        return ARC_X0 < x < ARC_X1 and ARC_Z0 < z < ARC_Z1 - .15


# --------------------------------------------------------------------------
# Analizza fascicoli: fascicoli a terra (3D) e finestra con le schede da numerare (UI)
# --------------------------------------------------------------------------
class FascicoliPatriottici:
    """I quattro fascicoli sparsi sul tappeto dell'archivio. Si esaminano con un clic, come ogni enigma."""
    CENTRO = (-0.8, 0, -5.7 - SPAZIO_INGRESSO)
    POSIZIONI = [(-.75, -.4, 18), (.2, -.65, -32), (-.45, .35, 72), (.5, .2, 8)]       # x, z locali, rotazione

    def __init__(self, gioco):
        g = gioco
        self.radice = Entity(parent=g.mondo, position=self.CENTRO)
        g.interattivi["libreria"] = self.radice
        # un tappeto sotto i fascicoli: sul pavimento di pietra dell'archivio si leggono meglio
        blocco(g.mondo, (self.CENTRO[0], .008, self.CENTRO[2]), (3.0, 1, 2.4), texture=g.t_tappeto, model="plane")
        rnd = random.Random(1848)
        for i, (x, z, rot) in enumerate(self.POSIZIONI):
            cartella = Entity(parent=self.radice, position=(x, 0, z), rotation_y=rot)
            blocco(cartella, (0, .018, 0), (.38, .036, .27), texture=g.t_fascicoli[i])
            blocco(cartella, (.02, .002, .01), (.36, .004, .26), col=C(120, 84, 44))             # ombra sotto
            # un paio di fogli sparsi fuori dalla cartella
            for k in range(2):
                blocco(cartella, (rnd.uniform(-.2, .2), .004 + k * .002, rnd.uniform(.16, .24) * rnd.choice((-1, 1))),
                       (.2, .003, .27), col=C(236, 226, 196), rot=(0, rnd.uniform(-35, 35), 0))
        Entity(parent=self.radice, model="cube", collider="box", position=(0, .25, 0), scale=(2.4, .5, 1.9),
               visible=False, id_oggetto="libreria")


class PannelloFascicoli(Entity):
    """Dentro la finestra dell'enigma: quattro schede cliccabili (per numerarle) e un lucchetto accanto al codice."""
    SCHEDA = (.25, .16)

    def __init__(self, parent, gioco):
        super().__init__(parent=parent, enabled=False)
        self.g = gioco
        self.ordine = []                                  # indici delle schede, nell'ordine in cui il giocatore le numera
        self.badge = []
        self.testo_badge = []
        testo_ui(self, "Clic su una scheda per numerarla nell'ordine in cui accaddero i fatti.", (0, .142), .8,
                 C(110, 84, 60), "i")
        for i, (titolo, anno) in enumerate(FASCICOLI):
            x = (i - (len(FASCICOLI) - 1) / 2) * .272
            scheda = Entity(parent=self, position=(x, .045), rotation_z=(-3, 2.5, -1.5, 3)[i % 4])
            b = Button(parent=scheda, scale=self.SCHEDA, color=color.white, highlight_color=C(255, 248, 226),
                       pressed_color=C(228, 212, 176), texture=gioco.t_scheda)
            b.on_click = lambda i=i: self._clic(i)
            testo_ui(scheda, avvolgi(titolo, 14), (0, .028), 1.05, INCHIOSTRO, "b", z=-.01)
            testo_ui(scheda, "(%d)" % anno, (0, -.045), 1.9, BORDEAUX, "b", z=-.01)
            disco = quad_ui(scheda, (-.118, .076), (.035, .035), BORDEAUX, z=-.02)
            disco.enabled = False
            numero = testo_ui(scheda, "", (-.118, .076), 1.5, ORO_CHIARO, "b", z=-.03)
            self.badge.append(disco)
            self.testo_badge.append(numero)
        self.lucchetto = quad_ui(self, (-.385, -.125), (.075, .075), color.white, gioco.t_lucchetto)
        self.lucchetto.enabled = False              # il codice non si digita più qui: niente campo, niente lucchetto
        # il codice ricavato dall'ordine scelto: appare quando tutte le schede sono numerate, cosi' lo si ricorda al Quadro
        self.etichetta_codice = testo_ui(self, "Codice ricavato", (0, -.105), .9, C(110, 84, 60), "i")
        self.testo_codice = testo_ui(self, "", (0, -.15), 2.6, BORDEAUX, "b")
        self.etichetta_codice.enabled = self.testo_codice.enabled = False

    def _clic(self, i):
        if i in self.ordine:
            self.ordine.remove(i)
        else:
            self.ordine.append(i)
        self.g.suoni.suona("click")
        self._aggiorna_badge()

    def _aggiorna_badge(self):
        for i, (disco, numero) in enumerate(zip(self.badge, self.testo_badge)):
            numerata = i in self.ordine
            disco.enabled = numerata
            numero.text = str(self.ordine.index(i) + 1) if numerata else ""
        completo = len(self.ordine) == len(FASCICOLI)
        self.etichetta_codice.enabled = self.testo_codice.enabled = completo
        self.testo_codice.text = " ".join(str(FASCICOLI[i][1])[-1] for i in self.ordine) if completo else ""

    def azzera(self):
        """Nuova partita o riapertura: schede senza numeri e lucchetto chiuso."""
        self.ordine = []
        self._aggiorna_badge()
        self.lucchetto.texture = self.g.t_lucchetto

    def apri_lucchetto(self):
        self.lucchetto.texture = self.g.t_lucchetto_aperto


# --------------------------------------------------------------------------
# La ferrovia a grandezza d'uomo (solo grafica: la logica è in Griglia)
# --------------------------------------------------------------------------
# Tutto è costruito in "unità del modello" (una tessera = LATO_TRENO) dentro un nodo ingrandito di SCALA_TRENO:
# una tessera misura 1,2 m, il treno è alto 80 cm e si cammina sul prato tra i binari.
LATO_TRENO = .30
SCALA_TRENO = 6.0
LATO_REALE = LATO_TRENO * SCALA_TRENO
QUOTA_PONTE = .36                      # altezza dell'impalcato dei ponti (2,16 m): anche tu passi sotto a testa alta, senza accovacciarti
ZOCCOLO = .05                          # il prato è appena rialzato rispetto al pavimento di pietra
PLASTICO_CENTRO = (2.4, -17.2 - SPAZIO_INGRESSO)         # x, z nel mondo
ASFALTO = C(78, 78, 86)
GHIAIA = C(116, 112, 106)
PIETRA_PONTE = C(150, 146, 140)


class Mattoncini:
    """Cubetti colorati sotto un unico nodo. Quelli dritti si fondono in una sola mesh (molto più veloce da disegnare);
    quelli inclinati restano separati."""

    def __init__(self, parent, pos=(0, 0, 0)):
        self.nodo = Entity(parent=parent, position=pos)
        self.liberi = Entity(parent=parent, position=pos)

    def box(self, pos, scala, col, rot=None):
        if rot is None:
            return Entity(parent=self.nodo, model="cube", position=pos, scale=scala, color=col)
        return Entity(parent=self.liberi, model="cube", position=pos, scale=scala, rotation=rot, color=col)

    def posa(self, x=0.0, z=0.0, quarti=0, y=0.0):
        return _Posa(self, x, z, quarti, y)

    def fondi(self):
        try:
            self.nodo.combine()
        except Exception as ex:              # nel peggiore dei casi restano cubetti separati: più lento ma identico
            print("combine non riuscito:", ex)
        return self


class _Posa:
    """Sposta e ruota (a quarti di giro) i cubetti 'locali' di una tessera dentro il Mattoncini."""

    def __init__(self, m, x, z, quarti, y):
        self.m, self.x, self.z, self.q, self.y = m, x, z, quarti % 4, y

    def ruotata(self, k):
        return _Posa(self.m, self.x, self.z, self.q + k, self.y)

    def box(self, pos, scala, col, rot=None):
        px, py, pz = pos
        c, s = ((1, 0), (0, 1), (-1, 0), (0, -1))[self.q]          # rotation_y = 90 * q: da +z verso +x
        wx, wz = px * c + pz * s, -px * s + pz * c
        sx, sy, sz = scala
        if rot is None:
            if self.q % 2:
                sx, sz = sz, sx
        else:
            rot = (rot[0], rot[1] + 90 * self.q, rot[2])
        return self.m.box((self.x + wx, self.y + py, self.z + wz), (sx, sy, sz), col, rot)


def _colori_binario(rosso):
    """(traversine, rotaie): grigie e legno normali, rosse sui binari pattugliati dagli austriaci."""
    return (C(112, 34, 34), C(220, 54, 48)) if rosso else (C(98, 68, 42), C(182, 182, 194))


def _rettilineo(L, trav, rot, y=0.0, massicciata=True):
    """Binario dritto lungo l'asse nord-sud della tessera (poi si ruota)."""
    if massicciata:
        L.box((0, y + .003, 0), (.22, .006, LATO_TRENO), GHIAIA)
    for z in (-.12, -.06, 0, .06, .12):
        L.box((0, y + .012, z), (.2, .012, .026), trav)
    for x in (-.07, .07):
        L.box((x, y + .028, 0), (.018, .02, LATO_TRENO), rot)


def _arco(R, passi):
    """Punti (x, z) dell'arco di raggio R attorno allo spigolo nord-est (.15, .15): la curva 'canonica' N-E."""
    return [(.15 - R * math.cos(math.pi / 2 * i / passi), .15 - R * math.sin(math.pi / 2 * i / passi))
            for i in range(passi + 1)]


def _curva(L, trav, rot, y=0.0):
    """Curva N-E a gradini, come in Minecraft: cubetti lungo l'arco su cui corre il treno."""
    for R in (.08, .15, .22):                                            # massicciata
        for (x, z) in _arco(R, 7):
            L.box((x, y + .003, z), (.085, .006, .085), GHIAIA)
    for (x, z) in ((.15 - R * math.cos(f), .15 - R * math.sin(f))
                   for f in (0, math.pi / 8, math.pi / 4, 3 * math.pi / 8, math.pi / 2)
                   for R in (.095, .125, .15, .175, .205)):                # traversine
        L.box((x, y + .012, z), (.034, .012, .034), trav)
    for R, n in ((.22, 20), (.08, 8)):                                   # rotaie
        for (x, z) in _arco(R, n):
            L.box((x, y + .028, z), (.02, .02, .02), rot)


def _testata(L, trav, rot, y=0.0):
    """Binario che finisce contro un respingente al centro; aperto verso sud (poi si ruota)."""
    L.box((0, y + .003, -.07), (.22, .006, .16), GHIAIA)
    for z in (-.12, -.06, 0):
        L.box((0, y + .012, z), (.2, .012, .026), trav)
    for x in (-.07, .07):
        L.box((x, y + .028, -.075), (.018, .02, .15), rot)
    L.box((0, y + .04, .035), (.2, .05, .03), C(60, 44, 30))
    for x in (-.08, .08):
        L.box((x, y + .025, .005), (.022, .03, .05), C(60, 44, 30))


def costruisci_binario(L, maschera, rosso=False, y=0.0, massicciata=True):
    """Disegna nella posa L la tessera di binario con quelle aperture."""
    trav, rot = _colori_binario(rosso)
    aperture = lati(maschera)
    if len(aperture) == 2 and maschera in (DIR_N | DIR_S, DIR_E | DIR_O):
        _rettilineo(L.ruotata(0 if maschera == DIR_N | DIR_S else 1), trav, rot, y, massicciata)
    elif len(aperture) == 2:
        k = next(k for k in range(4) if ruota_cw(CURVA_BASE, k) == maschera)
        _curva(L.ruotata(k), trav, rot, y)
    else:
        k = next(k for k in range(4) if ruota_cw(DIR_S, k) == maschera)
        _testata(L.ruotata(k), trav, rot, y)


def costruisci_strada(L, tipo):
    """Asfalto con la riga tratteggiata: 'eo', 'ns' oppure 'inc' (incrocio). Nessun pezzo ne sovrappone un altro."""
    riga = C(232, 226, 186)
    if tipo in ("eo", "inc"):
        L.box((0, .004, 0), (LATO_TRENO, .008, .2), ASFALTO)
    if tipo == "ns":
        L.box((0, .004, 0), (.2, .008, LATO_TRENO), ASFALTO)
    elif tipo == "inc":
        for sz in (-1, 1):
            L.box((0, .004, sz * .125), (.2, .008, .05), ASFALTO)
    if tipo in ("eo", "inc"):
        for x in (-.12, -.04, .04, .12):
            if tipo == "eo" or abs(x) > .1:
                L.box((x, .0105, 0), (.045, .005, .012), riga)
    if tipo == "ns":
        for z in (-.12, -.04, .04, .12):
            L.box((0, .0105, z), (.012, .005, .045), riga)


def costruisci_passaggio(L, rosso):
    """Passaggio a livello per un binario N-S che attraversa una strada E-O (poi si ruota): rotaie sull'asfalto,
    croci di Sant'Andrea con i lumi rossi ai due lati della strada."""
    costruisci_strada(L, "eo")
    trav, rot = _colori_binario(rosso)
    for z in (-.12, -.06, 0, .06, .12):
        L.box((0, .016, z), (.2, .012, .026), trav)
    for x in (-.07, .07):
        L.box((x, .032, 0), (.018, .02, LATO_TRENO), rot)
    bianco, rosso_l = C(238, 238, 232), C(210, 36, 36)
    for sz in (-1, 1):                                  # un cartello per lato, ben fuori dai binari
        px, pz = .125, sz * .125
        L.box((px, .13, pz), (.014, .26, .014), bianco)
        for a in (42, -42):
            L.box((px, .245, pz), (.012, .16, .02), bianco, rot=(a, 0, 0))
        for dz in (-.05, .05):
            L.box((px, .30, pz + dz), (.022, .022, .022), rosso_l)


def costruisci_ponte(L, rosso):
    """Impalcato con l'asse est-ovest (poi si ruota): due piloni di pietra, parapetti e il binario in quota;
    sotto, nel varco tra i piloni, passa l'altro binario (nord-sud)."""
    trav, rot = _colori_binario(rosso)
    q = QUOTA_PONTE
    costruisci_binario(L, DIR_N | DIR_S, rosso)                              # il binario che passa sotto
    L.box((0, q - .02, 0), (LATO_TRENO, .04, .23), PIETRA_PONTE)             # impalcato
    for sx in (-1, 1):
        L.box((sx * .125, q / 2 - .02, 0), (.05, q - .04, .23), PIETRA_PONTE)  # pilone: il varco misura .20
        L.box((sx * .125, .02, 0), (.056, .04, .25), C(120, 116, 110))         # plinto
    _rettilineo(L.ruotata(1), trav, rot, q)                                  # il binario sopra
    for sz in (-1, 1):
        L.box((0, q + .035, sz * .11), (LATO_TRENO, .07, .016), PIETRA_PONTE)
        L.box((0, q + .074, sz * .11), (LATO_TRENO + .01, .012, .024), C(176, 170, 160))
        for sx in (-1, 1):
            L.box((sx * .145, q + .05, sz * .11), (.03, .1, .03), C(130, 126, 120))


def costruisci_rampa(L, rosso):
    """Rampa con l'estremità alta a nord (poi si ruota): terrapieno a gradini e binario inclinato."""
    trav, rot = _colori_binario(rosso)
    q = QUOTA_PONTE
    alfa = math.degrees(math.atan2(q, LATO_TRENO))
    ca, sa = math.cos(math.radians(alfa)), math.sin(math.radians(alfa))
    lung = math.hypot(LATO_TRENO, q)
    n = 8
    for i in range(n):                                                       # terrapieno: ogni gradino sta sotto la rampa
        z0 = -.15 + i * LATO_TRENO / n
        h = max(.008, q * (i * 1.0 / n) - .004)
        L.box((0, h / 2, z0 + LATO_TRENO / n / 2), (.2, h, LATO_TRENO / n), C(112, 86, 58))

    def sul_piano(z, h):
        """Punto a distanza h dal piano inclinato (lungo la normale), nella posizione z lungo la rampa."""
        return (q * (z + .15) / LATO_TRENO + h * ca, z - h * sa)

    y, z = sul_piano(0, .003)
    L.box((0, y, z), (.22, .006, lung), GHIAIA, rot=(-alfa, 0, 0))
    for zs in (-.12, -.06, 0, .06, .12):
        y, z = sul_piano(zs, .012)
        L.box((0, y, z), (.2, .012, .026), trav, rot=(-alfa, 0, 0))
    for x in (-.07, .07):
        y, z = sul_piano(0, .028)
        L.box((x, y, z), (.018, .02, lung), rot, rot=(-alfa, 0, 0))


def costruisci_banchina(L, col_tetto, col_tetto2):
    """Banchina con tettoia e panchina, a est del binario nord-sud (poi si ruota con la posa)."""
    pietra = C(170, 164, 154)
    L.box((.2, .02, -.08), (.2, .04, .34), pietra)
    L.box((.11, .03, -.08), (.014, .02, .34), C(236, 200, 60))                   # linea gialla di sicurezza
    for z in (-.22, .06):
        for x in (.12, .28):
            L.box((x, .14, z), (.014, .2, .014), C(90, 62, 36))
    L.box((.2, .25, -.08), (.28, .025, .34), col_tetto)
    L.box((.2, .275, -.08), (.2, .02, .28), col_tetto2)
    L.box((.27, .07, -.08), (.05, .03, .16), C(110, 74, 44))                     # panchina
    L.box((.29, .1, -.08), (.012, .05, .16), C(110, 74, 44))


# --------------------------------------------------------------------------
# Scambi (visibili nel mondo: si ruotano con un clic) e treno
# --------------------------------------------------------------------------
class ScambioVisivo:
    """Un nodo di scambio sul prato: piastra dorata con i binari sopra, targa numerata e una leva.
    Si colpisce con la mira (id 'scambio_N'): a ogni clic i binari ruotano di 90° davanti ai tuoi occhi."""

    def __init__(self, gioco, parent, tessera, posizione):
        self.g = gioco
        self.tessera = tessera
        self.id = "scambio_" + tessera.sigla
        self.attivo = False
        self.radice = Entity(parent=parent, position=(posizione[0], 0, posizione[1]))
        gioco.interattivi[self.id] = self.radice
        fisso = Mattoncini(self.radice)
        fisso.box((0, .005, 0), (.285, .01, .285), ORO_SCURO)
        fisso.box((0, .014, 0), (.265, .01, .265), C(226, 178, 46))
        for dx, dz in ((-.12, -.12), (.12, -.12), (-.12, .12), (.12, .12)):          # borchie
            fisso.box((dx, .022, dz), (.022, .014, .022), C(120, 88, 20))
        fisso.box((-.115, .035, -.115), (.05, .06, .05), C(70, 60, 50))              # base della leva
        fisso.fondi()
        mobile = Mattoncini(Entity(parent=self.radice, y=.02))
        self.nodo = mobile.nodo.parent
        costruisci_binario(mobile.posa(), tessera.base, tessera.rosso, y=0.0)
        mobile.fondi()
        # la leva ruota quando ruota lo scambio
        self.perno = Entity(parent=self.radice, position=(-.115, .06, -.115))
        blocco(self.perno, (0, .055, 0), (.014, .11, .014), col=C(196, 196, 206))
        blocco(self.perno, (0, .12, 0), (.04, .04, .04), col=C(214, 40, 40), model="sphere")
        self.hitbox = Entity(parent=self.radice, model="cube", collider="box", position=(0, .22, 0),
                             scale=(.42, .5, .42), visible=False, id_oggetto=self.id)       # bersaglio largo: facile da centrare
        self.angolo = self.angolo_visibile = 90.0 * tessera.giri
        self.nodo.rotation_y = self.angolo
        self.n_clic = 0
        self.fase = random.uniform(0, 6)
        self.imposta_attivo(False)

    def ruota(self):
        self.tessera.ruota()
        self.angolo += 90.0
        self.n_clic += 1

    def ripristina(self):
        self.tessera.ripristina()
        self.angolo = self.angolo_visibile = 90.0 * self.tessera.giri
        self.nodo.rotation_y = self.angolo
        self.n_clic = 0
        self.perno.rotation_x = 0

    def imposta_attivo(self, si):
        self.attivo = si

    def aggiorna(self, dt, t):
        self.angolo_visibile += (self.angolo - self.angolo_visibile) * min(1.0, dt * 9)
        if abs(self.angolo - self.angolo_visibile) < .05:
            self.angolo_visibile = self.angolo
        self.nodo.rotation_y = self.angolo_visibile
        self.perno.rotation_x += ((38 if self.n_clic % 2 else -38) - self.perno.rotation_x) * min(1.0, dt * 10)


class TrenoVisivo:
    """Locomotiva a blocchi e vagone aperto con il pupo di Cavour: un cubetto con il cilindro in testa."""
    QUOTA_RUOTE = .012

    def __init__(self, gioco, parent):
        self.parent = parent
        self.base = Entity(parent=parent)                       # posizione e direzione sul percorso
        self.radice = Entity(parent=self.base)                  # inclinazione (rampe) e ribaltamento
        r = self.radice
        nero, ferro = C(24, 24, 28), C(58, 58, 64)
        # locomotiva (davanti, verso +z)
        blocco(r, (0, .05, .075), (.12, .04, .13), col=ferro)
        blocco(r, (0, .095, .085), (.10, .07, .105), col=C(32, 78, 50))
        blocco(r, (0, .145, .115), (.032, .06, .032), col=nero)                      # fumaiolo
        blocco(r, (0, .18, .115), (.045, .012, .045), col=nero)
        blocco(r, (0, .125, .0), (.12, .035, .045), col=C(120, 28, 36))             # cabina
        blocco(r, (0, .09, .142), (.03, .03, .012), col=C(255, 226, 120))            # fanale
        for x in (-.063, .063):
            for z in (.03, .11):
                blocco(r, (x, .026, z), (.014, .04, .04), col=nero)
        # vagone (dietro): pianale e sponde in legno
        blocco(r, (0, .045, -.075), (.12, .014, .14), col=C(110, 74, 44))
        for x in (-.054, .054):
            blocco(r, (x, .08, -.075), (.012, .06, .14), col=C(150, 90, 52))
        blocco(r, (0, .08, -.14), (.12, .06, .012), col=C(150, 90, 52))
        blocco(r, (0, .075, -.012), (.12, .05, .012), col=C(150, 90, 52))
        for x in (-.063, .063):
            for z in (-.12, -.04):
                blocco(r, (x, .026, z), (.014, .04, .04), col=nero)
        # Cavour: corpo in redingote, camicia, testa con occhiali e favoriti, cilindro
        z0 = -.075
        blocco(r, (0, .084, z0), (.046, .05, .032), col=C(30, 32, 52))
        blocco(r, (0, .088, z0 + .0165), (.02, .034, .004), col=C(240, 240, 236))
        blocco(r, (0, .105, z0 + .0185), (.016, .006, .004), col=C(160, 30, 40))
        blocco(r, (0, .13, z0), (.042, .04, .04), col=C(228, 186, 152))
        for sx in (-1, 1):
            blocco(r, (sx * .011, .134, z0 + .0215), (.014, .014, .004), col=C(222, 180, 50))      # montatura
            blocco(r, (sx * .011, .134, z0 + .0235), (.006, .006, .004), col=C(20, 16, 14))       # occhio
            blocco(r, (sx * .024, .124, z0 + .004), (.007, .024, .014), col=C(210, 208, 204))     # favorito
        blocco(r, (0, .12, z0 + .0215), (.014, .004, .004), col=C(150, 80, 70))                   # bocca
        blocco(r, (0, .154, z0), (.058, .006, .058), col=nero)                       # tesa
        blocco(r, (0, .184, z0), (.036, .054, .036), col=nero)                       # cilindro
        blocco(r, (0, .166, z0), (.038, .008, .038), col=C(150, 24, 36))             # nastro
        r.combine()
        self.fumo = []
        for i in range(6):
            p = Entity(parent=parent, model="cube", color=C(236, 236, 242), scale=.03, enabled=False)
            self.fumo.append([p, i / 6.0])

    def imposta(self, x, y, z, yaw, pitch=0.0, ribalta=0.0):
        """(x, z) sulla pianta, y = quota del binario, yaw = direzione, pitch = salita (gradi, positivo = muso in su)."""
        self.base.position = (x, y + self.QUOTA_RUOTE, z)
        self.base.rotation_y = yaw
        self.radice.rotation = (-pitch, 0, ribalta)

    def spegni_fumo(self):
        for i, voce in enumerate(self.fumo):
            voce[0].enabled = False
            voce[1] = i / 6.0

    def aggiorna_fumo(self, dt, in_marcia):
        """Sbuffi di fumo che salgono dal fumaiolo (restano nello spazio mentre il treno si sposta)."""
        for voce in self.fumo:
            p, eta = voce
            if not in_marcia and not p.enabled:
                continue
            eta += dt * .9
            if eta >= 1.0:
                eta = 0.0
                if in_marcia:
                    ry = math.radians(self.base.rotation_y)
                    lz = .115
                    p.position = (self.base.x + lz * math.sin(ry), self.base.y + .2, self.base.z + lz * math.cos(ry))
                    p.enabled = True
                else:
                    p.enabled = False
            if p.enabled:
                p.y += dt * .09
                p.scale = .034 * (1 - eta * .6)
            voce[1] = eta


# --------------------------------------------------------------------------
# Scenario: montagne, alberi, case, spie, bandiere, insegne (in unità del modello, con un fattore di scala)
# --------------------------------------------------------------------------
def costruisci_montagna(g, parent, pos, seme, larg=.56):
    rnd = random.Random(seme)
    x, z = pos
    larg *= FATTORE_SCENARIO
    h1, h2, h3 = .40 * larg, .30 * larg, .22 * larg
    blocco(parent, (x, h1 / 2, z), (larg, h1, larg), texture=g.t_roccia)
    blocco(parent, (x + rnd.uniform(-.03, .03), h1 + h2 / 2, z + rnd.uniform(-.03, .03)), (larg * .72, h2, larg * .72),
           texture=g.t_roccia)
    blocco(parent, (x + rnd.uniform(-.02, .02), h1 + h2 + h3 / 2, z + rnd.uniform(-.02, .02)), (larg * .42, h3, larg * .42),
           texture=g.t_neve)


def costruisci_albero(g, parent, pos, seme):
    rnd = random.Random(seme)
    x, z = pos[0] + rnd.uniform(-.04, .04), pos[1] + rnd.uniform(-.04, .04)
    k = rnd.uniform(.85, 1.2)
    nodo = Entity(parent=parent, position=(x, 0, z), scale=FATTORE_ALBERI)          # alberi più piccoli: non ingombrano il prato
    blocco(nodo, (0, .11 * k, 0), (.06 * k, .22 * k, .06 * k), texture=g.t_tronco)
    blocco(nodo, (0, .32 * k, 0), (.26 * k, .20 * k, .26 * k), texture=g.t_foglie)
    blocco(nodo, (0, .49 * k, 0), (.17 * k, .14 * k, .17 * k), texture=g.t_foglie)
    blocco(nodo, (0, .60 * k, 0), (.09 * k, .09 * k, .09 * k), texture=g.t_foglie)
    return (x, z)


def costruisci_casa(g, parent, pos, rot=0, tetto=None):
    """Casetta a blocchi: circa 2 m x 1,5 m in pianta, 2,2 m di altezza (con il fattore SCALA_TRENO)."""
    x, z = pos
    nodo = Entity(parent=parent, position=(x, 0, z), rotation_y=rot, scale=FATTORE_CASE)
    blocco(nodo, (0, .17, 0), (.50, .34, .38), texture=g.t_mattoni_mc)
    blocco(nodo, (0, .37, 0), (.56, .08, .44), texture=g.t_tetto_mc, col=tetto)
    blocco(nodo, (0, .45, 0), (.38, .08, .30), texture=g.t_tetto_mc, col=tetto)
    blocco(nodo, (0, .52, 0), (.2, .06, .22), texture=g.t_tetto_mc, col=tetto)
    blocco(nodo, (.12, .56, .05), (.07, .14, .07), texture=g.t_mattoni_mc)             # comignolo
    blocco(nodo, (0, .09, -.193), (.1, .18, .012), col=C(70, 44, 26))                  # porta
    for sx in (-.17, .17):
        blocco(nodo, (sx, .2, -.193), (.09, .09, .012), col=C(250, 226, 130))
        blocco(nodo, (sx, .2, -.197), (.1, .015, .006), col=C(70, 44, 26))
    return nodo


def costruisci_spia(g, parent, pos, rot=0, s=2.6):
    """Spia austriaca a grandezza d'uomo: cappotto grigio, cappello nero con nastro giallo."""
    x, z = pos
    nodo = Entity(parent=parent, position=(x, 0, z), rotation_y=rot, scale=s * FATTORE_SCENARIO)
    blocco(nodo, (0, .045, 0), (.05, .09, .035), col=C(88, 92, 104))
    blocco(nodo, (0, .105, 0), (.04, .04, .04), col=C(224, 182, 148))
    blocco(nodo, (0, .13, 0), (.056, .008, .056), col=C(20, 20, 22))
    blocco(nodo, (0, .146, 0), (.04, .028, .04), col=C(20, 20, 22))
    blocco(nodo, (0, .136, 0), (.042, .008, .042), col=C(236, 196, 40))
    for sx in (-.011, .011):
        blocco(nodo, (sx, .108, -.0205), (.007, .007, .004), col=C(160, 20, 20))              # occhi minacciosi
    return nodo


def costruisci_bandiera(parent, pos, colori, orizzontale=False, alta=.62):
    x, z = pos
    nodo = Entity(parent=parent, position=(x, 0, z), scale=FATTORE_SCENARIO)
    blocco(nodo, (0, alta / 2, 0), (.014, alta, .014), col=C(200, 200, 208))
    for i, c in enumerate(colori):
        if orizzontale:
            blocco(nodo, (.09, alta - .05 - i * .06, 0), (.18, .06, .008), col=c)
        else:
            blocco(nodo, (.03 + i * .06, alta - .06, 0), (.06, .12, .008), col=c)


def costruisci_cartello(g, parent, pos, chiave, larghezza=.5):
    """Insegna su due pali, rivolta verso l'ingresso dell'archivio (lato -z locale = lato dell'osservatore)."""
    x, z = pos
    nodo = Entity(parent=parent, position=(x, 0, z), scale=FATTORE_SCENARIO)
    for dx in (-larghezza / 2 + .03, larghezza / 2 - .03):
        blocco(nodo, (dx, .2, 0), (.02, .4, .02), col=C(90, 62, 36))
    e = Entity(parent=nodo, model="quad", texture=g.t_cartelli[chiave], position=(0, .44, -.016),
               scale=(larghezza, larghezza * 112 / 384))
    return e


FATTORE_ALBERI = .62                   # le dimensioni di alberi ed edifici rispetto al disegno originale
FATTORE_CASE = .66
FATTORE_SCENARIO = .66                 # montagne, spie, cartelli e bandiere (binari, stazioni e treno restano com'erano)

# Decorazioni, in coordinate di tessera (anche tra le caselle: ci sono pezzi grandi). Solo su caselle d'erba.
MONTAGNE_TRENO = [(.5, 5.5, .56), (.5, 2.5, .56), (12.3, 2.5, .40)]
ALBERI_TRENO = [(0, 0), (1, 0), (0, 1), (1, 1), (0, 4), (1, 4), (-.55, 8.3), (3, 3), (4, 3), (3, 2), (4, 2), (6, 5), (7, 5),
                (6, 3), (10, 0), (12.3, .2), (12.3, 4.6), (12.3, 5.6), (12.3, 6.2), (-.4, 4), (-.4, 1)]
CASE_TRENO = [((3.5, 4.5), 0, None), ((4.0, -.25), 0, None), ((8.1, -.25), 0, None), ((1.2, 8.25), 0, C(60, 130, 80)),
              ((9.5, 5.3), 180, C(150, 130, 60))]
SPIE_TRENO = [(6.4, 7.05), (7.1, 7.05), (9.4, 7.05), (10.4, 7.05), (7.0, 3.0), (9.0, 3.0)]


class PlasticoFerroviario:
    """La ferrovia nell'archivio: prato, strade, binari, ponti, scambi, stazioni, spie e il treno, più il Quadro di Comando.
    Fa solo da scena (e dice dove non si può camminare); le regole stanno in Griglia e in TrenoDiplomatico."""
    QUADRO = (6.6, -5.5 - SPAZIO_INGRESSO)                 # centro del Quadro di Comando (x, z nel mondo)

    def __init__(self, gioco, griglia):
        self.g = gioco
        self.griglia = griglia
        m = gioco.mondo
        cx, cz = PLASTICO_CENTRO
        self.larghezza = (griglia.colonne + 2) * LATO_TRENO            # una tessera di prato in più su ogni lato
        self.profondita = (griglia.righe + 2) * LATO_TRENO
        self.scacchiera = Entity(parent=m, position=(cx, ZOCCOLO, cz), rotation_y=180, scale=SCALA_TRENO)
        self.scacchiera.set_shader_input("lucido", 0.0)                # niente riflessi: sui cubetti fusi luccicherebbero a macchie
        self.ingombri = []                                             # (nome, x0, z0, x1, z1) in tessere: per i controlli
        self._costruisci_terreno()
        self.scambi = []
        self._costruisci_rete()
        self._costruisci_scenario()
        self.treno = TrenoVisivo(gioco, self.scacchiera)
        self.tiro = {"avvia": 0.0, "reset": 0.0}
        self._costruisci_quadro(m)
        self.riporta_alla_partenza()

    # ------------------------------------------------------------------ utilità
    def p(self, x, z):
        """Posizione locale (x, z) del centro della tessera (x, z); valgono anche valori frazionari."""
        return self.griglia.centro(x, z, LATO_TRENO)

    def mondo(self, lx, ly, lz):
        """Da coordinate locali (la scacchiera è ruotata di 180° e ingrandita) a coordinate del mondo."""
        return Vec3(self.scacchiera.x - lx * SCALA_TRENO, ZOCCOLO + ly * SCALA_TRENO, self.scacchiera.z - lz * SCALA_TRENO)

    def da_mondo(self, wx, wz):
        """Posizione sulla pianta (in tessere, frazionarie) di un punto del mondo."""
        lx = (self.scacchiera.x - wx) / SCALA_TRENO
        lz = (self.scacchiera.z - wz) / SCALA_TRENO
        g = self.griglia
        return lx / LATO_TRENO + (g.colonne - 1) / 2, lz / LATO_TRENO + (g.righe - 1) / 2

    def solido(self, tx, tz, q, box):
        """Un parallelepipedo della tessera (tx, tz) ruotata di q quarti di giro, dato in coordinate della tessera
        (x0, x1, z0, z1, y0, y1): lo mette tra i solidi del mondo (con altezza), su cui si può salire o sotto cui passare."""
        px, pz = self.p(tx, tz)
        c, s = ((1, 0), (0, 1), (-1, 0), (0, -1))[q % 4]
        xs, zs = [], []
        for x in (box[0], box[1]):
            for z in (box[2], box[3]):
                xs.append(px + x * c + z * s)
                zs.append(pz + (-x * s + z * c))
        wx = [self.scacchiera.x - v * SCALA_TRENO for v in xs]
        wz = [self.scacchiera.z - v * SCALA_TRENO for v in zs]
        self.g.solidi.append((min(wx), max(wx), min(wz), max(wz),
                              ZOCCOLO + box[4] * SCALA_TRENO, ZOCCOLO + box[5] * SCALA_TRENO))

    def ostacolo(self, nome, tx, tz, mx, mz, fisico=True):
        """Aggiunge un ingombro dove non si cammina: centro (tx, tz) e mezze misure (mx, mz) in tessere."""
        self.ingombri.append((nome, tx - mx, tz - mz, tx + mx, tz + mz))
        if not fisico:
            return
        lx, lz = self.p(tx, tz)
        cx, cz = self.scacchiera.x - lx * SCALA_TRENO, self.scacchiera.z - lz * SCALA_TRENO
        mxw, mzw = mx * LATO_REALE, mz * LATO_REALE
        self.g.ostacoli.append((cx - mxw, cz - mzw, cx + mxw, cz + mzw))

    # ------------------------------------------------------------------ costruzione
    def _costruisci_terreno(self):
        g, sc = self.g, self.scacchiera
        W, D = self.larghezza, self.profondita
        blocco(sc, (0, -.01, 0), (W, .02, D), texture=g.t_erba, tex_scale=(W / .15, D / .15))
        for sx in (-1, 1):                                              # cordolo di legno attorno al prato
            blocco(sc, (sx * (W / 2 + .008), .008, 0), (.016, .036, D + .032), texture=g.t_assi_mc)
        for sz in (-1, 1):
            blocco(sc, (0, .008, sz * (D / 2 + .008)), (W + .032, .036, .016), texture=g.t_assi_mc)

    def _costruisci_rete(self):
        g, sc = self.g, self.scacchiera
        stat = Mattoncini(sc)
        gr = self.griglia
        for (x, z), t in sorted(gr.tessere.items()):
            px, pz = self.p(x, z)
            L = stat.posa(px, pz)
            if t.tipo == "scambio":
                self.scambi.append(ScambioVisivo(g, sc, t, (px, pz)))
            elif t.tipo == "erba":
                if t.strada:
                    costruisci_strada(L, t.strada)
                    if x == 0 and t.strada == "eo":                      # le strade proseguono nel bordo del prato
                        costruisci_strada(stat.posa(self.p(-1, z)[0], self.p(-1, z)[1]), "eo")
                    if x == gr.colonne - 1 and t.strada == "eo":
                        costruisci_strada(stat.posa(self.p(x + 1, z)[0], self.p(x + 1, z)[1]), "eo")
                    if z == 0 and t.strada == "ns":
                        costruisci_strada(stat.posa(self.p(x, -1)[0], self.p(x, -1)[1]), "ns")
            elif t.tipo == "ponte":
                kp = 0 if t.asse_alto & DIR_E else 1
                costruisci_ponte(L.ruotata(kp), t.rosso)
                self.ostacolo("ponte", x, z, .5, .5, fisico=False)
                q = QUOTA_PONTE
                self.solido(x, z, kp, (-.15, .15, -.115, .115, q - .04, q))                      # impalcato
                for sx in (-1, 1):
                    self.solido(x, z, kp, (sx * .10 - (0 if sx > 0 else .05), sx * .10 + (.05 if sx > 0 else 0),
                                           -.115, .115, 0, q))                                    # piloni
                    self.solido(x, z, kp, (-.15, .15, sx * .11 - .01, sx * .11 + .01, q, q + .07))  # parapetti
            elif t.tipo == "rampa":
                k = next(k for k in range(4) if ruota_cw(DIR_N, k) == t.alta)
                costruisci_rampa(L.ruotata(k), t.rosso)
                self.ostacolo("rampa", x, z, .5, .5, fisico=False)
                for i in range(8):                                                                # la rampa è una scala di 8 gradini
                    z0 = -.15 + i * LATO_TRENO / 8
                    self.solido(x, z, k, (-.1, .1, z0, z0 + LATO_TRENO / 8, 0, QUOTA_PONTE * (i + 1) / 8))
            elif t.tipo == "binario" and t.strada:
                costruisci_passaggio(L if t.strada == "eo" else L.ruotata(1), t.rosso)
            elif t.tipo in ("partenza", "arrivo", "vienna"):
                fondo = {"partenza": C(60, 110, 200), "arrivo": C(40, 170, 80), "vienna": C(200, 40, 40)}[t.tipo]
                L.box((0, .002, 0), (.29, .004, .29), fondo)
                costruisci_binario(L, t.maschera, t.rosso)
                if t.tipo == "partenza":
                    costruisci_banchina(L, C(36, 78, 160), C(60, 110, 200))
                elif t.tipo == "arrivo":
                    costruisci_banchina(L.ruotata(3), C(26, 120, 66), C(40, 170, 80))
            else:
                costruisci_binario(L, t.maschera, t.rosso)
        stat.fondi()

    def _costruisci_scenario(self):
        g, sc = self.g, self.scacchiera
        for i, (x, z, larg) in enumerate(MONTAGNE_TRENO):
            px, pz = self.p(x, z)
            costruisci_montagna(g, sc, (px, pz), 10 + i, larg)
            self.ostacolo("montagna", x, z, larg * FATTORE_SCENARIO / 2 / LATO_TRENO,
                          larg * FATTORE_SCENARIO / 2 / LATO_TRENO)
        for i, (x, z) in enumerate(ALBERI_TRENO):
            tx, tz = costruisci_albero(g, sc, self.p(x, z), 40 + i)
            self.ostacolo("albero", x, z, .09 / LATO_TRENO * .9 * FATTORE_ALBERI, .09 / LATO_TRENO * .9 * FATTORE_ALBERI)
        for (pos, rot, tetto) in CASE_TRENO:
            costruisci_casa(g, sc, self.p(*pos), rot, tetto)
            self.ostacolo("casa", pos[0], pos[1], .28 / LATO_TRENO * FATTORE_CASE, .22 / LATO_TRENO * FATTORE_CASE)
        for i, (x, z) in enumerate(SPIE_TRENO):
            costruisci_spia(g, sc, self.p(x, z), rot=180 if i % 2 == 0 else 160)
            self.ostacolo("spia", x, z, .07 / LATO_TRENO * 1.3 * FATTORE_SCENARIO, .07 / LATO_TRENO * 1.3 * FATTORE_SCENARIO)
        # Torino (a sud della partenza), Plombières (a nord dell'arrivo) e Vienna (a nord del binario rosso)
        tx, tz = self.griglia.partenza
        ax, az = self.griglia.arrivo
        vx, vz = self.griglia.vienna
        costruisci_cartello(g, sc, self.p(tx, tz - .85), "torino")
        costruisci_bandiera(sc, self.p(tx - .9, tz - .75), TRICOLORE)
        costruisci_bandiera(sc, self.p(tx + .9, tz - .75), TRICOLORE)
        costruisci_cartello(g, sc, self.p(ax, az + .8), "plombieres")
        costruisci_bandiera(sc, self.p(ax - 1.1, az + .75), [C(0, 85, 164), C(244, 245, 240), C(239, 65, 53)])
        costruisci_cartello(g, sc, self.p(vx - .5, vz + .8), "vienna")
        costruisci_bandiera(sc, self.p(vx + .4, vz + .75), [C(20, 20, 22), C(250, 214, 40)], orizzontale=True)
        for (nome, x, z) in (("cartello", tx, tz - .85), ("cartello", ax, az + .8), ("cartello", vx - .5, vz + .8)):
            self.ostacolo(nome, x, z, .22 / LATO_TRENO * .6 * FATTORE_SCENARIO, .03 / LATO_TRENO * FATTORE_SCENARIO)

    def _costruisci_quadro(self, m):
        """Il Quadro di Comando Ferroviario: consolle di ottone all'ingresso dell'archivio, con la targa, le istruzioni,
        una leva verde (avvia il treno) e una rossa (rimette a posto gli scambi). Si accende quando vi si inserisce il codice dei fascicoli."""
        g = self.g
        qx, qz = self.QUADRO
        self.quadro = Entity(parent=m, position=(qx, 0, qz))
        q = self.quadro
        g.interattivi["treno"] = q
        blocco(q, (0, .42, 0), (2.2, .84, .7), texture=g.t_legno)
        blocco(q, (0, .85, 0), (2.3, .04, .78), col=ORO_SCURO)
        piano = Entity(parent=q, position=(0, .93, .02), rotation_x=16)
        blocco(piano, (0, 0, 0), (2.1, .05, .62), col=C(120, 86, 34))
        blocco(piano, (0, .03, 0), (1.96, .012, .5), col=C(40, 30, 20))
        for x in (-.62, 0, .62):                                      # tre quadranti
            blocco(piano, (x, .05, -.13), (.26, .03, .26), col=ORO, model=cilindro(14))
            blocco(piano, (x, .068, -.13), (.21, .012, .21), col=C(240, 232, 208), model=cilindro(14))
            blocco(piano, (x, .08, -.13), (.014, .008, .09), col=C(160, 20, 30), rot=(0, 25 * x * 4, 0))
        self.lampade = []
        for x in (-.92, .92):
            lamp = blocco(piano, (x, .05, .12), (.12, .035, .12), col=C(90, 16, 16), model=cilindro(12))
            self.lampade.append(lamp)
        # istruzioni: una targa in piedi dietro il piano
        blocco(q, (0, 1.58, -.3), (1.92, .8, .05), texture=g.t_legno)
        blocco(q, (0, .85 + .3, -.34), (.12, .6, .06), col=ORO_SCURO)               # il sostegno sta dietro la targa
        Entity(parent=q, model="quad", texture=g.t_istruzioni, position=(0, 1.58, -.272),
               scale=(1.8, 1.8 * 250 / 640), rotation_y=180, shader=unlit_shader)      # retroilluminata: si legge sempre
        # le due leve
        self.leve = {}
        for nome, x, col_pomo, col_base in (("avvia", .5, C(40, 200, 90), C(30, 100, 50)),
                                            ("reset", -.5, C(214, 40, 40), C(110, 24, 24))):
            blocco(piano, (x, .05, .17), (.16, .035, .16), col=col_base, model=cilindro(12))
            perno = Entity(parent=piano, position=(x, .07, .17))
            blocco(perno, (0, .15, 0), (.035, .3, .035), col=C(196, 196, 206))
            blocco(perno, (0, .32, 0), (.12, .12, .12), col=col_pomo, model="sphere")
            self.leve[nome] = perno
            g.interattivi["treno_" + nome] = perno
            Entity(parent=piano, model="cube", collider="box", position=(x, .2, .17), scale=(.34, .5, .34),
                   visible=False, id_oggetto="treno_" + nome)
        for nome, x in (("AVVIA", .5), ("RIPRISTINA", -.5)):          # etichette sul bordo anteriore
            Entity(parent=q, model="quad", texture=g.t_etichette[nome], position=(x, .62, .354),
                   scale=(.62, .62 * 80 / 320), rotation_y=180, shader=unlit_shader)
        self.alone_quadro = sprite_luminoso(q, (0, 1.9, -.2), (.6, .6), g.t_alone, C(120, 255, 150, 120))
        self.alone_quadro.enabled = False
        Entity(parent=q, model="quad", texture=g.t_targa_quadro, position=(0, .27, .354),
               scale=(1.5, 1.5 * 96 / 640), rotation_y=180, shader=unlit_shader)
        self.lucchetto = Entity(parent=q, model="quad", texture=g.t_lucchetto, position=(0, .52, .354),
                                scale=.2, rotation_y=180)
        # lampada d'ottone con paralume: illumina il piano e la targa (una vera luce della scena, accesa con l'archivio)
        blocco(q, (-.95, .9, -.12), (.16, .04, .16), col=ORO_SCURO, model=cilindro(12, start=-.5))
        blocco(q, (-.95, 1.3, -.12), (.03, .8, .03), col=ORO)
        blocco(q, (-.95, 1.72, -.12), (.34, .16, .34), col=C(28, 96, 60), model=cilindro(14, start=-.5))
        blocco(q, (-.95, 1.62, -.12), (.2, .04, .2), col=C(255, 232, 170)).shader = unlit_shader      # la lampadina
        self.alone_lampada = sprite_luminoso(q, (-.95, 1.55, -.12), (.9, .9), g.t_alone, C(255, 200, 110, 120))
        luce = {"col": Vec3(0, 0, 0), "piena": Vec3(2.6, 2.1, 1.25), "tremolio": .05, "nodo": self.alone_lampada,
                "offset": Vec3(0, -.05, .45)}
        g.luci.append(luce)
        g.stanza_segreta.luci.append(luce)
        Entity(parent=q, model="cube", collider="box", position=(0, .5, 0), scale=(2.3, 1.0, .8), visible=False,
               id_oggetto="treno")
        g.ostacoli.append((qx - 1.25, qz - .45, qx + 1.25, qz + .45))

    # ------------------------------------------------------------------ stato
    def imposta_quadro(self, acceso):
        for lamp in self.lampade:
            lamp.color = C(60, 230, 110) if acceso else C(90, 16, 16)
        self.alone_quadro.enabled = acceso
        self.lucchetto.enabled = not acceso
        for s in self.scambi:
            s.imposta_attivo(acceso)

    def tira_leva(self, nome):
        self.tiro[nome] = 1.0

    def riporta_alla_partenza(self):
        x, z = self.p(*self.griglia.partenza)
        self.treno.imposta(x, 0.0, z, 0.0)
        self.treno.spegni_fumo()

    def ripristina_scambi(self):
        self.griglia.ripristina()
        for s in self.scambi:
            s.ripristina()

    def aggiorna(self, dt, t):
        for s in self.scambi:
            s.aggiorna(dt, t)
        for nome, perno in self.leve.items():
            if self.tiro[nome] > 0:
                self.tiro[nome] = max(0.0, self.tiro[nome] - dt * 2.2)
            perno.rotation_x = 58 * math.sin(math.pi * self.tiro[nome])




# --------------------------------------------------------------------------
# Il Treno Diplomatico: il minigioco finale
# --------------------------------------------------------------------------




class MiniMappa(Entity):
    """La pianta della ferrovia, in alto a sinistra mentre si è nell'archivio: dove sei, dove guardi, dove sta il treno
    e come sono girati ora gli scambi (da terra, a un metro e mezzo d'altezza, la rete non si vede tutta)."""
    LARGHEZZA = .36

    def __init__(self, gioco, plastico):
        super().__init__(parent=camera.ui, enabled=False, z=1)
        self.g, self.plastico = gioco, plastico
        gr = plastico.griglia
        self.l = self.LARGHEZZA
        self.h = self.l * gr.righe / gr.colonne
        self.cw, self.ch = self.l / gr.colonne, self.h / gr.righe
        quad_ui(self, (0, 0), (self.l + .014, self.h + .014), ORO, z=.02)
        quad_ui(self, (0, 0), (self.l, self.h), color.white, gioco.t_minimappa, z=.01)
        self.overlay = {}                                    # sigla -> (quad, maschera mostrata)
        for sigla, t in gr.scambi.items():
            cella = next(c for c, tt in gr.tessere.items() if tt is t)
            q = quad_ui(self, self.pos_ui(*cella), (self.cw, self.ch), color.white, gioco.t_mm_scambio[t.maschera], z=-.01)
            self.overlay[sigla] = [q, t.maschera]
        self.scia = [Entity(parent=self, model=Circle(12), scale=.008, color=ORO_CHIARO, z=-.03) for _ in range(2)]
        self.treno = Entity(parent=self, model=Circle(14), scale=.016, color=C(255, 255, 255), z=-.03)
        self.treno_bordo = Entity(parent=self, model=Circle(14), scale=.024, color=C(20, 20, 24), z=-.025)
        self.io_bordo = Entity(parent=self, model=Circle(14), scale=.024, color=C(20, 20, 24), z=-.025)
        self.io = Entity(parent=self, model=Circle(14), scale=.016, color=C(80, 190, 255), z=-.04)
        self.legenda = testo_ui(self, "T Torino   P Plombières   V Vienna   ·   C: nascondi", (0, -self.h / 2 - .022), .62,
                                PERGAMENA, "i", z=-.01)

    def pos_ui(self, fx, fz):
        gr = self.plastico.griglia
        return ((fx + .5 - gr.colonne / 2) * self.cw, (fz + .5 - gr.righe / 2) * self.ch)

    def _tessera_di(self, wx, wz):
        fx, fz = self.plastico.da_mondo(wx, wz)
        gr = self.plastico.griglia
        return max(-.5, min(gr.colonne - .5, fx)), max(-.5, min(gr.righe - .5, fz))

    def posiziona(self, a):
        """Angolo in alto a sinistra, sotto il titolo."""
        self.x = -a / 2 + .02 + (self.l + .014) / 2
        self.y = .335 - (self.h + .014) / 2

    def aggiorna(self, giocatore, yaw):
        gr = self.plastico.griglia
        for sigla, voce in self.overlay.items():
            m = gr.scambi[sigla].maschera
            if m != voce[1]:
                voce[1] = m
                voce[0].texture = self.g.t_mm_scambio[m]
        px, pz = self.pos_ui(*self._tessera_di(giocatore.x, giocatore.z))
        self.io.position = self.io_bordo.position = (px, pz, -.04)
        ry = math.radians(yaw)
        dx, dy = -math.sin(ry), -math.cos(ry)             # davanti a te sulla pianta: il nord è in alto
        for i, p in enumerate(self.scia):
            p.position = (px + dx * .012 * (i + 1), pz + dy * .012 * (i + 1), -.03)
        tv = self.plastico.treno.base
        fx = tv.x / LATO_TRENO + (gr.colonne - 1) / 2
        fz = tv.z / LATO_TRENO + (gr.righe - 1) / 2
        self.treno.position = self.treno_bordo.position = (self.pos_ui(fx, fz)[0], self.pos_ui(fx, fz)[1], -.03)


class TrenoDiplomatico:
    """Il minigioco finale, a grandezza d'uomo: si cammina nell'archivio, si girano gli scambi con un clic (mira sullo
    scambio), si tira la leva verde e Cavour parte da Torino. Regole nella Griglia, scena nel PlasticoFerroviario;
    qui ci sono le fasi (fermo, corsa, esito, vittoria), i comandi e i messaggi."""
    VELOCITA = .42                     # unità del modello al secondo (circa 2,5 m/s: una camminata)
    NORD = {DIR_N: "Nord", DIR_E: "Est", DIR_S: "Sud", DIR_O: "Ovest"}

    def __init__(self, gioco, su_vittoria):
        self.g = gioco
        self.griglia = Griglia()
        self.plastico = PlasticoFerroviario(gioco, self.griglia)
        self.minimappa = MiniMappa(gioco, self.plastico)
        self.su_vittoria = su_vittoria
        self.per_id = {s.id: s for s in self.plastico.scambi}
        self.per_sigla = {s.tessera.sigla: s for s in self.plastico.scambi}
        self.sbloccato = False
        self.fase = "fermo"             # fermo | corsa | esito | vittoria
        self.corsa = None
        self.punti, self.cumulate = [], [0.0]
        self.s = self.t_corsa = self.t_sbuffo = self.timer_esito = self.inclinazione = 0.0
        self.yaw = self.pitch = 0.0
        self.ultima = (0.0, 0.0, 0.0)
        self.pop = 1.0
        self.vittoria_notificata = False
        self.mosse = 0
        self.tentativi = 0
        self._costruisci_ui()

    # ------------------------------------------------------------------ interfaccia
    def _costruisci_ui(self):
        self.esito = Entity(parent=camera.ui, enabled=False, z=-2)
        quad_ui(self.esito, (0, .08), (1.14, .27), ORO, z=.02)
        quad_ui(self.esito, (0, .08), (1.1, .25), C(110, 16, 26, 240), z=.01)
        testo_ui(self.esito, "Incidente diplomatico!", (0, .14), 2.6, C(255, 236, 200), "b", z=-.01)
        testo_ui(self.esito, "Cavour è stato intercettato dagli austriaci.", (0, .085), 1.5, C(255, 214, 206), "b", z=-.01)
        self.e_motivo = testo_ui(self.esito, "", (0, .04), 1.0, C(255, 200, 190), "i", z=-.01)
        testo_ui(self.esito, "Il treno torna alla partenza…", (0, .005), .9, PERGAMENA_SCURA, "i", z=-.01)

    # ------------------------------------------------------------------ stato esterno
    def imposta_sbloccato(self, si):
        self.sbloccato = si
        self.plastico.imposta_quadro(si)
        self._aggiorna_scambi()

    def _aggiorna_scambi(self):
        attivi = self.sbloccato and self.fase == "fermo"
        for s in self.plastico.scambi:
            s.imposta_attivo(attivi)

    def azzera(self):
        """Nuova partita."""
        self.disattiva()
        self.imposta_sbloccato(False)

    def disattiva(self):
        """Chiusura immediata (nuova partita, tempo scaduto): treno alla partenza, scambi com'erano."""
        self.fase = "fermo"
        self.esito.enabled = False
        self.ripristina()
        self.plastico.riporta_alla_partenza()
        self.vittoria_notificata = False
        self.yaw = self.pitch = 0.0
        self.pop = 1.0
        self.plastico.treno.radice.rotation = (0, 0, 0)
        self._aggiorna_scambi()

    # ------------------------------------------------------------------ comandi
    def ripristina(self):
        self.plastico.ripristina_scambi()
        self.mosse = 0

    def configurazione_testo(self, sigla):
        t = self.griglia.scambi[sigla]
        a = lati(t.maschera)
        return "%s e %s" % (self.NORD[a[0]], self.NORD[a[1]])

    def avvia_treno(self):
        if self.fase != "fermo":
            return False
        self.tentativi += 1
        self.corsa = self.griglia.simula()
        self.punti, fine = self.griglia.polilinea(self.corsa, LATO_TRENO, QUOTA_PONTE)
        self.cumulate = [0.0]
        for a, b in zip(self.punti, self.punti[1:]):
            self.cumulate.append(self.cumulate[-1] + math.dist(a, b))
        self.s = self.t_corsa = self.t_sbuffo = 0.0
        self.inclinazione = 0.0
        self.yaw = self.pitch = 0.0
        self.esito.enabled = False
        self.fase = "corsa"
        self._aggiorna_scambi()
        self.g.suoni.suona("fischio")
        return True

    def tasto(self, key):
        """Comandi da tastiera, validi ovunque nell'archivio: 1-7 girano gli scambi, Invio fa partire il treno,
        R rimette a posto gli scambi. Restituisce True se il tasto era per la ferrovia."""
        if key in self.per_sigla:
            return self.clic("scambio_" + key)
        if key in ("enter", "numpad enter"):
            return self.clic("treno_avvia")
        if key == "r":
            return self.clic("treno_reset")
        return False

    def clic(self, oid):
        """Un clic sull'oggetto mirato. Restituisce True se riguardava la ferrovia."""
        g = self.g
        if oid in self.per_id or oid in ("treno_avvia", "treno_reset", "treno"):
            if not self.sbloccato:
                g.suoni.suona("bloccato")
                g.scuoti = .3
                if oid in self.per_id:
                    g.mostra_toast("Gli scambi sono bloccati: sblocca il Quadro di Comando con il codice dei fascicoli.",
                                   ROSSO_ALLARME)
                else:
                    g.apri_terminale()              # il Quadro è bloccato: il codice dei fascicoli va inserito qui
                return True
            if oid == "treno":
                g.mostra_toast("Hai già svelato il segreto: frammento «%s». Puoi comunque giocare con gli scambi."
                               % ENIGMI_PER_ID["treno"]["frammento"] if "treno" in g.risolti else
                               "Gira gli scambi con un clic, poi tira la leva verde.", PERGAMENA)
                return True
            if self.fase != "fermo":
                g.mostra_toast("Aspetta che il treno finisca la sua corsa…", PERGAMENA)
                return True
        if oid in self.per_id:
            s = self.per_id[oid]
            s.ruota()
            self.mosse += 1
            g.suoni.suona("scambio")
            g.mostra_toast("Scambio: ora collega %s" % self.configurazione_testo(s.tessera.sigla),
                           ORO_CHIARO)
            return True
        if oid == "treno_avvia":
            self.plastico.tira_leva("avvia")
            g.mostra_toast("Il treno parte da Torino!", VERDE_CHIARO)
            self.avvia_treno()
            return True
        if oid == "treno_reset":
            self.plastico.tira_leva("reset")
            self.ripristina()
            g.suoni.suona("click")
            g.mostra_toast("Scambi rimessi nella posizione iniziale.", PERGAMENA)
            return True
        return False

    def suggerimento(self, oid):
        """(titolo, sottotitolo) della mira per gli oggetti della ferrovia; None se non lo è."""
        if oid in self.per_id:
            sigla = self.per_id[oid].tessera.sigla
            if not self.sbloccato:
                return "Scambio %s" % sigla, "Bloccato  ·  sblocca il Quadro di Comando"
            return "Scambio %s" % sigla, "Clic o tasto %s: ruota di 90°  ·  ora collega %s" % (sigla, self.configurazione_testo(sigla))
        if oid == "treno":
            e = ENIGMI_PER_ID["treno"]
            return "Quadro di Comando Ferroviario", ("Risolto  ·  frammento «%s»" % e["frammento"] if "treno" in self.g.risolti else
                                                    "Acceso  ·  scambi: clic o tasti 1-7  ·  Invio: parti  ·  R: ripristina" if self.sbloccato else
                                                    "Bloccato  ·  clic per inserire il codice")
        if oid == "treno_avvia":
            return "Leva verde: Avvia il treno", ("Clic o Invio per far partire Cavour da Torino" if self.sbloccato
                                                  else "Bloccata  ·  clic per inserire il codice")
        if oid == "treno_reset":
            return "Leva rossa: Ripristina", ("Clic o R per rimettere gli scambi come all'inizio" if self.sbloccato
                                              else "Bloccata  ·  clic per inserire il codice")
        return None

    # ------------------------------------------------------------------ aggiornamento
    def update(self, dt):
        t = time.monotonic()
        self.plastico.aggiorna(dt, t)
        self.plastico.treno.aggiorna_fumo(dt, self.fase == "corsa")
        if self.pop < 1.0:
            self.pop = min(1.0, self.pop + dt * 4)
            self.plastico.treno.radice.scale = .5 + .5 * self.pop
        f = self.fase
        if f == "corsa":
            self._avanza_corsa(dt)
        elif f == "esito":
            if self.corsa.esito == Corsa.DERAGLIATO:           # il treno si ribalta sull'erba
                self.inclinazione = min(34.0, self.inclinazione + dt * 110)
                x, y, z = self.ultima
                self.plastico.treno.imposta(x, y, z, self.yaw, self.pitch, self.inclinazione)
            self.timer_esito -= dt
            if self.timer_esito <= 0:
                self._riparti()
        elif f == "vittoria":
            self.timer_esito -= dt
            if self.timer_esito <= 0 and not self.vittoria_notificata and self.g.puo_notificare_vittoria():
                self.vittoria_notificata = True
                self.fase = "fermo"                             # si può continuare a giocare con gli scambi
                self._aggiorna_scambi()
                self.su_vittoria()

    def _posa(self, s):
        """Posizione, direzione e salita del treno alla distanza s lungo il percorso."""
        cum, pts = self.cumulate, self.punti
        i = max(0, min(bisect.bisect_right(cum, s) - 1, len(pts) - 2))
        lun = cum[i + 1] - cum[i]
        f = 0.0 if lun <= 1e-9 else (s - cum[i]) / lun
        a, b = pts[i], pts[i + 1]
        x, z, y = (a[k] + (b[k] - a[k]) * f for k in (0, 1, 2))
        orizz = math.hypot(b[0] - a[0], b[1] - a[1])
        yaw = math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))
        pitch = math.degrees(math.atan2(b[2] - a[2], orizz)) if orizz > 1e-9 else 0.0
        return x, y, z, yaw, pitch

    def _avanza_corsa(self, dt):
        self.t_corsa += dt
        vel = self.VELOCITA * min(1.0, .3 + self.t_corsa * .9)
        self.s = min(self.cumulate[-1], self.s + vel * dt)
        x, y, z, yaw, pitch = self._posa(self.s)
        k = min(1.0, dt * 18)
        self.yaw += ((yaw - self.yaw + 180) % 360 - 180) * k
        self.pitch += (pitch - self.pitch) * min(1.0, dt * 12)
        self.ultima = (x, y, z)
        self.plastico.treno.imposta(x, y, z, self.yaw, self.pitch)
        self.t_sbuffo -= dt
        if self.t_sbuffo <= 0:
            self.g.suoni.suona("sbuffo")
            self.t_sbuffo = .34
        if self.s >= self.cumulate[-1]:
            self._fine_corsa()

    def _fine_corsa(self):
        if self.corsa.vittoria:
            self.fase = "vittoria"
            self.timer_esito = 1.2
            self.vittoria_notificata = False
            self.g.suoni.suona("fischio")
        else:
            self.fase = "esito"
            self.timer_esito = 3.4
            self.inclinazione = 0.0
            self.e_motivo.text = self.corsa.motivo
            self.esito.enabled = True
            self.g.suoni.suona("incidente")

    def _riparti(self):
        """Dopo l'incidente il treno torna a Torino e si può riprovare."""
        self.esito.enabled = False
        self.plastico.riporta_alla_partenza()
        self.yaw = self.pitch = 0.0
        self.plastico.treno.radice.rotation = (0, 0, 0)
        self.pop = 0.0
        self.fase = "fermo"
        self._aggiorna_scambi()




# --------------------------------------------------------------------------
# Schermata di Vittoria Epica (il treno è arrivato a Plombières)
# --------------------------------------------------------------------------
class SchermataEpica(Entity):
    def __init__(self, gioco, su_continua):
        super().__init__(parent=camera.ui, enabled=False, z=-7.5)
        g = gioco
        self.testi = TestiAdattivi()
        self.aspetto = None
        quad_ui(self, (0, 0), (4, 1.2), color.white, g.t_oro, z=.3)
        
        # PANNELLO SCURO INGRANDITO per far entrare anche il testo dei frammenti
        self.pannello = quad_ui(self, (0, .26), (1.6, .52), C(28, 12, 8, 205), z=.12)
        
        self.raggi = quad_ui(self, (0, .28), (2.6, 2.6), color.white, g.t_raggi, z=.25)
        quad_ui(self, (0, .28), (1.2, 1.2), C(255, 220, 140, 120), g.t_alone, z=.2)
        
        self.strisce = []
        for i, c in enumerate(TRICOLORE):
            self.strisce.append((quad_ui(self, (0, .49), (.667, .02), c), quad_ui(self, (0, -.49), (.667, .02), c), i))
        
        libero = lambda a: a * .86
        
        # TESTI SUPERIORI: tutti allineati all'interno del pannello scuro
        self.testi.aggiungi(testo_ui(self, "PLOMBIÈRES  ·  21 luglio 1858", (0, .46), 1.2, PERGAMENA, "b"), 1.2, libero)
        self.titolo = quad_ui(self, (0, .32), (1.4, .2), color.white, g.t_epica, z=-.02)
        self.testi.aggiungi(testo_ui(self, "Complimenti! Hai forgiato le alleanze che hanno fatto l'Italia.", (0, .19), 1.15, PERGAMENA, "b"), 1.15, libero)
        self.tempo = self.testi.aggiungi(testo_ui(self, "", (0, .13), 1.1, ORO_CHIARO, "b"), 1.1, libero)
        self.frammento = self.testi.aggiungi(testo_ui(self, "", (0, .07), 1.1, PERGAMENA, "b"), 1.1, libero)
        
        # PERGAMENA INFERIORE: abbassata per non accavallarsi col pannello
        self.pergamena = quad_ui(self, (0, -.18), (1.3, .38), color.white, g.t_pergamena_larga, z=.1)
        dentro = lambda a: self.pergamena.scale_x - .16
        
        # TESTI INFERIORI: centrati all'interno della pergamena
        self.testi.aggiungi(testo_ui(self, "Il patto segreto di Cavour e Napoleone III", (0, -.03), 1.2, BORDEAUX_SCURO, "b", z=-.01), 1.2, dentro)
        self.curiosita = self.testi.aggiungi(RigheCentrate(self, (0, -.20), 1.05, INCHIOSTRO, "i", z=-.01), 1.05, dentro, .25)
        
        # PULSANTE E ISTRUZIONI: posizionati al fondo, sotto la pergamena
        self.b_continua = pulsante(self, "Continua verso l'uscita", (0, -.405), (.52, .085), True, su_continua)
        self.testi.aggiungi(testo_ui(self, "Invio: continua   ·   il tempo resta fermo", (0, -.462), .85, PERGAMENA_SCURA, "i"), .85, libero)
        
        self.coriandoli = []
        for _ in range(110):
            c = quad_ui(self, (random.uniform(-.9, .9), random.uniform(.5, 1.6)),
                        (random.uniform(.006, .012), random.uniform(.012, .02)),
                        random.choice(TRICOLORE + [ORO]), z=-.05)
            c.vel = Vec2(random.uniform(-.05, .05), -random.uniform(.12, .3))
            c.rot = random.uniform(-300, 300)
            self.coriandoli.append(c)    

    def adatta(self, a):
        self.aspetto = a
        for i, (alto, basso, k) in enumerate(self.strisce):
            larg = a / 3 + .002
            alto.scale_x = basso.scale_x = larg
            alto.x = basso.x = -a / 2 + larg * (k + .5)
        self.pergamena.scale_x = min(1.3, a * .94)
        self.pannello.scale_x = min(1.6, a * .96)
        w = min(1.4, a * .9) 
        self.titolo.scale = (w, w * .2 / 1.4)  # FIX proporzioni titolo largo
        self.testi.adatta(a)

    def mostra(self, tempo_fermo, enigma):
        self.tempo.text = "Il timer si è fermato a %s" % tempo_fermo
        self.frammento.text = "Frammento «%s» della parola d'ordine conquistato!" % enigma["frammento"]
        self.curiosita.text = avvolgi(enigma["curiosita"], 52)
        a = window.aspect_ratio
        self.adatta(a)
        w = self.titolo.scale_x
        self.titolo.scale = (w * 1.2, w * 1.2 * .2 / 1.4)
        self.titolo.animate_scale(Vec3(w, w * .2 / 1.4, 1), duration=.8, curve=curve.out_back)
        for c in self.coriandoli:
            c.position = (random.uniform(-a / 2, a / 2), random.uniform(.55, 1.6))
        self.enabled = True

    def nascondi(self):
        self.enabled = False

    def aggiorna(self, dt):
        a = window.aspect_ratio
        if abs(a - (self.aspetto or 0)) > 1e-3:                           
            self.adatta(a)
        self.raggi.rotation_z += dt * 6
        for c in self.coriandoli:
            c.x += c.vel.x * dt
            c.y += c.vel.y * dt
            c.rotation_z += c.rot * dt
            if c.y < -.6:
                c.y = random.uniform(.55, .7)
                c.x = random.uniform(-a / 2, a / 2)
# --------------------------------------------------------------------------
# Il gioco
# --------------------------------------------------------------------------
def escludi_statiche_dal_ciclo():
    """Ad ogni fotogramma Ursina scorre TUTTE le entità (qui quasi quattromila: ogni cubetto è un'entità) per chiamare
    il loro update e smistare i tasti, e per ciascuna risale la catena dei genitori. Quasi nessuna ha un update o un input:
    le tolgo dalla lista (restano nella scena e vengono disegnate come prima). Restano in lista quelle che hanno
    update, input, text_input, script o collider: i collider servono a mouse.hovered_entity e al mirino."""
    def serve(e):
        return ((hasattr(e, "update") and callable(e.update)) or (hasattr(e, "input") and callable(e.input))
                or (hasattr(e, "text_input") and callable(e.text_input)) or bool(getattr(e, "scripts", None))
                or bool(e.collider))
    scene.entities[:] = [e for e in scene.entities if serve(e)]


class Gioco(Entity):
    def __init__(self):
        super().__init__()
        self.suoni = Suoni()
        self._crea_texture()
        self.shader_stanza = crea_shader_stanza()
        self.mondo = Entity(shader=self.shader_stanza)
        self.mondo.set_shader_input("lucido", 0.15)
        self.mondo.set_shader_input("emissione", Vec3(0, 0, 0))
        self.luci = []
        self.fiamme = []
        self.ostacoli = []
        self.solidi = []                 # (x0, x1, z0, z1, y0, y1): ponti e rampe, con altezza
        self.interattivi = {}          # id -> radice dell'oggetto
        self._costruisci_stanza()
        self._prepara_luci()
        self._costruisci_hud()
        self._costruisci_modale()
        self._costruisci_schermate()
        self.polvere = [self._crea_granello() for _ in range(40)]
        camera.fov = 75
        self.filtro = None               # riduzione di risoluzione della scena (RisoluzioneScena), None = risoluzione piena
        self.scala_risoluzione = 1.0
        self.imposta_grafica(carica_grafica(), salva=False, avviso=False)
        self.stato = "intro"
        self._reset()
        self._mostra_intro()
        escludi_statiche_dal_ciclo()

    # ------------------------------------------------------------------ texture
    def _crea_texture(self):
        self.t_parati = tex(img_carta_da_parati())
        self.t_parquet = tex(img_parquet())
        self.t_legno = tex(img_legno())
        self.t_legno_chiaro = tex(img_legno((110, 70, 40), 7))
        self.t_boiserie = tex(img_boiserie())
        self.t_pietra = tex(img_pietra())
        self.t_mappa = tex(img_mappa())
        self.t_ritratto = tex(img_ritratto())
        self.t_spartito = tex(img_spartito())
        self.t_lettera = tex(img_lettera())
        self.t_lettera_bruciata = tex(img_lettera_bruciata())
        self.t_globo = tex(img_globo())
        self.t_tappeto = tex(img_tappeto())
        self.t_quadrante = tex(img_quadrante())
        self.t_alone = tex(img_radiale(128), "bilinear")
        self.t_fiamma = tex(img_fiamma(), "bilinear")
        self.t_vignetta = tex(img_vignetta(), "bilinear")
        self.t_sigillo = tex(img_sigillo(), "bilinear")
        self.t_coccarda = tex(img_coccarda(), "bilinear")
        self.t_pergamena_modale = tex(img_pergamena(1100, 760), "bilinear")
        self.t_pergamena_larga = tex(img_pergamena(1300, 440, seme=77), "bilinear")
        self.t_pannello = tex(img_pannello(420, 170), "bilinear")
        self.t_slot = tex(img_pergamena(220, 100, bordo=False, seme=5), "bilinear")
        self.t_raggi = tex(img_raggi(), "bilinear")
        self.t_targa = tex(img_targa())
        self.t_obbedisco = tex(img_titolo_oro("OBBEDISCO", 1100, 200), "bilinear")
        self.t_sigillo_ok = tex(img_sigillo(spunta=True), "bilinear")
        self.t_oro = tex(_gradiente(64, 256, (120, 80, 20), (20, 12, 6)), "bilinear")
        self.t_rosso = tex(_gradiente(64, 256, (110, 8, 16), (16, 2, 4)), "bilinear")
        # archivio segreto, Libreria Patriottica e Treno Diplomatico
        self.t_scheda = tex(img_scheda(), "bilinear")
        self.t_lucchetto = tex(img_lucchetto(False), "bilinear")
        self.t_lucchetto_aperto = tex(img_lucchetto(True), "bilinear")
        self.t_fascicoli = [tex(img_fascicolo(t, a, seme=i + 1, scritta=False)) for i, (t, a) in enumerate(FASCICOLI)]
        self.t_targa_quadro = tex(img_targa_quadro())
        self.t_epica = tex(img_titolo_oro("VITTORIA EPICA", 1100, 200), "bilinear")
        self.t_erba, self.t_terra, self.t_roccia, self.t_neve = (tex(img_erba()), tex(img_terra()),
                                                                tex(img_roccia()), tex(img_neve()))
        self.t_foglie, self.t_tronco = tex(img_foglie()), tex(img_tronco())
        self.t_mattoni_mc, self.t_tetto_mc, self.t_assi_mc = tex(img_mattoni_mc()), tex(img_tetto_mc()), tex(img_assi_mc())
        self.t_cartelli = {"torino": tex(img_cartello("TORINO", (28, 84, 150)), "bilinear"),
                           "plombieres": tex(img_cartello("PLOMBIÈRES", (20, 118, 62)), "bilinear"),
                           "vienna": tex(img_cartello("VIENNA", (170, 28, 28)), "bilinear")}
        self.t_numeri = {s: tex(img_numero(s), "bilinear") for s in "1234567"}
        self.t_istruzioni = tex(img_istruzioni_quadro(), "bilinear")
        self.t_etichette = {"AVVIA": tex(img_cartello("AVVIA", (28, 110, 54), w=320, h=80), "bilinear"),
                            "RIPRISTINA": tex(img_cartello("RIPRISTINA", (140, 28, 28), w=320, h=80), "bilinear")}
        pianta = Griglia()
        self.t_minimappa = tex(img_minimappa(pianta), "bilinear")
        self.t_mm_scambio = {m: tex(img_mm_scambio(m), "bilinear")
                             for m in (DIR_N | DIR_E, DIR_E | DIR_S, DIR_S | DIR_O, DIR_O | DIR_N, DIR_N | DIR_S, DIR_E | DIR_O)}

    # ------------------------------------------------------------------ stanza
    def _costruisci_stanza(self):
        m = self.mondo
        # pavimento, tappeto, soffitto
        blocco(m, (0, 0, 0), (8, 1, 8), texture=self.t_parquet, tex_scale=(3, 3), model="plane")
        blocco(m, (0, .006, .2), (3.6, 1, 2.5), texture=self.t_tappeto, model="plane")
        blocco(m, (0, 3.4, 0), (8, 1, 8), col=C(40, 26, 18), texture=self.t_legno, tex_scale=(4, 4),
               model="plane", rot=(180, 0, 0))
        for x in (-2.7, -.9, .9, 2.7):
            blocco(m, (x, 3.3, 0), (.22, .2, 8), col=C(70, 44, 26), texture=self.t_legno)
        # pareti: carta da parati sopra, boiserie sotto
        for (pos, scala, rot) in (((0, 1.7, 4.1), (8.4, 3.4, .2), 0),
                                  ((4.1, 1.7, 0), (.2, 3.4, 8.4), 0), ((-4.1, 1.7, 0), (.2, 3.4, 8.4), 0)):
            blocco(m, pos, scala, texture=self.t_parati, tex_scale=(10, 4))
        # la parete di fondo ha un varco nascosto dietro la libreria di destra (vedi StanzaSegreta)
        self.stanza_segreta = StanzaSegreta(self)
        self.stanza_segreta.costruisci_parete_nord()
        for lato in range(4):
            nodo = Entity(parent=m, rotation_y=lato * 90)
            # sulla parete nord la boiserie si interrompe in corrispondenza della porta
            tratti = [(-2.36, 3.28), (2.36, 3.28)] if lato == 0 else [(0, 8)]
            if lato == 2:
                tratti = [((-4.0 - APERTURA_X1) / 2, 4.0 - APERTURA_X1),
                          ((4.0 - APERTURA_X0) / 2, 4.0 + APERTURA_X0)]
            for (cx, lw) in tratti:
                blocco(nodo, (cx, .5, 3.97), (lw, 1.0, .06), texture=self.t_boiserie, tex_scale=(lw * .75, 1))
                blocco(nodo, (cx, 1.02, 3.95), (lw, .06, .1), col=LEGNO_SCURO, texture=self.t_legno)
                blocco(nodo, (cx, .06, 3.94), (lw, .12, .08), col=LEGNO_SCURO)
            blocco(nodo, (0, 3.33, 3.96), (8, .14, .1), col=C(60, 38, 22), texture=self.t_legno)
        self.ostacoli += [(-1.3, -4.2, 1.3, -3.15), (-3.3, -4.2, -1.7, -3.5), (1.7, -4.2, 3.3, -3.5)]
        self._costruisci_porta()
        self._costruisci_pianoforte()
        self._costruisci_scrivania()
        self._costruisci_ritratto()
        self._costruisci_mappa()
        self._costruisci_camino()
        for x in (-2.5, 2.5):
            libreria = self._costruisci_libreria((x, 0, -3.78))
            if x > 0:
                self.libreria_scorrevole = libreria
        self._costruisci_lampadario()
        # l'archivio segreto dietro la libreria: muri, luci, fascicoli a terra e plastico ferroviario
        prima = set(self.mondo.getChildren())            # per sapere quali nodi appartengono all'archivio
        self.stanza_segreta.costruisci()
        self.fascicoli = FascicoliPatriottici(self)
        self.stanza_segreta.candelabro((-2.75, 0, -5.7 - SPAZIO_INGRESSO), Vec3(1.5, .9, .46))
        for x in (10.5, 4.7, -.3, -5.7):                 # l'ultimo tratto di ferrovia (Vienna e Plombières) ha i suoi lampioni
            self.stanza_segreta.lampione(x, ARC_Z0 + 1.1)
        self.treno = TrenoDiplomatico(self, self._treno_vinto)
        self.stanza_segreta.nodi_archivio = [c for c in self.mondo.getChildren()
                                             if c not in prima and not c.isHidden() and not c.isStashed()]

    def _candela(self, parent, pos, altezza=.16, scala_fiamma=1.0, luce=None):
        blocco(parent, (pos[0], pos[1] + altezza / 2, pos[2]), (.035, altezza, .035), col=CERA, model=cilindro(10, start=-.5))
        punta = (pos[0], pos[1] + altezza + .03 * scala_fiamma, pos[2])
        f = sprite_luminoso(parent, punta, (.035 * scala_fiamma, .07 * scala_fiamma), self.t_fiamma, C(255, 230, 180))
        a = sprite_luminoso(parent, punta, (.35 * scala_fiamma, .35 * scala_fiamma), self.t_alone, C(255, 170, 80, 110))
        self.fiamme.append([f, a, f.scale, a.scale, random.uniform(0, 10)])
        if luce is not None:
            luce["nodo"] = f
            self.luci.append(luce)
        return f

    def _costruisci_porta(self):
        r = Entity(parent=self.mondo, position=(0, 0, 3.92))
        self.porta_radice = r
        # cornice in pietra
        for x in (-.86, .86):
            blocco(r, (x, 1.35, 0), (.32, 2.7, .3), texture=self.t_pietra, tex_scale=(.6, 3))
        blocco(r, (0, 2.82, 0), (2.04, .36, .32), texture=self.t_pietra, tex_scale=(3, .6))
        blocco(r, (0, 3.07, 0), (2.2, .1, .36), col=C(120, 116, 112), texture=self.t_pietra)
        # luce "esterna" dietro l'anta (visibile quando la porta si apre)
        self.luce_esterna = Entity(parent=r, model="quad", position=(0, 1.32, .0), scale=(1.42, 2.64),
                                   color=C(255, 236, 180), shader=unlit_shader)
        # anta con cardine a sinistra
        self.anta = Entity(parent=r, position=(-.7, 0, -.08))
        rnd = random.Random(1848)
        blocco(self.anta, (.7, 1.32, .05), (1.4, 2.64, .02), col=C(30, 18, 10))      # controfodera
        for i in range(5):
            t = rnd.uniform(.85, 1.1)
            blocco(self.anta, (.14 + i * .28, 1.32, 0), (.285, 2.64, .09),
                   col=C(int(96 * t), int(60 * t), int(36 * t)), texture=self.t_legno, tex_scale=(.3, 2))
        for y in (.45, 1.35, 2.25):
            blocco(self.anta, (.7, y, -.055), (1.4, .1, .02), col=FERRO)
            for k in range(6):
                blocco(self.anta, (.12 + k * .232, y, -.068), (.03, .03, .01), col=C(110, 110, 118))
        blocco(self.anta, (1.2, 1.2, -.06), (.1, .22, .02), col=ORO_SCURO)
        blocco(self.anta, (1.2, 1.26, -.09), (.05, .05, .06), col=ORO, model="sphere")
        blocco(self.anta, (1.2, 1.15, -.075), (.02, .05, .01), col=C(10, 8, 6))
        # catene incrociate e lucchetto
        self.catene = Entity(parent=r, position=(0, 0, -.2))
        for (x1, y1, x2, y2) in ((-.8, 2.2, .8, .7), (.8, 2.2, -.8, .7)):
            passi = 26
            ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
            for k in range(passi + 1):
                u = k / passi
                blocco(self.catene, (x1 + (x2 - x1) * u, y1 + (y2 - y1) * u, -.01 * (k % 2)),
                       (.085, .04, .02) if k % 2 else (.085, .04, .04), col=C(150, 150, 160),
                       rot=(0 if k % 2 else 90, 0, -ang))
        lucchetto = Entity(parent=self.catene, position=(0, 1.45, -.04))
        blocco(lucchetto, (0, 0, 0), (.22, .2, .08), col=ORO)
        blocco(lucchetto, (-.07, .15, 0), (.035, .14, .035), col=C(170, 170, 180))
        blocco(lucchetto, (.07, .15, 0), (.035, .14, .035), col=C(170, 170, 180))
        blocco(lucchetto, (0, .22, 0), (.175, .035, .035), col=C(170, 170, 180))
        blocco(lucchetto, (0, -.01, -.045), (.03, .06, .01), col=C(20, 14, 8))
        self.catene.set_shader_input("lucido", 0.9)
        # targa
        targa = blocco(r, (0, 2.82, -.17), (.9, .2, .03), texture=self.t_targa)
        targa.set_shader_input("lucido", 0.8)
        # applique ai lati della porta
        for x in (-1.45, 1.45):
            blocco(r, (x, 1.95, -.06), (.08, .2, .06), col=ORO_SCURO)
            blocco(r, (x, 2.0, -.16), (.03, .03, .2), col=ORO_SCURO)
            blocco(r, (x, 2.02, -.25), (.1, .02, .1), col=ORO_SCURO, model=cilindro(10))
            self._candela(r, (x, 2.03, -.25), .14, 1.0,
                          {"col": Vec3(1.3, .78, .4), "tremolio": .25})
        self.interattivi["porta"] = r
        Entity(parent=r, model="cube", collider="box", position=(0, 1.4, -.25), scale=(2.0, 2.9, .5), visible=False,
               id_oggetto="porta")

    def _costruisci_pianoforte(self):
        r = Entity(parent=self.mondo, position=(-1.95, 0, 2.2), rotation_y=-90)
        self.interattivi["pianoforte"] = r
        self.interattivi["inno"] = r
        cassa = Entity(parent=r)
        cassa.set_shader_input("lucido", 1.0)
        blocco(cassa, (0, .86, .45), (1.5, .3, 1.2), col=NERO_LACCA)
        # coda: lato sinistro (bassi) dritto, lato destro curvo, come in un vero pianoforte a coda
        blocco(cassa, (-.315, .86, 1.4), (.87, .3, .7), col=NERO_LACCA)
        blocco(cassa, (.12, .855, 1.2), (1.2, .29, 1.2), col=NERO_LACCA, model=cilindro(24))
        # coperchio: cerniera sul lato dritto (sinistra), si solleva sul lato curvo (destra)
        coperchio = Entity(parent=cassa, position=(-.75, 1.02, .5), rotation_z=-32)
        blocco(coperchio, (.72, 0, .4), (1.45, .03, 1.9), col=C(20, 18, 22))
        blocco(cassa, (.42, 1.38, .7), (.025, .74, .025), col=C(30, 26, 28))       # asta di sostegno
        # tastiera
        blocco(r, (0, .76, -.28), (1.5, .06, .36), col=NERO_LACCA)
        n = 26
        self.tasti = {}
        scala_do = [0, 2, 4, 5, 7, 9, 11]
        for i in range(n):
            x = -.68 + i * (1.36 / n)
            midi = 48 + 12 * (i // 7) + scala_do[i % 7]           # il tasto 0 è il Do3
            t = blocco(r, (x + .026, .8, -.36), (.049, .025, .2), col=C(236, 230, 214))
            t.collider = "box"
            self.tasti[midi] = t
            if i % 7 not in (2, 6) and i < n - 1:
                t = blocco(r, (x + .052, .82, -.32), (.028, .03, .12), col=C(10, 8, 8))
                t.collider = "box"
                self.tasti[midi + 1] = t
        for midi, t in self.tasti.items():
            t.nota = midi
            t.y0 = t.y
        # punti di vista per quando ci si siede a suonare
        self.piano_occhi = Entity(parent=r, position=(0, 1.5, -1.3))
        self.piano_mira = Entity(parent=r, position=(0, .93, -.1))
        blocco(r, (0, .86, -.14), (1.5, .14, .06), col=NERO_LACCA)
        # leggio con spartito
        blocco(r, (0, 1.2, -.07), (.62, .4, .02), col=C(20, 16, 18), rot=(-15, 0, 0))
        blocco(r, (0, 1.21, -.085), (.56, .36, .005), texture=self.t_spartito, rot=(-15, 0, 0))
        # gambe e pedali
        for (x, z) in ((-.65, -.1), (.65, -.1), (.1, 1.6)):
            blocco(r, (x, .37, z), (.1, .74, .1), col=NERO_LACCA, model=cilindro(10, start=-.5))
            blocco(r, (x, .02, z), (.12, .04, .12), col=ORO_SCURO, model=cilindro(10, start=-.5))
        # lira dei pedali
        for dx in (-.08, .08):
            blocco(r, (dx, .4, .02), (.03, .62, .03), col=NERO_LACCA)
        blocco(r, (0, .1, .02), (.26, .1, .1), col=NERO_LACCA)
        for dx in (-.07, 0, .07):
            blocco(r, (dx, .06, -.06), (.035, .015, .1), col=ORO)
        # candelabro sul pianoforte
        blocco(r, (.5, 1.02, -.02), (.12, .02, .12), col=ORO, model=cilindro(10, start=-.5))
        blocco(r, (.5, 1.1, -.02), (.025, .16, .025), col=ORO)
        blocco(r, (.5, 1.17, -.02), (.26, .02, .02), col=ORO)
        for dx in (-.12, 0, .12):
            self._candela(r, (.5 + dx, 1.18, -.02), .12, .9,
                          {"col": Vec3(1.2, .72, .36), "tremolio": .3} if dx == 0 else None)
        # sgabello
        blocco(r, (0, .5, -.85), (.8, .08, .38), col=C(40, 26, 18), texture=self.t_legno)
        blocco(r, (0, .56, -.85), (.76, .05, .34), col=BORDEAUX)
        for sx in (-1, 1):
            for sz in (-1, 1):
                blocco(r, (sx * .34, .25, -.85 + sz * .14), (.05, .5, .05), col=C(40, 26, 18))
        self.piano_hitbox = Entity(parent=r, model="cube", collider="box", position=(0, .9, .6), scale=(1.7, 1.8, 2.3),
                                   visible=False, id_oggetto="pianoforte")
        self.ostacoli += [(-3.75, 1.4, -1.55, 3.0), (-1.3, 1.75, -.95, 2.65)]

    def _costruisci_scrivania(self):
        r = Entity(parent=self.mondo, position=(2.85, 0, 2.2), rotation_y=90)
        self.interattivi["scrivania"] = r
        blocco(r, (0, .78, 0), (1.6, .06, .8), texture=self.t_legno_chiaro)
        blocco(r, (0, .79, -.02), (1.4, .005, .6), col=C(30, 70, 44))            # panno verde
        for sx in (-1, 1):
            blocco(r, (sx * .52, .45, .0), (.5, .6, .74), texture=self.t_legno)   # cassettiere
            for k in range(3):
                blocco(r, (sx * .52, .66 - k * .2, -.375), (.44, .16, .01), col=C(80, 50, 30), texture=self.t_legno)
                blocco(r, (sx * .52, .66 - k * .2, -.385), (.04, .04, .02), col=ORO, model="sphere")
            blocco(r, (sx * .52, .08, 0), (.52, .16, .76), col=LEGNO_SCURO)
        # oggetti sul piano
        blocco(r, (.05, .815, -.05), (.34, .005, .44), texture=self.t_lettera, rot=(0, 12, 0))
        blocco(r, (.45, .84, .1), (.1, .08, .1), col=C(16, 16, 24), model=cilindro(12, start=-.5))
        blocco(r, (.45, .885, .1), (.05, .02, .05), col=ORO_SCURO, model=cilindro(10, start=-.5))
        penna = Entity(parent=r, position=(.45, .9, .1), rotation=(0, 20, -25))
        blocco(penna, (.0, .16, 0), (.012, .34, .012), col=C(230, 222, 204))
        blocco(penna, (.0, .24, 0), (.06, .2, .006), col=C(240, 236, 226))
        for k, c in enumerate((C(92, 18, 30), C(22, 60, 40), C(40, 34, 70))):
            blocco(r, (-.45, .83 + k * .05, .18), (.34 - k * .03, .05, .24), col=c, rot=(0, k * 8, 0))
        blocco(r, (-.6, .81, -.15), (.14, .02, .14), col=ORO, model=cilindro(12, start=-.5))
        self._candela(r, (-.6, .82, -.15), .22, 1.1, {"col": Vec3(1.5, .9, .45), "tremolio": .35})
        # sedia
        blocco(r, (0, .45, -.7), (.5, .06, .48), col=C(60, 38, 22), texture=self.t_legno)
        blocco(r, (0, .49, -.7), (.44, .04, .42), col=BORDEAUX)
        blocco(r, (0, .8, -.93), (.5, .62, .05), col=C(60, 38, 22), texture=self.t_legno)
        for sx in (-1, 1):
            for sz in (-1, 1):
                blocco(r, (sx * .21, .22, -.7 + sz * .2), (.04, .44, .04), col=C(50, 30, 18))
        Entity(parent=r, model="cube", collider="box", position=(0, .8, -.1), scale=(1.8, 1.6, 1.2), visible=False,
               id_oggetto="scrivania")
        self.ostacoli += [(2.4, 1.35, 3.35, 3.05), (1.85, 1.9, 2.4, 2.5)]

    def _costruisci_ritratto(self):
        r = Entity(parent=self.mondo, position=(-3.93, 1.85, -.7), rotation_y=-90)
        self.interattivi["ritratto"] = r
        cornice = Entity(parent=r)
        cornice.set_shader_input("lucido", 0.9)
        
        for (pos, sc) in (((0, .66, 0), (1.12, .14, .08)), ((0, -.66, 0), (1.12, .14, .08)),
                          ((-.52, 0, 0), (.14, 1.46, .08)), ((.52, 0, 0), (.14, 1.46, .08))):
            blocco(cornice, pos, sc, col=ORO)
            
        for (pos, sc) in (((0, .6, -.03), (.94, .03, .04)), ((0, -.6, -.03), (.94, .03, .04)),
                          ((-.46, 0, -.03), (.03, 1.2, .04)), ((.46, 0, -.03), (.03, 1.2, .04))):
            blocco(cornice, pos, sc, col=ORO_SCURO)
            
        blocco(r, (0, 0, .01), (.9, 1.16, .01), texture=self.t_ritratto)
        
        # Corona abbassata a y=0.77 per aderire alla cornice
        corona = Entity(parent=cornice, position=(0, .77, -.02))
        blocco(corona, (0, 0, 0), (.32, .08, .06), col=ORO)
        for dx, h in ((-.13, .12), (0, .17), (.13, .12)):
            blocco(corona, (dx, h / 2, 0), (.05, h, .05), col=ORO)
            blocco(corona, (dx, h + .02, 0), (.05, .05, .05), col=ORO_CHIARO, model="sphere")
        blocco(corona, (0, .01, -.035), (.05, .05, .02), col=C(200, 30, 40), model="sphere")
        
        # Lampada sistemata: alzata a y=0.96, scala x/y invertita, aggiunta rotazione, rimossa direction
        blocco(r, (0, .96, -.14), (.05, .5, .06), col=ORO_SCURO, rot=(0, 0, 90), model=cilindro(10, start=-.5))
        
        Entity(parent=r, model="cube", collider="box", position=(0, 0, -.2), scale=(1.3, 1.9, .4), visible=False,
               id_oggetto="ritratto")

    def _costruisci_mappa(self):
        r = Entity(parent=self.mondo, position=(3.93, 1.8, -.7), rotation_y=90)
        self.interattivi["mappa"] = r
        blocco(r, (0, 0, 0), (1.5, 1.05, .01), texture=self.t_mappa)
        for y in (.56, -.56):
            # Nota la scala invertita (.07, 1.64, .07), la rotazione rot=(0, 0, 90) 
            # e la rimozione di direction=(1, 0, 0)
            blocco(r, (0, y, -.02), (.07, 1.64, .07), col=C(90, 58, 34), texture=self.t_legno,
                   rot=(0, 0, 90), model=cilindro(12, start=-.5))
            
            for x in (-.84, .84):
                blocco(r, (x, y, -.02), (.08, .1, .1), col=ORO, model="sphere")
        blocco(r, (-.4, .82, -.01), (.01, .5, .01), col=C(120, 90, 60), rot=(0, 0, -58))
        blocco(r, (.4, .82, -.01), (.01, .5, .01), col=C(120, 90, 60), rot=(0, 0, 58))
        blocco(r, (0, 1.03, -.02), (.05, .05, .05), col=ORO_SCURO, model="sphere")
        # la carta si clicca solo sopra il mappamondo (y da 1,32 a 2,5): sotto c'è il collider del globo
        Entity(parent=r, model="cube", collider="box", position=(0, .11, -.2), scale=(1.8, 1.18, .4), visible=False,
               id_oggetto="mappa")
        self.ostacoli.append((3.35, -1.35, 4.2, -.05))
        self._costruisci_mappamondo()

    def _costruisci_mappamondo(self):
        """Il mobiletto sotto la carta con il mappamondo. Gerarchia del globo:
        base (centro) -> rollio (asse inclinato di 23°) -> beccheggio (W-S nella modalità globo) -> self.globo (gira sul
        suo asse) -> sfera con la texture e gli spilli delle città, figli del globo così girano con lui."""
        mob = Entity(parent=self.mondo, position=(3.7, 0, -.7), rotation_y=90)      # avanti (+z locale) = verso il muro
        self.interattivi["globo"] = mob
        blocco(mob, (0, .4, 0), (1.1, .8, .45), texture=self.t_legno)
        blocco(mob, (0, .81, 0), (1.2, .03, .5), col=LEGNO_SCURO)
        blocco(mob, (-.3, .85, 0), (.16, .05, .16), col=ORO_SCURO, model=cilindro(12, start=-.5))
        self.globo_base = Entity(parent=mob, position=(-.3, .9 + RAGGIO_GLOBO + .025, 0))
        rollio = Entity(parent=self.globo_base, rotation_z=23)
        self.globo_beccheggio = Entity(parent=rollio)
        self.globo = Entity(parent=self.globo_beccheggio)
        self.globo_sfera = Entity(parent=self.globo, model="sphere", texture=self.t_globo, scale=2 * RAGGIO_GLOBO,
                                  collider="sphere")           # copre gli spilli sul lato nascosto
        self.globo_sfera.set_shader_input("lucido", .5)
        # meridiano d'ottone: mezzo anello attorno al globo, con i perni ai poli
        for k in range(41):
            a = math.radians(-90 + 180 * k / 40)
            blocco(rollio, (math.cos(a) * (RAGGIO_GLOBO + .016), math.sin(a) * (RAGGIO_GLOBO + .016), 0),
                   (.011, .011, .011), col=ORO, model="sphere")
        for y in (-1, 1):
            blocco(rollio, (0, y * (RAGGIO_GLOBO + .008), 0), (.016, .02, .016), col=ORO_SCURO, model="sphere")
        piede = Entity(parent=rollio, position=(0, -RAGGIO_GLOBO - .016, 0)).get_position(mob)
        alto = piede.y - .875
        blocco(mob, (piede.x, .875 + alto / 2, piede.z), (.022, alto, .022), col=ORO_SCURO, model=cilindro(8, start=-.5))
        # gli spilli: (lat, lon) -> punto della sfera, secondo la mappatura UV di model="sphere" di Ursina
        # (u = 0,75 - atan2(x, z) / 360, v = 0,5 + lat / 180): x = cos lat · cos lon, y = sin lat, z = cos lat · sin lon
        self.spilli = []
        dirs = {n: self._direzione_globo(la, lo) for n, la, lo in CITTA_GLOBO}
        vicini = min((dirs[a] - dirs[b]).length() for a in dirs for b in dirs if a < b) * (RAGGIO_GLOBO + .011)
        raggio_presa = min(.0034, vicini * .48)              # i collider di due spilli vicini non si toccano mai
        for nome, _, _ in CITTA_GLOBO:
            d = dirs[nome]
            # l'asse z dello spillo punta fuori dal globo (look_at di Ursina non va bene qui: il genitore è ruotato)
            spillo = Entity(parent=self.globo, position=d * RAGGIO_GLOBO,
                            rotation=(-math.degrees(math.asin(d.y)), math.degrees(math.atan2(d.x, d.z)), 0))
            blocco(spillo, (0, 0, .0055), (.0011, .0011, .011), col=C(200, 186, 150))         # ago
            testa = blocco(spillo, (0, 0, .0115), (.0046, .0046, .0046), col=C(196, 28, 40), model="sphere")
            presa = Entity(parent=spillo, model="sphere", position=(0, 0, .0115), scale=2 * raggio_presa,
                           collider="sphere", visible=False)
            presa.citta = nome
            presa.testa = testa
            self.spilli.append(presa)
        self.globo_hitbox = Entity(parent=mob, model="cube", collider="box", position=(0, .655, 0), scale=(1.2, 1.31, .55),
                                   visible=False, id_oggetto="globo")
        # punto di vista ravvicinato: davanti al globo, sul suo asse di vista (lo zoom sposta la distanza)
        self.globo_mob = mob

    @staticmethod
    def _direzione_globo(lat, lon):
        la, lo = math.radians(lat), math.radians(lon)
        return Vec3(math.cos(la) * math.cos(lo), math.sin(la), math.cos(la) * math.sin(lo))

    def _costruisci_camino(self):
        r = Entity(parent=self.mondo, position=(0, 0, -3.75), rotation_y=180)     # niente deve sporgere oltre il muro (z = -4.0)
        for x in (-.9, .9):
            blocco(r, (x, .62, 0), (.36, 1.24, .5), texture=self.t_pietra, tex_scale=(.7, 2))
        blocco(r, (0, 1.36, 0), (2.3, .24, .6), texture=self.t_pietra, tex_scale=(3, .5))
        blocco(r, (0, 1.52, -.02), (2.5, .08, .7), col=LEGNO_SCURO, texture=self.t_legno)
        blocco(r, (0, .62, .12), (1.44, 1.24, .3), col=C(10, 8, 8))
        blocco(r, (0, .02, -.25), (1.9, .04, .5), texture=self.t_pietra)
        for k, (x, rot) in enumerate(((-.25, 20), (.2, -15), (0, 90))):
            blocco(r, (x, .12 + (k == 2) * .08, .05), (.5, .1, .1), col=C(70, 44, 26),
                   rot=(0, rot, 0), model=cilindro(8, start=-.5, direction=(1, 0, 0)))
        for i in range(5):
            x = -.3 + i * .15
            f = sprite_luminoso(r, (x, .32 + (i % 2) * .05, .05), (.22, .42), self.t_fiamma, C(255, 180, 90))
            self.fiamme.append([f, None, f.scale, None, random.uniform(0, 10)])
        brace = sprite_luminoso(r, (0, .2, .05), (1.4, .8), self.t_alone, C(255, 110, 40, 140))
        self.fiamme.append([brace, None, brace.scale, None, 1.0])
        self.luci.append({"nodo": brace, "col": Vec3(2.4, 1.1, .45), "tremolio": .45, "offset": Vec3(0, .25, 0)})
        # enigma "La Lettera Bruciata": la lettera cifrata sul piano di pietra, davanti alle braci.
        # Quando la si inquadra (e quando è risolta) si illumina tutto il camino.
        self.interattivi["camino"] = r
        self.lettera_bruciata = blocco(r, (.14, .043, -.3), (.42, 1, .3), texture=self.t_lettera_bruciata,
                                       col=C(150, 140, 130), rot=(0, -10, 0), model="plane")   # carta più scura: il fuoco la illumina
        Entity(parent=r, model="cube", collider="box", position=(0, .62, -.22), scale=(1.9, 1.24, .64), visible=False,
               id_oggetto="camino")
        # orologio da camino e sciabole incrociate
        blocco(r, (.75, 1.72, -.05), (.32, .32, .16), col=C(60, 38, 22), texture=self.t_legno)
        blocco(r, (.75, 1.72, -.135), (.24, .24, .01), texture=self.t_quadrante, model="quad")
        self.lancette = []
        for lung, spess in ((.08, .012), (.1, .007)):
            perno = Entity(parent=r, position=(.75, 1.72, -.15))
            blocco(perno, (0, lung / 2, 0), (spess, lung, .004), col=C(20, 14, 10))
            self.lancette.append(perno)
        for i in range(2):
            self._candela(r, (-.85 + i * .25, 1.56, -.05), .2 - i * .05, .9)
        for s in (-1, 1):
            sciabola = Entity(parent=r, position=(0, 2.35, -.12), rotation=(0, 180, s * 38))
            blocco(sciabola, (0, 0, 0), (.035, 1.1, .01), col=C(190, 190, 200))
            blocco(sciabola, (0, -.58, 0), (.16, .03, .03), col=ORO)
            blocco(sciabola, (0, -.66, 0), (.035, .14, .035), col=C(40, 26, 18))
            sciabola.set_shader_input("lucido", 1.0)

    def _costruisci_libreria(self, pos):
        r = Entity(parent=self.mondo, position=pos, rotation_y=180)
        r.set_shader_input("emissione", Vec3(.34, .27, .2))       # un velo di luce propria: le librerie restano ben visibili
        legno = C(170, 118, 80)                                    # legno più chiaro: miele e noce, non quasi nero
        blocco(r, (0, 1.2, .12), (1.5, 2.4, .04), col=legno, texture=self.t_legno_chiaro)
        for x in (-.73, .73):
            blocco(r, (x, 1.2, -.05), (.05, 2.4, .38), col=legno, texture=self.t_legno_chiaro)
        rnd = random.Random(int(pos[0] * 10))
        libri = Entity(parent=r)
        colori = [(168, 44, 58), (52, 130, 88), (78, 76, 150), (184, 120, 64), (96, 88, 80), (212, 172, 80), (176, 70, 56),
                  (64, 112, 156), (218, 204, 172)]
        for k in range(6):
            y = .08 + k * .44
            blocco(r, (0, y, -.05), (1.42, .04, .36), col=legno, texture=self.t_legno_chiaro)
            if k == 5:
                continue
            x = -.68
            while x < .64:
                lw = rnd.uniform(.035, .07)
                lh = rnd.uniform(.26, .36)
                c = rnd.choice(colori)
                t = rnd.uniform(.85, 1.15)
                inclinato = rnd.random() < .06
                Entity(parent=libri, model="cube", position=(x + lw / 2, y + .02 + lh / 2, -.06),
                       scale=(lw, lh, rnd.uniform(.22, .28)), rotation_z=12 if inclinato else 0,
                       color=C(*(min(255, int(v * t)) for v in c)))
                if rnd.random() < .5:
                    Entity(parent=libri, model="cube", position=(x + lw / 2, y + .02 + lh * .75, -.2),
                           scale=(lw + .002, .012, .01), color=ORO_SCURO)
                x += lw + (.04 if inclinato else .002)
        libri.combine()
        return r

    def _costruisci_lampadario(self):
        r = Entity(parent=self.mondo, position=(0, 2.75, .3))
        blocco(r, (0, .33, 0), (.02, .65, .02), col=FERRO)
        blocco(r, (0, 0, 0), (.9, .03, .9), col=FERRO, model=cilindro(24, start=-.5))
        blocco(r, (0, .005, 0), (.82, .04, .82), col=C(30, 30, 34), model=cilindro(24, start=-.5))
        for i in range(6):
            a = i * math.tau / 6
            self._candela(r, (math.cos(a) * .4, .03, math.sin(a) * .4), .12, .8,
                          {"col": Vec3(1.0, .65, .36), "tremolio": .2} if i == 0 else None)

    def _prepara_luci(self):
        self.luci_pos = PTA_LVecBase3f.emptyArray(N_LUCI)
        self.luci_col = PTA_LVecBase3f.emptyArray(N_LUCI)
        self.luci = self.luci[:N_LUCI]
        for i, l in enumerate(self.luci):
            p = l["nodo"].world_position + l.get("offset", Vec3(0, 0, 0))
            l["pos"] = Vec3(p.x, p.y, p.z)
            l["base"] = Vec3(*l["col"])
            l["fase"] = random.uniform(0, 100)
            self.luci_pos[i] = LVecBase3f(p.x, p.y, p.z)
        for i in range(len(self.luci), N_LUCI):
            self.luci_pos[i] = LVecBase3f(0, -100, 0)
            self.luci_col[i] = LVecBase3f(0, 0, 0)
        scene.set_shader_input("luci_pos", self.luci_pos)
        scene.set_shader_input("luci_col", self.luci_col)
        scene.set_shader_input("ambiente", Vec3(.07, .06, .07))
        scene.set_shader_input("nebbia", Vec2(6, 14))
        scene.set_shader_input("cam_pos", camera.world_position)
        scene.set_shader_input("n_luci", len(self.luci))          # i valori veri li imposta imposta_grafica / _aggiorna_luci
        scene.set_shader_input("raggio_max", 0.0)
        scene.set_shader_input("riflessi", 1.0)
        self.indice_luce_porta = [i for i, l in enumerate(self.luci) if l["nodo"].parent == self.porta_radice]

    # ------------------------------------------------------------------ grafica
    def imposta_grafica(self, indice, salva=True, avviso=True):
        """Passa al livello di grafica 'indice' (0 Bassa, 1 Media, 2 Alta, 3 Max) e lo ricorda per il prossimo avvio."""
        indice = max(0, min(len(LIVELLI_GRAFICA) - 1, int(indice)))
        liv = LIVELLI_GRAFICA[indice]
        self.livello_grafica = indice
        self.grafica = liv
        scene.set_shader_input("raggio_max", float(liv["raggio"]))
        scene.set_shader_input("riflessi", float(liv["riflessi"]))
        for i, granello in enumerate(self.polvere):
            granello.enabled = i < liv["polvere"]
        ridotta = self._applica_risoluzione(liv["risoluzione"])
        if salva:
            salva_grafica(indice)
        self._aggiorna_menu_grafica(ridotta)
        if avviso:
            self.mostra_toast("Grafica: %s" % liv["nome"], PERGAMENA)

    def _applica_risoluzione(self, scala):
        """Disegna la scena 3D alla quota 'scala' della risoluzione della finestra. Restituisce False se la scheda grafica
        non lo permette: in quel caso si resta (da soli) alla risoluzione piena."""
        base = application.base
        try:
            if self.filtro is not None:
                self.filtro.cleanup()
                self.filtro_quad.removeNode()
                self.filtro = self.filtro_quad = None
            self.scala_risoluzione = 1.0
            if abs(scala - 1.0) < .001:                # risoluzione piena: la scena va dritta in finestra, senza buffer
                return True
            filtro = RisoluzioneScena(base.win, base.cam, scala)
            colore = TexturaPanda("scena-ridotta")
            colore.setWrapU(TexturaPanda.WMClamp)
            colore.setWrapV(TexturaPanda.WMClamp)
            colore.setMinfilter(SamplerState.FT_linear)
            colore.setMagfilter(SamplerState.FT_linear)
            quad = filtro.renderSceneInto(colortex=colore)
            if quad is None:
                raise RuntimeError("la scheda grafica non crea il buffer di disegno ridotto")
            quad.clearColor()
            quad.setShader(ShaderPanda.make(ShaderPanda.SL_GLSL, _VERTEX_QUAD, _FRAGMENT_QUAD))
            self.filtro, self.filtro_quad = filtro, quad
            self.scala_risoluzione = scala
            self.controllo_filtro = 6                  # tra qualche fotogramma si verifica che il buffer sia valido
            return True
        except Exception as ex:
            print("Risoluzione ridotta non disponibile, uso la risoluzione piena:", ex)
            self._disattiva_filtro()
            return False

    def _disattiva_filtro(self):
        try:
            if self.filtro is not None:
                self.filtro.cleanup()
                self.filtro_quad.removeNode()
        except Exception as ex:
            print("Pulizia del filtro non riuscita:", ex)
        self.filtro = self.filtro_quad = None
        self.scala_risoluzione = 1.0

    def _controlla_filtro(self):
        """Se il buffer ridotto smette di essere valido (driver, cambio di schermo) si torna alla risoluzione piena."""
        if self.filtro is None:
            return
        if self.controllo_filtro > 0:
            self.controllo_filtro -= 1
            if self.controllo_filtro:
                return
        buffer_valido = bool(self.filtro.buffers) and all(b.isValid() for b in self.filtro.buffers)
        if not buffer_valido:
            print("Il buffer ridotto non è valido: torno alla risoluzione piena")
            self._disattiva_filtro()
            self._aggiorna_menu_grafica(False)

    def _aggiorna_menu_grafica(self, ridotta_ok=True):
        for i, b in enumerate(self.pulsanti_grafica):
            scelto = i == self.livello_grafica
            b.color = BORDEAUX if scelto else C(34, 32, 38)
            b.highlight_color = BORDEAUX_CHIARO if scelto else C(60, 56, 64)
            b.text_color = ORO_CHIARO if scelto else PERGAMENA
        liv = self.grafica
        luci = "tutte le luci" if liv["luci"] >= N_LUCI else "%d luci" % liv["luci"]
        testo = "%s  ·  %s  ·  risoluzione %d" % (luci, "con riflessi" if liv["riflessi"] else "senza riflessi",
                                                  round(self.scala_risoluzione * 100)) + "%"
        if not ridotta_ok:
            testo += "   (risoluzione ridotta non disponibile su questa scheda grafica)"
        self.testo_grafica.text = testo

    def _su_menu_grafica(self):
        return mouse.hovered_entity in self.pulsanti_grafica

    def _crea_granello(self):
        g = sprite_luminoso(self.mondo, (random.uniform(-3.5, 3.5), random.uniform(.3, 3), random.uniform(-3.5, 3.5)),
                            (.012, .012), self.t_alone, C(255, 220, 160, 150))
        g.vel = Vec3(random.uniform(-.03, .03), random.uniform(-.02, .03), random.uniform(-.03, .03))
        return g

    # ------------------------------------------------------------------ interfaccia
    def _costruisci_hud(self):
        ui = camera.ui
        self.vignetta = quad_ui(ui, (0, 0), (3, 1.05), color.white, self.t_vignetta, z=5)
        self.hud = Entity(parent=ui)
        self.coccarda = quad_ui(self.hud, (0, .445), (.075, .075), color.white, self.t_coccarda)
        self.titolo = testo_ui(self.hud, "IL SEGRETO DEL CARBONARO", (0, .458), 1.55, ORO, "b", (-.5, 0))
        self.sottotitolo = testo_ui(self.hud, "", (0, .42), .95, PERGAMENA, "i", (-.5, 0))
        self.pannello_timer = quad_ui(self.hud, (0, .43), (.32, .12), color.white, self.t_pannello)
        self.etichetta_timer = testo_ui(self.hud, "I GENDARMI ENTRERANNO TRA", (0, .469), .52, PERGAMENA_SCURA, "b")
        self._etichetta_timer = "I GENDARMI ENTRERANNO TRA"
        self.testo_timer = testo_ui(self.hud, formatta_tempo(TEMPO_TOTALE), (0, .42), 2.9, ORO_CHIARO, "b", z=-.01)
        self.barra_tempo = quad_ui(self.hud, (0, .364), (.3, .008), ORO)
        # frammenti: nove slot, uno per lettera; il gruppo si rimpicciolisce se la finestra è più stretta della pergamena
        self.hud_frammenti = Entity(parent=self.hud, y=-.425)
        hf = self.hud_frammenti
        quad_ui(hf, (0, 0), (LARGHEZZA_FRAMMENTI, .15), color.white, self.t_pergamena_larga)
        testo_ui(hf, "FRAMMENTI DELLA CHIAVE", (0, .05), .75, BORDEAUX_SCURO, "b", z=-.01)
        self.slot = []
        self.slot_nomi = {}
        for i, e in enumerate(ENIGMI):
            x = (i - (N_ENIGMI - 1) / 2) * PASSO_SLOT
            quad_ui(hf, (x, -.007), (.125, .065), color.white, self.t_slot, z=-.01)
            t = testo_ui(hf, "?", (x, -.005), 1.3, C(150, 124, 90), "b", z=-.02)
            self.slot_nomi[e["id"]] = testo_ui(hf, self._nome_slot(e), (x, -.053), .6, C(110, 84, 60), "i", z=-.02)
            self.slot.append(t)
            if i < N_ENIGMI - 1:
                testo_ui(hf, "+", (x + PASSO_SLOT / 2, -.005), 1.3, BORDEAUX, "b", z=-.02)
        # mirino e suggerimenti
        self.mirino = Entity(parent=self.hud, model=Circle(16), scale=.008, color=C(240, 230, 210, 180))
        self.mirino_anello = Entity(parent=self.hud, model=Circle(24, mode="line", thickness=2), scale=.03,
                                    color=ORO_CHIARO, enabled=False)
        self.sugg_sfondo = quad_ui(self.hud, (0, -.066), (.1, .07), C(8, 6, 8, 150), z=.01)
        self.suggerimento = testo_ui(self.hud, "", (0, -.05), 1.05, ORO_CHIARO, "b")
        self.suggerimento2 = testo_ui(self.hud, "", (0, -.085), .85, PERGAMENA, "i")
        self.toast = testo_ui(self.hud, "", (0, -.3), 1.15, ORO_CHIARO, "b", z=-.02)
        self.toast_sfondo = quad_ui(self.hud, (0, -.3), (.1, .05), C(10, 6, 8, 200), z=-.01)
        self.toast_t0 = -100
        self.aiuto = testo_ui(self.hud, "WASD: muoviti (Maiusc: corri)  ·  Spazio: salta  ·  Ctrl: accovacciati  ·  Mouse: guarda  ·  Clic: esamina\n"
                              "Esc: pausa  ·  M: audio  ·  C: mappa  ·  F11: schermo intero",
                              (0, .345), .65, C(190, 170, 140), "i", (.5, .5))      # in alto a destra, sotto il timer
        self.guida_piano = Entity(parent=ui, enabled=False)
        quad_ui(self.guida_piano, (0, -.265), (1.25, .15), C(8, 6, 8, 180))
        testo_ui(self.guida_piano, "A Do   S Re   D Mi   F Fa   G Sol   H La   J Si   K Do   L Re      (neri: W E T Y U O P)",
                 (0, -.215), 1.0, ORO_CHIARO, "b", z=-.01)
        testo_ui(self.guida_piano, "Suona lo spartito sul leggio  ·  puoi anche cliccare i tasti  ·  Esc per alzarti",
                 (0, -.25), .85, PERGAMENA, "i", z=-.01)
        self.pallini_inno = []
        for k in range(len(INNO)):
            self.pallini_inno.append(quad_ui(self.guida_piano, ((k - (len(INNO) - 1) / 2) * .036, -.3), (.022, .022),
                                             C(90, 80, 70), z=-.01))
        # modalità globo: in alto la domanda e i comandi
        self.guida_globo = Entity(parent=ui, enabled=False)
        quad_ui(self.guida_globo, (0, .29), (1.3, .135), C(8, 6, 8, 185))
        e = ENIGMI_PER_ID["globo"]
        testo_ui(self.guida_globo, e["titolo"].upper(), (0, .34), .85, ORO, "b", z=-.01)
        testo_ui(self.guida_globo, "«" + e["domanda"] + "»", (0, .298), .88, PERGAMENA, "i", wordwrap=90, z=-.01)
        testo_ui(self.guida_globo, "Trascina col mouse o usa A-D / frecce per girarlo  ·  W-S: inclina  ·  rotellina: zoom  ·  "
                 "clic su uno spillo per indicare la città  ·  Esc per uscire", (0, .247), .7, ORO_CHIARO, "b", z=-.01)
        self.pausa = Entity(parent=ui, enabled=False, z=-3)
        quad_ui(self.pausa, (0, 0), (4, 1.2), C(0, 0, 0, 170))
        testo_ui(self.pausa, "IN PAUSA", (0, .06), 3, ORO, "b", z=-.01)
        testo_ui(self.pausa, "Clicca per riprendere  ·  il tempo continua a scorrere!", (0, -.02), 1.1,
                 PERGAMENA, "i", z=-.01)
        # menu Grafica: quattro livelli, con un clic o con i tasti 1-4 (i clic qui non fanno riprendere il gioco)
        testo_ui(self.pausa, "GRAFICA   ·   clic o tasti 1-4", (0, -.11), 1.0, ORO_CHIARO, "b", z=-.01)
        self.pulsanti_grafica = []
        for i, liv in enumerate(LIVELLI_GRAFICA):
            b = pulsante(self.pausa, "%d  %s" % (i + 1, liv["nome"]), ((i - 1.5) * .21, -.175), (.19, .058), False,
                         lambda i=i: self.imposta_grafica(i))
            b.z = -.01
            self.pulsanti_grafica.append(b)
        self.testo_grafica = testo_ui(self.pausa, "", (0, -.235), .85, PERGAMENA, "i", z=-.01)
        self.velo_colore = quad_ui(ui, (0, 0), (4, 1.2), C(255, 240, 200, 0), z=-9)

    def _costruisci_modale(self):
        ui = camera.ui
        self.modale = Entity(parent=ui, enabled=False, z=-4)
        quad_ui(self.modale, (0, 0), (4, 1.2), C(6, 4, 6, 190), z=.2)
        self.pannello = Entity(parent=self.modale)
        p = self.pannello
        quad_ui(p, (0, 0), (1.2, .83), color.white, self.t_pergamena_modale, z=.1)
        self.m_titolo = testo_ui(p, "", (0, .32), 2.4, BORDEAUX_SCURO, "b")
        quad_ui(p, (0, .265), (.44, .003), BORDEAUX)
        quad_ui(p, (0, .265), (.018, .018), BORDEAUX).rotation_z = 45
        self.m_domanda = testo_ui(p, "", (0, .17), 1.3, INCHIOSTRO, "i")
        self.m_frammenti = testo_ui(p, "", (0, .045), 2.2, BORDEAUX, "b")
        self.campo = CampoTesto(p, (0, -.07), .64, self._conferma)
        self.pannello_fascicoli = PannelloFascicoli(p, self)
        self.m_errore = testo_ui(p, "", (0, -.14), 1.05, C(190, 30, 40), "b")
        self.b_conferma = pulsante(p, "Conferma", (-.15, -.27), (.26, .075), True, self._conferma)
        self.b_chiudi = pulsante(p, "Chiudi", (.16, -.27), (.22, .075), False, self.chiudi_modale)
        self.gruppo_domanda = [self.m_domanda, self.m_frammenti, self.campo, self.m_errore, self.b_conferma, self.b_chiudi]
        # ricompensa
        self.r_sottotitolo = testo_ui(p, "Hai trovato un frammento della chiave finale", (0, .215), 1.1, INCHIOSTRO, "i")
        self.r_sigillo = quad_ui(p, (0, .09), (.24, .24), color.white, self.t_sigillo)
        self.r_frammento = testo_ui(p, "", (0, .09), 2.6, ORO_CHIARO, "b", z=-.01)
        self.r_curiosita_t = testo_ui(p, "Curiosità storica", (0, -.04), 1.3, BORDEAUX, "b")
        self.r_curiosita = testo_ui(p, "", (0, -.07), 1.2, INCHIOSTRO, "i", origin=(0, .5))
        self.b_continua = pulsante(p, "Continua", (0, -.29), (.28, .075), True, self.chiudi_modale)
        self.gruppo_ricompensa = [self.r_sottotitolo, self.r_sigillo, self.r_frammento, self.r_curiosita_t,
                                  self.r_curiosita, self.b_continua]
        self.enigma_aperto = None
        self.via_terminale = False        # True: la finestra è il pannello del Quadro di Comando (digita il codice)
        self.fase_modale = None
        self.scuoti = 0.0

    def _costruisci_schermate(self):
        ui = camera.ui
        # introduzione
        self.intro = Entity(parent=ui, enabled=False, z=-6)
        quad_ui(self.intro, (0, 0), (4, 1.2), C(4, 3, 4, 150), z=.3)
        quad_ui(self.intro, (0, .385), (.1, .1), color.white, self.t_coccarda)
        testo_ui(self.intro, "IL SEGRETO DEL CARBONARO", (0, .29), 3.4, ORO, "b")
        quad_ui(self.intro, (0, .235), (.6, .003), ORO_SCURO)
        testo_ui(self.intro, "Torino  ·  4 maggio 1860", (0, .2), 1.4, PERGAMENA, "i")
        quad_ui(self.intro, (0, -.02), (1.3, .38), color.white, self.t_pergamena_larga, z=.1)
        testo_ui(self.intro, TRAMA, (0, -.02), 1.25, INCHIOSTRO, "i", wordwrap=72)
        testo_ui(self.intro, "WASD per muoverti · mouse per guardarti intorno · clic sugli oggetti per esaminarli",
                 (0, -.255), .9, PERGAMENA_SCURA, "i")
        self.b_inizia = pulsante(self.intro, "Inizia la fuga", (0, -.35), (.34, .085), True, self.avvia)
        # vittoria (ogni riga di testo resta dentro la finestra, anche stretta: vedi TestiAdattivi)
        self.vittoria_ui = Entity(parent=ui, enabled=False, z=-7)
        self.vit_testi = TestiAdattivi()
        self.vit_aspetto = None
        libero = lambda a: a * .92
        quad_ui(self.vittoria_ui, (0, 0), (4, 1.2), color.white, self.t_oro, z=.3)
        self.raggi = quad_ui(self.vittoria_ui, (0, .28), (2.6, 2.6), color.white, self.t_raggi, z=.25)
        quad_ui(self.vittoria_ui, (0, .28), (1.2, 1.2), C(255, 220, 140, 120), self.t_alone, z=.2)
        self.vit_strisce = []
        for i, c in enumerate(TRICOLORE):
            self.vit_strisce.append((quad_ui(self.vittoria_ui, (0, .49), (.667, .02), c),
                                     quad_ui(self.vittoria_ui, (0, -.49), (.667, .02), c), i))
        self.vit_testi.aggiungi(testo_ui(self.vittoria_ui, "SEI FUGGITO!", (0, .43), 1.8, PERGAMENA, "b"), 1.8, libero)
        self.v_titolo = quad_ui(self.vittoria_ui, (0, .305), (1.1, .2), color.white, self.t_obbedisco, z=-.02)
        self.vit_testi.aggiungi(testo_ui(self.vittoria_ui, "La parola d'ordine era giusta: l'uscita segreta si apre sui vicoli di Torino.",
                                         (0, .19), 1.1, PERGAMENA, "i"), 1.1, libero)
        self.v_tempo = self.vit_testi.aggiungi(testo_ui(self.vittoria_ui, "", (0, .15), 1.15, ORO_CHIARO, "b"), 1.15, libero)
        self.vit_pergamena = quad_ui(self.vittoria_ui, (0, -.16), (1.3, .56), color.white, self.t_pergamena_larga, z=.1)
        dentro = lambda a: self.vit_pergamena.scale_x - .16
        self.vit_testi.aggiungi(testo_ui(self.vittoria_ui, "Curiosità finale: il telegramma di Garibaldi", (0, .062), 1.7,
                                         BORDEAUX_SCURO, "b", z=-.01), 1.7, dentro)
        self.vit_testi.aggiungi(testo_ui(self.vittoria_ui, CURIOSITA_FINALE, (0, -.19), 1.75, INCHIOSTRO, "i", wordwrap=50, z=-.01),
                                1.75, dentro, .36)
        self.vit_testi.aggiungi(testo_ui(self.vittoria_ui, "R: gioca ancora   ·   Esc: esci   ·   F11: schermo intero", (0, -.465), 1.0,
                                         PERGAMENA_SCURA, "i"), 1.0, libero)
        self.coriandoli = []
        for _ in range(110):
            c = quad_ui(self.vittoria_ui, (random.uniform(-.9, .9), random.uniform(.5, 1.6)),
                        (random.uniform(.006, .012), random.uniform(.012, .02)),
                        random.choice(TRICOLORE + [ORO]), z=-.05)
            c.vel = Vec2(random.uniform(-.05, .05), -random.uniform(.12, .3))
            c.rot = random.uniform(-300, 300)
            self.coriandoli.append(c)
        # game over
        self.sconfitta_ui = Entity(parent=ui, enabled=False, z=-7)
        quad_ui(self.sconfitta_ui, (0, 0), (4, 1.2), color.white, self.t_rosso, z=.3)
        quad_ui(self.sconfitta_ui, (0, .15), (1.4, 1.4), C(255, 60, 40, 70), self.t_alone, z=.2)
        testo_ui(self.sconfitta_ui, "GAME OVER", (0, .3), 1.9, C(255, 190, 180), "b")
        testo_ui(self.sconfitta_ui, "I gendarmi hanno sfondato la porta!", (0, .19), 3.2, C(250, 244, 236), "b")
        quad_ui(self.sconfitta_ui, (0, .125), (.6, .003), C(255, 160, 150))
        testo_ui(self.sconfitta_ui, "Il tempo è scaduto: sei stato arrestato e il messaggio per Garibaldi non partirà mai.",
                 (0, .08), 1.2, C(255, 214, 206), "i")
        self.s_frammenti = testo_ui(self.sconfitta_ui, "", (0, -.02), 1.4, ORO_CHIARO, "b")
        self.s_lista = testo_ui(self.sconfitta_ui, "", (0, -.09), 2.0, PERGAMENA, "b")
        testo_ui(self.sconfitta_ui, "R: riprova   ·   Esc: esci", (0, -.33), 1.2, C(255, 200, 190), "i")
        # vittoria epica del Treno Diplomatico (a tutto schermo, a metà partita)
        self.epica = SchermataEpica(self, self._chiudi_epica)

    # ------------------------------------------------------------------ stato di gioco
    def _reset(self):
        self.risolti = set()
        self.inizio = None
        self.tempo_congelato = None
        self.ultimo_secondo = None
        self.mirato = None
        self.t_chiusura = 0.0
        self.progresso_inno = 0
        if getattr(self, "al_piano", False):
            self.alzati()
        self.al_piano = False
        if getattr(self, "al_globo", False):
            self.esci_dal_globo()
        self.al_globo = False
        self.trascina_globo = False
        self.distanza_globo = GLOBO_DISTANZA[2]
        self.globo_beccheggio.rotation_x = GLOBO_INCLINAZIONE_INIZIALE
        self.pos = Vec3(0, 0, -1.9)
        self.yaw, self.pitch = 0.0, 0.0
        self.passo = 0.0
        self.vy, self.a_terra, self.accosciato = 0.0, True, 0.0
        self.t_evento = 0.0
        self.anta.rotation_y = 0
        self.catene.enabled = True
        self.catene.position = (0, 0, -.2)
        self.catene.rotation = (0, 0, 0)
        self.luce_esterna.color = C(255, 236, 180)
        for oid, radice in self.interattivi.items():
            radice.set_shader_input("emissione", self._emissione_base(oid))
        for e in getattr(self, "etichette_risolte", []):
            destroy(e)
        self.etichette_risolte = []
        for i, t in enumerate(self.slot):
            t.text = "?"
            t.color = C(150, 124, 90)
            t.scale = 1.3
        self.velo_colore.color = C(255, 240, 200, 0)
        self.vittoria_ui.enabled = self.sconfitta_ui.enabled = False
        self.modale.enabled = False
        self.via_terminale = False
        self.enigma_aperto = None
        self.pausa.enabled = False
        # archivio segreto: libreria di nuovo al suo posto, quadro spento, minigioco azzerato
        self.passaggio_in_attesa = False
        self.t_passaggio = 0.0
        self.porta_da_sbloccare = False
        self.stanza_segreta.chiudi_subito()
        self.pannello_fascicoli.azzera()
        self.treno.azzera()
        self.mostra_mappa = True
        self.epica.nascondi()
        camera.fov = 75
        for e in ENIGMI:
            self.slot_nomi[e["id"]].text = self._nome_slot(e)

    @staticmethod
    def _nome_slot(e):
        """Il nome sotto lo slot dell'HUD: '???' per gli enigmi dell'archivio ancora segreto."""
        return e.get("nome_nascosto", e.get("nome_hud", e["nome"]))

    def _mostra_intro(self):
        self.stato = "intro"
        self.intro.enabled = True
        self.hud.enabled = False
        mouse.locked = False
        mouse.visible = True
        self.suoni.ambiente(True)

    def avvia(self):
        self.suoni.suona("click")
        self._reset()
        self.stato = "gioco"
        self.intro.enabled = False
        self.hud.enabled = True
        self.inizio = time.monotonic()
        self._blocca_mouse(True)
        self.mostra_toast("Il tempo scorre: esamina gli oggetti dello studio.")
        self.suoni.ambiente(True)

    def tempo_rimasto(self):
        if self.tempo_congelato is not None:
            return self.tempo_congelato
        if self.inizio is None:
            return float(TEMPO_TOTALE)
        return max(0.0, TEMPO_TOTALE - (time.monotonic() - self.inizio))

    def _blocca_mouse(self, blocca):
        mouse.locked = blocca
        mouse.visible = not blocca

    def mostra_toast(self, msg, col=ORO_CHIARO):
        self.toast.text = msg
        self.toast.color = col
        self.toast_sfondo.scale_x = self.toast.width * self.toast.scale_x + .06
        self.toast_t0 = time.monotonic()

    # ------------------------------------------------------------------ interazione
    def interagisci(self):
        oid = self.mirato
        if oid is None:
            return
        if oid == "porta":
            if len(self.risolti) < len(ENIGMI):
                self.suoni.suona("bloccato")
                self.scuoti = .5
                self.mostra_toast("La porta è sbarrata! Risolvi prima tutti gli enigmi (%d/%d)." % (len(self.risolti), N_ENIGMI),
                                  ROSSO_ALLARME)
            else:
                self.apri_modale(None)
        elif self.treno.clic(oid):                  # scambi, leve e Quadro di Comando della ferrovia
            pass
        elif oid in self.risolti:
            self.mostra_toast("Hai già svelato il segreto: frammento «%s»." % ENIGMI_PER_ID[oid]["frammento"], PERGAMENA)
        elif oid == "globo":
            self.avvicinati_al_globo()
        else:
            self.apri_modale(ENIGMI_PER_ID[oid])

    def _pulisci_mira(self):
        """Toglie l'evidenziazione dall'oggetto mirato e svuota i suggerimenti (prima di cambiare schermata)."""
        if self.mirato and self.mirato not in self.risolti:
            self.interattivi[self.mirato].set_shader_input("emissione", self._emissione_base(self.mirato))
        self.mirato = None
        self.mirino_anello.enabled = self.sugg_sfondo.enabled = False
        self.suggerimento.text = self.suggerimento2.text = ""

    def _emissione_base(self, oid):
        """Bagliore di riposo di un oggetto non risolto: solo la porta, quando è finalmente sbloccata."""
        if oid == "porta" and len(self.risolti) == N_ENIGMI:
            return Vec3(.12, .1, .03)
        if oid == "treno":                       # il Quadro di Comando ha sempre un tenue bagliore d'ottone
            return Vec3(.22, .17, .09)
        return Vec3(0, 0, 0)

    def puo_notificare_vittoria(self):
        """Il treno è arrivato: la schermata epica può aprirsi solo se non c'è altro (una finestra, il piano) davanti."""
        return self.stato == "gioco" and not self.modale.enabled and not self.al_piano and not self.al_globo

    def _treno_vinto(self):
        """Cavour è arrivato a Plombières: il timer si ferma e si apre la Vittoria Epica."""
        if self.stato != "gioco" or "treno" in self.risolti:
            return
        self.tempo_congelato = self.tempo_rimasto()
        enigma = ENIGMI_PER_ID["treno"]
        self._segna_risolto(enigma, porta=False)
        self.porta_da_sbloccare = len(self.risolti) == N_ENIGMI
        self._pulisci_mira()
        self.stato = "vittoria_treno"
        self._blocca_mouse(False)
        self.suoni.suona("vittoria")
        self.epica.mostra(formatta_tempo(self.tempo_congelato), enigma)

    def _chiudi_epica(self):
        """Dalla schermata epica si torna nell'archivio, a piedi; se i frammenti sono tutti, cadono le catene dell'uscita."""
        if self.stato != "vittoria_treno":
            return
        self.suoni.suona("click")
        self.epica.nascondi()
        self.stato = "gioco"
        self._blocca_mouse(True)
        self.t_chiusura = time.monotonic()
        if self.porta_da_sbloccare:
            self.porta_da_sbloccare = False
            invoke(self._sblocca_porta, delay=.8)
            self.mostra_toast("Tutti i frammenti sono tuoi! Le catene della porta sono cadute…")

    @staticmethod
    def _imposta_schermo_intero(si):
        try:
            if bool(window.fullscreen) != si:
                window.fullscreen = si
        except Exception:
            pass

    def _avvia_passaggio(self):
        """Dopo i primi sette enigmi la libreria scorre di lato e rivela l'archivio segreto."""
        if self.stato != "gioco" or self.stanza_segreta.aperta:
            return
        self.passaggio_in_attesa = False
        self.stato = "passaggio"
        self.t_passaggio = 0.0
        self._pulisci_mira()
        self.stanza_segreta.apri()
        self.suoni.suona("scorrimento")
        self.mostra_toast("Un rumore sordo… la libreria si sta spostando!")
        for eid in ("libreria", "treno"):                 # ora si sa come si chiamano gli ultimi due enigmi
            e = ENIGMI_PER_ID[eid]
            self.slot_nomi[eid].text = e.get("nome_hud", e["nome"])

    def _aggiorna_passaggio(self, dt):
        """Piccola scena: lo sguardo si volge verso la libreria che scorre, poi si torna a giocare."""
        self.t_passaggio += dt
        p = self.stanza_segreta.punto_libreria
        d = p - Vec3(self.pos.x, ALTEZZA_OCCHI, self.pos.z)
        yaw_t = math.degrees(math.atan2(d.x, d.z))
        pitch_t = -math.degrees(math.atan2(d.y, math.hypot(d.x, d.z)))
        k = min(1.0, dt * 3.0)
        self.yaw += ((yaw_t - self.yaw + 180) % 360 - 180) * k
        self.pitch += (pitch_t - self.pitch) * k
        self._applica_camera()
        if self.t_passaggio < 2.6:
            tremito = .012
            camera.position += Vec3(random.uniform(-tremito, tremito), random.uniform(-tremito, tremito), 0)
        if self.t_passaggio > 3.8:
            self.stato = "gioco"
            self.mostra_toast("Dietro la libreria si apre un passaggio segreto: entra!")

    def siediti_al_piano(self):
        self.al_piano = True
        self.mirato = None
        self.piano_hitbox.collider = None          # così il mouse "vede" i singoli tasti
        self.guida_piano.enabled = True
        self.progresso_inno = 0
        self._aggiorna_pallini()
        self.toast_t0 = -100
        self._blocca_mouse(False)
        self.suoni.volume_musica(.12)
        self.suoni.suona("click")

    def alzati(self):
        self.al_piano = False
        self.piano_hitbox.collider = "box"
        self.guida_piano.enabled = False
        self.suoni.volume_musica(.38)
        if self.stato == "gioco" and not self.modale.enabled:
            self._blocca_mouse(True)

    def suona_tasto(self, midi):
        tasto = self.tasti.get(midi)
        if tasto is None:
            return
        self.suoni.nota_piano(midi)
        tasto.y = tasto.y0 - .012
        tasto.animate_y(tasto.y0, duration=.18, curve=curve.out_quad)
        self._controlla_inno(midi)

    def _controlla_inno(self, midi):
        """Conta le note giuste dell'inno (vale il nome della nota, in qualunque ottava)."""
        if "inno" in self.risolti:
            return
        attesa = INNO[self.progresso_inno][1]
        if midi % 12 == attesa % 12:
            self.progresso_inno += 1
        else:
            self.progresso_inno = 1 if midi % 12 == INNO[0][1] % 12 else 0
        self._aggiorna_pallini()
        if self.progresso_inno == len(INNO):
            invoke(self._inno_completato, delay=.6)

    def _aggiorna_pallini(self):
        for k, q in enumerate(self.pallini_inno):
            q.color = ORO_CHIARO if k < self.progresso_inno else C(90, 80, 70)

    def _inno_completato(self):
        if self.stato != "gioco" or "inno" in self.risolti:
            return
        self.alzati()
        self.via_terminale = False
        self.enigma_aperto = ENIGMI_PER_ID["inno"]
        self.modale.enabled = True
        self.pannello.x = 0
        self._blocca_mouse(False)
        self._risolvi(ENIGMI_PER_ID["inno"])

    # ------------------------------------------------------------------ modalità globo
    def avvicinati_al_globo(self):
        """Clic sul mappamondo: la visuale si avvicina (come al pianoforte), il mouse si libera e il globo smette di
        girare da solo. Lo si gira trascinando o coi tasti e si clicca lo spillo della città giusta."""
        self._pulisci_mira()
        self.al_globo = True
        self.trascina_globo = False
        self.distanza_globo = GLOBO_DISTANZA[2]
        self.globo_hitbox.collider = None              # così il mouse "vede" gli spilli
        self.globo.set_shader_input("emissione", Vec3(.55, .5, .42))    # da vicino il globo si legge bene
        self.guida_globo.enabled = True
        self.toast_t0 = -100
        self._blocca_mouse(False)
        self.suoni.suona("click")

    def esci_dal_globo(self):
        self.al_globo = False
        self.trascina_globo = False
        self.globo_hitbox.collider = "box"
        self.globo.clearShaderInput("emissione")
        self.guida_globo.enabled = False
        self._evidenzia_spillo(None)
        self.t_chiusura = time.monotonic()              # lo stesso clic non deve riaprire subito il globo
        if self.stato == "gioco" and not self.modale.enabled:
            self._blocca_mouse(True)

    def _occhi_globo(self):
        """Dove sta la visuale nella modalità globo: davanti al globo, a distanza_globo dal centro."""
        return self.globo_base.world_position - self.globo_mob.forward * self.distanza_globo

    def _aggiorna_globo(self, dt):
        camera.position = lerp(camera.position, self._occhi_globo(), min(1, dt * 6))
        # si guarda un poco sopra il centro: il globo scende sotto il riquadro con la domanda
        camera.look_at(self.globo_base.world_position + Vec3(0, self.distanza_globo * .11, 0))
        lento = self.distanza_globo / GLOBO_DISTANZA[2]            # da vicino il globo gira più piano
        giro = held_keys["d"] + held_keys["right arrow"] - held_keys["a"] - held_keys["left arrow"]
        incl = held_keys["w"] + held_keys["up arrow"] - held_keys["s"] - held_keys["down arrow"]
        self.globo.rotation_y -= giro * 90 * dt * lento
        b = self.globo_beccheggio.rotation_x + incl * 60 * dt * lento
        if self.trascina_globo and mouse.left:                     # trascinando, il punto preso segue il mouse
            self.globo.rotation_y -= mouse.velocity[0] * 260 / window.aspect_ratio * lento   # Ursina divide solo la y per l'aspetto
            b += mouse.velocity[1] * 260 * lento
        self.globo_beccheggio.rotation_x = max(-GLOBO_BECCHEGGIO, min(GLOBO_BECCHEGGIO, b))
        h = mouse.hovered_entity
        self._evidenzia_spillo(h if getattr(h, "citta", None) else None)

    def _evidenzia_spillo(self, presa):
        for p in self.spilli:
            sopra = p is presa
            p.testa.color = ORO_CHIARO if sopra else C(196, 28, 40)
            p.testa.scale = .0046 * (1.35 if sopra else 1.0)

    def _clic_globo(self):
        citta = getattr(mouse.hovered_entity, "citta", None)
        if citta is None:
            self.trascina_globo = True                  # clic sul globo (o accanto): si trascina
        elif citta == CITTA_GIUSTA:
            self._globo_risolto()
        else:
            self.suoni.suona("sbagliato")
            self.mostra_toast("Questa è %s… non è la città che cerchi." % citta, ROSSO_ALLARME)

    def _globo_risolto(self):
        """Nizza: si torna in piedi e si apre la ricompensa standard (frammento e curiosità), come per l'inno."""
        if self.stato != "gioco" or "globo" in self.risolti:
            return
        self.esci_dal_globo()
        self.via_terminale = False
        self.enigma_aperto = ENIGMI_PER_ID["globo"]
        self.modale.enabled = True
        self.pannello.x = 0
        self._blocca_mouse(False)
        self._risolvi(ENIGMI_PER_ID["globo"])

    def apri_terminale(self):
        """Il Quadro di Comando è bloccato: qui si digita il codice ricavato dai fascicoli a terra."""
        if "libreria" not in self.risolti and not self.modale.enabled:
            self.apri_modale(ENIGMI_PER_ID["libreria"], via_terminale=True)

    def apri_modale(self, enigma, via_terminale=False):
        self.suoni.suona("click")
        self.enigma_aperto = enigma
        self.via_terminale = via_terminale
        self.fase_modale = "domanda"
        self.modale.enabled = True
        self.pannello.x = 0
        self.pannello.y = -.03
        self.pannello.animate_y(0, duration=.18, curve=curve.out_quad)
        for e in self.gruppo_domanda:
            e.enabled = True
        for e in self.gruppo_ricompensa:
            e.enabled = False
        if enigma is None:
            self.m_titolo.text = "La Porta Uscita"
            self.m_domanda.text = avvolgi("«Inserisci la parola d'ordine unendo i %d frammenti di chiave trovati.»" % N_ENIGMI, 56)
            self.m_frammenti.text = "  ·  ".join(e["frammento"] for e in ENIGMI)
            self.m_titolo.color = BORDEAUX_SCURO
        elif via_terminale:
            self.m_titolo.text = "Quadro di Comando"
            self.m_domanda.text = avvolgi("«" + enigma["istruzione_quadro"] + "»", 56)
            self.m_frammenti.text = ""
            self.m_titolo.color = BORDEAUX_SCURO
        else:
            self.m_titolo.text = enigma["titolo"]
            self.m_domanda.text = avvolgi("«" + enigma["domanda"] + "»", 56)
            self.m_frammenti.text = ""
            self.m_titolo.color = BORDEAUX_SCURO
        self._layout_modale(enigma)
        self.m_errore.text = ""
        self.campo.svuota()
        self.campo.attivo = not self.solo_analisi
        self._blocca_mouse(False)

    @property
    def solo_analisi(self):
        """La finestra dei fascicoli serve solo a studiarli: il codice si digita nel Quadro di Comando."""
        e = self.enigma_aperto
        return bool(e) and e.get("tipo") == "fascicoli" and not self.via_terminale

    def _layout_modale(self, enigma):
        """La finestra 'Analizza fascicoli' ha le schede da numerare e nessun campo di testo; tutto il resto è standard."""
        analisi = self.solo_analisi
        self.pannello_fascicoli.enabled = analisi
        for e in (self.campo, self.m_errore, self.b_conferma):
            e.enabled = not analisi
        self.b_conferma.x, self.b_chiudi.x = (-.15, .16)
        if analisi:
            self.m_domanda.text = avvolgi("«" + enigma["domanda"] + " Il codice va inserito nel Quadro di Comando "
                                          "Ferroviario.»", 66)
            self.m_domanda.y, self.m_domanda.scale = .2, 1.2
            self.pannello_fascicoli.y = -.05                      # le schede scendono: la domanda occupa tre righe
            self.b_chiudi.x = 0
            self.b_chiudi.y = -.27
        else:
            self.m_domanda.y, self.m_domanda.scale = (.17 if enigma else .18), 1.3
            self.campo.y, self.m_errore.y = -.07, -.14
            self.b_conferma.y = self.b_chiudi.y = -.27

    def chiudi_modale(self):
        if not self.modale.enabled or self.fase_modale == "sblocco":     # il lucchetto sta scattando: un attimo
            return
        self.suoni.suona("click")
        self.modale.enabled = False
        self.campo.attivo = False
        self.enigma_aperto = None
        self.via_terminale = False
        self.t_chiusura = time.monotonic()      # evita che lo stesso clic riapra subito l'oggetto
        if self.stato == "gioco":
            self._blocca_mouse(True)
            if self.passaggio_in_attesa:
                invoke(self._avvia_passaggio, delay=.6)

    def _conferma(self):
        if self.fase_modale != "domanda" or not self.modale.enabled:
            return
        risposta = self.campo.valore
        if not normalizza(risposta):
            self._errore("Scrivi una risposta prima di confermare.", suono=False)
            return
        enigma = self.enigma_aperto
        if enigma is None:
            if normalizza(risposta) == PAROLA_ORDINE:
                self.modale.enabled = False
                self.campo.attivo = False
                self.fuga()
            else:
                self._errore("Parola d'ordine errata! I gendarmi colpiscono la porta…")
            return
        if risposta_corretta(enigma, risposta):
            if self.via_terminale:                           # prima scatta il lucchetto del Quadro, poi la ricompensa
                self.fase_modale = "sblocco"
                self.campo.attivo = False
                self.suoni.suona("catene")
                invoke(self._risolvi_dopo_lucchetto, enigma, delay=.8)
            else:
                self._risolvi(enigma)
        elif self.via_terminale:
            self._errore("Codice errato: il Quadro non risponde. I passi dei gendarmi si avvicinano…")
        else:
            self._errore("Risposta errata. I passi dei gendarmi si avvicinano…")

    def _risolvi_dopo_lucchetto(self, enigma):
        if self.stato == "gioco" and self.modale.enabled and self.enigma_aperto is enigma \
                and enigma["id"] not in self.risolti:
            self._risolvi(enigma)

    def _errore(self, msg, suono=True):
        self.m_errore.text = msg
        self.scuoti = .45
        self.campo.svuota()
        if suono:
            self.suoni.suona("sbagliato")

    def _risolvi(self, enigma):
        """Enigma risolto: ricompensa nella finestra e registrazione del frammento."""
        self.suoni.suona("giusto")
        self.fase_modale = "ricompensa"
        self.campo.attivo = False
        for e in self.gruppo_domanda:
            e.enabled = False
        self.pannello_fascicoli.enabled = False
        for e in self.gruppo_ricompensa:
            e.enabled = True
        self.m_titolo.text = "Enigma risolto!"
        self.m_titolo.color = VERDE_SCURO
        self.r_frammento.text = enigma["frammento"]
        self.r_frammento.scale = 2.0 if len(enigma["frammento"]) > 2 else 3.0
        # le curiosità lunghe (Nizza) usano un corpo più piccolo: il testo non deve arrivare al pulsante Continua
        for scala in (1.2, 1.1, 1.0, .92, .85):
            self.r_curiosita.text = avvolgi(enigma["curiosita"], int(58 * 1.2 / scala))
            if self.r_curiosita.height * scala <= .17:        # height = righe x altezza di riga, a scala 1
                break
        self.r_curiosita.scale = scala
        self.r_sigillo.scale = .05
        self.r_sigillo.animate_scale(.24, duration=.35, curve=curve.out_back)
        self._segna_risolto(enigma)

    def _segna_risolto(self, enigma, porta=True):
        """Registra il frammento: HUD, bagliore sull'oggetto, sigillo sospeso e le conseguenze sul resto del gioco.
        Con porta=False il sblocco della porta è rimandato (il Treno lo fa quando si torna nello studio)."""
        eid = enigma["id"]
        self.risolti.add(eid)
        # l'oggetto risolto si illumina di verde-oro e mostra il suo frammento
        radice = self.interattivi[eid]
        radice.set_shader_input("emissione", Vec3(.06, .22, .09))
        i = ENIGMI.index(enigma)
        self.slot[i].text = enigma["frammento"]
        self.slot[i].color = BORDEAUX
        self.slot[i].scale = 1.55
        colli = [c for c in radice.children if getattr(c, "id_oggetto", None)]
        cima = colli[0].world_position + Vec3(0, colli[0].world_scale_y / 2 + .15, 0) if colli else radice.world_position
        if eid == "inno":
            cima += Vec3(0, .32, 0)
        elif eid == "globo":
            cima = self.globo_base.world_position + Vec3(0, RAGGIO_GLOBO + .17, 0)
        elif eid == "camino":                      # sopra la lettera, davanti alle braci
            cima = self.lettera_bruciata.world_position + Vec3(0, .38, 0)
        elif eid == "libreria":
            cima += Vec3(0, .45, 0)
        elif eid == "treno":                       # il sigillo sta sopra la consolle, non in mezzo al plastico
            cima = self.treno.plastico.alone_quadro.world_position + Vec3(0, .45, 0)
        alone = sprite_luminoso(self.mondo, cima, (.5, .5), self.t_alone, C(120, 255, 140, 120))
        sigillo = Entity(parent=self.mondo, model="quad", texture=self.t_sigillo_ok, position=cima, scale=.2,
                         shader=unlit_shader, billboard=True)
        sigillo.setTransparency(TransparencyAttrib.MAlpha)
        sigillo.y0 = cima.y
        alone.y0 = cima.y
        self.etichette_risolte += [sigillo, alone]
        if eid == "libreria":                      # la ricompensa: il Quadro di Comando Ferroviario si accende
            self.treno.imposta_sbloccato(True)
        if eid in ID_FASE1 and all(k in self.risolti for k in ID_FASE1):
            self.passaggio_in_attesa = True        # la libreria si sposterà appena si chiude la finestra
        if not porta:
            return
        if len(self.risolti) == N_ENIGMI:
            invoke(self._sblocca_porta, delay=.8)
            self.mostra_toast("Tutti i frammenti sono tuoi! Le catene della porta sono cadute…")
        elif eid == "libreria":
            self.mostra_toast("Frammento «%s» trovato! (%d/%d)  ·  Il Quadro di Comando si è acceso!"
                              % (enigma["frammento"], len(self.risolti), N_ENIGMI), VERDE_CHIARO)
        else:
            self.mostra_toast("Frammento «%s» trovato! (%d/%d)" % (enigma["frammento"], len(self.risolti), N_ENIGMI), VERDE_CHIARO)

    def _sblocca_porta(self):
        if self.stato != "gioco":
            return
        self.suoni.suona("catene")
        self.catene.animate_position(Vec3(0, -2.2, -.3), duration=.9, curve=curve.in_quad)
        self.catene.animate_rotation(Vec3(0, 0, 25), duration=.9, curve=curve.in_quad)
        invoke(setattr, self.catene, "enabled", False, delay=1.0)
        self.interattivi["porta"].set_shader_input("emissione", Vec3(.12, .1, .03))

    def fuga(self):
        """Parola d'ordine corretta: la porta si apre e si esce verso la luce."""
        self.tempo_congelato = self.tempo_rimasto()
        if self.al_piano:
            self.alzati()
        if self.al_globo:
            self.esci_dal_globo()
        self.stato = "fuga"
        self.t_evento = time.monotonic()
        self._blocca_mouse(False)
        self.hud.enabled = False
        self.suoni.ambiente(True, musica=False)
        self.suoni.suona("porta")
        self.anta.animate_rotation_y(105, duration=2.2, curve=curve.in_out_sine)
        for i in self.indice_luce_porta:
            self.luci[i]["base"] = Vec3(3.0, 2.6, 1.8)

    def vittoria(self):
        self.stato = "vittoria"
        self.t_evento = time.monotonic()
        self.suoni.suona("vittoria")
        self.v_tempo.text = ("Tempo rimasto: %s  ·  Il messaggio raggiungerà Quarto prima che Garibaldi salpi!"
                             % formatta_tempo(self.tempo_congelato or 0))
        self.vittoria_ui.enabled = True
        a = window.aspect_ratio
        self._adatta_vittoria(a)
        w = self.v_titolo.scale_x
        self.v_titolo.scale = (w * 1.4, w * 1.4 * .2 / 1.1)
        self.v_titolo.animate_scale(Vec3(w, w * .2 / 1.1, 1), duration=.8, curve=curve.out_back)
        for c in self.coriandoli:
            c.position = (random.uniform(-a / 2, a / 2), random.uniform(.55, 1.6))
        self.velo_colore.animate_color(C(255, 240, 200, 0), duration=.8)
        try:
            if not window.fullscreen:
                window.fullscreen = True
        except Exception:
            pass

    def _adatta_vittoria(self, a):
        """Schermata finale: strisce, pergamena, titolo e ogni riga di testo dentro la finestra larga 'a'."""
        self.vit_aspetto = a
        for alto, basso, k in self.vit_strisce:
            larg = a / 3 + .002
            alto.scale_x = basso.scale_x = larg
            alto.x = basso.x = -a / 2 + larg * (k + .5)
        self.vit_pergamena.scale_x = min(1.3, a * .94)
        w = min(1.1, a * .9)
        self.v_titolo.scale = (w, w * .2 / 1.1)
        self.vit_testi.adatta(a)

    def irruzione(self):
        """Tempo scaduto: i gendarmi sfondano la porta."""
        self.tempo_congelato = 0.0
        if self.al_piano:
            self.alzati()
        if self.al_globo:
            self.esci_dal_globo()
        self.treno.disattiva()                    # se il tempo scade mentre si gioca al plastico
        self.epica.nascondi()
        camera.fov = 75
        self.passaggio_in_attesa = False
        self.stato = "irruzione"
        self.t_evento = time.monotonic()
        self.modale.enabled = False
        self.campo.attivo = False
        self.hud.enabled = False
        self._blocca_mouse(False)
        self.suoni.ambiente(True, musica=False)
        self.suoni.suona("sconfitta")
        self.catene.enabled = False
        self.anta.animate_rotation_y(100, duration=.25, curve=curve.out_expo)
        self.luce_esterna.color = C(255, 120, 60)
        for i in self.indice_luce_porta:
            self.luci[i]["base"] = Vec3(3.2, 1.2, .5)
        self.velo_colore.color = C(255, 30, 20, 190)
        self.velo_colore.animate_color(C(255, 30, 20, 0), duration=.9)

    def sconfitta(self):
        self.stato = "sconfitta"
        self.s_frammenti.text = "Frammenti della chiave recuperati: %d/%d" % (len(self.risolti), N_ENIGMI)
        self.s_lista.text = "  ".join(e["frammento"] if e["id"] in self.risolti else "?" for e in ENIGMI)
        self.sconfitta_ui.enabled = True

    # ------------------------------------------------------------------ input
    def input(self, key):
        if key == "escape":
            if self.stato in ("vittoria", "sconfitta"):
                application.quit()
            elif self.stato == "vittoria_treno":
                self._chiudi_epica()
            elif self.modale.enabled:
                self.chiudi_modale()
            elif self.al_piano:
                self.alzati()
            elif self.al_globo:
                self.esci_dal_globo()
            elif self.stato == "gioco" and mouse.locked:
                self._blocca_mouse(False)
            return
        if self.stato in ("vittoria", "sconfitta") and key == "r":
            if window.fullscreen and self.stato == "vittoria":
                window.fullscreen = False
            self.avvia()
            return
        if self.stato == "intro" and key in ("enter", "space"):
            self.avvia()
            return
        if self.stato == "vittoria_treno":
            if key in ("enter", "numpad enter", "space"):
                self._chiudi_epica()
            return
        if self.stato != "gioco" or self.modale.enabled:
            return
        if self.pausa.enabled and key in ("1", "2", "3", "4"):      # in pausa i tasti 1-4 scelgono la grafica
            self.imposta_grafica(int(key) - 1)
            return
        if self.al_piano:
            if key in TASTI_PIANO:
                self.suona_tasto(TASTI_PIANO[key])
            elif key == "left mouse down" and getattr(mouse.hovered_entity, "nota", None):
                self.suona_tasto(mouse.hovered_entity.nota)
            return
        if self.al_globo:
            if key == "left mouse down":
                self._clic_globo()
            elif key == "left mouse up":
                self.trascina_globo = False
            elif key in ("scroll up", "scroll down"):
                passo = -.05 if key == "scroll up" else .05
                self.distanza_globo = max(GLOBO_DISTANZA[0], min(GLOBO_DISTANZA[1], self.distanza_globo + passo))
            elif key == "m":
                self.suoni.attivo = not self.suoni.attivo
                self.suoni.ambiente(self.suoni.attivo)
            return
        if key == "p" and self.mirato == "pianoforte" and mouse.locked:
            self.siediti_al_piano()
            return
        if (key in ("1", "2", "3", "4", "5", "6", "7", "enter", "numpad enter", "r") and mouse.locked
                and self.treno.sbloccato and self.stanza_segreta.aperta
                and self.stanza_segreta.nell_archivio(self.pos.x, self.pos.z)):
            if self.treno.tasto(key):                  # comandi da remoto della ferrovia (nell'archivio, a Quadro acceso)
                return
        if key == "m":
            self.suoni.attivo = not self.suoni.attivo
            self.suoni.ambiente(self.suoni.attivo)
            self.mostra_toast("Audio " + ("attivato" if self.suoni.attivo else "disattivato"), PERGAMENA)
        elif key == "c":
            self.mostra_mappa = not self.mostra_mappa
        elif key == "left mouse down":
            if not mouse.locked:
                if not self._su_menu_grafica():          # un clic sui pulsanti della grafica non fa riprendere il gioco
                    self._blocca_mouse(True)
            elif time.monotonic() - self.t_chiusura > .3:
                self.interagisci()

    # ------------------------------------------------------------------ aggiornamento
    def update(self):
        dt = min(time.dt, .05)
        t = time.monotonic()
        self.stanza_segreta.aggiorna(dt)          # libreria che scorre e luci dell'archivio
        self._aggiorna_luci(t)
        if self.stato == "intro":
            a = t * .08
            camera.position = (math.sin(a) * 2.2, 1.9, math.cos(a) * 2.2 - .3)
            camera.look_at(Vec3(0, 1.3, .3))
        elif self.stato in ("gioco", "passaggio", "vittoria_treno"):
            rimasto = self.tempo_rimasto()             # il tempo corre anche nel passaggio e al plastico
            if rimasto <= 0:
                self.irruzione()
            else:
                sec = int(math.ceil(rimasto))
                if sec != self.ultimo_secondo:
                    if self.ultimo_secondo is not None and sec <= 60:
                        self.suoni.suona("tick")
                    self.ultimo_secondo = sec
                self.treno.update(dt)                  # il treno corre anche mentre si cammina o si guarda altro
                if self.stato == "gioco":
                    if self.al_piano:
                        camera.position = lerp(camera.position, self.piano_occhi.world_position, min(1, dt * 6))
                        camera.look_at(self.piano_mira.world_position)
                    elif self.al_globo:
                        self._aggiorna_globo(dt)
                    else:
                        if not self.modale.enabled and mouse.locked:
                            self._muovi(dt)
                        self._applica_camera()
                        self._aggiorna_mira()
                elif self.stato == "passaggio":
                    self._aggiorna_passaggio(dt)
                elif self.stato == "vittoria_treno":
                    self.epica.aggiorna(dt)
        elif self.stato == "fuga":
            e = t - self.t_evento
            u = min(1.0, max(0.0, (e - .6) / 2.4))
            u = u * u * (3 - 2 * u)
            inizio = Vec3(self.pos.x, ALTEZZA_OCCHI, self.pos.z)
            camera.position = lerp(inizio, Vec3(0, 1.55, 3.6), u)
            camera.look_at(Vec3(0, 1.4, 4.5))
            if e > 2.2:
                self.velo_colore.color = C(255, 240, 200, int(255 * min(1.0, (e - 2.2) / .8)))
            if e > 3.1:
                self.vittoria()
        elif self.stato == "irruzione":
            e = t - self.t_evento
            forza = max(0.0, 1 - e / 1.2) * .06
            self._applica_camera()
            camera.position += Vec3(random.uniform(-forza, forza), random.uniform(-forza, forza), 0)
            if e > 1.6:
                self.sconfitta()
        elif self.stato == "vittoria":
            a = window.aspect_ratio
            if abs(a - (self.vit_aspetto or 0)) > 1e-3:      # finestra ridimensionata
                self._adatta_vittoria(a)
            self.raggi.rotation_z += dt * 6
            for c in self.coriandoli:
                c.x += c.vel.x * dt
                c.y += c.vel.y * dt
                c.rotation_z += c.rot * dt
                if c.y < -.6:
                    c.y = random.uniform(.55, .7)
                    c.x = random.uniform(-a / 2, a / 2)
        self._aggiorna_hud(t, dt)
        self._aggiorna_ambiente(t, dt)

    def _muovi(self, dt):
        self.yaw += mouse.velocity[0] * SENSIBILITA_MOUSE
        self.pitch = max(-80, min(80, self.pitch - mouse.velocity[1] * SENSIBILITA_MOUSE))
        avanti = held_keys["w"] + held_keys["up arrow"] - held_keys["s"] - held_keys["down arrow"]
        lato = held_keys["d"] + held_keys["right arrow"] - held_keys["a"] - held_keys["left arrow"]
        self._verticale(dt)
        if not avanti and not lato:
            return
        ry = math.radians(self.yaw)
        fwd = Vec3(math.sin(ry), 0, math.cos(ry))
        dx = Vec3(math.cos(ry), 0, -math.sin(ry))
        mov = (fwd * avanti + dx * lato)
        if mov.length() > 0:
            corsa = 1.8 if held_keys["shift"] or held_keys["left shift"] else 1.0
            if self.stanza_segreta.nell_archivio(self.pos.x, self.pos.z):
                corsa *= BONUS_VELOCITA_ARCHIVIO
            mov = mov.normalized() * VELOCITA * dt * corsa * (1 - .5 * self.accosciato)
        for asse in ("x", "z"):
            nuovo = Vec3(self.pos)
            setattr(nuovo, asse, getattr(nuovo, asse) + getattr(mov, asse))
            if self._libero(nuovo.x, nuovo.z):
                self.pos = nuovo
        self.passo += dt * 9

    def _altezza_corpo(self, acc=None):
        acc = self.accosciato if acc is None else acc
        return ALTEZZA_OCCHI + .12 - acc * (ALTEZZA_OCCHI * .42)

    def _suolo(self, x, z, y):
        """Quota del piano su cui si sta in piedi in (x, z): il pavimento o il solido più alto che si raggiunge salendo."""
        r, h = .12, 0.0
        for (x0, x1, z0, z1, y0, y1) in self.solidi:
            if x0 - r < x < x1 + r and z0 - r < z < z1 + r and y1 <= y + SCALINO and y1 > h:
                h = y1
        return h

    def _ostruito(self, x, z, y, alt, raggio=.28):
        """Un solido (ponte, parapetto, pilone...) sbarra il passo: troppo alto da scavalcare e dentro l'altezza del corpo."""
        for (x0, x1, z0, z1, y0, y1) in self.solidi:
            if x0 - raggio < x < x1 + raggio and z0 - raggio < z < z1 + raggio and y1 > y + SCALINO and y0 < y + alt:
                return True
        return False

    def _verticale(self, dt):
        """Salto, accovacciarsi e gravità."""
        vuole = held_keys["left control"] or held_keys["control"] or held_keys["x"]
        if vuole:
            self.accosciato = min(1.0, self.accosciato + dt * 7)
        else:                                  # ci si rialza solo se sopra la testa c'è spazio (sotto il ponte si resta giù)
            nuovo = max(0.0, self.accosciato - dt * 7)
            if not self._ostruito(self.pos.x, self.pos.z, self.pos.y, self._altezza_corpo(nuovo), .2):
                self.accosciato = nuovo
        suolo = self._suolo(self.pos.x, self.pos.z, self.pos.y)
        if held_keys["space"] and self.a_terra and not vuole:
            self.vy = SALTO
            self.a_terra = False
        self.vy -= GRAVITA * dt
        y = self.pos.y + self.vy * dt
        if self.vy > 0:                        # testata contro la faccia inferiore di un impalcato
            testa0, testa1 = self.pos.y + self._altezza_corpo(), y + self._altezza_corpo()
            for (x0, x1, z0, z1, y0, y1) in self.solidi:
                if x0 - .2 < self.pos.x < x1 + .2 and z0 - .2 < self.pos.z < z1 + .2 and testa0 <= y0 < testa1:
                    self.vy, y = 0.0, self.pos.y
                    break
        if y <= suolo:
            y, self.vy, self.a_terra = suolo, 0.0, True
        else:
            self.a_terra = False
        self.pos = Vec3(self.pos.x, y, self.pos.z)

    def _libero(self, x, z, raggio=.28):
        dentro = -3.72 < x < 3.72 and -3.5 < z < 3.55            # lo studio
        if not dentro:                                           # oppure il varco e l'archivio, a libreria spostata
            dentro = any(x0 < x < x1 and z0 < z < z1 for (x0, z0, x1, z1) in self.stanza_segreta.zone_agibili())
        if not dentro:
            return False
        for (x0, z0, x1, z1) in self.ostacoli:
            if x0 - raggio < x < x1 + raggio and z0 - raggio < z < z1 + raggio:
                return False
        if self.solidi and self._ostruito(x, z, self.pos.y, self._altezza_corpo(), raggio):
            return False
        return True

    def _applica_camera(self):
        occhi = ALTEZZA_OCCHI * (1 - .42 * self.accosciato)
        camera.position = Vec3(self.pos.x, self.pos.y + occhi + math.sin(self.passo) * .025, self.pos.z)
        camera.rotation = (self.pitch, self.yaw, 0)

    def _aggiorna_mira(self):
        mirato = None
        if not self.modale.enabled and not self.pausa.enabled:        # in pausa il mirino non evidenzia nulla
            lontano = self.stanza_segreta.aperta and self.stanza_segreta.nell_archivio(self.pos.x, self.pos.z)
            hit = raycast(camera.world_position, camera.forward,
                          distance=DISTANZA_INTERAZIONE_ARCHIVIO if lontano else DISTANZA_INTERAZIONE)
            if hit.hit:
                mirato = getattr(hit.entity, "id_oggetto", None)
        if mirato != self.mirato:
            if self.mirato and self.mirato not in self.risolti:
                self.interattivi[self.mirato].set_shader_input("emissione", self._emissione_base(self.mirato))
            if mirato and mirato not in self.risolti:
                self.interattivi[mirato].set_shader_input("emissione", self._emissione_base(mirato) + Vec3(.22, .17, .08))
            self.mirato = mirato
        self.mirino_anello.enabled = mirato is not None
        self.sugg_sfondo.enabled = mirato is not None
        if mirato is None:
            self.suggerimento.text = self.suggerimento2.text = ""
        elif mirato == "porta":
            self.suggerimento.text = "Porta Uscita"
            self.suggerimento2.text = ("Clic per inserire la parola d'ordine" if len(self.risolti) == N_ENIGMI else
                                       "Sbarrata  ·  %d/%d frammenti" % (len(self.risolti), N_ENIGMI))
        elif self.treno.suggerimento(mirato):
            self.suggerimento.text, self.suggerimento2.text = self.treno.suggerimento(mirato)
        else:
            e = ENIGMI_PER_ID[mirato]
            self.suggerimento.text = e["nome"]
            self.suggerimento2.text = ("Risolto  ·  frammento «%s»" % e["frammento"] if mirato in self.risolti else
                                       "Clic per analizzare  ·  il codice va nel Quadro" if mirato == "libreria" else
                                       "Clic per avvicinarti e girarlo" if mirato == "globo" else
                                       "Clic per esaminare la lettera tra le braci" if mirato == "camino" else
                                       "Clic per esaminare")
            if mirato == "pianoforte":
                self.suggerimento2.text += ("   ·   P: suona" if "inno" in self.risolti else
                                            "   ·   P: siediti e suona lo spartito")
        if mirato is not None:
            self.sugg_sfondo.scale_x = max(self.suggerimento.width * self.suggerimento.scale_x,
                                           self.suggerimento2.width * self.suggerimento2.scale_x) + .05

    def _luci_attive(self, cp):
        """Le luci che contano per questo fotogramma: tutte a Max, altrimenti solo le più vicine alla telecamera."""
        n = min(self.grafica["luci"], N_LUCI)
        if n >= len(self.luci):
            return self.luci                                  # Max: tutte, nell'ordine originale
        fuori = cp.z < -4.1                                   # la telecamera è nell'archivio (z < -4,1) o nello studio

        def costo(l):
            p = l["pos"]
            d2 = (p.x - cp.x) ** 2 + (p.y - cp.y) ** 2 + (p.z - cp.z) ** 2
            if (p.z < -4.1) != fuori:                         # l'altra stanza: la luce non passa, conta meno
                d2 += 400.0
            if l["base"].x + l["base"].y + l["base"].z < .01:  # spenta (archivio ancora chiuso): in fondo alla lista
                d2 += 1e6
            return d2

        vicine = sorted(self.luci, key=costo)[:n]
        return [l for l in vicine if l["base"].x + l["base"].y + l["base"].z >= .01]

    def _aggiorna_luci(self, t):
        cp = camera.world_position
        attive = self._luci_attive(cp)
        for i, l in enumerate(attive):
            k = 1 + l["tremolio"] * (.5 * math.sin(t * 9.1 + l["fase"]) + .3 * math.sin(t * 23.7 + l["fase"] * 2)
                                     + .2 * math.sin(t * 5.3 + l["fase"] * 3))
            c = l["base"] * k
            p = l["pos"]
            self.luci_pos[i] = LVecBase3f(p.x, p.y, p.z)
            self.luci_col[i] = LVecBase3f(c.x, c.y, c.z)
        scene.set_shader_input("n_luci", len(attive))
        scene.set_shader_input("cam_pos", cp)
        self._controlla_filtro()
        k = 1 + 3.0 * self.stanza_segreta.luminosita            # la sala dell'archivio è grande: la nebbia comincia più lontano
        scene.set_shader_input("nebbia", Vec2(6 * k, 14 * k))

    def _aggiorna_ambiente(self, t, dt):
        for f in self.fiamme:
            spr, alone, s0, a0, fase = f
            k = 1 + .12 * math.sin(t * 13 + fase) + .08 * math.sin(t * 29 + fase)
            spr.scale = Vec3(s0.x * (2 - k), s0.y * k, 1)
            if alone is not None:
                alone.scale = a0 * (0.94 + .08 * math.sin(t * 7 + fase))
        for g in self.polvere:
            if not g.enabled:                       # a grafica bassa i granelli di polvere sono meno
                continue
            g.position += g.vel * dt
            if abs(g.x) > 3.8 or abs(g.z) > 3.8 or g.y < .1 or g.y > 3.2:
                g.position = (random.uniform(-3.5, 3.5), random.uniform(.3, 3), random.uniform(-3.5, 3.5))
        rimasto = self.tempo_rimasto()
        # le lancette dell'orologio da camino segnano il tempo che resta
        self.lancette[0].rotation_z = -(rimasto / 3600) * 360
        self.lancette[1].rotation_z = -(rimasto % 60) * 6
        if not self.al_globo:                       # gira da solo, tranne quando lo si gira a mano
            self.globo.rotation_y += dt * 12
        self.suoni.volume_camino((camera.world_position - Vec3(0, 1, -3.6)).length())
        for k, e in enumerate(self.etichette_risolte):
            e.y = e.y0 + .04 * math.sin(t * 2 + k // 2)

    def _aggiorna_hud(self, t, dt):
        a = window.aspect_ratio
        self.vignetta.scale_x = a * 1.06
        self.coccarda.x = -a / 2 + .06
        self.titolo.x = self.sottotitolo.x = -a / 2 + .11
        for e in (self.pannello_timer, self.etichetta_timer, self.testo_timer, self.barra_tempo):
            e.x = a / 2 - .18
        self.aiuto.x = a / 2 - .02
        k = min(1.0, (a - .04) / LARGHEZZA_FRAMMENTI)          # finestra stretta: la pergamena dei frammenti si riduce
        self.hud_frammenti.scale = k
        self.hud_frammenti.y = -.5 + .075 * k
        # la pianta della ferrovia compare nell'archivio (C: nascondi / mostra)
        in_archivio = (self.stato == "gioco" and self.stanza_segreta.aperta and not self.modale.enabled and not self.al_piano
                       and not self.al_globo and self.stanza_segreta.nell_archivio(self.pos.x, self.pos.z))
        mm = self.treno.minimappa
        mm.enabled = in_archivio and self.mostra_mappa
        if mm.enabled:
            mm.posiziona(a)
            mm.aggiorna(self.pos, self.yaw)
        etichetta = "TEMPO FERMATO" if self.tempo_congelato is not None else "I GENDARMI ENTRERANNO TRA"
        if etichetta != self._etichetta_timer:
            self._etichetta_timer = etichetta
            self.etichetta_timer.text = etichetta
        self.sottotitolo.text = "Torino, 4 maggio 1860  ·  Studio segreto della Carboneria  ·  Enigmi risolti: %d/%d" % (len(self.risolti), N_ENIGMI)
        rimasto = self.tempo_rimasto()
        self.testo_timer.text = formatta_tempo(rimasto)
        frac = rimasto / TEMPO_TOTALE
        self.barra_tempo.scale_x = .28 * frac
        self.barra_tempo.x = a / 2 - .18 - .14 * (1 - frac)
        if rimasto <= 60:
            self.testo_timer.color = lerp(ROSSO_ALLARME, C(255, 200, 190), (math.sin(t * 8) + 1) / 4)
            self.barra_tempo.color = ROSSO_ALLARME
        elif rimasto <= 300:
            self.testo_timer.color = C(236, 140, 60)
            self.barra_tempo.color = C(236, 140, 60)
        else:
            self.testo_timer.color = ORO_CHIARO
            self.barra_tempo.color = ORO
        eta = t - self.toast_t0
        vis = eta < 4.0
        self.toast.enabled = self.toast_sfondo.enabled = vis
        if vis:
            alpha = 1.0 if eta < 3.2 else (4.0 - eta) / .8
            self.toast.alpha = alpha
            self.toast_sfondo.alpha = .8 * alpha
        ravvicinato = self.al_piano or self.al_globo
        self.aiuto.enabled = not ravvicinato                    # al piano e al globo valgono i comandi della loro guida
        self.pausa.enabled = self.stato == "gioco" and not self.modale.enabled and not mouse.locked and not ravvicinato
        self.mirino.enabled = self.stato == "gioco" and not self.modale.enabled and not ravvicinato
        if ravvicinato:
            self.mirino_anello.enabled = self.sugg_sfondo.enabled = False
            self.suggerimento.text = self.suggerimento2.text = ""
        if self.scuoti > 0:
            self.scuoti = max(0.0, self.scuoti - dt)
            dx = math.sin(self.scuoti * 70) * .02 * (self.scuoti / .45)
            self.pannello.x = dx if self.modale.enabled else 0
            if not self.modale.enabled:
                self.anta.rotation_y = dx * 60 if self.stato == "gioco" and len(self.risolti) < N_ENIGMI else self.anta.rotation_y


def main():
    app = Ursina(title="Il Segreto del Carbonaro", borderless=False, development_mode=False, vsync=True)
    window.color = color.black
    gioco = Gioco()
    try:
        app.run()
    finally:
        gioco.suoni.pulisci()


if __name__ == "__main__":
    main()
