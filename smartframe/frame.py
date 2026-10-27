"""Talking to the Samsung Frame's Art Mode over the home Wi-Fi.

Uses the art channel of the open source samsungtvws library for the connection, and does the
picture upload by hand: on the Frames we tested, the TV answers an upload with a "ready_to_use"
event rather than a reply to the request, which the library's own upload waits for, so the
library's upload stalls where this one works.

Safety rule, enforced here: the only pictures this code deletes are ones this tool uploaded and
recorded in data/state.json, and only when the TV still describes them the way they were sent.
"""
import asyncio
import json
import logging
import os
import random
import socket
import time
import warnings
from datetime import datetime

MY_PHOTOS = "MY-C0002"   # the TV's "My Photos" category, where uploads go
logging.getLogger("samsungtvws").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="aiohttp")


class FrameError(Exception):
    pass


class FrameAsleep(FrameError):
    pass


class FrameRefused(FrameError):
    pass


def reachable(ip, port=8002, timeout=3.0):
    try:
        socket.create_connection((ip, port), timeout=timeout).close()
        return True
    except OSError:
        return False


def _lib():
    try:
        from samsungtvws import exceptions
        from samsungtvws.async_art import ArtChannelEmitCommand, SamsungTVAsyncArt
    except ImportError:
        raise FrameError("the samsungtvws library is missing: run pip install -r requirements.txt")
    return SamsungTVAsyncArt, ArtChannelEmitCommand, exceptions


REFUSED = ("The Frame did not accept this computer. Run `smartframe pair` and press Allow on the TV "
           "(after a factory reset, or a long time unplugged, the TV can forget it).")


class Frame:
    """One art channel connection. Use `async with Frame(cfg) as tv:`."""

    def __init__(self, cfg, token_file=None, connect_timeout=10):
        f = cfg["frame"]
        if not f.get("ip"):
            raise FrameError("frame.ip is not set in config.json (run `smartframe find` to see the TV's address)")
        self.ip, self.port, self.name = f["ip"], int(f.get("port", 8002)), f.get("name") or "SmartFrame"
        self.token_file = token_file or cfg.file("token.txt")
        self.timeout = connect_timeout
        self.tv = None
        self.events = {}

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def open(self):
        if not reachable(self.ip, self.port):
            raise FrameAsleep("The Frame at %s is not answering. It is off, asleep in a way that drops the Wi-Fi, "
                              "or on another network. Press the remote's power button once (Art Mode) and try again." % self.ip)
        Art, _, exc = _lib()
        loop = asyncio.get_running_loop()
        try:
            # The constructor asks the TV what it is over HTTP (and on 2024 models opens the remote
            # channel to get a token), which blocks, so it runs off the event loop.
            self.tv = await loop.run_in_executor(None, lambda: Art(
                host=self.ip, port=self.port, token_file=self.token_file, name=self.name, timeout=self.timeout))
        except exc.HttpApiError as e:
            raise FrameAsleep("The Frame did not answer its web address: %s" % e)
        orig = self.tv.process_event

        async def spy(event=None, response=None):
            try:
                d = json.loads(response.get("data", "{}")) if isinstance(response, dict) else {}
                name = d.get("event")
                if name in ("ready_to_use", "image_added", "error"):
                    fut = self.events.setdefault(name, loop.create_future())
                    if not fut.done():
                        fut.set_result(d)
            except Exception:
                pass
            return await orig(event, response)

        self.tv.process_event = spy
        try:
            await self.tv.start_listening()
        except (exc.UnauthorizedError, exc.ConnectionFailure) as e:
            raise FrameRefused(REFUSED + " (%s)" % type(e).__name__)
        except (OSError, asyncio.TimeoutError) as e:
            raise FrameAsleep("Could not open the Frame's art connection: %s" % e)
        if os.path.exists(self.token_file):
            os.chmod(self.token_file, 0o600)
        return self

    async def close(self):
        if self.tv:
            try:
                await self.tv.close()
            except Exception:
                pass
            self.tv = None

    # ---------------------------------------------------------------- read only

    async def device_info(self):
        try:
            return (await self.tv._get_device_info()).get("device", {})
        except Exception:
            return {}

    async def api_version(self):
        try:
            return await self.tv.get_api_version()
        except Exception:
            return None

    async def art_mode(self):
        try:
            return await self.tv.get_artmode()
        except Exception:
            return None

    async def current(self):
        try:
            return await self.tv.get_current()
        except Exception:
            return None

    async def my_photos(self):
        """Everything in the TV's My Photos, as the TV describes it. Raises FrameError if it will not say."""
        for attempt in range(3):
            try:
                return await self.tv.available(MY_PHOTOS, timeout=8)
            except AssertionError:
                await asyncio.sleep(1)
        raise FrameError("the Frame did not list its photos")

    # ---------------------------------------------------------------- changes

    async def _wait(self, name, timeout):
        loop = asyncio.get_running_loop()
        fut = self.events.setdefault(name, loop.create_future())
        err = self.events.setdefault("error", loop.create_future())
        done, _ = await asyncio.wait([fut, err], timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if err in done:
            raise FrameError("the Frame said error: %s" % err.result().get("error_code", err.result()))
        if not done:
            raise asyncio.TimeoutError(name)
        return fut.result()

    async def upload(self, path):
        """Upload one JPEG to My Photos. Returns (content_id, image_date)."""
        _, Cmd, _ = _lib()
        with open(path, "rb") as f:
            data = f.read()
        before = {p["content_id"] for p in await self.my_photos()}
        stamp = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
        for k in ("ready_to_use", "image_added", "error"):
            self.events.pop(k, None)
        rid = self.tv.get_uuid()
        await self.tv.send_command(Cmd.art_app_request({
            "request": "send_image", "file_type": "jpg", "id": rid, "request_id": rid,
            "conn_info": {"d2d_mode": "socket", "connection_id": random.randrange(4 * 1024 ** 3), "id": rid},
            "image_date": stamp, "matte_id": "none", "portrait_matte_id": "none", "file_size": len(data)}))
        try:
            ready = await self._wait("ready_to_use", 20)
        except asyncio.TimeoutError:
            raise FrameError("the Frame did not get ready for the picture (no ready_to_use in 20 s)")
        ci = ready["conn_info"]
        ci = json.loads(ci) if isinstance(ci, str) else ci
        header = json.dumps({"num": 0, "total": 1, "fileLength": len(data), "fileName": "smartframe",
                             "fileType": "jpg", "secKey": ci["key"], "version": "0.0.1"})
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ci["ip"], int(ci["port"])), 15)
        writer.write(len(header).to_bytes(4, "big") + header.encode("ascii"))
        for i in range(0, len(data), 64 * 1024):
            writer.write(data[i:i + 64 * 1024])
            await writer.drain()
        writer.close()
        try:
            added = await self._wait("image_added", 60)
            return added["content_id"], stamp
        except asyncio.TimeoutError:
            pass
        # Some TVs store the picture but never say so. Look for it before giving up, so a
        # second copy is never sent.
        for _ in range(5):
            await asyncio.sleep(2)
            new = [p for p in await self.my_photos() if p["content_id"] not in before]
            ours = [p for p in new if p.get("image_date") in (None, stamp)]
            if ours:
                return ours[-1]["content_id"], stamp
        raise FrameError("the picture was sent but the Frame never listed it")

    async def select(self, content_id):
        # Without the category some Frames quietly ignore the request.
        await self.tv.select_image(content_id, category=MY_PHOTOS, show=True)

    async def delete_ours(self, records):
        """Delete pictures this tool uploaded. records: [{"id", "image_date"}].

        Returns (deleted_ids, gone_ids, skipped_ids). A record is skipped (and kept away from) when
        the TV lists that id with a different date stamp: after a factory reset the TV starts
        numbering again, and that id may now be one of the owner's photos.
        """
        listing = {p["content_id"]: p for p in await self.my_photos()}
        delete, gone, skipped = [], [], []
        for r in records:
            p = listing.get(r["id"])
            if p is None:
                gone.append(r["id"])
            elif r.get("image_date") and p.get("image_date") and p["image_date"] != r["image_date"]:
                skipped.append(r["id"])
            else:
                delete.append(r["id"])
        if delete:
            await self.tv.delete_list(delete)
            await asyncio.sleep(1)
            still = {p["content_id"] for p in await self.my_photos()}
            left = [d for d in delete if d in still]
            if left:
                raise FrameError("the Frame did not delete %s" % ", ".join(left))
        return delete, gone, skipped


