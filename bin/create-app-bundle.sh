#!/bin/bash
# Script pour créer IndexaoManager.app bundle

APP_NAME="IndexaoManager"
APP_PATH="$HOME/Applications/$APP_NAME.app"
CONTENTS="$APP_PATH/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

# Nettoyer l'ancienne app si elle existe
rm -rf "$APP_PATH"

# Créer la structure
mkdir -p "$MACOS"
mkdir -p "$RESOURCES"

# Créer Info.plist
cat > "$CONTENTS/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>fr</string>
    <key>CFBundleExecutable</key>
    <string>IndexaoManager</string>
    <key>CFBundleIdentifier</key>
    <string>com.indexao.manager</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>IndexaoManager</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Créer le launcher script
cat > "$MACOS/IndexaoManager" << 'EOF'
#!/bin/bash
# Launcher for IndexaoManager.app
# Logs to /tmp/indexaomanager.app.log for troubleshooting
exec > /tmp/indexaomanager.app.log 2>&1

PY_APP_DIR="/Users/phil/Library/CloudStorage/Dropbox/devwww/app/indexao"
PY_BIN="$PY_APP_DIR/venv/bin/python"

if [ ! -x "$PY_BIN" ]; then
    echo "Python venv introuvable: $PY_BIN" >&2
    exit 1
fi

cd "$PY_APP_DIR" || exit 1
echo "Lancement IndexaoManager via $PY_BIN" >&2
"$PY_BIN" IndexaoManager.py
EOF

# Rendre exécutable
chmod +x "$MACOS/IndexaoManager"

echo "✅ App créée: $APP_PATH"
echo "Pour lancer: open $APP_PATH"
echo "Ou double-cliquez dans Applications"
