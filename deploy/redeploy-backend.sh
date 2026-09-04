set -euo pipefail

APP_DIR="/home/datascience/NCD_SocialImpact"

cd "$APP_DIR"
git pull

cd "$APP_DIR/backend"
venv/bin/pip install -r requirements.txt

sudo systemctl restart ncd-app