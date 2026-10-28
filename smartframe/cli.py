"""smartframe: the commands.

  smartframe find                  look for Samsung TVs on the Wi-Fi (read only)
  smartframe pair                  first connection: press Allow on the TV, the token is saved
  smartframe check                 read only: is Art Mode there, what is showing, what is ours
  smartframe preview               make a picture on this computer to look at (nothing sent)
  smartframe run                   make today's picture, send it, show it, tidy up old ones
  smartframe run --when-due        the same, but only when the schedule says it is time
  smartframe undo                  delete every picture this tool put on the TV
"""
import argparse
import asyncio
import os
import sys
from datetime import date, datetime

from . import __version__, config, info, photos, render
from .state import State

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def say(msg):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def _load(args, required=True):
    return config.load(args.config, required=required)


# ---------------------------------------------------------------- find

def cmd_find(args):
    from .discover import find
    print("Looking for Samsung TVs on this network (about 3 seconds%s)..." % (", plus a scan" if args.scan else ""))
    tvs = find(scan=args.scan)
    if not tvs:
        print("No Samsung TV answered. Is it switched on (TV or Art Mode) and on the same Wi-Fi as this computer?")
        print("Try again with --scan, or read the address off the TV: Settings, General, Network, Network Status.")
        return 1
    for t in tvs:
        kind = "The Frame (Art Mode supported)" if t["frame"] else "Samsung TV, no Art Mode"
        print("  %-15s  %s  %s  [%s]" % (t["ip"], t["name"] or "(no name)", t["model"], kind))
    print('Put the Frame\'s address in config.json as "frame": {"ip": "..."}.')
    return 0


# ---------------------------------------------------------------- pair

def cmd_pair(args):
    from .frame import FrameError, pair
    cfg = _load(args)
    print("Connecting to the Frame at %s. If the TV shows a prompt asking to allow \"%s\", choose Allow."
          % (cfg["frame"]["ip"], cfg["frame"].get("name") or "SmartFrame"))
    try:
        r = asyncio.run(pair(cfg))
    except FrameError as e:
        print(e)
        return 1
    if r["token"]:
        print("Paired in %s s. The token is saved in data/token.txt (private, never shared)." % r["seconds"])
    else:
        print("Connected in %s s. This TV did not need a token, which is normal for some Frames." % r["seconds"])
    print("Art Mode API version: %s" % (r["api_version"] or "unknown"))
    return 0


# ---------------------------------------------------------------- check

async def _check(cfg):
    from .frame import Frame
    state = State(cfg.file("state.json"))
    async with Frame(cfg) as tv:
        dev = await tv.device_info()
        print("TV:              %s %s" % (dev.get("name", ""), dev.get("modelName", "")))
        print("Art Mode:        %s" % ("supported" if dev.get("FrameTVSupport") == "true" else "not reported by the TV"))
        print("Power:           %s" % (dev.get("PowerState") or "unknown"))
        print("Art API version: %s" % (await tv.api_version() or "unknown"))
        mode = await tv.art_mode()
        print("Showing:         %s" % {"on": "Art Mode", "off": "TV (not Art Mode)"}.get(mode, mode or "unknown"))
        cur = await tv.current() or {}
        mine = await tv.my_photos()
        ours = {u["id"] for u in state.uploaded}
        cid = cur.get("content_id")
        print("Art picture:     %s%s" % (cid or "unknown", " (made by this tool)" if cid in ours else ""))
        print("My Photos:       %d stored, %d of them made by this tool" % (len(mine), len([p for p in mine if p["content_id"] in ours])))
        missing = [u["id"] for u in state.uploaded if u["id"] not in {p["content_id"] for p in mine}]
        if missing:
            print("Note:            %d picture(s) in data/state.json are no longer on the TV" % len(missing))
        if cid in ours:
            item = next((p for p in mine if p["content_id"] == cid), {})
            rec = next(u for u in state.uploaded if u["id"] == cid)
            same = item.get("image_date") == rec.get("image_date")
            print("Date stamp:      %s" % ("matches what this tool sent" if same else "differs (%s)" % item.get("image_date")))


def cmd_check(args):
    from .frame import FrameError
    cfg = _load(args)
    print("Read only: this changes nothing on the TV.")
    try:
        asyncio.run(_check(cfg))
    except FrameError as e:
        print(e)
        return 1
    return 0


# ---------------------------------------------------------------- preview

