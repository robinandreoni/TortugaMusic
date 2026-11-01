# 📱 Guida Completa: Avviare Tortuga Music & TV dal Telefono (Android)

Puoi decidere in qualsiasi momento se avviare il server dal **PC di casa** (tramite `AVVIA_TORTUGA_ONLINE.bat`) oppure dal **tuo smartphone Android** (tramite `./AVVIA_TORTUGA_ONLINE.sh`). In entrambi i casi, il tuo dominio fisso:
👉 **https://your-subdomain.workers.dev**
si collegherà automaticamente al dispositivo attivo in quel momento!

---

## 🛠️ Passo 1: Installare Termux sul telefono

> [!IMPORTANT]
> **Non** scaricare Termux dal Google Play Store (la versione del Play Store è abbandonata dal 2020 e dà errori di repository).
> Scaricalo gratuitamente da **F-Droid** oppure direttamente dal GitHub ufficiale:
> 🔗 **Download APK diretto**: [Termux GitHub Releases](https://github.com/termux/termux-app/releases/latest) (scegli il file `termux-app_..._arm64-v8a.apk` o `universal.apk`).

Installa l'app e aprila.

---

## 📥 Passo 2: Scaricare il progetto sul telefono

Apri l'app **Termux** e copia/incolla questo comando per scaricare Git e clonare la tua repository (include già l'autorizzazione):

```bash
pkg update -y && pkg install -y git ca-certificates
git clone https://github.com/robinandreoni/TortugaMusic.git
cd TortugaMusic/PC
```

---

## ⚙️ Passo 3: Installazione automatica (da fare una sola volta)

Abbiamo creato uno script che installa Python, FFmpeg, Cloudflared nativo e tutte le librerie necessarie:

```bash
bash INSTALLA_TERMUX.sh
```

Attendi che completi l'installazione di tutti i pacchetti. Al termine vedrai il messaggio `INSTALLAZIONE COMPLETATA CON SUCCESSO!`.

---

## 🚀 Passo 4: Avviare Tortuga dal Telefono!

Per avviare il server online e il Cloudflare Tunnel dal telefono, entra nella cartella e digita:

```bash
./AVVIA_TORTUGA_ONLINE.sh
```

### Cosa fa lo script in automatico:
1. 🔒 **Attiva il Wake-Lock**: impedisce ad Android di addormentare la CPU a schermo spento.
2. 🌐 **Scarica Cloudflared ARM64**: usa il binario ufficiale Cloudflare ottimizzato per smartphone.
3. ⚡ **Avvia Flask (porta 5000)** e il **Tunnel Cloudflare**.
4. 🔄 **Sincronizza il Gist**: aggiorna istantaneamente il Worker di Cloudflare.
5. A schermo vedrai:
   ```
   ============================================================
    [*] TORTUGA ONLINE: https://xxxx-xxxx.trycloudflare.com
    [*] INDIRIZZO FISSO: https://tortuga.cybergrid.workers.dev
   ============================================================
   [OK] Gist aggiornato con successo!
   ```

Tutti gli utenti che apriranno `https://tortuga.cybergrid.workers.dev` saranno ora connessi al tuo smartphone!

---

## ⏹️ Come fermare il server dal telefono
* All'interno di Termux premi la combinazione di tasti:
  **`CTRL` + `C`**
* Lo script fermerà Flask, chiuderà il tunnel Cloudflare e rilascerà il risparmio energetico del telefono.

---

## 💡 Consigli Utili per l'uso da Mobile:
* **Batteria**: Se lasci il server attivo per molto tempo, tieni il telefono collegato al caricatore.
* **Wi-Fi**: Preferisci il Wi-Fi alla rete dati mobile per avere banda illimitata e zero consumo di Giga della SIM.
* **Aggiornamenti futuri**: Quando faremo modifiche dal PC e le caricheremo su GitHub, per averle anche sul telefono basterà digitare in Termux:
  ```bash
  git pull
  ```
