#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IL SEGRETO DEL CARBONARO
Escape room "punta e clicca" ambientata a Torino, 4 maggio 1860.

Installazione:   pip install pygame
Avvio:           python il_segreto_del_carbonaro.py

Tutta la grafica e tutti i suoni sono generati via codice:
nessuna immagine, font o file audio esterno.

Comandi:  clic = esamina un oggetto · Invio = conferma · Esc = chiudi
          M = audio on/off · F11 = schermo intero · R = rigioca (a fine partita)
          Mappamondo: trascina (o A-D / frecce) per girarlo · W-S inclina · rotellina = zoom · clic su uno spillo

La parola d'ordine OBBEDISCO è divisa in sei frammenti (OB · B · E · DI · S · CO), uno per ciascuno
dei sei oggetti dello studio: pianoforte, mappa, mappamondo, camino, ritratto e scrivania.
"""

import math
import operator
import random
import re
import sys
import time
import unicodedata
from array import array
from functools import lru_cache

import pygame

# --------------------------------------------------------------------------
# Configurazione
# --------------------------------------------------------------------------
W, H = 1280, 800                 # risoluzione logica (scalata alla finestra)
FPS = 60
TEMPO_TOTALE = 25 * 60           # 25:00
MAX_INPUT = 32

# Palette "Dark Academia / Risorgimento"
ANTRACITE = (22, 22, 26)
ANTRACITE_2 = (34, 33, 39)
ANTRACITE_3 = (48, 46, 54)
BORDEAUX = (120, 24, 40)
BORDEAUX_SCURO = (68, 12, 24)
BORDEAUX_CHIARO = (160, 40, 58)
LEGNO = (82, 52, 32)
LEGNO_SCURO = (44, 27, 17)
LEGNO_CHIARO = (122, 82, 50)
ORO = (212, 175, 55)
ORO_CHIARO = (244, 218, 138)
ORO_SCURO = (140, 108, 30)
PERGAMENA = (238, 225, 194)
PERGAMENA_SCURA = (206, 186, 146)
INCHIOSTRO = (44, 30, 22)
VERDE = (40, 110, 66)
VERDE_SCURO = (16, 52, 32)
VERDE_CHIARO = (96, 176, 112)
ROSSO = (206, 43, 55)
ROSSO_ALLARME = (232, 64, 52)
BIANCO = (245, 242, 232)
TRICOLORE = [(0, 146, 70), (244, 245, 240), (206, 43, 55)]

SERIF = ("georgia,palatinolinotype,bookantiqua,garamond,cambria,"
         "timesnewroman,dejavuserif,liberationserif,freeserif,serif")

# --------------------------------------------------------------------------
# Contenuti del gioco
# --------------------------------------------------------------------------
ENIGMI = [
    {
        "id": "pianoforte",
        "nome": "Pianoforte",
        "titolo": "Il Pianoforte",
        "domanda": ("I patrioti scrivono sui muri un nome per ingannare gli "
                    "austriaci, lodando un compositore. Ma è l'acronimo del "
                    "futuro Re d'Italia. Chi è il musicista?"),
        "soluzioni": ["verdi", "giuseppe verdi", "viva verdi"],
        "frammento": "OB",
        "curiosita": ("La polizia austriaca mandava ogni notte agenti a cancellare le scritte "
                      "«Viva V.E.R.D.I.», ma il giorno dopo ricomparivano: non si poteva "
                      "vietare di inneggiare a un compositore amatissimo."),
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
        "titolo": "Il Mappamondo",
        "domanda": ("Cavour ha fatto una rinuncia dolorosa per l'alleanza francese: ha ceduto "
                    "la Savoia e quale città? Gira il mappamondo e indicala."),
        "soluzioni": [],                # niente campo di testo: si clicca lo spillo della città giusta
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
                    "(A diventa D, B diventa E, C diventa F…). Decifrala: come si chiamavano tra loro i "
                    "carbonari? EXRQL FXJLQL"),
        "soluzioni": ["buoni cugini", "i buoni cugini", "cugini"],
        "frammento": "DI",
        "curiosita": ("I carbonari si chiamavano tra loro \"buoni cugini\" e chiamavano \"pagani\" chi "
                      "non era affiliato. Le loro cellule si dicevano \"vendite\", come le botteghe dei "
                      "carbonai da cui la società prese nome e simboli."),
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
        "frammento": "CO",
        "curiosita": ("Cavour, nato a Torino nel 1810, era di madrelingua francese e scrisse in "
                      "francese gran parte della sua corrispondenza privata."),
    },
]

PAROLA_ORDINE = "obbedisco"
assert "".join(e["frammento"] for e in ENIGMI) == PAROLA_ORDINE.upper(), "i frammenti non formano la parola d'ordine"
N_ENIGMI = len(ENIGMI)

TRAMA = ("4 maggio 1860. Sei un corriere della Carboneria, nascosto nello "
         "studio segreto di un patriota torinese. Porti un messaggio che deve "
         "raggiungere Garibaldi prima che salpi da Quarto. Ma qualcuno ha "
         "parlato: i gendarmi hanno circondato il palazzo e stanno forzando "
         "l'ingresso.\n"
         "Il patriota ha nascosto la parola d'ordine che apre l'uscita "
         "segreta in sei frammenti, custoditi dagli oggetti della stanza. "
         "Hai 25 minuti per decifrare i codici, ricomporre la chiave e fuggire.")

CURIOSITA_FINALE = ("Sei anni dopo, il 9 agosto 1866, durante la Terza guerra "
                    "d'indipendenza, Garibaldi aveva appena battuto gli "
                    "austriaci a Bezzecca e marciava verso Trento. Dal "
                    "generale La Marmora arrivò l'ordine di sgomberare il "
                    "Trentino: erano in corso le trattative di armistizio con "
                    "l'Austria. Garibaldi, a malincuore, rispose con un "
                    "telegramma di una sola parola, entrato nella storia: "
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


def mescola(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def schiarisci(c, k):
    return mescola(c, (255, 255, 255), k)


def scurisci(c, k):
    return mescola(c, (0, 0, 0), k)


_FONT_CACHE = {}


def font(size, bold=False, italic=False):
    key = (size, bold, italic)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.SysFont(SERIF, size, bold=bold, italic=italic)
    return _FONT_CACHE[key]


def testo(surf, txt, fnt, col, pos, anchor="center", ombra=True, alpha=255):
    img = fnt.render(txt, True, col)
    rect = img.get_rect(**{anchor: pos})
    if ombra:
        sh = fnt.render(txt, True, (0, 0, 0))
        sh.set_alpha(int(alpha * 0.55))
        surf.blit(sh, rect.move(2, 2))
    if alpha < 255:
        img.set_alpha(int(alpha))
    surf.blit(img, rect)
    return rect


def a_capo(txt, fnt, larghezza):
    righe = []
    for paragrafo in txt.split("\n"):
        riga = ""
        for parola in paragrafo.split(" "):
            prova = (riga + " " + parola).strip()
            if fnt.size(prova)[0] <= larghezza or not riga:
                riga = prova
            else:
                righe.append(riga)
                riga = parola
        righe.append(riga)
    return righe


def paragrafo(surf, txt, fnt, col, x_centro, y, larghezza, interlinea=1.3,
              ombra=False, alpha=255):
    passo = int(fnt.get_linesize() * interlinea)
    for riga in a_capo(txt, fnt, larghezza):
        testo(surf, riga, fnt, col, (x_centro, y), "midtop", ombra, alpha)
        y += passo
    return y


def gradiente(w, h, alto, basso):
    s = pygame.Surface((w, h))
    for y in range(h):
        pygame.draw.line(s, mescola(alto, basso, y / max(1, h - 1)), (0, y), (w, y))
    return s


def maschera(surf, disegna_forma):
    """Ritaglia 'surf' con la forma disegnata da disegna_forma(mask)."""
    w, h = surf.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(surf, (0, 0))
    m = pygame.Surface((w, h), pygame.SRCALPHA)
    disegna_forma(m)
    out.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return out


def arrotonda(surf, raggio):
    w, h = surf.get_size()
    return maschera(surf, lambda m: pygame.draw.rect(
        m, (255, 255, 255, 255), (0, 0, w, h), border_radius=raggio))


@lru_cache(maxsize=128)
def pannello(w, h, alto, basso, raggio):
    """Gradiente verticale con angoli arrotondati (in cache: si usa a ogni frame)."""
    return arrotonda(gradiente(w, h, alto, basso), raggio)


@lru_cache(maxsize=512)
def _bagliore(w, h, col, raggio, forza, strati):
    g = pygame.Surface((w + strati * 8, h + strati * 8), pygame.SRCALPHA)
    for i in range(strati, 0, -1):
        a = int(forza * (1 - i / (strati + 1)) / 2.2)
        r = pygame.Rect(0, 0, w + i * 8, h + i * 8)
        r.center = g.get_rect().center
        pygame.draw.rect(g, col + (a,), r, border_radius=raggio + i * 4)
    return g


def bagliore(surf, rect, col, raggio=16, forza=90, strati=7):
    g = _bagliore(rect.w, rect.h, col, raggio, max(0, int(forza) // 6 * 6), strati)
    surf.blit(g, g.get_rect(center=rect.center))


def cerchio_alpha(surf, col, centro, raggio, alpha):
    if raggio <= 0:
        return
    g = pygame.Surface((raggio * 2, raggio * 2), pygame.SRCALPHA)
    pygame.draw.circle(g, col + (int(alpha),), (raggio, raggio), raggio)
    surf.blit(g, (centro[0] - raggio, centro[1] - raggio))


def alone(col, raggio, forza=120):
    """Cerchio sfumato (luce morbida)."""
    return _alone(col, int(raggio), max(0, int(forza) // 4 * 4))


@lru_cache(maxsize=512)
def _alone(col, raggio, forza):
    g = pygame.Surface((raggio * 2, raggio * 2), pygame.SRCALPHA)
    for r in range(raggio, 0, -2):
        a = int(forza * (1 - r / raggio) ** 1.6)
        pygame.draw.circle(g, col + (a,), (raggio, raggio), r)
    return g


def coccarda(surf, centro, r):
    pygame.draw.circle(surf, ORO, centro, r + 3)
    pygame.draw.circle(surf, TRICOLORE[2], centro, r)
    pygame.draw.circle(surf, TRICOLORE[1], centro, int(r * 0.68))
    pygame.draw.circle(surf, TRICOLORE[0], centro, int(r * 0.36))
    for i in range(16):
        a = i * math.pi / 8
        p1 = (centro[0] + math.cos(a) * r * 0.4, centro[1] + math.sin(a) * r * 0.4)
        p2 = (centro[0] + math.cos(a) * r, centro[1] + math.sin(a) * r)
        pygame.draw.line(surf, scurisci(TRICOLORE[2], 0.25) if i % 2 else (220, 220, 214), p1, p2, 1)
    pygame.draw.circle(surf, TRICOLORE[0], centro, int(r * 0.36))


def fregio(surf, centro, larghezza, col):
    """Linea ornamentale con rombo centrale."""
    cx, cy = centro
    pygame.draw.line(surf, col, (cx - larghezza // 2, cy), (cx - 12, cy), 1)
    pygame.draw.line(surf, col, (cx + 12, cy), (cx + larghezza // 2, cy), 1)
    pygame.draw.polygon(surf, col, [(cx, cy - 6), (cx + 8, cy), (cx, cy + 6), (cx - 8, cy)])
    for s in (-1, 1):
        pygame.draw.circle(surf, col, (cx + s * (larghezza // 2 + 4), cy), 2)


def angoli_ornati(surf, rect, col, l=18):
    for (x, y, dx, dy) in ((rect.left, rect.top, 1, 1), (rect.right - 1, rect.top, -1, 1),
                           (rect.left, rect.bottom - 1, 1, -1), (rect.right - 1, rect.bottom - 1, -1, -1)):
        pygame.draw.line(surf, col, (x, y), (x + dx * l, y), 2)
        pygame.draw.line(surf, col, (x, y), (x, y + dy * l), 2)
        pygame.draw.circle(surf, col, (x + dx * 6, y + dy * 6), 2)


def ceralacca(surf, centro, r, testo_sigillo=None, fnt=None, spunta=False):
    cx, cy = centro
    pts = []
    for i in range(18):
        a = i * math.tau / 18
        rr = r * (1.0 + 0.08 * math.sin(i * 2.7))
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(surf, BORDEAUX_SCURO, pts)
    pygame.draw.circle(surf, BORDEAUX, centro, int(r * 0.86))
    pygame.draw.circle(surf, BORDEAUX_CHIARO, (cx - r // 4, cy - r // 4), max(2, r // 5))
    pygame.draw.circle(surf, scurisci(BORDEAUX, 0.2), centro, int(r * 0.7), 2)
    if testo_sigillo and fnt:
        testo(surf, testo_sigillo, fnt, ORO_CHIARO, centro)
    if spunta:
        pygame.draw.lines(surf, ORO_CHIARO, False,
                          [(cx - r * 0.38, cy), (cx - r * 0.08, cy + r * 0.32), (cx + r * 0.42, cy - r * 0.32)],
                          max(2, r // 6))


# --------------------------------------------------------------------------
# Audio sintetizzato (nessun file esterno)
# --------------------------------------------------------------------------
class Suoni:
    def __init__(self):
        self.attivo = True
        self.sfx = {}
        try:
            init = pygame.mixer.get_init()
            if not init or init[1] != -16:
                return
            self.freq, self.canali = init[0], init[2]
            rnd = random.Random(1860)
            tau = math.tau

            def note(seq, dur, timbro=1.0, decad=5.0):
                def f(t):
                    v = 0.0
                    for inizio, fr, vol in seq:
                        if t >= inizio:
                            dt = t - inizio
                            env = math.exp(-dt * decad) * min(1.0, dt * 200)
                            v += vol * env * (math.sin(tau * fr * dt)
                                              + timbro * 0.35 * math.sin(tau * 2 * fr * dt)
                                              + timbro * 0.15 * math.sin(tau * 3 * fr * dt))
                    return v
                return self._crea(dur, f)

            self.sfx["click"] = self._crea(0.06, lambda t: 0.5 * math.sin(tau * 880 * t) * math.exp(-t * 70))
            self.sfx["giusto"] = note([(0.00, 523.25, 0.3), (0.11, 659.25, 0.3),
                                       (0.22, 783.99, 0.3), (0.33, 1046.5, 0.35)], 1.2)
            self.sfx["sbagliato"] = self._crea(0.38, lambda t: math.exp(-t * 7) * (
                0.35 * (1 if math.sin(tau * 98 * t) > 0 else -1) + 0.3 * math.sin(tau * 104 * t)))
            self.sfx["bloccato"] = self._crea(0.45, lambda t: (
                (rnd.random() * 2 - 1) * 0.6 * math.exp(-t * 30)
                + 0.45 * math.sin(tau * 196 * t) * math.exp(-t * 9)
                + 0.3 * math.sin(tau * 587 * t) * math.exp(-t * 14)
                + 0.2 * math.sin(tau * 1244 * t) * math.exp(-t * 18)))
            self.sfx["tick"] = self._crea(0.05, lambda t: 0.5 * math.sin(tau * 1760 * t) * math.exp(-t * 110))
            self.sfx["vittoria"] = note([(0.00, 392.0, 0.25), (0.16, 523.25, 0.25), (0.32, 659.25, 0.25),
                                         (0.48, 783.99, 0.28), (0.72, 1046.5, 0.3), (0.72, 523.25, 0.2),
                                         (0.72, 659.25, 0.18)], 2.6, decad=1.8)
            self.sfx["sconfitta"] = self._crea(1.8, lambda t: (
                (rnd.random() * 2 - 1) * 0.9 * math.exp(-t * 7)
                + 0.5 * math.sin(tau * (70 - 18 * t) * t) * math.exp(-t * 1.5)
                + (0.25 * math.sin(tau * 233 * (t - 0.5)) * math.exp(-(t - 0.5) * 3) if t > 0.5 else 0)
                + (0.25 * math.sin(tau * 220 * (t - 0.9)) * math.exp(-(t - 0.9) * 2) if t > 0.9 else 0)))
        except Exception:
            self.sfx = {}

    def _crea(self, durata, funzione):
        n = int(self.freq * durata)
        dati = array("h")
        for i in range(n):
            v = funzione(i / self.freq)
            v = max(-1.0, min(1.0, v)) * 0.55
            fade = min(1.0, (n - i) / (self.freq * 0.01))   # evita "click" finali
            campione = int(v * fade * 32767)
            dati.extend([campione] * self.canali)
        return pygame.mixer.Sound(buffer=dati.tobytes())

    def suona(self, nome):
        if self.attivo and nome in self.sfx:
            try:
                self.sfx[nome].play()
            except Exception:
                pass


# --------------------------------------------------------------------------
# Disegni procedurali degli oggetti
# --------------------------------------------------------------------------
def nota_musicale(surf, x, y, col, alpha):
    g = pygame.Surface((26, 40), pygame.SRCALPHA)
    c = col + (int(alpha),)
    pygame.draw.ellipse(g, c, (1, 28, 13, 10))
    pygame.draw.line(g, c, (13, 32), (13, 4), 2)
    pygame.draw.polygon(g, c, [(13, 4), (24, 12), (22, 16), (13, 10)])
    surf.blit(g, (x - 7, y - 33))


def icona_pianoforte(s, a, t):
    cx, cy = a.centerx, a.centery + 18
    corpo = pygame.Rect(0, 0, 164, 86)
    corpo.center = (cx, cy)
    # coperchio sollevato
    pygame.draw.polygon(s, (12, 10, 12), [(corpo.left + 6, corpo.top), (corpo.left + 34, corpo.top - 62),
                                          (corpo.right - 4, corpo.top - 16), (corpo.right - 4, corpo.top)])
    pygame.draw.lines(s, ORO_SCURO, False, [(corpo.left + 6, corpo.top), (corpo.left + 34, corpo.top - 62),
                                            (corpo.right - 4, corpo.top - 16)], 2)
    pygame.draw.line(s, (60, 50, 50), (corpo.centerx, corpo.top), (corpo.left + 60, corpo.top - 40), 2)
    # gambe
    for x in (corpo.left + 12, corpo.right - 22):
        pygame.draw.rect(s, (14, 11, 12), (x, corpo.bottom - 4, 10, 44), border_radius=3)
        pygame.draw.rect(s, ORO_SCURO, (x - 2, corpo.bottom + 36, 14, 5), border_radius=2)
    pygame.draw.rect(s, (20, 16, 18), corpo, border_radius=8)
    pygame.draw.rect(s, (54, 44, 46), corpo, 2, border_radius=8)
    # leggio con spartito
    leggio = pygame.Rect(0, 0, 54, 30)
    leggio.midbottom = (cx, corpo.top + 20)
    pygame.draw.rect(s, PERGAMENA, leggio)
    for i in range(4):
        pygame.draw.line(s, (120, 100, 80), (leggio.left + 4, leggio.top + 6 + i * 5),
                         (leggio.right - 4, leggio.top + 6 + i * 5), 1)
    # tastiera
    tastiera = pygame.Rect(corpo.left + 12, corpo.top + 30, corpo.w - 24, 34)
    n = 14
    tw = tastiera.w / n
    for i in range(n):
        r = pygame.Rect(int(tastiera.left + i * tw), tastiera.top, int(tw) - 1, tastiera.h)
        pygame.draw.rect(s, (236, 230, 214), r, border_bottom_left_radius=2, border_bottom_right_radius=2)
    for i in range(n - 1):
        if i % 7 in (2, 6):
            continue
        r = pygame.Rect(int(tastiera.left + (i + 1) * tw - tw * 0.3), tastiera.top, int(tw * 0.6), 20)
        pygame.draw.rect(s, (10, 8, 8), r)
    pygame.draw.line(s, BORDEAUX, (tastiera.left, tastiera.top - 2), (tastiera.right, tastiera.top - 2), 3)
    # note che fluttuano
    for i in range(3):
        fase = (t * 0.35 + i / 3) % 1.0
        x = cx + 30 + i * 18 + math.sin(t * 1.5 + i) * 8
        y = corpo.top - 20 - fase * 60
        nota_musicale(s, int(x), int(y), ORO_CHIARO, 255 * math.sin(fase * math.pi))


ITALIA = [(0.18, 0.12), (0.30, 0.06), (0.45, 0.09), (0.58, 0.05), (0.67, 0.10), (0.62, 0.17),
          (0.60, 0.23), (0.63, 0.31), (0.70, 0.42), (0.79, 0.51), (0.86, 0.55), (0.90, 0.54),
          (0.89, 0.60), (0.96, 0.67), (0.99, 0.74), (0.93, 0.72), (0.85, 0.66), (0.81, 0.69),
          (0.83, 0.77), (0.77, 0.87), (0.72, 0.84), (0.74, 0.75), (0.67, 0.65), (0.57, 0.57),
          (0.47, 0.47), (0.39, 0.37), (0.33, 0.29), (0.27, 0.24), (0.22, 0.25), (0.15, 0.27),
          (0.12, 0.20)]
SICILIA = [(0.56, 0.86), (0.66, 0.87), (0.75, 0.86), (0.72, 0.96), (0.60, 0.92)]
SARDEGNA = [(0.26, 0.51), (0.32, 0.51), (0.34, 0.60), (0.32, 0.72), (0.27, 0.71), (0.25, 0.61)]


@lru_cache(maxsize=4)
def _carta_mappa(w, h):
    carta = gradiente(w, h, PERGAMENA, PERGAMENA_SCURA)
    rnd = random.Random(7)
    for _ in range(10):
        r = rnd.randint(8, 24)
        carta.blit(alone((140, 110, 60), r, 50), (rnd.randint(-r, w - r), rnd.randint(-r, h - r)))
    return carta


def icona_mappa(s, a, t):
    m = pygame.Rect(0, 0, 168, 176)
    m.center = (a.centerx, a.centery + 6)
    s.blit(_carta_mappa(m.w, m.h), m)
    # rotoli
    for y in (m.top - 6, m.bottom - 6):
        pygame.draw.rect(s, (170, 140, 96), (m.left - 8, y, m.w + 16, 12), border_radius=6)
        pygame.draw.rect(s, (120, 94, 60), (m.left - 8, y, m.w + 16, 12), 1, border_radius=6)
    area = m.inflate(-26, -30)

    def P(pts):
        return [(area.left + x * area.w, area.top + y * area.h) for x, y in pts]

    for isola in (ITALIA, SICILIA, SARDEGNA):
        pygame.draw.polygon(s, (186, 158, 108), P(isola))
        pygame.draw.polygon(s, INCHIOSTRO, P(isola), 1)
    # rotta Quarto -> Marsala (curva di Bézier tratteggiata)
    p0, p1, p2 = P([(0.23, 0.26)])[0], P([(0.46, 0.62)])[0], P([(0.57, 0.88)])[0]

    def bez(u):
        return ((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
                (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1])

    offset = (t * 0.15) % 0.05
    u = offset
    while u < 1.0:
        pygame.draw.line(s, BORDEAUX, bez(u), bez(min(1.0, u + 0.025)), 2)
        u += 0.05
    pygame.draw.circle(s, BORDEAUX, p0, 4)
    pygame.draw.line(s, BORDEAUX, (p2[0] - 4, p2[1] - 4), (p2[0] + 4, p2[1] + 4), 2)
    pygame.draw.line(s, BORDEAUX, (p2[0] - 4, p2[1] + 4), (p2[0] + 4, p2[1] - 4), 2)
    # nave in viaggio
    nx, ny = bez((t * 0.08) % 1.0)
    pygame.draw.polygon(s, INCHIOSTRO, [(nx - 7, ny), (nx + 7, ny), (nx + 4, ny + 4), (nx - 4, ny + 4)])
    pygame.draw.line(s, INCHIOSTRO, (nx, ny), (nx, ny - 10), 1)
    pygame.draw.polygon(s, BIANCO, [(nx + 1, ny - 10), (nx + 7, ny - 3), (nx + 1, ny - 3)])
    # rosa dei venti
    rc = (m.right - 22, m.bottom - 26)
    for k in range(4):
        ang = k * math.pi / 2
        punta = (rc[0] + math.cos(ang) * 12, rc[1] + math.sin(ang) * 12)
        lat1 = (rc[0] + math.cos(ang + 0.5) * 4, rc[1] + math.sin(ang + 0.5) * 4)
        lat2 = (rc[0] + math.cos(ang - 0.5) * 4, rc[1] + math.sin(ang - 0.5) * 4)
        pygame.draw.polygon(s, BORDEAUX if k == 3 else INCHIOSTRO, [punta, lat1, rc, lat2])
    testo(s, "Quarto", font(11, italic=True), INCHIOSTRO, (p0[0] - 4, p0[1] - 12), ombra=False)


@lru_cache(maxsize=2)
def _tela_ritratto(w, h):
    tela_r = pygame.Rect(0, 0, w, h)
    tela = gradiente(tela_r.w, tela_r.h, (70, 40, 34), (26, 16, 16))
    # busto: uniforme blu scuro con spalline dorate
    pygame.draw.ellipse(tela, (28, 34, 62), (4, tela_r.h - 52, tela_r.w - 8, 90))
    pygame.draw.ellipse(tela, ORO, (8, tela_r.h - 46, 26, 12))
    pygame.draw.ellipse(tela, ORO, (tela_r.w - 34, tela_r.h - 46, 26, 12))
    pygame.draw.polygon(tela, (230, 226, 214), [(tela_r.w // 2 - 10, tela_r.h - 50), (tela_r.w // 2 + 10, tela_r.h - 50),
                                                 (tela_r.w // 2, tela_r.h - 30)])
    pygame.draw.circle(tela, ROSSO, (tela_r.w // 2 - 20, tela_r.h - 24), 4)
    pygame.draw.circle(tela, ORO_CHIARO, (tela_r.w // 2 + 20, tela_r.h - 24), 4)
    # collo e testa
    hx, hy = tela_r.w // 2, tela_r.h // 2 - 4
    pygame.draw.rect(tela, (170, 124, 94), (hx - 9, hy + 22, 18, 20))
    pygame.draw.ellipse(tela, (196, 150, 114), (hx - 25, hy - 32, 50, 64))
    pygame.draw.ellipse(tela, (40, 28, 22), (hx - 27, hy - 38, 54, 26))       # capelli
    pygame.draw.polygon(tela, (40, 28, 22), [(hx - 7, hy + 20), (hx + 7, hy + 20), (hx + 3, hy + 36),
                                             (hx, hy + 40), (hx - 3, hy + 36)])     # pizzetto
    # i celebri baffoni
    for d in (-1, 1):
        pygame.draw.polygon(tela, (40, 28, 22), [(hx, hy + 10), (hx + d * 12, hy + 6), (hx + d * 30, hy - 2),
                                                  (hx + d * 36, hy - 10), (hx + d * 32, hy + 4), (hx + d * 14, hy + 16)])
    pygame.draw.circle(tela, (30, 20, 16), (hx - 10, hy - 6), 3)
    pygame.draw.circle(tela, (30, 20, 16), (hx + 10, hy - 6), 3)
    tela = maschera(tela, lambda m: pygame.draw.ellipse(m, (255, 255, 255, 255), m.get_rect()))
    return tela


def icona_ritratto(s, a, t):
    cx, cy = a.centerx, a.centery + 12
    cornice = pygame.Rect(0, 0, 138, 172)
    cornice.center = (cx, cy)
    pygame.draw.ellipse(s, ORO_SCURO, cornice.inflate(10, 10))
    pygame.draw.ellipse(s, ORO, cornice)
    pygame.draw.ellipse(s, ORO_CHIARO, cornice, 2)
    tela_r = cornice.inflate(-22, -22)
    tela = _tela_ritratto(tela_r.w, tela_r.h)
    s.blit(tela, tela_r)
    pygame.draw.ellipse(s, ORO_SCURO, tela_r, 2)
    # corona
    cy0 = cornice.top - 4
    corona = [(cx - 26, cy0), (cx - 30, cy0 - 22), (cx - 14, cy0 - 10), (cx, cy0 - 28),
              (cx + 14, cy0 - 10), (cx + 30, cy0 - 22), (cx + 26, cy0)]
    pygame.draw.polygon(s, ORO, corona)
    pygame.draw.polygon(s, ORO_SCURO, corona, 2)
    for px, py in ((cx - 30, cy0 - 22), (cx, cy0 - 28), (cx + 30, cy0 - 22)):
        pygame.draw.circle(s, ORO_CHIARO, (px, py), 4)
    pygame.draw.circle(s, ROSSO, (cx, cy0 - 7), 4)
    # riflesso che scorre sulla cornice
    ang = t * 0.8
    rx = cx + math.cos(ang) * cornice.w / 2
    ry = cy + math.sin(ang) * cornice.h / 2
    s.blit(alone((255, 240, 190), 14, 160), (rx - 14, ry - 14))


def icona_scrivania(s, a, t):
    cx, cy = a.centerx, a.centery + 30
    piano = [(cx - 86, cy), (cx + 86, cy), (cx + 70, cy - 28), (cx - 70, cy - 28)]
    # gambe
    for x in (cx - 80, cx + 70):
        pygame.draw.rect(s, LEGNO_SCURO, (x, cy + 40, 10, 40))
    fronte = pygame.Rect(cx - 86, cy, 172, 46)
    pygame.draw.rect(s, LEGNO, fronte)
    pygame.draw.rect(s, LEGNO_SCURO, fronte, 2)
    for i in range(2):
        cassetto = pygame.Rect(fronte.left + 10 + i * 82, fronte.top + 8, 70, 30)
        pygame.draw.rect(s, scurisci(LEGNO, 0.15), cassetto)
        pygame.draw.rect(s, LEGNO_SCURO, cassetto, 1)
        pygame.draw.circle(s, ORO, cassetto.center, 4)
    pygame.draw.polygon(s, LEGNO_CHIARO, piano)
    pygame.draw.polygon(s, LEGNO_SCURO, piano, 2)
    # lettera con sigillo
    lettera = [(cx - 30, cy - 6), (cx + 26, cy - 10), (cx + 20, cy - 26), (cx - 26, cy - 22)]
    pygame.draw.polygon(s, PERGAMENA, lettera)
    for k in range(3):
        pygame.draw.line(s, (140, 120, 96), (cx - 22, cy - 19 + k * 4), (cx + 14, cy - 22 + k * 4), 1)
    pygame.draw.circle(s, BORDEAUX, (cx + 10, cy - 10), 5)
    # calamaio e penna d'oca
    pygame.draw.rect(s, (18, 18, 26), (cx + 40, cy - 34, 22, 18), border_radius=5)
    pygame.draw.rect(s, ORO_SCURO, (cx + 45, cy - 38, 12, 5), border_radius=2)
    piuma = [(cx + 51, cy - 36), (cx + 74, cy - 104), (cx + 84, cy - 110), (cx + 80, cy - 92), (cx + 56, cy - 40)]
    pygame.draw.polygon(s, (232, 226, 210), piuma)
    pygame.draw.line(s, (170, 160, 140), (cx + 52, cy - 37), (cx + 82, cy - 108), 1)
    # candela con fiamma tremolante
    base_x, base_y = cx - 58, cy - 20
    pygame.draw.ellipse(s, ORO_SCURO, (base_x - 14, base_y - 4, 28, 10))
    pygame.draw.rect(s, (236, 226, 200), (base_x - 6, base_y - 54, 12, 52))
    pygame.draw.line(s, (40, 30, 20), (base_x, base_y - 54), (base_x, base_y - 60), 2)
    tremolio = math.sin(t * 13) * 1.5 + math.sin(t * 7.3) * 1.2
    fh = 20 + math.sin(t * 9.1) * 2
    s.blit(alone((255, 190, 90), 46, 110), (base_x - 46, base_y - 66 - 46))
    pygame.draw.ellipse(s, (255, 150, 40), (base_x - 6 + tremolio * 0.5, base_y - 60 - fh, 12, fh + 4))
    pygame.draw.ellipse(s, (255, 236, 150), (base_x - 3 + tremolio * 0.5, base_y - 56 - fh * 0.7, 6, fh * 0.7))


# --------------------------------------------------------------------------
# Mappamondo (enigma "globo"): texture equirettangolare e proiezione ortografica
# --------------------------------------------------------------------------
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
GLOBO_TW, GLOBO_TH = 1440, 720            # texture: 4 pixel per grado
GLOBO_ROLLIO = math.radians(23)           # l'asse del mappamondo è inclinato come quello terrestre
GLOBO_INCLINAZIONI = (0, 15, 30, 45, 60)  # latitudine al centro della vista: W-S (o trascinando in su e in giù) cambiano
GLOBO_INCLINAZIONE_INIZIALE = 2
_PALETTE_GLOBO = [(0, 0, 0), (150, 178, 172), (184, 204, 190), (222, 202, 154), (92, 66, 40), (128, 108, 86),
                  (150, 44, 44)]          # 0 = trasparente (fuori dal disco)
_DATI_GLOBO = []
_MAPPE_GLOBO = {}
_IN_BYTE = getattr(pygame.image, "tobytes", None) or pygame.image.tostring        # pygame 2.3+ / versioni precedenti
_DA_BYTE = getattr(pygame.image, "frombytes", None) or pygame.image.fromstring


def dati_globo():
    """La texture del mappamondo come byte di indici di colore (8 bit). Ogni riga contiene due giri del mondo
    affiancati, così girare il globo vuol dire solo leggere a partire da un byte più avanti; in fondo c'è una fascia
    di zeri (colore trasparente) per i pixel fuori dal disco."""
    if not _DATI_GLOBO:
        w, h = GLOBO_TW, GLOBO_TH
        img = pygame.Surface((w, h), 0, 8)
        img.set_palette(_PALETTE_GLOBO + [(0, 0, 0)] * (256 - len(_PALETTE_GLOBO)))
        mare, basso, terra, costa, griglia, equatore = _PALETTE_GLOBO[1:]
        img.fill(mare)

        def P(pts):
            return [((lon + 180) / 360 * w, (90 - lat) / 180 * h) for lon, lat in pts]

        rnd = random.Random(5)
        antartide = ([(-180, -90)] + [(lon, -70 + 4 * math.sin(lon * .05) + rnd.uniform(-1.5, 1.5))
                                      for lon in range(-180, 181, 6)] + [(180, -90)])
        terre = [COSTA_EURASIA, COSTA_AFRICA, COSTA_NORD_AMERICA, COSTA_SUD_AMERICA, COSTA_AUSTRALIA,
                 COSTA_GROENLANDIA, antartide] + COSTA_ISOLE
        for t in terre:                          # bassi fondali: una fascia più chiara lungo le coste
            pygame.draw.polygon(img, basso, P(t), 9)
        for t in terre:
            pygame.draw.polygon(img, terra, P(t))
            pygame.draw.polygon(img, costa, P(t), 2)
        for m in COSTA_MARI_INTERNI:
            pygame.draw.polygon(img, mare, P(m))
            pygame.draw.polygon(img, costa, P(m), 2)
        for lon in range(-180, 181, 15):         # meridiani e paralleli ogni 15 gradi, equatore in rosso
            x = (lon + 180) / 360 * (w - 1)
            pygame.draw.line(img, griglia, (x, 0), (x, h), 1)
        for lat in range(-75, 76, 15):
            y = (90 - lat) / 180 * h
            pygame.draw.line(img, equatore if lat == 0 else griglia, (0, y), (w, y), 2 if lat == 0 else 1)
        righe = _IN_BYTE(img, "P")
        _DATI_GLOBO.append(b"".join(righe[y * w:(y + 1) * w] * 2 for y in range(h)) + bytes(w))
    return _DATI_GLOBO[0]


def mappa_globo(R, lat0, vista):
    """Per ogni pixel di una finestra (vista = larghezza, altezza, centro x, centro y del globo) il byte della texture
    che ci va sopra: proiezione ortografica di un globo di raggio R, con la latitudine lat0 al centro e l'asse inclinato
    di GLOBO_ROLLIO. È un calcolo lento (decimi di secondo): si fa una volta e si tiene da parte.
    Restituisce un itemgetter che, applicato ai dati della texture, dà in un colpo solo tutti i pixel."""
    chiave = (R, lat0, vista)
    if chiave not in _MAPPE_GLOBO:
        vw, vh, cx, cy = vista
        w2 = 2 * GLOBO_TW
        fuori = GLOBO_TH * w2                    # primo byte della fascia trasparente
        s0, c0 = math.sin(math.radians(lat0)), math.cos(math.radians(lat0))
        sr, cr = math.sin(GLOBO_ROLLIO), math.cos(GLOBO_ROLLIO)
        kx, ky = GLOBO_TW / math.tau, GLOBO_TH / math.pi
        asin, atan2, sqrt = math.asin, math.atan2, math.sqrt
        idx = []
        ap = idx.append
        for py in range(vh):
            y0 = (cy - py) / R
            for px in range(vw):
                x0 = (px - cx) / R
                x = x0 * cr + y0 * sr
                y = y0 * cr - x0 * sr
                d = x * x + y * y
                if d >= 1.0:
                    ap(fuori)
                    continue
                z = sqrt(1.0 - d)
                Y = y * c0 + z * s0
                Z = z * c0 - y * s0
                col = int(atan2(x, Z) * kx + GLOBO_TW / 2) % GLOBO_TW
                riga = min(GLOBO_TH - 1, int((math.pi / 2 - asin(max(-1.0, min(1.0, Y)))) * ky))
                ap(riga * w2 + col)
        _MAPPE_GLOBO[chiave] = operator.itemgetter(*idx)
    return _MAPPE_GLOBO[chiave]


def disegna_globo(R, lat0, vista, giro):
    """Il globo girato di 'giro' pixel di texture (0 .. GLOBO_TW-1): fuori dal disco la superficie è trasparente."""
    pixel = bytes(mappa_globo(R, lat0, vista)(dati_globo()[giro % GLOBO_TW:]))
    img = _DA_BYTE(pixel, vista[:2], "P")
    img.set_palette(_PALETTE_GLOBO + [(0, 0, 0)] * (256 - len(_PALETTE_GLOBO)))
    img.set_colorkey(0)
    return img


@lru_cache(maxsize=8)
def ombra_globo(R, vista):
    """Luce sul globo: bordo in ombra, un riflesso in alto a sinistra e un filo scuro attorno."""
    vw, vh, cx, cy = vista
    o = pygame.Surface((vw, vh), pygame.SRCALPHA)
    for r in range(R, 0, -2):
        pygame.draw.circle(o, (20, 12, 6, int(150 * (r / R) ** 4)), (cx, cy), r)
    luce = pygame.Surface((vw, vh), pygame.SRCALPHA)
    for r in range(R // 2, 0, -2):
        pygame.draw.circle(luce, (255, 248, 230, int(46 * (1 - r / (R / 2)))), (cx - R // 3, cy - R // 3), r)
    o.blit(luce, (0, 0))
    pygame.draw.circle(o, (40, 26, 14, 220), (cx, cy), R, 2)
    return o


def proietta_citta(lat, lon, R, lat0, giro, cx, cy, quota=1.0):
    """Posizione sullo schermo di un punto del globo (quota > 1: sopra la superficie, come la capocchia di uno
    spillo) e la sua profondità z: se z <= 0 il punto è sul lato nascosto."""
    lon_rel = math.radians((lon - giro * 360 / GLOBO_TW + 180) % 360 - 180)
    la = math.radians(lat)
    s0, c0 = math.sin(math.radians(lat0)), math.cos(math.radians(lat0))
    X, Y, Z = math.cos(la) * math.sin(lon_rel), math.sin(la), math.cos(la) * math.cos(lon_rel)
    y, z = Y * c0 - Z * s0, Y * s0 + Z * c0
    x0 = X * math.cos(GLOBO_ROLLIO) - y * math.sin(GLOBO_ROLLIO)
    y0 = X * math.sin(GLOBO_ROLLIO) + y * math.cos(GLOBO_ROLLIO)
    return cx + x0 * R * quota, cy - y0 * R * quota, z


def icona_globo(s, a, t):
    cx, cy = a.centerx, a.centery - 4
    R = 64
    pygame.draw.ellipse(s, LEGNO_SCURO, (cx - 52, cy + R + 30, 104, 18))
    pygame.draw.rect(s, ORO_SCURO, (cx - 6, cy + R + 4, 12, 32))
    vista = (2 * R + 1, 2 * R + 1, R, R)
    giro = int(t * 10 * GLOBO_TW / 360)           # gira piano da solo
    s.blit(disegna_globo(R, 30, vista, giro), (cx - R, cy - R))
    s.blit(ombra_globo(R, vista), (cx - R, cy - R))
    # meridiano d'ottone: mezzo anello inclinato come l'asse
    pts = []
    for k in range(25):
        ang = GLOBO_ROLLIO - math.pi / 2 + math.pi * k / 24
        pts.append((cx + math.cos(ang) * (R + 7), cy - math.sin(ang) * (R + 7)))
    pygame.draw.lines(s, ORO, False, pts, 4)
    for x, y in (pts[0], pts[-1]):
        pygame.draw.circle(s, ORO_CHIARO, (int(x), int(y)), 4)


def icona_camino(s, a, t):
    cx, base = a.centerx, a.centery + 86
    corpo = pygame.Rect(0, 0, 176, 150)
    corpo.midbottom = (cx, base)
    s.blit(gradiente(corpo.w, corpo.h, (138, 130, 122), (86, 80, 76)), corpo)
    for y in range(corpo.top + 22, corpo.bottom, 22):                       # conci di pietra
        pygame.draw.line(s, (70, 64, 60), (corpo.left, y), (corpo.right, y), 1)
        for x in range(corpo.left + (14 if (y // 22) % 2 else 0), corpo.right, 30):
            pygame.draw.line(s, (70, 64, 60), (x, y - 22), (x, y), 1)
    bocca = pygame.Rect(0, 0, 112, 104)
    bocca.midbottom = (cx, base - 8)
    pygame.draw.rect(s, (14, 10, 10), bocca, border_top_left_radius=46, border_top_right_radius=46)
    pygame.draw.rect(s, LEGNO_SCURO, (corpo.left - 12, corpo.top - 14, corpo.w + 24, 16), border_radius=3)
    pygame.draw.line(s, ORO_SCURO, (corpo.left - 12, corpo.top - 14), (corpo.right + 12, corpo.top - 14), 2)
    # braci e fiamme
    s.blit(alone((255, 140, 50), 70, 110), (cx - 70, bocca.bottom - 100))
    for dx, ang in ((-18, .3), (14, -.25)):
        x1, y1 = cx + dx - 32 * math.cos(ang), bocca.bottom - 12 - 32 * math.sin(ang)
        x2, y2 = cx + dx + 32 * math.cos(ang), bocca.bottom - 12 + 32 * math.sin(ang)
        pygame.draw.line(s, (70, 44, 26), (x1, y1), (x2, y2), 9)
    for i in range(5):
        fx = cx - 32 + i * 16
        fh = 34 + 12 * math.sin(t * 9 + i * 1.7) + (10 if i == 2 else 0)
        pygame.draw.ellipse(s, (255, 130, 40), (fx - 9, bocca.bottom - 16 - fh, 18, fh))
        pygame.draw.ellipse(s, (255, 226, 130), (fx - 4, bocca.bottom - 12 - fh * .6, 8, fh * .55))
    # la lettera mezza bruciata sul focolare
    lettera = [(cx + 20, base - 2), (cx + 68, base - 10), (cx + 64, base - 30), (cx + 50, base - 34),
               (cx + 40, base - 26), (cx + 18, base - 22)]
    pygame.draw.polygon(s, PERGAMENA, lettera)
    pygame.draw.polygon(s, (60, 30, 14), lettera, 2)
    for k in range(2):
        pygame.draw.line(s, INCHIOSTRO, (cx + 26, base - 16 + k * 6), (cx + 58, base - 21 + k * 6), 2)

ICONE = {"pianoforte": icona_pianoforte, "mappa": icona_mappa, "globo": icona_globo, "camino": icona_camino,
         "ritratto": icona_ritratto, "scrivania": icona_scrivania}


def crea_porta(w, h, aperta):
    """Porta ad arco in legno con bande di ferro."""
    tavole = pygame.Surface((w, h), pygame.SRCALPHA)
    rnd = random.Random(1848)
    n = 6
    lw = w / n
    for i in range(n):
        base = mescola(LEGNO, LEGNO_SCURO, rnd.random() * 0.5)
        col = gradiente(int(lw) + 1, h, schiarisci(base, 0.06), scurisci(base, 0.25))
        tavole.blit(col, (int(i * lw), 0))
        for _ in range(9):   # venature
            x = int(i * lw + rnd.random() * lw)
            y = rnd.randint(0, h)
            pygame.draw.line(tavole, scurisci(base, 0.35), (x, y), (x + rnd.randint(-2, 2), y + rnd.randint(30, 90)), 1)
        pygame.draw.line(tavole, (20, 12, 8), (int(i * lw), 0), (int(i * lw), h), 2)
    for y in (int(h * 0.30), int(h * 0.62), int(h * 0.88)):
        pygame.draw.rect(tavole, (34, 34, 38), (0, y, w, 14))
        pygame.draw.line(tavole, (80, 80, 88), (0, y), (w, y), 1)
        for x in range(10, w, 26):
            pygame.draw.circle(tavole, (96, 96, 104), (x, y + 7), 3)
    r = w // 2
    tavole = maschera(tavole, lambda m: (pygame.draw.rect(m, (255, 255, 255, 255), (0, r, w, h - r)),
                                          pygame.draw.circle(m, (255, 255, 255, 255), (r, r), r)))
    pygame.draw.circle(tavole, (20, 12, 8), (r, r), r, 3, draw_top_left=True, draw_top_right=True)
    # maniglia ad anello e serratura
    pygame.draw.circle(tavole, ORO_SCURO, (w - 38, int(h * 0.55)), 14, 4)
    pygame.draw.rect(tavole, (30, 30, 34), (w - 50, int(h * 0.47), 24, 34), border_radius=4)
    pygame.draw.circle(tavole, (5, 5, 5), (w - 38, int(h * 0.49) + 8), 4)
    pygame.draw.rect(tavole, (5, 5, 5), (w - 40, int(h * 0.49) + 9, 4, 10))
    if not aperta:
        # catene incrociate
        for (x1, y1, x2, y2) in ((6, h * 0.36, w - 6, h * 0.80), (w - 6, h * 0.36, 6, h * 0.80)):
            passi = 16
            for k in range(passi + 1):
                u = k / passi
                x = x1 + (x2 - x1) * u
                y = y1 + (y2 - y1) * u
                if k % 2:
                    pygame.draw.ellipse(tavole, (120, 120, 128), (x - 8, y - 4, 16, 8), 3)
                else:
                    pygame.draw.ellipse(tavole, (150, 150, 158), (x - 4, y - 8, 8, 16), 3)
    return tavole


# --------------------------------------------------------------------------
# Componenti interfaccia
# --------------------------------------------------------------------------
class Pulsante:
    def __init__(self, etichetta, rect, stile="primario"):
        self.etichetta = etichetta
        self.rect = pygame.Rect(rect)
        self.stile = stile

    def disegna(self, s, mouse):
        hover = self.rect.collidepoint(mouse)
        r = self.rect.move(0, -2 if hover else 0)
        if self.stile == "primario":
            if hover:
                bagliore(s, r, ORO, 10, 110, 5)
            base = pannello(r.w, r.h, BORDEAUX_CHIARO if hover else BORDEAUX, BORDEAUX_SCURO, 10)
            s.blit(base, r)
            pygame.draw.rect(s, ORO_CHIARO if hover else ORO, r, 2, border_radius=10)
            testo(s, self.etichetta, font(24, bold=True), ORO_CHIARO, r.center)
        else:
            base = pannello(r.w, r.h, ANTRACITE_3 if hover else ANTRACITE_2, ANTRACITE, 10)
            s.blit(base, r)
            pygame.draw.rect(s, PERGAMENA_SCURA if hover else (120, 110, 96), r, 2, border_radius=10)
            testo(s, self.etichetta, font(22), PERGAMENA, r.center)
        return hover

    def colpito(self, pos):
        return self.rect.collidepoint(pos)


class Carta:
    """Uno dei sei oggetti cliccabili della stanza."""
    LARGHEZZA_ICONA = 188                  # le icone sono disegnate per questa larghezza; nelle carte strette si riducono

    def __init__(self, enigma, rect):
        self.enigma = enigma
        self.rect = pygame.Rect(rect)
        self.fondo = pannello(self.rect.w - 16, self.rect.h - 16, (86, 26, 38), (24, 18, 22), 10)
        self.fondo_ok = pannello(self.rect.w - 16, self.rect.h - 16, (38, 96, 60), (14, 34, 24), 10)
        self.cornice = pannello(self.rect.w, self.rect.h, LEGNO_CHIARO, LEGNO_SCURO, 14)
        self.sollevamento = 0.0
        self.ombra = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(self.ombra, (0, 0, 0, 120), self.ombra.get_rect(), border_radius=14)
        self.foglio_icona = pygame.Surface((self.LARGHEZZA_ICONA, 210), pygame.SRCALPHA)

    def disegna(self, s, mouse, t, risolto, dt):
        hover = self.rect.collidepoint(mouse) and not risolto
        obiettivo = 1.0 if hover else 0.0
        self.sollevamento += (obiettivo - self.sollevamento) * min(1.0, dt * 12)
        r = self.rect.move(0, -int(self.sollevamento * 8))
        # ombra
        s.blit(self.ombra, r.move(6, 10 + int(self.sollevamento * 6)))
        if risolto:
            bagliore(s, r, ORO, 14, 70 + 30 * math.sin(t * 2), 6)
        elif self.sollevamento > 0.02:
            bagliore(s, r, ORO, 14, int(150 * self.sollevamento), 7)
        s.blit(self.cornice, r)
        interno = r.inflate(-16, -16)
        s.blit(self.fondo_ok if risolto else self.fondo, interno)
        pygame.draw.rect(s, ORO if (risolto or hover) else ORO_SCURO, interno, 2, border_radius=10)
        angoli_ornati(s, interno.inflate(-10, -10), ORO_CHIARO if (risolto or hover) else ORO_SCURO)
        # luce morbida dietro l'oggetto
        s.blit(alone((255, 210, 140), 90, 50 + 20 * self.sollevamento), (r.centerx - 90, r.y + 40))
        area = pygame.Rect(r.x + 10, r.y + 34, r.w - 20, 210)
        if area.w >= self.LARGHEZZA_ICONA:
            ICONE[self.enigma["id"]](s, area, t)
        else:
            self.foglio_icona.fill((0, 0, 0, 0))
            ICONE[self.enigma["id"]](self.foglio_icona, self.foglio_icona.get_rect(), t)
            k = area.w / self.LARGHEZZA_ICONA
            icona = pygame.transform.smoothscale(self.foglio_icona, (area.w, int(210 * k)))
            s.blit(icona, (area.x, area.y + (210 - icona.get_height()) // 2))
        # targhetta d'ottone
        targa = pygame.Rect(0, 0, r.w - 44, 42)
        targa.midtop = (r.centerx, r.bottom - 96)
        s.blit(pannello(targa.w, targa.h, ORO_CHIARO, ORO_SCURO, 6), targa)
        pygame.draw.rect(s, (90, 66, 20), targa, 2, border_radius=6)
        for x in (targa.left + 8, targa.right - 8):
            pygame.draw.circle(s, (110, 84, 30), (x, targa.centery), 3)
        dim = 22
        while dim > 12 and font(dim, bold=True).size(self.enigma["nome"].upper())[0] > targa.w - 30:
            dim -= 1
        testo(s, self.enigma["nome"].upper(), font(dim, bold=True), INCHIOSTRO, targa.center, ombra=False)
        if risolto:
            scritta = "Risolto · «%s»" % self.enigma["frammento"]
            dim = 18
            while dim > 11 and font(dim, bold=True).size(scritta)[0] > r.w - 18:
                dim -= 1
            testo(s, scritta, font(dim, bold=True), ORO_CHIARO, (r.centerx, r.bottom - 34))
            ceralacca(s, (r.right - 30, r.top + 30), 20, spunta=True)
        else:
            alpha = 150 + 105 * self.sollevamento
            dim = 17
            while dim > 11 and font(dim, italic=True).size("Clicca per esaminare")[0] > r.w - 18:
                dim -= 1
            testo(s, "Clicca per esaminare", font(dim, italic=True), PERGAMENA, (r.centerx, r.bottom - 34),
                  alpha=alpha)
        return hover


class Modale:
    """Finestra dell'enigma: domanda -> input -> ricompensa."""

    def __init__(self, gioco, enigma=None):
        self.gioco = gioco
        self.enigma = enigma            # None = porta finale
        self.fase = "domanda"
        self.input = ""
        self.messaggio = ""
        self.scuoti = 0.0
        self.apertura = time.monotonic()
        self.pannello = pygame.Rect(0, 0, 800, 520)
        self.pannello.center = (W // 2, H // 2 + 10)
        p = self.pannello
        self.btn_conferma = Pulsante("Conferma", (p.centerx - 240, p.bottom - 84, 250, 56))
        self.btn_chiudi = Pulsante("Chiudi", (p.centerx + 30, p.bottom - 84, 210, 56), "secondario")
        self.btn_continua = Pulsante("Continua", (p.centerx - 125, p.bottom - 84, 250, 56))
        self.input_rect = pygame.Rect(p.centerx - 290, p.top + 300, 580, 58)
        self.carta = self._crea_pergamena(p.w, p.h)

    @staticmethod
    def _crea_pergamena(w, h):
        base = gradiente(w, h, PERGAMENA, PERGAMENA_SCURA)
        rnd = random.Random(1860)
        for _ in range(26):
            r = rnd.randint(20, 70)
            macchia = alone((150, 116, 70), r, 34)
            base.blit(macchia, (rnd.randint(-r, w - r), rnd.randint(-r, h - r)))
        # bordi bruciati
        bordo = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(18):
            pygame.draw.rect(bordo, (110, 70, 30, 10), (i, i, w - 2 * i, h - 2 * i), 1, border_radius=14)
        for i in range(6):
            pygame.draw.rect(bordo, (110, 70, 30, 14), (i, i, w - 2 * i, h - 2 * i), 1, border_radius=14)
        base.blit(bordo, (0, 0))
        return arrotonda(base, 14)

    # ---- logica
    def conferma(self):
        risposta = self.input
        if not normalizza(risposta):
            self.messaggio = "Scrivi una risposta prima di confermare."
            self.scuoti = 0.35
            return
        if self.enigma is None:
            if normalizza(risposta) == PAROLA_ORDINE:
                self.gioco.vittoria()
            else:
                self._errore("Parola d'ordine errata! I gendarmi colpiscono la porta…")
            return
        if risposta_corretta(self.enigma, risposta):
            self.fase = "ricompensa"
            self.apertura = time.monotonic()
            self.gioco.risolvi(self.enigma)
        else:
            self._errore("Risposta errata. I passi dei gendarmi si avvicinano…")

    def _errore(self, msg):
        self.messaggio = msg
        self.scuoti = 0.45
        self.input = ""
        self.gioco.suoni.suona("sbagliato")

    def gestisci(self, e, pos):
        """Ritorna True se la modale va chiusa."""
        if self.fase == "ricompensa":
            if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.btn_continua.colpito(pos)) or \
               (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_SPACE)):
                self.gioco.suoni.suona("click")
                return True
            return False
        if e.type == pygame.TEXTINPUT:
            for ch in e.text:
                if ch.isprintable() and len(self.input) < MAX_INPUT:
                    self.input += ch
            self.messaggio = ""
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                self.input = self.input[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.conferma()
            elif e.key == pygame.K_ESCAPE:
                return True
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_conferma.colpito(pos):
                self.gioco.suoni.suona("click")
                self.conferma()
            elif self.btn_chiudi.colpito(pos):
                self.gioco.suoni.suona("click")
                return True
        return False

    # ---- disegno
    def disegna(self, s, mouse, t, dt):
        anim = min(1.0, (time.monotonic() - self.apertura) / 0.22)
        ease = 1 - (1 - anim) ** 3
        velo = self.gioco.velo
        velo.fill((8, 6, 8, int(200 * ease)))
        s.blit(velo, (0, 0))
        dx = 0
        if self.scuoti > 0:
            dx = int(math.sin(self.scuoti * 70) * 12 * (self.scuoti / 0.45))
            self.scuoti = max(0.0, self.scuoti - dt)
        p = self.pannello.move(dx, int((1 - ease) * 30))
        off = (p.x - self.pannello.x, p.y - self.pannello.y)
        ombra = pygame.Surface(p.size, pygame.SRCALPHA)
        pygame.draw.rect(ombra, (0, 0, 0, 150), ombra.get_rect(), border_radius=14)
        s.blit(ombra, p.move(10, 14))
        s.blit(self.carta, p)
        pygame.draw.rect(s, BORDEAUX, p, 4, border_radius=14)
        pygame.draw.rect(s, ORO_SCURO, p.inflate(-16, -16), 1, border_radius=10)
        angoli_ornati(s, p.inflate(-26, -26), BORDEAUX)
        if self.fase == "domanda":
            self._disegna_domanda(s, p, off, mouse, t)
        else:
            self._disegna_ricompensa(s, p, off, mouse, t)

    def _disegna_domanda(self, s, p, off, mouse, t):
        if self.enigma is None:
            titolo, domanda = "La Porta Uscita", ("Inserisci la parola d'ordine unendo i %d frammenti di chiave trovati."
                                                  % N_ENIGMI)
        else:
            titolo, domanda = self.enigma["titolo"], self.enigma["domanda"]
        testo(s, titolo, font(40, bold=True), BORDEAUX_SCURO, (p.centerx, p.top + 52), ombra=False)
        fregio(s, (p.centerx, p.top + 88), 360, BORDEAUX)
        spazio = self.input_rect.top - 34 - (p.top + 112)        # la domanda deve finire sopra "La tua risposta"
        for corpo in (25, 23, 22, 21, 20):
            f = font(corpo, italic=True)
            if len(a_capo("«" + domanda + "»", f, p.w - 120)) * int(f.get_linesize() * 1.2) <= spazio:
                break
        y = paragrafo(s, "«" + domanda + "»", f, INCHIOSTRO, p.centerx, p.top + 112, p.w - 120, 1.2)
        if self.enigma is None:
            frammenti = "  ·  ".join(e["frammento"] for e in ENIGMI)
            testo(s, frammenti, font(34, bold=True), BORDEAUX, (p.centerx, max(y + 30, p.top + 232)), ombra=False)
        # campo di testo
        ir = self.input_rect.move(*off)
        testo(s, "La tua risposta:", font(18, italic=True), (110, 84, 60), (ir.left + 4, ir.top - 6), "bottomleft",
              ombra=False)
        pygame.draw.rect(s, (252, 246, 232), ir, border_radius=8)
        pygame.draw.rect(s, BORDEAUX, ir, 2, border_radius=8)
        f = font(28)
        if self.input:
            img = f.render(self.input, True, INCHIOSTRO)
            testo_x = ir.left + 16
            if img.get_width() > ir.w - 34:
                testo_x = ir.right - 18 - img.get_width()
            clip = s.get_clip()
            s.set_clip(ir.inflate(-8, -4))
            s.blit(img, (testo_x, ir.centery - img.get_height() // 2))
            s.set_clip(clip)
            cursore_x = min(ir.right - 16, testo_x + img.get_width() + 3)
        else:
            testo(s, "Scrivi qui la risposta…", font(24, italic=True), (170, 150, 128), (ir.left + 16, ir.centery),
                  "midleft", ombra=False)
            cursore_x = ir.left + 14
        if int(t * 2) % 2 == 0:
            pygame.draw.line(s, INCHIOSTRO, (cursore_x, ir.top + 12), (cursore_x, ir.bottom - 12), 2)
        if self.messaggio:
            testo(s, self.messaggio, font(20, bold=True), ROSSO, (p.centerx, ir.bottom + 26), ombra=False)
        for b in (self.btn_conferma, self.btn_chiudi):
            orig = b.rect
            b.rect = orig.move(*off)
            b.disegna(s, mouse)
            b.rect = orig

    def _disegna_ricompensa(self, s, p, off, mouse, t):
        e = self.enigma
        testo(s, "Enigma risolto!", font(40, bold=True), VERDE_SCURO, (p.centerx, p.top + 52), ombra=False)
        fregio(s, (p.centerx, p.top + 88), 360, BORDEAUX)
        testo(s, "Hai trovato un frammento della chiave finale", font(21, italic=True), INCHIOSTRO,
              (p.centerx, p.top + 116), ombra=False)
        pulsa = 1 + 0.04 * math.sin(t * 4)
        # le curiosità lunghe (Nizza) hanno un sigillo più piccolo e un corpo più piccolo: devono stare sopra il pulsante
        lunga = len(a_capo(e["curiosita"], font(23, italic=True), p.w - 140)) > 3
        cy, r0, yt = (p.top + 178, 52, p.top + 250) if lunga else (p.top + 200, 72, p.top + 300)
        spazio = self.btn_continua.rect.top - 12 - (yt + 30)
        for corpo in (23, 21, 20, 19, 18, 17):
            f = font(corpo, italic=True)
            if len(a_capo(e["curiosita"], f, p.w - 140)) * int(f.get_linesize() * 1.2) <= spazio:
                break
        raggio = int(r0 * pulsa)
        s.blit(alone((255, 200, 90), 120, 90), (p.centerx - 120, cy - 120))
        ceralacca(s, (p.centerx, cy), raggio, e["frammento"], font(34 if len(e["frammento"]) > 2 else 46, bold=True))
        testo(s, "Curiosità storica", font(24, bold=True), BORDEAUX, (p.centerx, yt), ombra=False)
        paragrafo(s, e["curiosita"], f, INCHIOSTRO, p.centerx, yt + 30, p.w - 140, 1.2)
        orig = self.btn_continua.rect
        self.btn_continua.rect = orig.move(*off)
        self.btn_continua.disegna(s, mouse)
        self.btn_continua.rect = orig


class ModaleGlobo(Modale):
    """Il mappamondo: si gira trascinando (o con A-D / frecce), W-S cambiano l'inclinazione, la rotellina fa lo zoom.
    Gli spilli non hanno nome: cliccando quello sbagliato compare il nome della città, con Nizza l'enigma è risolto."""
    RAGGI = (128, 260, 460)                # raggio del globo in pixel: intero e due livelli di zoom (rotellina)

    def __init__(self, gioco, enigma):
        super().__init__(gioco, enigma)
        p = self.pannello
        self.vista_rect = pygame.Rect(0, 0, 640, 262)
        self.vista_rect.midtop = (p.centerx, p.top + 160)
        self.btn_chiudi = Pulsante("Chiudi", (p.right - 176, p.bottom - 68, 136, 46), "secondario")
        if gioco.giro_globo is None:
            gioco.giro_globo = random.randrange(GLOBO_TW)
        self.giro = float(gioco.giro_globo)
        self.incl = GLOBO_INCLINAZIONE_INIZIALE
        self.zoom = 0
        self.trascina = False
        self.su_giu = 0.0                  # trascinamento verticale accumulato: ogni 40 pixel cambia l'inclinazione
        self.sopra = None                  # lo spillo sotto il mouse
        self.immagine = None

    @property
    def vista(self):
        return self.vista_rect.w, self.vista_rect.h, self.vista_rect.w // 2, self.vista_rect.h // 2

    def _gira(self, pixel_schermo):
        """Sposta la superficie del globo di tanti pixel dello schermo verso destra (negativi: a sinistra)."""
        gradi = math.degrees(pixel_schermo / self.RAGGI[self.zoom])
        self.giro = (self.giro - gradi * GLOBO_TW / 360) % GLOBO_TW
        self.gioco.giro_globo = self.giro

    def _inclina(self, verso):
        self.incl = max(0, min(len(GLOBO_INCLINAZIONI) - 1, self.incl + verso))

    def gestisci(self, e, pos):
        if self.fase == "ricompensa":
            return super().gestisci(e, pos)
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                return True
            if e.key in (pygame.K_w, pygame.K_UP):          # come trascinare in su: la superficie sale
                self._inclina(-1)
            elif e.key in (pygame.K_s, pygame.K_DOWN):
                self._inclina(1)
        elif e.type == pygame.MOUSEWHEEL:
            self.zoom = max(0, min(len(self.RAGGI) - 1, self.zoom + (e.y > 0) - (e.y < 0)))
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.btn_chiudi.colpito(pos):
                self.gioco.suoni.suona("click")
                return True
            if self.sopra == CITTA_GIUSTA:
                self.sopra = None
                self.fase = "ricompensa"
                self.apertura = time.monotonic()
                self.gioco.risolvi(self.enigma)
            elif self.sopra:
                self.messaggio = "Questa è %s… non è la città che cerchi." % self.sopra
                self.scuoti = 0.3
                self.gioco.suoni.suona("sbagliato")
            elif self.vista_rect.collidepoint(pos):
                self.trascina, self.su_giu = True, 0.0
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.trascina = False
        elif e.type == pygame.MOUSEMOTION and self.trascina:
            dx, dy = (v / max(self.gioco.scala, 1e-3) for v in e.rel)       # pixel della finestra -> pixel del gioco
            self._gira(dx)
            self.su_giu += dy
            while abs(self.su_giu) >= 40:
                self._inclina(-1 if self.su_giu < 0 else 1)
                self.su_giu -= math.copysign(40, self.su_giu)
        return False

    def disegna(self, s, mouse, t, dt):
        if self.fase == "domanda":
            k = pygame.key.get_pressed()
            verso = (k[pygame.K_d] or k[pygame.K_RIGHT]) - (k[pygame.K_a] or k[pygame.K_LEFT])
            if verso:
                self._gira(verso * dt * 1.2 * self.RAGGI[self.zoom])       # circa 70 gradi al secondo
        super().disegna(s, mouse, t, dt)

    def _disegna_domanda(self, s, p, off, mouse, t):
        e = self.enigma
        testo(s, e["titolo"], font(38, bold=True), BORDEAUX_SCURO, (p.centerx, p.top + 46), ombra=False)
        fregio(s, (p.centerx, p.top + 80), 360, BORDEAUX)
        paragrafo(s, "«" + e["domanda"] + "»", font(21, italic=True), INCHIOSTRO, p.centerx, p.top + 96, p.w - 120, 1.15)
        v = self.vista_rect.move(*off)
        R, lat0 = self.RAGGI[self.zoom], GLOBO_INCLINAZIONI[self.incl]
        vista = self.vista
        giro = int(self.giro) % GLOBO_TW
        chiave = (R, lat0, giro)
        if self.immagine is None or self.immagine[0] != chiave:
            self.immagine = (chiave, disegna_globo(R, lat0, vista, giro))
        pygame.draw.rect(s, (40, 30, 24), v.inflate(8, 8), border_radius=10)
        pygame.draw.rect(s, (62, 46, 34), v, border_radius=8)
        clip = s.get_clip()
        s.set_clip(v)
        s.blit(self.immagine[1], v.topleft)
        s.blit(ombra_globo(R, vista), v.topleft)
        # spilli: la capocchia sta un po' sopra la superficie; quello più vicino al mouse si illumina
        cx, cy = v.x + vista[2], v.y + vista[3]
        spilli, self.sopra, vicino = [], None, (5 + 3 * self.zoom) ** 2
        for nome, la, lo in CITTA_GLOBO:
            bx, by, z = proietta_citta(la, lo, R, lat0, giro, cx, cy)
            if z <= .08:
                continue
            hx, hy, _ = proietta_citta(la, lo, R, lat0, giro, cx, cy, 1 + 9 / R)      # capocchia 9 pixel sopra
            spilli.append((nome, bx, by, hx, hy))
            d = (hx - mouse[0]) ** 2 + (hy - mouse[1]) ** 2
            if d < vicino and v.collidepoint(mouse):
                self.sopra, vicino = nome, d
        rc = 4 + self.zoom
        for nome, bx, by, hx, hy in spilli:
            pygame.draw.line(s, (200, 186, 150), (bx, by), (hx, hy), 2)
            pygame.draw.circle(s, (60, 20, 20), (int(hx) + 1, int(hy) + 2), rc)
            pygame.draw.circle(s, ORO_CHIARO if nome == self.sopra else (196, 28, 40), (int(hx), int(hy)),
                               rc + (2 if nome == self.sopra else 0))
            pygame.draw.circle(s, (255, 230, 220), (int(hx) - rc // 3, int(hy) - rc // 3), max(1, rc // 3))
        s.set_clip(clip)
        testo(s, "Trascina col mouse o usa A-D / frecce per girarlo  ·  W-S: inclina  ·  rotellina: zoom  ·  "
                 "clic su uno spillo", font(15, italic=True), (110, 84, 60), (p.centerx, v.bottom + 16), ombra=False)
        if self.messaggio:
            testo(s, self.messaggio, font(20, bold=True), ROSSO, (p.centerx - 70, v.bottom + 46), ombra=False)
        orig = self.btn_chiudi.rect
        self.btn_chiudi.rect = orig.move(*off)
        self.btn_chiudi.disegna(s, mouse)
        self.btn_chiudi.rect = orig


# --------------------------------------------------------------------------
# Il gioco
# --------------------------------------------------------------------------
class Gioco:
    def __init__(self):
        info = pygame.display.Info()
        scala = min(1.0, (info.current_w * 0.94) / W, (info.current_h * 0.88) / H) if info.current_w > 0 else 1.0
        self.dim_finestra = (max(640, int(W * scala)), max(400, int(H * scala)))
        self.schermo_intero = False
        self.finestra = pygame.display.set_mode(self.dim_finestra, pygame.RESIZABLE)
        pygame.display.set_caption("Il Segreto del Carbonaro")
        icona = pygame.Surface((64, 64), pygame.SRCALPHA)
        coccarda(icona, (32, 32), 26)
        pygame.display.set_icon(icona)
        self.tela = pygame.Surface((W, H))
        self.scala, self.offset = 1.0, (0, 0)

        self.suoni = Suoni()
        self.sfondo = self._crea_sfondo()
        self.vignetta = self._crea_vignetta()
        larg, passo = 150, 158                                  # sei carte tra il bordo sinistro e la porta
        x0 = 505 - (passo * (N_ENIGMI - 1) + larg) // 2
        self.carte = [Carta(e, (x0 + i * passo, 150, larg, 372)) for i, e in enumerate(ENIGMI)]
        self.giro_globo = None                                  # dove si era lasciato il mappamondo (None: a caso)
        self.porta_rect = pygame.Rect(1000, 144, 240, 440)       # area cliccabile (arco + targa)
        self.porta_img = {False: crea_porta(196, 352, False), True: crea_porta(196, 352, True)}
        self.fondo_barra = gradiente(W, 118, (40, 12, 20), (14, 10, 12))
        self.fondo_barra.set_alpha(235)
        self.fondo_vittoria = gradiente(W, H, (52, 34, 14), (10, 8, 6))
        self.fondo_sconfitta = gradiente(W, H, (96, 8, 14), (18, 2, 4))
        rnd = random.Random(99)
        for _ in range(26):   # crepe della porta sfondata
            x, y = W // 2, 300
            ang = rnd.uniform(0, math.tau)
            lung = rnd.uniform(200, 800)
            punti = [(x, y)]
            for k in range(6):
                ang += rnd.uniform(-0.4, 0.4)
                x += math.cos(ang) * lung / 6
                y += math.sin(ang) * lung / 6
                punti.append((x, y))
            pygame.draw.lines(self.fondo_sconfitta, (30, 0, 4), False, punti, 2)
        self.velo = pygame.Surface((W, H), pygame.SRCALPHA)
        self.scritte_vittoria = tuple(font(118, bold=True).render("OBBEDISCO", True, c)
                                      for c in (ORO, (255, 230, 150), (0, 0, 0)))
        self.carta_intro = Modale._crea_pergamena(860, 276)
        self.carta_vittoria = Modale._crea_pergamena(900, 360)
        self.btn_inizia = Pulsante("Inizia la fuga", (W // 2 - 150, 640, 300, 62))
        rnd = random.Random()
        self.polvere = [[rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(-6, 6), rnd.uniform(-12, -3),
                         rnd.uniform(0, math.tau), rnd.uniform(1, 2.4)] for _ in range(70)]
        self.cursore_mano = None
        self.t0 = time.monotonic()
        self.reset()
        self.stato = "intro"

    # ---- stato
    def reset(self):
        self.risolti = set()
        self.modale = None
        self.inizio = None
        self.tempo_congelato = None
        self.toast = None
        self.scuoti_porta = 0.0
        self.ultimo_secondo = None
        self.t_evento = 0.0
        self.coriandoli = []
        self.lampo = 0.0

    def nuova_partita(self):
        self.reset()
        self.stato = "gioco"
        self.inizio = time.monotonic()
        self.mostra_toast("Il tempo scorre: esamina gli oggetti dello studio.", ORO_CHIARO)

    def tempo_rimasto(self):
        if self.tempo_congelato is not None:
            return self.tempo_congelato
        if self.inizio is None:
            return float(TEMPO_TOTALE)
        return max(0.0, TEMPO_TOTALE - (time.monotonic() - self.inizio))

    def mostra_toast(self, msg, col=ORO_CHIARO):
        self.toast = (msg, time.monotonic(), col)

    def risolvi(self, enigma):
        self.risolti.add(enigma["id"])
        self.suoni.suona("giusto")
        if len(self.risolti) == len(ENIGMI):
            self.mostra_toast("Tutti i frammenti sono tuoi! Le catene della porta sono cadute…", ORO_CHIARO)
        else:
            self.mostra_toast("Frammento «%s» trovato! (%d/%d)" % (enigma["frammento"], len(self.risolti), N_ENIGMI),
                              VERDE_CHIARO)

    def vittoria(self):
        self.tempo_congelato = self.tempo_rimasto()      # il timer si ferma
        self.stato = "vittoria"
        self.modale = None
        self.t_evento = time.monotonic()
        self.suoni.suona("vittoria")
        rnd = random.Random()
        self.coriandoli = [[rnd.uniform(0, W), rnd.uniform(-H, 0), rnd.uniform(-30, 30), rnd.uniform(70, 170),
                            rnd.uniform(0, math.tau), rnd.uniform(2, 6), rnd.choice(TRICOLORE + [ORO])]
                           for _ in range(170)]
        if not self.schermo_intero:
            self.cambia_schermo()

    def sconfitta(self):
        self.tempo_congelato = 0.0
        self.stato = "sconfitta"
        self.modale = None
        self.t_evento = time.monotonic()
        self.lampo = 1.0
        self.suoni.suona("sconfitta")

    def cambia_schermo(self):
        try:
            if self.schermo_intero:
                self.finestra = pygame.display.set_mode(self.dim_finestra, pygame.RESIZABLE)
            else:
                self.finestra = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.schermo_intero = not self.schermo_intero
        except pygame.error:
            self.finestra = pygame.display.set_mode(self.dim_finestra, pygame.RESIZABLE)
            self.schermo_intero = False

    # ---- conversione coordinate finestra -> tela logica
    def logico(self, pos):
        return (int((pos[0] - self.offset[0]) / self.scala), int((pos[1] - self.offset[1]) / self.scala))

    # ---- eventi
    def gestisci(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
            self.cambia_schermo()
            return True
        pos = self.logico(e.pos) if hasattr(e, "pos") else (0, 0)

        if self.stato == "intro":
            if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.btn_inizia.colpito(pos)) or \
               (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)):
                self.suoni.suona("click")
                self.nuova_partita()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                self.suoni.attivo = not self.suoni.attivo
            return True

        if self.stato in ("vittoria", "sconfitta"):
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return False
                if e.key == pygame.K_r:
                    if self.schermo_intero and self.stato == "vittoria":
                        self.cambia_schermo()
                    self.nuova_partita()
            return True

        # stato "gioco"
        if self.modale:
            if self.modale.gestisci(e, pos):
                self.modale = None
            return True
        if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
            self.suoni.attivo = not self.suoni.attivo
            self.mostra_toast("Audio " + ("attivato" if self.suoni.attivo else "disattivato"), PERGAMENA)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for carta in self.carte:
                if carta.rect.collidepoint(pos):
                    if carta.enigma["id"] in self.risolti:
                        self.mostra_toast("Hai già svelato il segreto del %s." % carta.enigma["nome"].lower(), PERGAMENA)
                    else:
                        self.suoni.suona("click")
                        self.modale = (ModaleGlobo if carta.enigma["id"] == "globo" else Modale)(self, carta.enigma)
                    return True
            if self.porta_rect.collidepoint(pos):
                if len(self.risolti) < len(ENIGMI):
                    self.suoni.suona("bloccato")
                    self.scuoti_porta = 0.5
                    self.mostra_toast("La porta è sbarrata! Risolvi prima tutti gli enigmi (%d/%d)." % (len(self.risolti), N_ENIGMI),
                                      ROSSO_ALLARME)
                else:
                    self.suoni.suona("click")
                    self.modale = Modale(self, None)
        return True

    def aggiorna(self, dt):
        if self.stato == "gioco":
            rimasto = self.tempo_rimasto()
            if rimasto <= 0:
                self.sconfitta()
                return
            sec = int(math.ceil(rimasto))
            if sec != self.ultimo_secondo:
                if self.ultimo_secondo is not None and sec <= 60:
                    self.suoni.suona("tick")
                self.ultimo_secondo = sec
        for p in self.polvere:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] += dt
            if p[1] < -5:
                p[1] = H + 5
                p[0] = random.uniform(0, W)
            p[0] %= W
        for c in self.coriandoli:
            c[0] += (c[2] + math.sin(c[4]) * 20) * dt
            c[1] += c[3] * dt
            c[4] += dt * 3
            if c[1] > H + 10:
                c[1] = random.uniform(-60, -10)
                c[0] = random.uniform(0, W)
        self.scuoti_porta = max(0.0, self.scuoti_porta - dt)
        self.lampo = max(0.0, self.lampo - dt * 1.2)

    # ---- sfondi precalcolati
    def _crea_sfondo(self):
        s = gradiente(W, H, (30, 28, 34), (16, 15, 18))
        rnd = random.Random(1831)
        # carta da parati damascata
        motivo = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, 560, 56):
            for x in range(0, W + 56, 56):
                ox = 28 if (y // 56) % 2 else 0
                cx, cy = x + ox, y + 28
                pygame.draw.polygon(motivo, (120, 40, 54, 26), [(cx, cy - 18), (cx + 12, cy), (cx, cy + 18), (cx - 12, cy)])
                pygame.draw.circle(motivo, (212, 175, 55, 18), (cx, cy), 3)
        s.blit(motivo, (0, 0))
        # boiserie
        zoccolo = gradiente(W, H - 540, LEGNO, LEGNO_SCURO)
        s.blit(zoccolo, (0, 540))
        for x in range(0, W, 160):
            pygame.draw.rect(s, scurisci(LEGNO, 0.35), (x + 14, 566, 132, 214), 2, border_radius=4)
            pygame.draw.rect(s, schiarisci(LEGNO, 0.08), (x + 20, 572, 120, 202), 1, border_radius=3)
        for _ in range(300):
            x = rnd.randint(0, W)
            y = rnd.randint(545, H)
            pygame.draw.line(s, scurisci(LEGNO, rnd.uniform(0.2, 0.45)), (x, y), (x + rnd.randint(20, 90), y), 1)
        pygame.draw.rect(s, LEGNO_SCURO, (0, 532, W, 12))
        pygame.draw.line(s, ORO_SCURO, (0, 532), (W, 532), 2)
        # arco in pietra della porta
        arco = pygame.Surface((252, 420), pygame.SRCALPHA)
        pietra = gradiente(252, 420, (92, 88, 86), (52, 50, 52))
        pietra = maschera(pietra, lambda m: (pygame.draw.rect(m, (255, 255, 255, 255), (0, 126, 252, 294)),
                                             pygame.draw.circle(m, (255, 255, 255, 255), (126, 126), 126)))
        arco.blit(pietra, (0, 0))
        for k in range(9):
            ang = math.pi + k * math.pi / 8
            pygame.draw.line(arco, (40, 38, 40), (126 + math.cos(ang) * 98, 126 + math.sin(ang) * 98),
                             (126 + math.cos(ang) * 126, 126 + math.sin(ang) * 126), 2)
        for y in range(160, 420, 44):
            pygame.draw.line(arco, (40, 38, 40), (0, y), (28, y), 2)
            pygame.draw.line(arco, (40, 38, 40), (224, y), (252, y), 2)
        s.blit(arco, (994, 136))
        return s

    def _crea_vignetta(self):
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        v.fill((0, 0, 0, 215))
        passi = 60
        for i in range(passi):
            k = i / passi
            rw, rh = int(W * 1.5 * (1 - k)), int(H * 1.5 * (1 - k))
            a = int(215 * (1 - k) ** 2.2)
            r = pygame.Rect(0, 0, rw, rh)
            r.center = (W // 2, H // 2 - 60)
            pygame.draw.ellipse(v, (0, 0, 0, a), r)
        return v

    # ---- disegno
    def disegna(self, dt):
        t = time.monotonic() - self.t0
        mouse = self.logico(pygame.mouse.get_pos())
        s = self.tela
        cliccabile = False
        if self.stato == "vittoria":
            self._disegna_vittoria(s, t)
        elif self.stato == "sconfitta":
            self._disegna_sconfitta(s, t)
        else:
            cliccabile = self._disegna_stanza(s, mouse, t, dt)
            if self.stato == "intro":
                cliccabile = self._disegna_intro(s, mouse, t)
            elif self.modale:
                self.modale.disegna(s, mouse, t, dt)
                m = self.modale
                bott = [m.btn_continua] if m.fase == "ricompensa" else [m.btn_conferma, m.btn_chiudi]
                cliccabile = any(b.rect.collidepoint(mouse) for b in bott) or getattr(m, "sopra", None) is not None
        self._aggiorna_cursore(cliccabile)
        self._presenta()

    def _presenta(self):
        fw, fh = self.finestra.get_size()
        self.scala = min(fw / W, fh / H)
        dw, dh = int(W * self.scala), int(H * self.scala)
        self.offset = ((fw - dw) // 2, (fh - dh) // 2)
        if (dw, dh) == (W, H):
            self.finestra.blit(self.tela, self.offset)
        else:
            self.finestra.fill((0, 0, 0))
            self.finestra.blit(pygame.transform.smoothscale(self.tela, (dw, dh)), self.offset)
        pygame.display.flip()

    def _aggiorna_cursore(self, mano):
        if mano != self.cursore_mano:
            self.cursore_mano = mano
            try:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if mano else pygame.SYSTEM_CURSOR_ARROW)
            except (AttributeError, pygame.error):
                pass

    def _disegna_stanza(self, s, mouse, t, dt):
        s.blit(self.sfondo, (0, 0))
        attivo = self.stato == "gioco" and self.modale is None
        m = mouse if attivo else (-100, -100)
        cliccabile = False
        for carta in self.carte:
            if carta.disegna(s, m, t, carta.enigma["id"] in self.risolti, dt):
                cliccabile = True
        if self._disegna_porta(s, m, t):
            cliccabile = True
        self._disegna_frammenti(s, t)
        # polvere nella luce delle candele
        for p in self.polvere:
            a = 70 + 60 * math.sin(p[4] * 1.3)
            r = int(p[5] * 2)
            s.blit(alone((255, 220, 150), r, a * 2.2), (int(p[0]) - r, int(p[1]) - r))
        s.blit(self.vignetta, (0, 0))
        # tremolio caldo delle candele
        luce = 14 + 6 * math.sin(t * 7.1) + 4 * math.sin(t * 13.7)
        self.velo.fill((255, 150, 60, int(max(0, luce))))
        s.blit(self.velo, (0, 0))
        self._disegna_barra(s, t)
        self._disegna_toast(s)
        testo(s, "Clic: esamina  ·  Invio: conferma  ·  Esc: chiudi  ·  M: audio %s  ·  F11: schermo intero"
              % ("on" if self.suoni.attivo else "off"), font(15, italic=True), (170, 150, 120), (W // 2, H - 16))
        return cliccabile

    def _disegna_barra(self, s, t):
        s.blit(self.fondo_barra, (0, 0))
        pygame.draw.line(s, ORO, (0, 118), (W, 118), 2)
        pygame.draw.line(s, ORO_SCURO, (0, 122), (W, 122), 1)
        coccarda(s, (70, 59), 34)
        testo(s, "IL SEGRETO DEL CARBONARO", font(42, bold=True), ORO, (124, 44), "midleft")
        testo(s, "Torino, 4 maggio 1860  ·  Studio segreto della Carboneria  ·  Enigmi risolti: %d/%d"
              % (len(self.risolti), N_ENIGMI), font(19, italic=True), PERGAMENA, (126, 88), "midleft")
        # timer
        rimasto = self.tempo_rimasto()
        box = pygame.Rect(W - 290, 14, 262, 92)
        if rimasto <= 60:
            col = ROSSO_ALLARME
            pulsa = (math.sin(t * 8) + 1) / 2
        elif rimasto <= 300:
            col = (236, 140, 60)
            pulsa = (math.sin(t * 3) + 1) / 4
        else:
            col = ORO_CHIARO
            pulsa = 0
        if pulsa:
            bagliore(s, box, col, 10, int(160 * pulsa), 5)
        s.blit(pannello(box.w, box.h, (26, 20, 22), (8, 6, 8), 10), box)
        pygame.draw.rect(s, col if pulsa else ORO, box, 2, border_radius=10)
        testo(s, "I GENDARMI ENTRERANNO TRA", font(13, bold=True), PERGAMENA_SCURA, (box.centerx, box.top + 14))
        stringa = formatta_tempo(rimasto)
        f = font(56, bold=True)
        cella = f.size("0")[0] + 2
        larg = cella * 4 + f.size(":")[0]
        x = box.centerx - larg // 2
        for ch in stringa:
            wch = f.size(":")[0] if ch == ":" else cella
            testo(s, ch, f, col, (x + wch // 2, box.centery + 12))
            x += wch
        # barra del tempo
        frac = rimasto / TEMPO_TOTALE
        pygame.draw.rect(s, (30, 24, 26), (0, 124, W, 6))
        pygame.draw.rect(s, mescola(ROSSO_ALLARME, ORO, frac * 1.4), (0, 124, int(W * frac), 6))

    def _disegna_porta(self, s, mouse, t):
        aperta = len(self.risolti) == len(ENIGMI)
        hover = self.porta_rect.collidepoint(mouse)
        dx = int(math.sin(self.scuoti_porta * 60) * 8 * (self.scuoti_porta / 0.5)) if self.scuoti_porta else 0
        pos = (1022 + dx, 170)
        if aperta:
            # luce che filtra dai bordi
            pulsa = 0.6 + 0.4 * math.sin(t * 3)
            s.blit(alone((255, 210, 120), 190, int(110 * pulsa)), (1120 - 190, 340 - 190))
        elif hover:
            s.blit(alone((255, 120, 90), 170, 60), (1120 - 170, 340 - 170))
        s.blit(self.porta_img[aperta], pos)
        if aperta:
            k = (1022 + dx + 196 - 38, 170 + int(352 * 0.49) + 12)
            s.blit(alone((255, 220, 120), 30, int(220 * (0.6 + 0.4 * math.sin(t * 5)))), (k[0] - 30, k[1] - 30))
        else:
            # lucchetto
            lx, ly = 1120 + dx, 170 + int(352 * 0.58)
            pygame.draw.arc(s, (150, 150, 160), (lx - 16, ly - 34, 32, 40), 0, math.pi, 5)
            corpo = pygame.Rect(lx - 24, ly - 14, 48, 40)
            s.blit(pannello(48, 40, ORO_CHIARO, ORO_SCURO, 6), corpo)
            pygame.draw.rect(s, (90, 66, 20), corpo, 2, border_radius=6)
            pygame.draw.circle(s, (30, 20, 10), (lx, ly + 2), 5)
            pygame.draw.rect(s, (30, 20, 10), (lx - 2, ly + 2, 4, 12))
        # targa
        targa = pygame.Rect(0, 0, 220, 58)
        targa.midtop = (1120, 530)
        if aperta:
            bagliore(s, targa, ORO, 8, int(90 + 70 * math.sin(t * 3)) if not hover else 200, 5)
        elif hover:
            bagliore(s, targa, ROSSO_ALLARME, 8, 120, 5)
        s.blit(pannello(targa.w, targa.h, (40, 30, 30), (16, 12, 14), 8), targa)
        pygame.draw.rect(s, ORO if aperta else BORDEAUX_CHIARO, targa, 2, border_radius=8)
        testo(s, "PORTA USCITA", font(22, bold=True), ORO_CHIARO if aperta else PERGAMENA, (targa.centerx, targa.top + 19))
        stato = "Clicca per aprire" if aperta else "Sbarrata  ·  %d/%d frammenti" % (len(self.risolti), N_ENIGMI)
        testo(s, stato, font(15, italic=True), VERDE_CHIARO if aperta else (230, 120, 110), (targa.centerx, targa.top + 42))
        return hover

    def _disegna_frammenti(self, s, t):
        riquadro = pygame.Rect(170, 596, 840, 118)
        s.blit(pannello(riquadro.w, riquadro.h, PERGAMENA, PERGAMENA_SCURA, 10), riquadro)
        pygame.draw.rect(s, BORDEAUX, riquadro, 3, border_radius=10)
        angoli_ornati(s, riquadro.inflate(-12, -12), BORDEAUX, 12)
        testo(s, "FRAMMENTI DELLA CHIAVE", font(17, bold=True), BORDEAUX_SCURO, (riquadro.centerx, riquadro.top + 16),
              ombra=False)
        sw, gap = 112, 26
        x0 = riquadro.centerx - (sw * N_ENIGMI + gap * (N_ENIGMI - 1)) // 2
        for i, e in enumerate(ENIGMI):
            r = pygame.Rect(x0 + i * (sw + gap), riquadro.top + 32, sw, 56)
            if e["id"] in self.risolti:
                pygame.draw.rect(s, (250, 240, 214), r, border_radius=8)
                pygame.draw.rect(s, ORO_SCURO, r, 2, border_radius=8)
                testo(s, e["frammento"], font(34, bold=True), BORDEAUX, r.center, ombra=False)
            else:
                pygame.draw.rect(s, (214, 196, 158), r, border_radius=8)
                for k in range(0, r.w, 12):   # bordo tratteggiato
                    pygame.draw.line(s, (150, 124, 90), (r.left + k, r.top), (r.left + min(r.w, k + 6), r.top), 2)
                    pygame.draw.line(s, (150, 124, 90), (r.left + k, r.bottom - 1), (r.left + min(r.w, k + 6), r.bottom - 1), 2)
                testo(s, "? ? ?", font(26, bold=True), (150, 124, 90), r.center, ombra=False)
            testo(s, e["nome"], font(13, italic=True), (110, 84, 60), (r.centerx, r.bottom + 12), ombra=False)
            if i < N_ENIGMI - 1:
                testo(s, "+", font(30, bold=True), BORDEAUX, (r.right + gap // 2, r.centery), ombra=False)

    def _disegna_toast(self, s):
        if not self.toast:
            return
        msg, t0, col = self.toast
        eta = time.monotonic() - t0
        if eta > 4.0:
            self.toast = None
            return
        alpha = 255 if eta < 3.2 else int(255 * (4.0 - eta) / 0.8)
        f = font(21, bold=True)
        w = f.size(msg)[0] + 60
        r = pygame.Rect(0, 0, w, 40)
        r.center = (W // 2, 742)
        box = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(box, (12, 8, 10, int(alpha * 0.85)), box.get_rect(), border_radius=20)
        pygame.draw.rect(box, col + (alpha,), box.get_rect(), 2, border_radius=20)
        s.blit(box, r)
        testo(s, msg, f, col, r.center, alpha=alpha)

    def _disegna_intro(self, s, mouse, t):
        self.velo.fill((6, 4, 6, 215))
        s.blit(self.velo, (0, 0))
        s.blit(alone((255, 190, 100), 380, 60), (W // 2 - 380, 330 - 380))
        coccarda(s, (W // 2, 92), 40)
        testo(s, "IL SEGRETO DEL CARBONARO", font(64, bold=True), ORO, (W // 2, 186))
        fregio(s, (W // 2, 232), 520, ORO_SCURO)
        testo(s, "Torino  ·  4 maggio 1860", font(26, italic=True), PERGAMENA, (W // 2, 264))
        foglio = pygame.Rect(0, 0, 860, 276)
        foglio.midtop = (W // 2, 300)
        s.blit(self.carta_intro, foglio)
        pygame.draw.rect(s, BORDEAUX, foglio, 3, border_radius=14)
        angoli_ornati(s, foglio.inflate(-20, -20), BORDEAUX)
        paragrafo(s, TRAMA, font(22, italic=True), INCHIOSTRO, foglio.centerx, foglio.top + 32, foglio.w - 110, 1.25)
        hover = self.btn_inizia.disegna(s, mouse)
        testo(s, "Premi Invio o clicca per iniziare  ·  il timer partirà subito", font(16, italic=True),
              (180, 160, 130), (W // 2, 728))
        return hover

    def _disegna_vittoria(self, s, t):
        dt_ev = time.monotonic() - self.t_evento
        s.blit(self.fondo_vittoria, (0, 0))
        # raggi di luce dorata
        raggi = pygame.Surface((W, H), pygame.SRCALPHA)
        c = (W // 2, 210)
        for k in range(18):
            a = t * 0.12 + k * math.tau / 18
            p1 = (c[0] + math.cos(a - 0.07) * 1500, c[1] + math.sin(a - 0.07) * 1500)
            p2 = (c[0] + math.cos(a + 0.07) * 1500, c[1] + math.sin(a + 0.07) * 1500)
            pygame.draw.polygon(raggi, (255, 214, 120, 22), [c, p1, p2])
        s.blit(raggi, (0, 0))
        s.blit(alone((255, 220, 140), 360, 120), (c[0] - 360, c[1] - 360))
        # fasce tricolori
        for i, col in enumerate(TRICOLORE):
            pygame.draw.rect(s, col, (i * W // 3, 0, W // 3 + 1, 12))
            pygame.draw.rect(s, col, (i * W // 3, H - 12, W // 3 + 1, 12))
        comparsa = min(1.0, dt_ev / 1.2)
        testo(s, "SEI FUGGITO!", font(34, bold=True), PERGAMENA, (W // 2, 70), alpha=255 * comparsa)
        scala = 1.0 + 0.6 * (1 - min(1.0, dt_ev / 0.8)) ** 3
        img, glow, ombra = self.scritte_vittoria
        if scala > 1.001:
            dim = (int(img.get_width() * scala), int(img.get_height() * scala))
            img, glow, ombra = (pygame.transform.smoothscale(x, dim) for x in (img, glow, ombra))
        glow.set_alpha(int(60 + 40 * math.sin(t * 3)))
        r = img.get_rect(center=(W // 2, 190))
        for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
            s.blit(glow, r.move(ox, oy))
        ombra.set_alpha(150)
        s.blit(ombra, r.move(5, 6))
        s.blit(img, r)
        testo(s, "La parola d'ordine era giusta: l'uscita segreta si apre sui vicoli di Torino.",
              font(22, italic=True), PERGAMENA, (W // 2, 272), alpha=255 * comparsa)
        testo(s, "Tempo rimasto: %s  ·  Il messaggio raggiungerà Quarto prima che Garibaldi salpi!"
              % formatta_tempo(self.tempo_congelato or 0), font(22, bold=True), ORO_CHIARO, (W // 2, 306),
              alpha=255 * comparsa)
        foglio = pygame.Rect(0, 0, 900, 360)
        foglio.midtop = (W // 2, 348)
        s.blit(self.carta_vittoria, foglio)
        pygame.draw.rect(s, BORDEAUX, foglio, 3, border_radius=14)
        angoli_ornati(s, foglio.inflate(-20, -20), BORDEAUX)
        testo(s, "Curiosità finale: il telegramma di Garibaldi", font(27, bold=True), BORDEAUX_SCURO,
              (foglio.centerx, foglio.top + 36), ombra=False)
        fregio(s, (foglio.centerx, foglio.top + 66), 360, BORDEAUX)
        paragrafo(s, CURIOSITA_FINALE, font(27, italic=True), INCHIOSTRO, foglio.centerx, foglio.top + 86,
                  foglio.w - 110, 1.16)
        ceralacca(s, (foglio.right - 50, foglio.bottom - 38), 24, "G", font(22, bold=True))
        for cf in self.coriandoli:
            x, y, _, _, ang, dim, col = cf
            w2 = abs(math.cos(ang)) * dim + 1
            pygame.draw.rect(s, col, (int(x), int(y), int(w2 * 2), int(dim * 1.6)))
        testo(s, "R: gioca ancora   ·   Esc: esci   ·   F11: finestra/schermo intero", font(19, italic=True),
              PERGAMENA_SCURA, (W // 2, 752))

    def _disegna_sconfitta(self, s, t):
        dt_ev = time.monotonic() - self.t_evento
        s.blit(self.fondo_sconfitta, (0, 0))
        s.blit(alone((255, 60, 40), 300, int(80 + 30 * math.sin(t * 2))), (W // 2 - 300, 300 - 300))
        sx = int(math.sin(dt_ev * 50) * 14 * max(0.0, 1 - dt_ev / 0.8)) if dt_ev < 0.8 else 0
        testo(s, "GAME OVER", font(34, bold=True), (255, 190, 180), (W // 2 + sx, 150))
        testo(s, "I gendarmi hanno sfondato la porta!", font(62, bold=True), BIANCO, (W // 2 + sx, 250))
        fregio(s, (W // 2, 312), 520, (255, 160, 150))
        testo(s, "Il tempo è scaduto: sei stato arrestato e il messaggio per Garibaldi non partirà mai.",
              font(24, italic=True), (255, 214, 206), (W // 2, 360))
        testo(s, "Frammenti della chiave recuperati: %d/%d" % (len(self.risolti), N_ENIGMI), font(26, bold=True), ORO_CHIARO,
              (W // 2, 430))
        frammenti = "  ".join(e["frammento"] if e["id"] in self.risolti else "???" for e in ENIGMI)
        testo(s, frammenti, font(34, bold=True), PERGAMENA, (W // 2, 480))
        testo(s, "R: riprova   ·   Esc: esci", font(22, italic=True), (255, 200, 190), (W // 2, 640))
        if self.lampo > 0:
            self.velo.fill((255, 40, 30, int(200 * self.lampo)))
            s.blit(self.velo, (0, 0))

    # ---- ciclo principale
    def esegui(self):
        orologio = pygame.time.Clock()
        pygame.key.set_repeat(400, 35)
        try:
            pygame.key.start_text_input()
        except (AttributeError, pygame.error):
            pass
        attivo = True
        while attivo:
            dt = min(0.05, orologio.tick(FPS) / 1000.0)
            for e in pygame.event.get():
                if not self.gestisci(e):
                    attivo = False
                    break
            self.aggiorna(dt)
            self.disegna(dt)


def main():
    try:
        pygame.mixer.pre_init(22050, -16, 1, 512)
    except Exception:
        pass
    pygame.init()
    try:
        Gioco().esegui()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
    sys.exit(0)
