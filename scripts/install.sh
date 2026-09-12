#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Install Rocky on a Raspberry Pi.
#
#   curl -fsSL .../install.sh | sudo bash        (or clone and run it)
#
# Installs to /opt/rocky, creates a `rocky` user, and sets up the service.
# Re-running it is safe: it upgrades in place and leaves your config alone.
# ---------------------------------------------------------------------------
set -euo pipefail

PREFIX=${PREFIX:-/opt/rocky}
USER_NAME=${USER_NAME:-rocky}
REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

say() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  ! \033[0m%s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "run this with sudo" >&2; exit 1; }

say "Checking the machine"
if ! grep -qi raspberry /proc/device-tree/model 2>/dev/null; then
    warn "This does not look like a Raspberry Pi."
    warn "Installing anyway; hardware backends will fall back to simulation."
fi

say "Installing system packages"
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 python3-venv python3-dev python3-pip \
    git i2c-tools libatlas-base-dev \
    python3-picamera2 \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
    libportaudio2 libsndfile1 alsa-utils \
    espeak-ng

say "Enabling I2C"
raspi-config nonint do_i2c 0 2>/dev/null || warn "could not enable I2C automatically"

say "Creating the ${USER_NAME} user"
if ! id -u "$USER_NAME" >/dev/null 2>&1; then
    useradd --system --create-home --home-dir "/home/$USER_NAME" --shell /usr/sbin/nologin "$USER_NAME"
fi
for group in video audio i2c gpio render input; do
    getent group "$group" >/dev/null && usermod -aG "$group" "$USER_NAME"
done

say "Installing to ${PREFIX}"
mkdir -p "$PREFIX"
if [ "$REPO_DIR" != "$PREFIX" ]; then
    # --exclude keeps a previous install's state and config out of the way.
    rsync -a --delete \
        --exclude '.venv' --exclude 'var' --exclude 'config.toml' --exclude '.git' \
        "$REPO_DIR"/ "$PREFIX"/
fi
mkdir -p "$PREFIX/var"

# system-site-packages so picamera2, which comes from apt rather than pip, is
# importable. It cannot be pip-installed reliably on a Pi.
if [ ! -d "$PREFIX/.venv" ]; then
    say "Creating the virtualenv"
    python3 -m venv --system-site-packages "$PREFIX/.venv"
fi

say "Installing Rocky and its dependencies (this takes a few minutes)"
"$PREFIX/.venv/bin/pip" install --quiet --upgrade pip wheel
"$PREFIX/.venv/bin/pip" install --quiet -e "$PREFIX"
"$PREFIX/.venv/bin/pip" install --quiet -e "$PREFIX[hardware]" || \
    warn "some hardware extras failed; run 'rocky check' to see what is missing"

say "Speech engines"
if ! "$PREFIX/.venv/bin/pip" install --quiet -e "$PREFIX[speech]"; then
    warn "faster-whisper / piper / openwakeword did not install."
    warn "Rocky will fall back to espeak-ng and speech-triggered wake."
fi

if [ ! -f "$PREFIX/config.toml" ]; then
    say "Writing a starter config"
    cp "$PREFIX/config.example.toml" "$PREFIX/config.toml"
fi

mkdir -p /etc/rocky
if [ ! -f /etc/rocky/rocky.env ]; then
    cp "$PREFIX/systemd/rocky.env.example" /etc/rocky/rocky.env
    chmod 600 /etc/rocky/rocky.env
    warn "Put your ANTHROPIC_API_KEY in /etc/rocky/rocky.env"
fi

chown -R "$USER_NAME:$USER_NAME" "$PREFIX"

say "Installing the service"
install -m 644 "$PREFIX/systemd/rocky.service" /etc/systemd/system/rocky.service
systemctl daemon-reload
systemctl enable rocky.service

cat <<EOF

  Rocky is installed.

    Check the hardware     sudo -u $USER_NAME $PREFIX/.venv/bin/rocky check
    Centre the servos      sudo -u $USER_NAME $PREFIX/.venv/bin/rocky calibrate pan
    Start                  sudo systemctl start rocky
    Watch the log          journalctl -u rocky -f
    Dashboard              http://\$(hostname -I | awk '{print \$1}'):8080

  Put your API key in /etc/rocky/rocky.env before starting, or Rocky will
  come up able to move and chirp but not to talk.

EOF
