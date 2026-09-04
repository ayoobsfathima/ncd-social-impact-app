set -euo pipefail

SERVER_USER="datascience"
SERVER_HOST="datascience-virtual-machine"
REMOTE_DIST="/home/datascience/NCD_SocialImpact/frontend/dist"

cd "$(dirname "$0")/../frontend"
npm ci
npm run build

if command -v rsync >/dev/null 2>&1; then
    rsync -avz --delete dist/ "$SERVER_USER@$SERVER_HOST:$REMOTE_DIST/"
else
    # fallback for plain Git Bash on Windows without rsync
    scp -r dist/* "$SERVER_USER@$SERVER_HOST:$REMOTE_DIST/"
fi