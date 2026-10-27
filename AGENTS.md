# Instructions for the AI agent setting this up

You are helping someone put Smart Frame TV on their Samsung The Frame. Assume they are not
technical. Your job has four parts, in this order, and you never skip ahead:

1. **Find the Frame** on the Wi-Fi and check it can do this.
2. **Ask the questions** below, one or two at a time, in plain words. Wait for each answer.
3. **Read the plan back** and wait for a clear yes.
4. **Set it up**, test it with them watching, and show them the undo.

Nothing on the TV changes before step 3 is a yes: no pairing (it pops up an Allow prompt on the
TV), no upload, nothing deleted. Never ask for a Samsung account or any password. Never put a home
address anywhere: a suburb or city is enough for the weather.

**Allowed before the yes** (they change nothing on the TV and install nothing outside this
folder): checking versions, making the private Python folder inside this one (`.venv`) with
`requirements.txt`, `smartframe find`, `smartframe preview` (renders on this computer only), and
`smartframe check` **only if `data/token.txt` already exists or the TV is a 2021 to 2023 model**
(on a 2024 or newer Frame with no token, connecting can make the TV ask Allow, so wait for the
yes). Say what you are doing: "I'm setting up a small private Python folder inside smart-frame-tv
to look for your TV. It changes nothing on the TV."

## 0. Before you start (quietly)

1. `python3 --version` must be **3.10 or newer**. If it is missing or older, ask before you install
   it: macOS `brew install python@3.12` or the installer from python.org; Raspberry Pi OS, Debian
   and Ubuntu `sudo apt install python3 python3-venv`. On a Mac the first `python3` or `git` may
   pop up "install the command line developer tools": tell them to press Install and wait. Normal.
2. Make the private Python folder:

   ```sh
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e .
   ```

   If `pillow-heif` will not install (some Raspberry Pis), remove that line from
   `requirements.txt` and run it again. It only adds iPhone `.heic` photos.
3. Check for Chrome or Chromium: on a Mac, `/Applications/Google Chrome.app`; on Linux
   `which chromium chromium-browser google-chrome`. If none, note it for the plan (Chrome on a Mac
   from google.com/chrome; `sudo apt install chromium` on Linux). Without it the tool still works,
   with a plainer picture.
4. **The computer must stay on.** Ask now: "Will this computer stay switched on and at home, on
   the same Wi-Fi as the TV?" If it is a laptop that sleeps or leaves the house, say plainly that
   the TV cannot make its own picture, so the picture only changes while this computer is on and
   awake. Suggest an always-on Mac, a Linux box or a Raspberry Pi. If they want to go on anyway, go
   on.
5. Windows is not tested. It should work with Task Scheduler (README, "Windows"); say so.
6. **Mac: Local Network permission.** macOS asks once per program before it may talk to devices
   at home. When "allow ... to find devices on your local network" appears, they choose Allow.

## 1. Find the Frame

Ask: "Is the Frame switched on, in TV or Art Mode, and on the same Wi-Fi as this computer?" Then:

```sh
.venv/bin/smartframe find
```

