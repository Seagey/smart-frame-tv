# config.json, every setting

Copy `config.example.json` to `config.json` and change what you need. Anything left out uses the
default shown here. `config.json` is ignored by git, so your TV's address, place and calendar links
stay on your computer. After a change, `smartframe preview` shows the result without touching the
TV. A mistake in the file is reported in plain words when any command runs.

## The TV

| Key | Default | Meaning |
|---|---|---|
| `frame.ip` | (none, needed) | The Frame's address on your Wi-Fi, from `smartframe find` or the TV's Network Status. |
| `frame.port` | `8002` | The Frame's secure art connection. Leave it. |
| `frame.name` | `"SmartFrame"` | The name the TV shows in its Allow prompt and Device List. |
| `timezone` | this computer's | Your time zone, like `"Australia/Melbourne"`. Decides what "today" is and when the schedule fires. |
| `chrome` | found by itself | Full path to Chrome, Chromium, Edge or Brave, if it is somewhere unusual. |

## Photos

| Key | Default | Meaning |
|---|---|---|
| `photos.folder` | `"photos"` | The folder of photos. A relative path is inside this folder. `~/Pictures/Frame` works too. |
| `photos.pick` | `"day"` | `"day"`, `"rotate"`, `"random"` or `"fixed"` (README, "Choosing your photos"). |
| `photos.file` | `""` | The photo for `"fixed"`. |
| `photos.focus` | `"centre"` | Which part survives the 16:9 crop: `"centre"`, `"top"`, `"bottom"`, `"left"`, `"right"`. |

File names starting with a month and day (`"12-25 tree.jpg"`) show on that date every year only.

## The look

| Key | Default | Meaning |
|---|---|---|
| `style` | `"gallery"` | `"gallery"`, `"sky"`, `"minimal"` or `"postcard"`. |
| `position` | `"top-left"` | `"top-left"`, `"top-right"`, `"bottom-left"`, `"bottom-right"`. Gallery and postcard use only the left or right part. |
| `ink` | `"auto"` | Sky and minimal: `"auto"` picks dark or light writing from the photo, or force `"dark"` or `"light"`. |
| `mat` | `"#f4f2ee"` | Gallery: the mat colour. |
| `date_order` | `"day-month"` | `"day-month"` (Tuesday 3 March) or `"month-day"` (Tuesday, March 3). |
| `clock` | `"12h"` | Event times as `"9:30 am"` or `"09:30"`. |

## What it shows

`blocks` is a list; the order is the order on the picture. Each entry is `{"type": "..."}` with an
optional `"on": false` to switch it off.

```json
"blocks": [
  {"type": "date"},
  {"type": "weather"},
  {"type": "calendar"},
  {"type": "reminders"},
  {"type": "quote", "on": false}
]
```

### Weather

| Key | Default | Meaning |
|---|---|---|
| `place.name` | `""` | A suburb or city. Looked up once and remembered. Never a street address. |
| `place.country` | (none) | Two letter country code to pick the right place, like `"AU"`, `"GB"`, `"US"`. |
| `place.latitude`, `place.longitude` | (none) | Use these instead of a name for an exact spot (two decimals is plenty). |
| `weather.units` | `"celsius"` | Or `"fahrenheit"`. |
| `weather.show_place` | `false` | Starts the line with the place name. |
| `weather.rain_chance` | `false` | Adds "40% chance of rain" when it is 20% or more. |

### Calendar

| Key | Default | Meaning |
|---|---|---|
| `calendar.ics_urls` | `[]` | One or more iCal (.ics) links. README, "Getting a calendar link". |
| `calendar.days` | `2` | 1 = today only, 2 = today and tomorrow, 3 or more adds the next days by name. |
| `calendar.max` | `3` | At most this many events. |
| `calendar.hide` | `[]` | Events whose title contains any of these words are left out, like `["Birthday"]`. |
| `calendar.empty_text` | `"Nothing planned today"` | Shown when there are no events; `""` shows nothing. |

### Reminders

A list. Each one shows only on its days.

| Key | Meaning |
|---|---|
| `text` | What it says, like `"Bins out tonight"`. |
| `days` | `["mon"]`, `["tue", "fri"]`. Leave out for every day. |
| `every_weeks` | `2` for every second week. Needs `start`. |
| `start` | A date (YYYY-MM-DD) that the reminder falls on, to count the weeks from. |
| `dots` | Optional colours drawn before the text, like `["#e2b33c", "#4a8a4a"]` for bin lids. |

### Quote

| Key | Meaning |
|---|---|
| `quote.text` | One line, shown every day. |
| `quote.lines` | A list; a different line each day, in turn. Wins over `text`. |

## When, and tidying up

| Key | Default | Meaning |
|---|---|---|
| `schedule.start_hour` | `5` | The earliest hour a picture is made (your time zone). |
| `schedule.every_hours` | `0` | `0` once a day; `3` a new picture every 3 hours from the start hour. |
| `keep_previous` | `0` | How many of this tool's older pictures to keep on the TV. `0` keeps only today's. Your own photos are never deleted. |

## Files the tool writes (all in `data/`, ignored by git)

| File | What |
|---|---|
| `token.txt` | The TV's pairing token (private). Delete it and run `smartframe pair` to pair again. |
| `state.json` | Every picture this tool uploaded, when it last ran, where the rotation is. |
| `today.jpg` | The last picture sent. |
| `preview-*.png` | Pictures from `smartframe preview`. |
| `weather.json`, `place.json`, `calendar-*.ics` | The last weather, place and calendar, used when the internet drops out. |
| `smartframe.log` | The schedule's log (Mac and cron). |
