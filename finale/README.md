# Il Segreto del Carbonaro · versione finale (3D)

Escape room ambientata a Torino, 4 maggio 1860: stesso gioco, stessi enigmi e stessa storia della versione 3D nella
radice della repository (`il_segreto_del_carbonaro_3d.py`), con in più:

- un **menu Grafica** nella schermata di pausa, con quattro livelli;
- alcune **ottimizzazioni** che fanno girare il gioco più fluido anche a grafica massima;
- uno script (`crea_exe.bat`) per ottenere un **eseguibile Windows** senza installare Python.

La versione 3D originale e la versione 2D nella radice non sono state toccate.

## Avvio dal codice

Serve Python 3.10 o più recente.

```bash
cd finale
pip install -r requirements.txt
python il_segreto_del_carbonaro_finale.py
```

Comandi di gioco: WASD / frecce per muoversi · Maiusc corri · Spazio salta · Ctrl accovacciati · mouse per guardare ·
clic per esaminare gli oggetti · Invio per confermare · **Esc: pausa** · M audio · C pianta della ferrovia ·
F11 schermo intero · R per rigiocare a fine partita. Tutta la storia e le soluzioni sono nel README della radice.

## Menu Grafica

Premi **Esc** per mettere in pausa: sotto "IN PAUSA" compaiono quattro pulsanti. Si scelgono con un clic oppure con i
tasti **1-4**. Un clic sui pulsanti non fa riprendere il gioco (per riprendere clicca altrove). La scelta viene
**ricordata** tra un avvio e l'altro nel file `.il_segreto_del_carbonaro.json`, nella cartella personale dell'utente
(per esempio `C:\Users\nome\.il_segreto_del_carbonaro.json`); se il file manca si parte da **Media**.

| Livello | Luci per pixel | Riflessi lucidi | Risoluzione della scena 3D | Polvere |
|---|---|---|---|---|
| 1 Bassa | 6 più vicine | no | 65% | 12 granelli |
| 2 **Media** (predefinito) | 10 più vicine | no | 85% | 40 |
| 3 Alta | 16 più vicine | sì | 100% | 40 |
| 4 Max | tutte (36) | sì | 100% | 40 |

**Max è identico alla versione 3D originale** (stesse luci, stessi riflessi, risoluzione piena): confrontando le
immagini pixel per pixel la differenza media è di 1-2 su 255, dovuta solo allo sfarfallio casuale delle candele.

Come funziona:

- **Luci.** Lo shader (GLSL) riceve tre valori: quante luci contare, il raggio massimo oltre cui una luce è ignorata e se
  i riflessi sono accesi. A ogni fotogramma le luci sono ordinate dalla più vicina alla telecamera; lo shader si ferma
  dopo le prime *n* e salta quelle lontane o nell'altra stanza. Le luci dell'altra stanza e quelle spente passano in
  fondo alla lista, così non occupano posti inutilmente.
- **Risoluzione.** La scena 3D viene disegnata in un buffer più piccolo e poi stesa a tutta finestra; l'interfaccia
  (testi, pulsanti, timer) ha la sua telecamera e resta sempre nitida. Se la scheda grafica non riesce a creare il
  buffer, il gioco torna da solo alla risoluzione piena e il menu lo segnala.

## Ottimizzazioni (valgono per tutti i livelli)

Misurando il gioco è emerso che su un PC normale **il limite non è la scheda grafica ma la CPU**:

1. **Ciclo di Ursina.** La scena ha circa 3900 oggetti (ogni cubetto è un'entità) e Ursina li scorreva tutti a ogni
   fotogramma per chiamarne `update` e `input`, anche se ne servono solo 87. Gli altri sono stati tolti da quella lista
   (restano nella scena e si vedono uguali).
2. **Archivio nascosto a passaggio chiuso.** Finché la libreria non scorre, tutto ciò che sta nell'archivio segreto viene
   nascosto: dietro il muro non si vede, ma prima veniva disegnato comunque quando nello studio si guardava a nord.

## Prestazioni misurate

Misurate su un solo PC (NVIDIA GTX 1050 Ti, finestra 1280x720; mediana di tre prove da 2 secondi per ogni punto).
**Sulla grafica integrata del secondo PC non è stato possibile provare il gioco**: i numeri riguardano solo questo PC.
60 FPS è il tetto raggiunto in questi test, non un limite del gioco.

| Punto della mappa | 3D originale | Bassa | Media | Alta | Max |
|---|---|---|---|---|---|
| Studio, verso la porta | 46 | 60 | 60 | 60 | 60 |
| Studio, verso il camino | 31 | 60 | 60 | 60 | 60 |
| Archivio, ingresso | 37 | 48 | 46 | 47 | 47 |
| Archivio, plastico dall'alto | 39 | 51 | 50 | 51 | 51 |

Su questa scheda i quattro livelli danno FPS simili, perché a monte c'è comunque il limite della CPU: i livelli
Bassa/Media riducono il lavoro della scheda grafica (luci, riflessi, pixel) e dovrebbero servire dove è questa a
limitare, ma questo non è stato verificato su una grafica integrata.

## Eseguibile (.exe)

Su Windows, con Python 3.10+ installato, basta fare doppio clic su **`crea_exe.bat`** (oppure lanciarlo da cmd nella
cartella `finale`). Installa le dipendenze e PyInstaller e produce `dist\IlSegretoDelCarbonaro.exe` (un solo file, senza
finestra nera). La prima volta ci vogliono alcuni minuti. L'exe pronto si scarica anche dalla pagina **Releases** della
repository: non serve Python per usarlo.

Il comando eseguito dal bat è:

```bash
python -m PyInstaller --noconfirm --clean --onefile --windowed --name IlSegretoDelCarbonaro ^
    --collect-all ursina --collect-all panda3d --collect-all direct il_segreto_del_carbonaro_finale.py
```

## Cosa non è stato fatto

- **Unione della geometria per ridurre i draw call: scartata.** Provando a fondere la scena con `flattenStrong` il numero
  di geometrie non cambia (1256 prima e dopo, perché ogni oggetto ha uno stato di disegno proprio: texture, parametri
  dello shader, colore) e il guadagno misurato è piccolo. Unirle a mano avrebbe richiesto di toccare colori, texture,
  oggetti animati e i collider usati dal mirino, per un risparmio stimato di pochi millisecondi: troppo rischio per
  troppo poco.
