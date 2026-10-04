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
"""

import math
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
TEMPO_TOTALE = 15 * 60           # 15:00
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
        "frammento": "OBBE",
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
        "frammento": "DI",
        "curiosita": ("La donna era Rose Montmasson, moglie di Francesco Crispi: unica donna "
                      "della spedizione, curò i feriti e fu soprannominata «l'angelo di "
                      "Calatafimi». Compare nell'elenco ufficiale dei 1089."),
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

TRAMA = ("4 maggio 1860. Sei un corriere della Carboneria, nascosto nello "
         "studio segreto di un patriota torinese. Porti un messaggio che deve "
         "raggiungere Garibaldi prima che salpi da Quarto. Ma qualcuno ha "
         "parlato: i gendarmi hanno circondato il palazzo e stanno forzando "
         "l'ingresso.\n"
         "Il patriota ha nascosto la parola d'ordine che apre l'uscita "
         "segreta in quattro frammenti, custoditi dagli oggetti della stanza. "
         "Hai 15 minuti per decifrare i codici, ricomporre la chiave e fuggire.")

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


ICONE = {"pianoforte": icona_pianoforte, "mappa": icona_mappa,
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
    """Uno dei quattro oggetti cliccabili della stanza."""

    def __init__(self, enigma, rect):
        self.enigma = enigma
        self.rect = pygame.Rect(rect)
        self.fondo = pannello(self.rect.w - 16, self.rect.h - 16, (86, 26, 38), (24, 18, 22), 10)
        self.fondo_ok = pannello(self.rect.w - 16, self.rect.h - 16, (38, 96, 60), (14, 34, 24), 10)
        self.cornice = pannello(self.rect.w, self.rect.h, LEGNO_CHIARO, LEGNO_SCURO, 14)
        self.sollevamento = 0.0
        self.ombra = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(self.ombra, (0, 0, 0, 120), self.ombra.get_rect(), border_radius=14)

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
        ICONE[self.enigma["id"]](s, pygame.Rect(r.x + 10, r.y + 34, r.w - 20, 210), t)
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
            testo(s, "Risolto · «%s»" % self.enigma["frammento"], font(18, bold=True), ORO_CHIARO,
                  (r.centerx, r.bottom - 34))
            ceralacca(s, (r.right - 30, r.top + 30), 20, spunta=True)
        else:
            alpha = 150 + 105 * self.sollevamento
            testo(s, "Clicca per esaminare", font(17, italic=True), PERGAMENA, (r.centerx, r.bottom - 34),
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
            titolo, domanda = "La Porta Uscita", "Inserisci la parola d'ordine unendo i 4 frammenti di chiave trovati."
        else:
            titolo, domanda = self.enigma["titolo"], self.enigma["domanda"]
        testo(s, titolo, font(40, bold=True), BORDEAUX_SCURO, (p.centerx, p.top + 52), ombra=False)
        fregio(s, (p.centerx, p.top + 88), 360, BORDEAUX)
        y = paragrafo(s, "«" + domanda + "»", font(25, italic=True), INCHIOSTRO, p.centerx, p.top + 112,
                      p.w - 120, 1.2)
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
        raggio = int(72 * pulsa)
        s.blit(alone((255, 200, 90), 120, 90), (p.centerx - 120, p.top + 200 - 120))
        ceralacca(s, (p.centerx, p.top + 200), raggio, e["frammento"], font(34 if len(e["frammento"]) > 2 else 46, bold=True))
        testo(s, "Curiosità storica", font(24, bold=True), BORDEAUX, (p.centerx, p.top + 300), ombra=False)
        paragrafo(s, e["curiosita"], font(23, italic=True), INCHIOSTRO, p.centerx, p.top + 330, p.w - 140, 1.2)
        orig = self.btn_continua.rect
        self.btn_continua.rect = orig.move(*off)
        self.btn_continua.disegna(s, mouse)
        self.btn_continua.rect = orig


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
        self.carte = [Carta(e, (40 + i * 232, 150, 208, 372)) for i, e in enumerate(ENIGMI)]
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
            self.mostra_toast("Frammento «%s» trovato! (%d/4)" % (enigma["frammento"], len(self.risolti)),
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
                        self.modale = Modale(self, carta.enigma)
                    return True
            if self.porta_rect.collidepoint(pos):
                if len(self.risolti) < len(ENIGMI):
                    self.suoni.suona("bloccato")
                    self.scuoti_porta = 0.5
                    self.mostra_toast("La porta è sbarrata! Risolvi prima tutti gli enigmi (%d/4)." % len(self.risolti),
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
                cliccabile = any(b.rect.collidepoint(mouse) for b in bott)
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
        testo(s, "Torino, 4 maggio 1860  ·  Studio segreto della Carboneria  ·  Enigmi risolti: %d/4"
              % len(self.risolti), font(19, italic=True), PERGAMENA, (126, 88), "midleft")
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
        stato = "Clicca per aprire" if aperta else "Sbarrata  ·  %d/4 frammenti" % len(self.risolti)
        testo(s, stato, font(15, italic=True), VERDE_CHIARO if aperta else (230, 120, 110), (targa.centerx, targa.top + 42))
        return hover

    def _disegna_frammenti(self, s, t):
        riquadro = pygame.Rect(210, 596, 760, 118)
        s.blit(pannello(riquadro.w, riquadro.h, PERGAMENA, PERGAMENA_SCURA, 10), riquadro)
        pygame.draw.rect(s, BORDEAUX, riquadro, 3, border_radius=10)
        angoli_ornati(s, riquadro.inflate(-12, -12), BORDEAUX, 12)
        testo(s, "FRAMMENTI DELLA CHIAVE", font(17, bold=True), BORDEAUX_SCURO, (riquadro.centerx, riquadro.top + 16),
              ombra=False)
        sw, gap = 150, 42
        x0 = riquadro.centerx - (sw * 4 + gap * 3) // 2
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
            if i < 3:
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
        testo(s, "Frammenti della chiave recuperati: %d/4" % len(self.risolti), font(26, bold=True), ORO_CHIARO,
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