def _preview_config(args):
    cfg = _load(args, required=False)
    if not cfg.path or not os.path.exists(cfg.path):
        cfg.data["photos"]["folder"] = os.path.join(REPO, "samples", "photos")
        args.sample = True
    if args.style:
        cfg.data["style"] = args.style
    if args.position:
        cfg.data["position"] = args.position
    if args.photo:
        cfg.data["photos"]["folder"] = os.path.dirname(os.path.abspath(args.photo))
        cfg.data["photos"]["pick"] = "fixed"
        cfg.data["photos"]["file"] = os.path.basename(args.photo)
    cfg.validate()
    return cfg


def cmd_preview(args):
    cfg = _preview_config(args)
    state = State(cfg.file("state.json"))
    when = cfg.now()
    if args.date:
        d = date.fromisoformat(args.date)
        when = datetime(d.year, d.month, d.day, 7, 0, tzinfo=cfg.tz)
    styles = list(config.STYLES) if args.style == "all" or args.all else [cfg["style"]]
    details = info.gather(cfg, when, sample=args.sample)
    for style in styles:
        cfg.data["style"] = style
        name = photos.choose(cfg, state, when.date())
        out = args.out if (args.out and len(styles) == 1) else os.path.join(cfg.data_dir, "preview-%s.png" % style)
        engine = render.render(cfg, os.path.join(cfg.photo_folder, name), details, out, engine=args.engine)
        print("%s: %s (photo %s, made with %s)" % (style, out, name, engine))
    return 0


# ---------------------------------------------------------------- run

def due(cfg, state, now):
    s = cfg["schedule"]
    if now.hour < int(s.get("start_hour", 5)):
        return False
    if state.data.get("last_date") != now.date().isoformat():
        return True
    every = int(s.get("every_hours", 0))
    return every > 0 and now.timestamp() - float(state.data.get("last_run", 0)) >= every * 3600 - 120


async def _send(cfg, state, path):
    from .frame import Frame
    async with Frame(cfg) as tv:
        if not state.data.get("before"):
            # Remember the owner's picture once, so undo can put it back.
            cur = await tv.current() or {}
            if cur.get("content_id") and cur["content_id"] not in {u["id"] for u in state.uploaded}:
                state.data["before"] = {"id": cur["content_id"], "category": cur.get("category_id") or ""}
        cid, stamp = await tv.upload(path)
        state.add_upload(cid, stamp)
        state.save()   # recorded before anything else, so it can always be tidied later
        shown = await tv.make_current(cid)
        state.data["shown"] = shown
        keep = max(0, int(cfg.get("keep_previous", 0)))
        older = [u for u in state.uploaded if u["id"] != cid]
        older = older[: max(0, len(older) - keep)]
        deleted, gone, skipped = await tv.delete_ours(older) if older else ([], [], [])
        for x in deleted + gone + skipped:
            state.forget(x)
        if skipped:
            say("left alone %s: the TV now describes it differently, so it may not be ours any more" % ", ".join(skipped))
        return cid, deleted, shown


async def _show_again(cfg, state):
    from .frame import Frame
    async with Frame(cfg) as tv:
        return await tv.make_current(state.data["current"])


def cmd_run(args):
    from .frame import FrameAsleep, FrameError, reachable
    cfg = _load(args)
    state = State(cfg.file("state.json"))
    now = cfg.now()
    if args.when_due and state.data.get("shown") is False and state.data.get("current") \
            and reachable(cfg["frame"]["ip"], int(cfg["frame"].get("port", 8002))):
        # Today's picture is on the TV but the Frame kept another one: try again (it works while
        # the TV shows TV), then carry on as usual.
        try:
            if asyncio.run(_show_again(cfg, state)):
                state.data["shown"] = True
                state.save()
                say("today's picture %s is now the Art Mode picture" % state.data["current"])
        except Exception:
            pass
    if args.when_due and not due(cfg, state, now):
        return 0   # not time yet: stay quiet, the next run checks again
    if not reachable(cfg["frame"]["ip"], int(cfg["frame"].get("port", 8002))):
        if args.when_due:
            return 0   # the TV is off; the next run tries again
        print("The Frame at %s is not answering. Is it on (TV or Art Mode) and on the Wi-Fi?" % cfg["frame"]["ip"])
        return 1
    try:
        name = photos.choose(cfg, state, now.date())
        details = info.gather(cfg, now)
        out = cfg.file("today.jpg")
        engine = render.render(cfg, os.path.join(cfg.photo_folder, name), details, out)
        cid, deleted, shown = asyncio.run(_send(cfg, state, out))
    except (FrameAsleep,) as e:
        if args.when_due:
            return 0
        say(str(e))
        return 1
    except (FrameError, photos.PhotoError, config.ConfigError) as e:
        say("failed: %s" % e)
        return 1
    state.data["last_photo"] = name
    state.mark_run(now.date().isoformat())
    state.save()
    say("showing %s (%s, %s, made with %s), removed %s%s" % (cid, cfg["style"], name, engine, ", ".join(deleted) or "nothing",
        "" if shown else ". The Frame kept another picture for now: the schedule tries again while the TV shows TV"))
    return 0


