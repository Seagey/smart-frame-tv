"""Finding Samsung TVs on the home Wi-Fi. Read only: it asks, it changes nothing.

First a standard "who is there?" broadcast (SSDP) that Samsung TVs answer. With --scan it also
knocks on port 8001 of every address in this computer's own /24 network, for routers that block
broadcasts. Each TV found is asked for its name and whether it is a Frame.
"""
import asyncio
import ipaddress
import json
import socket
import time
import urllib.request

STS = ("urn:samsung.com:device:RemoteControlReceiver:1", "urn:dial-multiscreen-org:service:dial:1")


def _ssdp(seconds=3.0):
    found = set()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    s.settimeout(0.5)
    for st in STS:
        msg = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: %s\r\n\r\n' % st)
        try:
            s.sendto(msg.encode(), ("239.255.255.250", 1900))
        except OSError:
            pass
    end = time.time() + seconds
    while time.time() < end:
        try:
            data, addr = s.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        text = data.decode(errors="replace").lower()
        if "samsung" in text or "remotecontrolreceiver" in text:
            found.add(addr[0])
    s.close()
    return found


def own_network():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))   # no packet is sent; this only picks the Wi-Fi address
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ipaddress.ip_network(ip + "/24", strict=False)


async def _knock(ip, port, timeout):
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(str(ip), port), timeout)
        w.close()
        return str(ip)
    except Exception:
        return None


async def _scan(net, port=8001, timeout=0.6):
    hosts = list(net.hosts())
    out = []
    for i in range(0, len(hosts), 64):
        res = await asyncio.gather(*[_knock(h, port, timeout) for h in hosts[i:i + 64]])
        out += [r for r in res if r]
    return set(out)


def describe(ip, timeout=3):
    """Ask a TV at ip what it is. Returns a dict, or None if it is not a Samsung TV."""
    try:
        with urllib.request.urlopen("http://%s:8001/api/v2/" % ip, timeout=timeout) as r:
            d = json.loads(r.read()).get("device", {})
    except Exception:
        return None
    return {"ip": ip, "name": d.get("name", ""), "model": d.get("modelName", ""),
            "frame": d.get("FrameTVSupport") == "true", "power": d.get("PowerState", ""),
            "token_auth": d.get("TokenAuthSupport") == "true", "os": d.get("OS", "")}


def find(scan=False):
    ips = _ssdp()
    if scan or not ips:
        try:
            ips |= asyncio.run(_scan(own_network()))
        except OSError:
            pass
    tvs = [d for d in (describe(ip) for ip in sorted(ips, key=lambda x: tuple(int(p) for p in x.split(".")))) if d]
    return tvs
