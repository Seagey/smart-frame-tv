#!/bin/bash
# Turn the daily picture on or off on this computer.
#
#   scripts/schedule.sh install    run `smartframe run --when-due` every 5 minutes, in the background
#   scripts/schedule.sh remove     stop it and remove the schedule
#   scripts/schedule.sh status     say whether it is on, and show the end of the log
#
# Every 5 minutes is not one picture every 5 minutes: `--when-due` does nothing until the time set in
# config.json ("schedule"), and does nothing while the TV is off. That way a TV switched on at noon
# still gets the day's picture, without you doing anything.
#
# macOS: a launchd agent (~/Library/LaunchAgents). Linux: a systemd user timer, or a cron line if
# systemd is not there. Windows: not tested; use Task Scheduler (README, "Windows").

set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$ROOT/.venv/bin/smartframe"
CONFIG="$ROOT/config.json"
LOG="$ROOT/data/smartframe.log"
LABEL="io.github.smart-frame-tv"
ACTION="${1:-status}"

if [ "$ACTION" = "install" ]; then
  [ -x "$BIN" ] || { echo "Set up first: python3 -m venv .venv && .venv/bin/pip install -e ."; exit 1; }
  [ -f "$CONFIG" ] || { echo "No config.json yet: copy config.example.json to config.json and fill it in."; exit 1; }
  mkdir -p "$ROOT/data"
fi

case "$(uname -s)" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
    case "$ACTION" in
      install)
        mkdir -p "$HOME/Library/LaunchAgents"
        cat > "$PLIST" << PLIST_END
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$BIN</string>
    <string>--config</string><string>$CONFIG</string>
    <string>run</string><string>--when-due</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string></dict>
  <key>StartInterval</key><integer>300</integer>
  <key>RunAtLoad</key><true/>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_END
        launchctl bootout "gui/$(id -u)/$LABEL" 2> /dev/null
        launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "On. It checks every 5 minutes. Log: data/smartframe.log"
        ;;
      remove)
        launchctl bootout "gui/$(id -u)/$LABEL" 2> /dev/null
        rm -f "$PLIST" && echo "Off. No more new pictures."
        ;;
      *)
        if launchctl print "gui/$(id -u)/$LABEL" > /dev/null 2>&1; then echo "On (launchd: $LABEL)"; else echo "Off"; fi
        [ -f "$LOG" ] && tail -n 5 "$LOG"
        ;;
    esac
    ;;
  Linux)
    UNIT_DIR="$HOME/.config/systemd/user"
    if command -v systemctl > /dev/null 2>&1 && systemctl --user show-environment > /dev/null 2>&1; then
      case "$ACTION" in
        install)
          mkdir -p "$UNIT_DIR"
          printf '[Unit]\nDescription=Smart Frame TV daily picture\nAfter=network-online.target\n\n[Service]\nType=oneshot\nWorkingDirectory=%s\nExecStart="%s" --config "%s" run --when-due\n' \
            "$ROOT" "$BIN" "$CONFIG" > "$UNIT_DIR/smart-frame-tv.service"
          printf '[Unit]\nDescription=Smart Frame TV, every 5 minutes\n\n[Timer]\nOnBootSec=1min\nOnUnitActiveSec=5min\n\n[Install]\nWantedBy=timers.target\n' \
            > "$UNIT_DIR/smart-frame-tv.timer"
          systemctl --user daemon-reload
          systemctl --user enable --now smart-frame-tv.timer && echo "On. It checks every 5 minutes. Log: journalctl --user -u smart-frame-tv"
          echo "So it also runs when nobody is logged in: sudo loginctl enable-linger $USER"
          ;;
        remove)
          systemctl --user disable --now smart-frame-tv.timer 2> /dev/null
          rm -f "$UNIT_DIR/smart-frame-tv.service" "$UNIT_DIR/smart-frame-tv.timer"
          systemctl --user daemon-reload
          echo "Off. No more new pictures."
          ;;
        *)
          systemctl --user is-active smart-frame-tv.timer > /dev/null 2>&1 && echo "On (systemd user timer)" || echo "Off"
          journalctl --user -u smart-frame-tv -n 5 --no-pager 2> /dev/null
          ;;
      esac
    else
      LINE="*/5 * * * * cd \"$ROOT\" && \"$BIN\" --config \"$CONFIG\" run --when-due >> \"$LOG\" 2>&1"
      case "$ACTION" in
        install)
          ( crontab -l 2> /dev/null | grep -v "smartframe" ; echo "$LINE" ) | crontab - && echo "On (cron, every 5 minutes). Log: data/smartframe.log"
          ;;
        remove)
          crontab -l 2> /dev/null | grep -v "smartframe" | crontab - && echo "Off. No more new pictures."
          ;;
        *)
          crontab -l 2> /dev/null | grep -q "smartframe" && echo "On (cron)" || echo "Off"
          [ -f "$LOG" ] && tail -n 5 "$LOG"
          ;;
      esac
    fi
    ;;
  *)
    echo "This script knows macOS and Linux. On Windows use Task Scheduler (README, \"Windows\")."
    exit 1
    ;;
esac