# ---------------------------------------------------------------- undo

async def _undo(cfg, state):
    from .frame import Frame
    async with Frame(cfg) as tv:
        # Put the owner's picture back FIRST. A real 2021 Frame whose showing picture was deleted
        # fell back to a Samsung artwork and then ignored every request to show a photo.
        before, put_back = state.data.get("before") or {}, None
        if before.get("id") and before["id"] not in {u["id"] for u in state.uploaded}:
            try:
                await tv.select(before["id"], category=before.get("category") or None)
                put_back = before["id"]
            except Exception:
                pass
        return (await tv.delete_ours(list(state.uploaded))) + (put_back,)


def cmd_undo(args):
    from .frame import FrameError
    cfg = _load(args)
    state = State(cfg.file("state.json"))
    if not state.uploaded:
        print("Nothing to remove: data/state.json lists no pictures from this tool.")
        return 0
    print("This removes the %d picture(s) this tool put on the Frame. Your own photos stay." % len(state.uploaded))
    if not args.yes:
        if input('Type "yes" to go ahead: ').strip().lower() != "yes":
            print("Nothing changed.")
            return 1
    try:
        deleted, gone, skipped, put_back = asyncio.run(_undo(cfg, state))
    except FrameError as e:
        print(e)
        return 1
    for x in deleted + gone + skipped:
        state.forget(x)
    state.data["last_date"] = ""
    state.data["before"] = None
    state.save()
    print("Removed %d. %s%s" % (len(deleted), "%d were already gone. " % len(gone) if gone else "",
                                 "Left %d alone (they no longer look like ours)." % len(skipped) if skipped else ""))
    if put_back:
        print("Asked the Frame to show your picture from before (%s) again." % put_back)
    print("If the Frame shows one of Samsung's artworks instead, pick your photo with the remote: "
          "Art Mode, My Photos.")
    print("To stop new pictures, turn off the schedule too (README, \"Undo\").")
    return 0


# ---------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(prog="smartframe", description="A fresh Art Mode picture every day for a Samsung The Frame.")
    p.add_argument("--config", help="settings file (default: config.json in this folder)")
    p.add_argument("--version", action="version", version="smartframe " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="look for Samsung TVs on the Wi-Fi (read only)")
    f.add_argument("--scan", action="store_true", help="also knock on every address in this network")
    sub.add_parser("pair", help="first connection: press Allow on the TV")
    sub.add_parser("check", help="read only: what the TV says about Art Mode")
    v = sub.add_parser("preview", help="make a picture here to look at, send nothing")
    v.add_argument("--style", choices=list(config.STYLES) + ["all"])
    v.add_argument("--all", action="store_true", help="one picture for every style")
    v.add_argument("--position", choices=config.POSITIONS)
    v.add_argument("--photo", help="use this photo instead of the folder's pick")
    v.add_argument("--date", help="pretend it is this day (YYYY-MM-DD)")
    v.add_argument("--sample", action="store_true", help="made-up details instead of your weather and calendar")
    v.add_argument("--engine", choices=("auto", "chrome", "pillow"), default="auto")
    v.add_argument("--out", help="where to save the PNG")
    r = sub.add_parser("run", help="make today's picture and show it on the Frame")
    r.add_argument("--when-due", action="store_true", help="only if the schedule says it is time (for launchd, systemd or cron)")
    u = sub.add_parser("undo", help="remove every picture this tool put on the Frame")
    u.add_argument("--yes", action="store_true", help="do not ask first")
    args = p.parse_args(argv)
    try:
        return {"find": cmd_find, "pair": cmd_pair, "check": cmd_check, "preview": cmd_preview,
                "run": cmd_run, "undo": cmd_undo}[args.cmd](args)
    except config.ConfigError as e:
        print("config: %s" % e)
        return 2
    except photos.PhotoError as e:
        print("photos: %s" % e)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