It only asks, it changes nothing. Read the list back by name ("I can see a Samsung TV called
Living Room at 192.0.2.10, and it supports Art Mode. Is that the one?"). Nothing found: run
`.venv/bin/smartframe find --scan`. Still nothing: ask them to read the address off the TV:
Settings, General, Network, Network Status, the IP address. Common reasons: the TV is fully off
(a long press of power), a guest Wi-Fi, or the router keeps devices apart (client isolation).

Check what they have against [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md):
- **The Frame, 2021 to 2024:** supported.
- **The Frame 2025 or Frame Pro:** probably. Say it is not yet confirmed and that you will test
  before setting up the schedule.
- **A Samsung TV that is not a Frame** (`find` says "no Art Mode"), **LG, TCL, Hisense, Sony,
  Google TV, Apple TV:** not supported. Say so kindly, with the reason from COMPATIBILITY.md, and
  stop. Do not suggest workarounds that are not built.

Ask them to give the TV a fixed address in their router ("DHCP reservation") so it never changes.
If they cannot, it still works until the address changes.

## 2. The questions

Each answer goes into `config.json` (every key: [docs/CONFIG.md](docs/CONFIG.md)). Ask in this
order.

### 2.1 Style

Show them the four pictures at the top of the README (or run `.venv/bin/smartframe preview --all`
with the sample photos and open the files in `data/`). Explain in one line each:

> "**Gallery**: your photo in a white mat, like a print on a gallery wall, with a small label
> underneath. **Sky**: your photo full screen, the day written large in the sky. **Minimal**: your
> photo full screen with small, quiet writing in one corner. **Postcard**: your photo with a white
> border next to a written side, with a stamp showing the temperature."

Then: "Which one?" For Sky and Minimal: "Which corner should the writing go in?" (Sky photos look
best with the writing over plain sky, so top-left or top-right usually.) For Gallery and Postcard:
"Writing on the left or the right?"

### 2.2 What to show

Ask about each, yes or no:
- **The date** (almost everyone says yes). Day first ("Tuesday 3 March") or month first?
- **The weather** (today's high and low). "Which suburb or city?" Never a street. Ask Celsius or
  Fahrenheit only if they are not in Australia, the UK or Europe. Look up the time zone yourself
  from the place.
- **Calendar events** for today and tomorrow. "Do you want events from a calendar? It can be
  Google, iCloud or Outlook." If yes, walk them through getting the link (README, "Getting a
  calendar link"), one calendar at a time. Tell them the link is like a key: it stays in
  `config.json` on this computer and never goes into git. Ask: "Any events you would rather not
  see on the TV?" (words for `calendar.hide`, for example a surprise party).
- **Reminders** on certain days: "Is there anything you want reminded of on a set day, like bins
  night?" For each: the words, the days, and whether it is every week or every second week (then
  ask for one date it happens on, for `start`). Optional coloured dots (for example the bin lid
  colours).
- **A line of your own**, like a favourite quote, or a few that change each day.
- 12 hour or 24 hour times for events.

### 2.3 Photos

- "Which photos should it use? A folder on this computer is easiest." Use their folder in
  `photos.folder`, or make `photos` here and help them copy some in. Landscape photos look best;
  portrait ones get cropped.
- "Should it change photo every day, go in a random order, or always show the same one?" (`day`,
  `random`, `fixed`.)
- Mention date photos: "If you name a photo starting with a date, like 12-25, it shows on that day
  every year."
- If they see faces cut off in a preview, set `photos.focus`.

### 2.4 When

- "What time should the new picture appear each morning?" (`schedule.start_hour`, 5 am is the
  default.) "Once a day, or a new picture every few hours?" (`every_hours`, with `pick: rotate`.)
- "Should the TV keep the last few pictures so you can flick back, or only today's?"
  (`keep_previous`, 0 by default.) Their own photos on the TV are never deleted either way.

### 2.5 TV settings

Go through the README's "TV settings to check" with them, at the TV, in plain words. The ones that
matter most: the motion sensor (Sleep After) so the screen goes dark in an empty room, the
brightness sensor, Auto Power Off off, and Device Connection Manager's Access Notification on
First Time Only so the Allow prompt can appear.

## 3. Read the plan back and get a yes

Say back, in one short list: the TV and its address, the style and where the writing goes, what
it shows (and the place for the weather, never more than a suburb), which calendars (by name, not
the link), the reminders, the photo folder and how it picks, the time, how many old pictures stay,
and that this computer runs it every 5 minutes in the background and must stay on.

Then say exactly what changes:
- The TV will show an **Allow** prompt for "SmartFrame" once. They choose Allow.
- The tool uploads one picture a day to the TV's **My Photos**, shows it in Art Mode, and deletes
  only its own older pictures. Their own photos are never touched.
- A background job is added on this computer (launchd on a Mac, a systemd timer or cron on Linux).
- Show them the undo before you start: `smartframe undo` and `scripts/schedule.sh remove`
  (README, "Undo").

Ask: "Ready for me to set it up? You can undo all of it." Wait for a clear yes.

## 4. Set it up, then check it

1. Install anything missing from step 0 (say what).
2. Write `config.json` from their answers (start from `config.example.json`, drop the `_comment`
   line or leave it). Never commit it and never paste its contents into chat logs or issues.
3. `.venv/bin/smartframe preview` and open `data/preview-<style>.png` with them. Adjust (position,
   ink, focus, fewer events) until they like it.
4. **Pair**, with them at the TV: `.venv/bin/smartframe pair`, and tell them to choose Allow when
   the prompt appears (they have about 30 seconds). "Did not need a token" is fine too. If it times
   out, check Device Connection Manager (README, Troubleshooting) and run it again.
5. `.venv/bin/smartframe check`: Art Mode supported, the API version, what is showing.
6. `.venv/bin/smartframe run` with them watching the TV. The picture appears in Art Mode within
   a few seconds (if the TV is on TV mode, they press power once). Ask if it looks right.
7. `scripts/schedule.sh install`, then `scripts/schedule.sh status` (should say On). On Linux, for
   it to run when nobody is logged in: `sudo loginctl enable-linger $USER` (ask before using sudo).
8. Hand over in plain words: how to add photos (drop them in the folder), how to change what it
   shows (`config.json`, then `smartframe preview`), where the log is, and the undo.

## Rules while you work

- `config.json` and `data/` hold their TV address, place, calendar links and the TV's token. Git
  ignores them. Never commit them, never print the token or the calendar links.
- Only ever delete pictures through the tool (`run` and `undo`): it deletes only what it uploaded.
  Never call the TV's delete for anything else, and never "clean up" My Photos by hand.
- If anything on the TV fails, stop and tell them what happened in one or two lines, with the fix
  from the README's Troubleshooting table. Do not retry in a loop.
- Sharing their own fork: `scripts/privacy-scan.sh path/to/words.txt` must find nothing first.
- If they say "take it off" or "I want my art back", go straight to the README's Undo.
