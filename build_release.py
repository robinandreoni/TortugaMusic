"""
Build Automation Script per Tortuga Music & Tortuga TV
Aggiorna la versione in tutti i punti dell'app (Gradle, Python, UI HTML)
e genera sia l'APK firmato che l'AAB (Android App Bundle) per Google Play.
"""

import os
import sys
import re
import shutil
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANDROID_DIR = os.path.join(BASE_DIR, "android")
APP_DIR = os.path.join(ANDROID_DIR, "app")
SRC_DIR = os.path.join(APP_DIR, "src", "main")
GRADLE_BAT = shutil.which("gradle") or os.path.join(ANDROID_DIR, "gradlew.bat")
JBR_DIR = os.environ.get("JAVA_HOME") or (r"C:\Program Files\Android\Android Studio\jbr" if os.path.exists(r"C:\Program Files\Android\Android Studio\jbr") else "")

GRADLE_FILE = os.path.join(APP_DIR, "build.gradle")
SERVER_PY = os.path.join(SRC_DIR, "python", "server.py")
INDEX_HTML = os.path.join(SRC_DIR, "python", "static", "index.html")
TV_HTML = os.path.join(SRC_DIR, "python", "static", "tv.html")

def get_current_version():
    with open(GRADLE_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    vc_m = re.search(r'versionCode\s+(\d+)', content)
    vn_m = re.search(r'versionName\s+["\']([^"\']+)["\']', content)
    vc = int(vc_m.group(1)) if vc_m else 20
    vn = vn_m.group(1) if vn_m else "3.6"
    return vc, vn

def update_version(new_code, new_name):
    print(f"\n[+] Aggiornamento versione: Code={new_code}, Name='{new_name}'")
    
    # 1. build.gradle
    with open(GRADLE_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'versionCode\s+\d+', f'versionCode {new_code}', content)
    content = re.sub(r'versionName\s+["\'][^"\']+["\']', f'versionName "{new_name}"', content)
    with open(GRADLE_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print("  ✓ android/app/build.gradle aggiornato")

    # 2. server.py
    if os.path.exists(SERVER_PY):
        with open(SERVER_PY, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r'"version":\s*"[^"]+"', f'"version": "{new_name}"', content)
        with open(SERVER_PY, "w", encoding="utf-8") as f:
            f.write(content)
        print("  ✓ server.py (/api/health) aggiornato")

    # 3. index.html
    if os.path.exists(INDEX_HTML):
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r'href="/static/style\.css\?v=[^"]+"', f'href="/static/style.css?v={new_name}"', content)
        content = re.sub(r'src="/static/app\.js\?v=[^"]+"', f'src="/static/app.js?v={new_name}"', content)
        content = re.sub(r'<div class="app-version">Tortuga Music v[^•]+•', f'<div class="app-version">Tortuga Music v{new_name} •', content)
        content = re.sub(r'<span class="info-tag">v[^<]+Premium</span>', f'<span class="info-tag">v{new_name} Premium</span>', content)
        with open(INDEX_HTML, "w", encoding="utf-8") as f:
            f.write(content)
        print("  ✓ index.html (UI & Cache Busters) aggiornato")

    # 4. tv.html
    if os.path.exists(TV_HTML):
        with open(TV_HTML, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r'TortugaTV\s*•\s*v[^\s<]+\s*Integrated', f'TortugaTV • v{new_name} Integrated', content)
        content = re.sub(r'src="/static/app_tv\.js\?v=[^"]+"', f'src="/static/app_tv.js?v={new_name}"', content)
        with open(TV_HTML, "w", encoding="utf-8") as f:
            f.write(content)
        print("  ✓ tv.html (UI & Cache Busters) aggiornato")

def run_build(new_name):
    print("\n[+] Avvio compilazione Gradle (assembleRelease + bundleRelease)...")
    env = os.environ.copy()
    if os.path.exists(JBR_DIR):
        env["JAVA_HOME"] = JBR_DIR

    cmd = [GRADLE_BAT, "assembleRelease", "bundleRelease", "--no-daemon"]
    start_time = time.time()
    
    proc = subprocess.Popen(
        cmd,
        cwd=ANDROID_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="ignore"
    )

    for line in proc.stdout:
        line_clean = line.strip()
        if any(k in line_clean for k in ["> Task", "BUILD SUCCESSFUL", "BUILD FAILED", "FAILED", "warning:"]):
            print(f"  {line_clean}")

    proc.wait()
    duration = time.time() - start_time

    if proc.returncode != 0:
        print(f"\n❌ ERRORE: La compilazione Gradle è fallita con codice {proc.returncode}!")
        return False

    print(f"\n🎉 Compilazione completata con successo in {duration:.1f} secondi!")

    # Copia artefatti
    apk_src = os.path.join(APP_DIR, "build", "outputs", "apk", "release", "app-release.apk")
    aab_src = os.path.join(APP_DIR, "build", "outputs", "bundle", "release", "app-release.aab")

    apk_dst = os.path.join(BASE_DIR, f"TortugaMusic-v{new_name}-Release.apk")
    aab_dst = os.path.join(BASE_DIR, f"TortugaMusic-v{new_name}-Release.aab")

    if os.path.exists(apk_src):
        shutil.copy2(apk_src, apk_dst)
        size_mb = os.path.getsize(apk_dst) / (1024 * 1024)
        print(f"  ✓ APK creato: {apk_dst} ({size_mb:.1f} MB)")
    else:
        print(f"  ⚠️ APK non trovato in {apk_src}")

    if os.path.exists(aab_src):
        shutil.copy2(aab_src, aab_dst)
        size_mb = os.path.getsize(aab_dst) / (1024 * 1024)
        print(f"  ✓ AAB creato: {aab_dst} ({size_mb:.1f} MB)")
    else:
        print(f"  ⚠️ AAB non trovato in {aab_src}")

    return True

if __name__ == "__main__":
    current_vc, current_vn = get_current_version()
    print(f"Versione attuale: Code={current_vc}, Name={current_vn}")

    if len(sys.argv) > 1:
        target_vn = sys.argv[1]
        target_vc = current_vc + 1 if len(sys.argv) < 3 else int(sys.argv[2])
    else:
        target_vn = current_vn
        target_vc = current_vc

    update_version(target_vc, target_vn)
    run_build(target_vn)
