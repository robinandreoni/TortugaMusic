# TortugaTV — Android TV Edition

Questo è il progetto Android ufficiale per generare l'APK.
Utilizza **Chaquopy** per includere l'intero server Flask (Python) direttamente dentro l'App Android, permettendoti di installare il programma con una normale chiavetta USB su qualsiasi Smart TV Android o Android TV Box.

## Come compilare l'APK

1. Scarica e installa **Android Studio**.
2. Apri Android Studio e clicca su **Open**.
3. Seleziona questa cartella `tv_app/android`.
4. Attendi che Gradle sincronizzi le librerie (scaricherà Chaquopy, Flask, ecc.).
5. Clicca sul menu in alto **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
6. Alla fine del processo, l'APK sarà generato in `tv_app/android/app/build/outputs/apk/debug/app-debug.apk`.

## Come installare sulla TV

1. Copia il file `app-debug.apk` in una pennetta USB.
2. Inserisci la pennetta USB nella Android TV o nel TV Box.
3. Sulla TV, installa un file manager dal Play Store (es. "File Commander" o "FX File Explorer").
4. **IMPORTANTE:** Nelle impostazioni della TV, vai su _Sicurezza e Restrizioni_ e abilita "Sorgenti Sconosciute" per il file manager.
5. Apri il file manager, naviga nella pennetta USB e clicca sull'APK per installarlo.
6. Troverai "TortugaTV" tra le tue app!
