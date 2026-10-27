# Which picture-frame TVs this works with

Short version: **Samsung The Frame**. It is the only gallery-style TV found where a computer on
the same Wi-Fi can upload a picture, show it and delete it, with nothing but a one-time Allow on
the TV. Researched October 2026.

| TV | Works? | How | Notes |
|---|---|---|---|
| Samsung The Frame 2021 (LS03A) | **Yes, tested** | Art Mode connection on port 8002 | Tested with this tool: art API 2.03, a 4K JPEG of about 2 MB uploads in 2 to 4 seconds and shows in about 3. The art connection opened without an Allow prompt on our TV. Waking it from fully off over the network did not work. |
| Samsung The Frame 2022 to 2024 (LS03B, LS03C, LS03D) | **Yes** | Same connection | Tested by the library's author on 2022 (API 4.x) and reported working by users on 2023 and 2024. 2024 models ask for the Allow on the remote connection first; `smartframe pair` does that. A 2022 firmware once removed the art connection and a later one restored it, so a future update could change things. |
| Samsung The Frame 2025 (LS03F), Frame Pro | Probably | Same connection | Not yet confirmed by anyone. Run `smartframe check` before relying on it. |
| Samsung The Frame 2020 and older | Possibly | Same connection | Older projects worked on 2020 Frames; untested here. |
| LG Gallery and Gallery+ | Not supported | Gallery+ (2025 TVs) can show a Google Photos album | No way found for a home computer to send a picture to the TV. A photo album route may be added later. |
| TCL NXTFRAME and T-Exhibition (select 2025 Google TV models) | Not supported | Ambient Mode set to a Google Photos album | Same as Google TV below. |
| Google TV, Chromecast with Google TV, Google TV Streamer | Not supported | Ambient mode can show a named Google Photos album | A tool could refresh that album daily; Google's rules for apps writing to Google Photos and the TV's own refresh timing make it unreliable. Possible later. |
| Apple TV | Not supported | A shared iCloud album as the screen saver | Possible later, the same way. |
| Hisense CanvasTV | Not supported | Own photos only through the TV's Art Mode app | No home-network route found. |
| Fire TV Omni (Ambient Experience) | Not supported | Curated art or a personal album | No route found. |
| Sony, Philips, Meural | Not supported | | Not found to have a way in. |

Not on the list? If it is not a Samsung The Frame, it almost certainly will not work. A Samsung TV
that is not a Frame has no Art Mode: `smartframe find` marks which is which.

## Sources

- samsungtvws (the art connection, models tested, pairing, the token being forgotten after a long
  power-off): https://github.com/NickWaterton/samsung-tv-ws-api
- Samsung developer forum on the art connection in 2022 firmware:
  https://forum.developer.samsung.com/t/most-reliable-approach-to-manage-art-mode-images-on-samsung-frame-tvs/29155
- An earlier Frame art project, tested on 2020 and 2021: https://github.com/ow/samsung-frame-art
- Home Assistant community, Frame art changer (lower-case .jpg and .png):
  https://community.home-assistant.io/t/home-assistant-add-on-samsung-the-frame-art-changer/627104
- LG Gallery+: https://www.advanced-television.com/2025/08/26/lg-rolls-out-lg-gallery
- TCL T-Exhibition: https://support.tcl.com/en_US/t-exhibition-turning-your-tcl-tv-into-a-work-of-art
- Google TV Ambient mode and albums: https://support.google.com/chromecast/answer/6080931
- Google Photos API limits: https://www.androidauthority.com/want-samsung-the-frame-tv-google-photos-support-3514571
- Fire TV Ambient: https://www.aftvnews.com/?p=42431
- Apple TV screen saver albums: https://support.apple.com/guide/tv/atvba33d9fa3
