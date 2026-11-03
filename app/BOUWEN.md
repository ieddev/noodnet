# De Noodnet-app bouwen (Sideband 2.1.0 + Noodnet-patch)

De app is Sideband met daarin het M/ETHANE-scherm, de aanmeldkaart met
ingebouwde QR-scanner, automatisch aanmelden en een zuinig positiebaken.
Getest op Ubuntu 24.04 / Zorin (ook WSL2 kan; werk dan in de Linux-thuismap).
Ruimte: minimaal 20 GB. Eerste bouw 1-2 uur, daarna enkele minuten.

## 1. Benodigdheden (eenmalig)

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
    autoconf automake libtool pkg-config zlib1g-dev libncurses-dev libtinfo6 \
    cmake libffi-dev libssl-dev build-essential ccache patch patchelf \
    libogg-dev libopus-dev
python3 -m venv ~/bouwvenv && source ~/bouwvenv/bin/activate
pip install buildozer "cython==0.29.36" setuptools rich

# codec2 heeft tijdens het bouwen 'generate_codebook' voor de pc nodig
git clone https://github.com/markqvist/codec2.git ~/codec2-host
gcc -O2 -o /tmp/generate_codebook ~/codec2-host/src/generate_codebook.c -lm
sudo cp /tmp/generate_codebook /usr/local/bin/
```

## 2. Broncode (vier echte git-clones naast elkaar in je thuismap)

```bash
cd ~
git clone https://github.com/markqvist/Reticulum.git
git clone https://github.com/markqvist/LXMF.git
git clone https://github.com/markqvist/LXST.git
git clone https://github.com/markqvist/Sideband.git
git clone https://github.com/ieddev/noodnet.git
cd Sideband && git checkout 2.1.0 && git switch -c noodnet
git apply ~/noodnet/app/noodnet_sideband_2.1.0.patch
git add -A && git commit -m "Noodnet"
```

Nodig: Reticulum >= 1.2.0, LXMF >= 0.9.6, LXST >= 0.4.6.

Naast de Noodnet-schermen repareert de patch de bouw buiten de computer van de
Sideband-maker:

- `buildozer.spec`: python-for-android vast op develop-commit `ee326409`
  (7 okt 2025); `cryptography` weggelaten (alleen voor Webshare-HTTPS);
  Google Code Scanner (QR) toegevoegd.
- `Makefile` + `noodnet_constraints.txt`: `build<1.4.3` (nieuwere versies
  maken PYTHONPATH leeg); pycodec2 ook in `python-installs` patchen.
- `recipes/lxst`: bron uit `~/LXST`; `recipes/python3`: `pybuilddir.txt` wijst
  naar de host-modules; `recipes/numpy`: ontbrekende `#include <unordered_map>`.

## 3. Bouwen

```bash
source ~/bouwvenv/bin/activate
cd ~/Sideband/sbapp
make prepare prebake pacthfiles injectlibs debug postbuild 2>&1 | tee ~/bouw.log
```

- **Niet** `make devapk` (de stap `fetchshare` zoekt bestanden van de Sideband-maker).
  `pacthfiles` is echt zo gespeld.
- De `prebake`-stap mag eindigen met "Buildozer failed" (Gradle); daarna gaat het verder.
- Klaar bij: `APK sideband-1.9.2-arm64-v8a-debug.apk available in the bin directory`.
- Fout zoeken: `grep -n -B40 "Command failed" ~/bouw.log`

## 4. Sleutel bewaren

De APK wordt ondertekend met `~/.android/debug.keystore`. **Bewaar die op een
veilige plek** (niet in deze repository). Met een andere sleutel kunnen updates
niet over de geïnstalleerde app heen.

## 5. Publiceren (zodat elke Pi hem aanbiedt)

Zet de APK als release op GitHub, met de vaste naam `noodnet.apk`:

```bash
cp ~/Sideband/sbapp/bin/sideband-*-arm64-v8a-debug.apk ~/noodnet.apk
echo "$(date +%Y-%m-%d)" > ~/versie.txt
gh release create app-$(date +%Y%m%d) ~/noodnet.apk ~/versie.txt \
   --repo ieddev/noodnet --title "Noodnet-app $(date +%Y-%m-%d)" --notes "Nieuwe versie van de app"
```

Of via de website: *Releases → Draft a new release*, bestanden `noodnet.apk` en
`versie.txt` toevoegen. Elke Pi haalt bij `noodnet-bijwerken` de nieuwste op.

## 6. Op de telefoon

- Gewone Sideband eerst weg (na een backup via *Backup & Keys*): de handtekening
  verschilt.
- Plugin `send_Telemetry.py` is niet meer nodig (het baken zit in de app).
