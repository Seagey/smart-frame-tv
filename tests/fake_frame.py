"""A pretend Samsung Frame for the tests: speaks the art channel over a local websocket.

It answers the same requests a real Frame does (device info over HTTP, get_content_list,
send_image with its "ready_to_use" event and a raw socket upload, select_image,
delete_image_list), holding "My Photos" in memory. Runs in its own thread.
"""
import asyncio
import http
import json
import threading

from websockets.asyncio.server import serve


class FakeFrame:
    def __init__(self, photos=None, refuse=False, silent_upload=False, token="faketoken123"):
        # photos: [{"content_id": ..., "image_date": ...}] that "the owner" put there
        self.items = [dict(p, category_id="MY-C0002", width=3840, height=2160) for p in (photos or [])]
        self.current = self.items[0]["content_id"] if self.items else None
        self.refuse, self.silent_upload, self.token = refuse, silent_upload, token
        self.next_number = 1 + max([int(p["content_id"].split("_F")[1]) for p in self.items] or [0])
        self.uploads, self.selects, self.deletes = [], [], []
        self.port = None
        self.loop = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    # ---- lifecycle ----
    def start(self):
        self._thread.start()
        self._ready.wait(5)
        return self

    def stop(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(5)

    def _run(self):
        self.loop = asyncio.new_event_loop()
        self.loop.run_until_complete(self._main())

    async def _main(self):
        self._stop = asyncio.Event()
        self.tcp = await asyncio.start_server(self._receive_file, "127.0.0.1", 0)
        self.tcp_port = self.tcp.sockets[0].getsockname()[1]
        async with serve(self._ws, "127.0.0.1", 0, process_request=self._http) as server:
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            await self._stop.wait()
        self.tcp.close()

    # ---- the HTTP device info (what /api/v2/ says) ----
    def _http(self, connection, request):
        if request.path.rstrip("/") == "/api/v2":
            body = json.dumps({"device": {"name": "Fake Frame", "modelName": "FAKE65", "model": "21_FAKE",
                                          "FrameTVSupport": "true", "PowerState": "on", "TokenAuthSupport": "true"}})
            return connection.respond(http.HTTPStatus.OK, body)
        return None

    # ---- the websocket art channel ----
    async def _send(self, ws, payload):
        await ws.send(json.dumps({"event": "d2d_service_message", "data": json.dumps(payload)}))

    async def _ws(self, ws):
        self.ws = ws
        if self.refuse:
            await ws.send(json.dumps({"event": "ms.channel.unauthorized", "data": {}}))
            return
        await ws.send(json.dumps({"event": "ms.channel.connect", "data": {"id": "c1", "clients": [], "token": self.token}}))
        await ws.send(json.dumps({"event": "ms.channel.ready", "data": {}}))
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("method") != "ms.channel.emit":
                continue
            d = json.loads(msg["params"]["data"])
            req, rid = d["request"], d.get("request_id") or d.get("id")
            if req == "get_artmode_status":
                await self._send(ws, {"id": rid, "event": "artmode_status", "value": "on"})
            elif req in ("get_api_version", "api_version"):
                await self._send(ws, {"id": rid, "version": "2.03"})
            elif req == "get_content_list":
                await self._send(ws, {"id": rid, "content_list": json.dumps(self.items)})
            elif req == "get_current_artwork":
                await self._send(ws, {"id": rid, "content_id": self.current, "category_id": "MY-C0002"})
            elif req == "send_image":
                self._pending = {"rid": rid, "image_date": d.get("image_date"), "size": d["file_size"]}
                await self._send(ws, {"event": "ready_to_use", "request_id": rid, "id": rid,
                                      "conn_info": json.dumps({"ip": "127.0.0.1", "port": self.tcp_port, "key": "k1"})})
            elif req == "select_image":
                self.current = d["content_id"]
                self.selects.append(d["content_id"])
                await self._send(ws, {"id": rid, "event": "select_image"})
            elif req == "delete_image_list":
                ids = [x["content_id"] for x in d["content_id_list"]]
                self.deletes += ids
                self.items = [p for p in self.items if p["content_id"] not in ids]
                await self._send(ws, {"id": rid, "event": "image_deleted"})

    async def _receive_file(self, reader, writer):
        n = int.from_bytes(await reader.readexactly(4), "big")
        header = json.loads(await reader.readexactly(n))
        data = await reader.readexactly(header["fileLength"])
        writer.close()
        assert header["secKey"] == "k1" and len(data) == self._pending["size"]
        cid = "MY_F%04d" % self.next_number
        self.next_number += 1
        self.items.append({"content_id": cid, "category_id": "MY-C0002", "image_date": self._pending["image_date"],
                           "width": 3840, "height": 2160})
        self.uploads.append(cid)
        if not self.silent_upload:
            await self._send(self.ws, {"event": "image_added", "content_id": cid, "request_id": self._pending["rid"]})

    # ---- helpers for the tests ----
    def ids(self):
        return [p["content_id"] for p in self.items]