async def pair(cfg, wait=40):
    """First connection: the TV shows an Allow prompt, and the token it hands back is saved."""
    f = cfg["frame"]
    ip, port, name = f["ip"], int(f.get("port", 8002)), f.get("name") or "SmartFrame"
    if not ip:
        raise FrameError("frame.ip is not set in config.json (run `smartframe find`)")
    if not reachable(ip, port):
        raise FrameAsleep("The Frame at %s is not answering. Turn it on (TV or Art Mode) and try again." % ip)
    token_file = cfg.file("token.txt")
    try:
        from samsungtvws import exceptions
        from samsungtvws.async_remote import SamsungTVWSAsyncRemote
    except ImportError:
        raise FrameError("the samsungtvws library is missing: run pip install -r requirements.txt")
    had = open(token_file).read().strip() if os.path.exists(token_file) else ""
    if had:
        os.replace(token_file, token_file + ".old")   # a fresh pairing, the old token kept aside
    remote = SamsungTVWSAsyncRemote(host=ip, port=port, token_file=token_file, name=name, timeout=wait)
    t = time.time()
    try:
        await asyncio.wait_for(remote.open(), wait + 5)
    except (exceptions.UnauthorizedError, exceptions.ConnectionFailure, asyncio.TimeoutError) as e:
        if had and not os.path.exists(token_file):
            os.replace(token_file + ".old", token_file)
        raise FrameRefused("No Allow came from the TV in time (%s). Stand at the TV, run `smartframe pair` again, "
                           "and choose Allow when the prompt appears." % type(e).__name__)
    finally:
        try:
            await remote.close()
        except Exception:
            pass
    if os.path.exists(token_file):
        os.chmod(token_file, 0o600)
    got_token = os.path.exists(token_file) and open(token_file).read().strip() != ""
    if not got_token and had:
        os.replace(token_file + ".old", token_file)   # this TV hands out no new token: keep the old one
    async with Frame(cfg) as tv:
        version = await tv.api_version()
    return {"token": got_token, "seconds": round(time.time() - t, 1), "api_version": version}
