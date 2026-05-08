#!/usr/bin/env python3
"""
Theem-r Scanner Bridge
======================
Bridges the Theem-r browser app (HTTP) to EmuLnk-compatible emulators (UDP / EMLKV2).

WHY THIS EXISTS
  Browsers can only speak HTTP — they cannot send or receive UDP packets.
  EmuLnk-compatible emulators (Dolphin-Lnk, PPSSPP-Lnk, RetroArch-Lnk, etc.)
  communicate over a binary UDP protocol called EMLKV2.  This script sits in
  the middle: Theem-r talks HTTP to this script, this script talks UDP to the
  emulator, and results flow back the other way.

WHEN TO RUN IT
  Only needed when using the Scanner tab in Theem-r from a desktop browser.
  If you open Theem-r directly on the Android device itself, it connects
  automatically and this script is NOT required.

REQUIREMENTS
  Python 3.6 or newer — no extra packages needed (standard library only).
  Download Python at https://www.python.org/downloads/

HOW TO USE
  1. Connect your Android device via USB and enable USB Debugging
  2. Run:  adb forward tcp:55356 tcp:55356
  3. Run:  python bridge.py          (keep this window open)
  4. In Theem-r Scanner tab: set IP to 127.0.0.1, port 55356, click Test

CURRENT STATUS
  The HTTP server is fully working.
  The EMLKV2 UDP section is stubbed — packet format confirmation pending
  from the EmuLnk developer.  See TODO markers below.
  Until confirmed, /data returns a placeholder and /scan returns empty results.
"""

# ── Standard library imports (no pip install needed) ──────────────────────────

import json           # encode / decode JSON — used for all HTTP responses
import socket         # low-level networking — used to send / receive UDP packets
import threading      # run the live-poll loop on a background thread
import sys            # access command-line args and exit cleanly
from http.server import HTTPServer, BaseHTTPRequestHandler  # built-in HTTP server
from urllib.parse import urlparse, parse_qs                 # parse URL query strings


# ── Configuration — edit these if needed ──────────────────────────────────────

HTTP_HOST = "127.0.0.1"   # only accept connections from this machine (safe default)
HTTP_PORT = 55356          # must match the port field in Theem-r's Scanner tab

DEVICE_IP   = "127.0.0.1" # device IP after 'adb forward' (or LAN IP for Wi-Fi)
DEVICE_PORT = 55356        # UDP port the emulator listens on
                           # TODO: confirm exact port with EmuLnk developer

UDP_TIMEOUT = 2.0          # seconds to wait for a UDP response before giving up


# ── EMLKV2 protocol constants ──────────────────────────────────────────────────

# Every EmuLnk packet starts with these two magic bytes: ASCII "EL"
EMLKV2_MAGIC = b'\x45\x4C'   # 0x45 = 'E',  0x4C = 'L'

# TODO: obtain full EMLKV2 packet specification from EmuLnk developer.
# Known so far (from public wiki):
#   - Packets begin with EMLKV2_MAGIC
#   - Handshake response is JSON: { "game_id": "...", "game_hash": "...", "platform": "..." }
#   - Memory reads are batched: one UDP packet out, one UDP packet back (~64 KB max)
#   - Packet type is detected in order: EMLKV2 handshake → batch read → single read → text


# ── UDP helpers ───────────────────────────────────────────────────────────────

def udp_send_recv(packet: bytes) -> bytes | None:
    """
    Send a single UDP packet to the device and return the response bytes.
    Returns None on timeout (emulator not running / wrong port) or error.
    """
    # SOCK_DGRAM = UDP (connectionless datagrams, as opposed to SOCK_STREAM = TCP)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)   # don't block forever if nothing responds

    try:
        sock.sendto(packet, (DEVICE_IP, DEVICE_PORT))   # fire the packet
        data, _ = sock.recvfrom(65536)                  # 64 KB receive buffer
        return data
    except socket.timeout:
        return None    # emulator didn't respond in time
    except OSError:
        return None    # network error (wrong IP, port unreachable, etc.)
    finally:
        sock.close()   # always release the socket, even if an exception occurred


def handshake() -> dict | None:
    """
    Send the EMLKV2 discovery handshake and parse the emulator's JSON response.
    Returns { game_id, game_hash, platform } on success, or None on failure.

    TODO: replace stub packet with confirmed EMLKV2 handshake payload.
    """
    # Build the outgoing handshake packet
    # TODO: append correct header bytes after the magic — spec pending
    packet = EMLKV2_MAGIC   # + additional bytes TBD

    raw = udp_send_recv(packet)   # send and wait for reply
    if raw is None:
        return None               # no response — emulator not reachable

    try:
        # Emulator replies with a UTF-8 JSON string
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None   # got a response but couldn't parse it — protocol mismatch


def read_memory(address: int, size: int, data_type: str) -> int | float | None:
    """
    Read `size` bytes from `address` in the emulator's RAM.
    Returns the decoded value (int or float) or None on failure.

    TODO: implement using the EMLKV2 batch-read packet format once confirmed.
    The batch protocol sends all requested reads in one UDP packet and
    receives all values back in a single response (~64 KB max).
    """
    # TODO: build batch-read packet and call udp_send_recv()
    return None   # stub — returns None until protocol is confirmed


def scan_memory(value: int | float, size: int, data_type: str) -> list[dict]:
    """
    Ask the emulator to scan its RAM for all addresses currently holding `value`.
    Returns a list of { addr, value } dicts (may be empty).

    TODO: implement using EMLKV2 scan command once packet format is confirmed.
    """
    # TODO: build scan packet, send, parse result list from response
    return []   # stub — returns empty list until protocol is confirmed


# ── HTTP request handler ───────────────────────────────────────────────────────

class BridgeHandler(BaseHTTPRequestHandler):
    """
    Handles HTTP requests from Theem-r's browser app.
    Each GET endpoint maps to one emulator operation.
    """

    # ── CORS headers ──────────────────────────────────────────────────────────
    # Browsers block cross-origin requests by default.
    # These headers tell the browser it's safe to call localhost from any page.
    CORS_HEADERS = {
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type":                 "application/json",
    }

    def send_json(self, status: int, payload: dict):
        """Helper: send a JSON response with CORS headers."""
        body = json.dumps(payload).encode("utf-8")   # dict → JSON bytes
        self.send_response(status)                   # e.g. 200 OK or 503
        for key, val in self.CORS_HEADERS.items():   # attach CORS + content-type
            self.send_header(key, val)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()                           # blank line separates headers from body
        self.wfile.write(body)                       # send the JSON body

    def do_OPTIONS(self, *_):
        """
        Browsers send an OPTIONS 'preflight' request before cross-origin calls.
        Reply with 204 No Content + CORS headers to approve it.
        """
        self.send_response(204)
        for key, val in self.CORS_HEADERS.items():
            self.send_header(key, val)
        self.end_headers()

    def do_GET(self):
        """Route incoming GET requests to the correct handler method."""
        parsed = urlparse(self.path)           # split URL into path + query string
        params = parse_qs(parsed.query)        # parse ?key=value pairs into a dict

        if parsed.path == "/data":
            self.handle_data()
        elif parsed.path == "/scan":
            self.handle_scan(params)
        elif parsed.path == "/read":
            self.handle_read(params)
        else:
            # Unknown endpoint — tell the caller what's available
            self.send_json(404, {"error": "Unknown endpoint", "available": ["/data", "/scan", "/read"]})

    # ── /data ─────────────────────────────────────────────────────────────────
    def handle_data(self):
        """
        GET /data
        Fire the EMLKV2 handshake and return the game info the emulator reports.
        Theem-r uses this to auto-fill the Game ID field on connect.

        Response: { "serial": "SLUS-20946", "platform": "PS2", "isConnected": true }
                  { "isConnected": false }  — on failure
        """
        result = handshake()   # send UDP handshake, parse JSON response

        if result is None:
            # Couldn't reach the emulator
            self.send_json(503, {"isConnected": False, "error": "No response from emulator — check adb forward and that the game is running"})
            return

        # Map the EMLKV2 response fields to what Theem-r expects
        self.send_json(200, {
            "isConnected": True,
            "serial":      result.get("game_id", ""),       # game_id from emulator → serial in Theem-r
            "platform":    result.get("platform", ""),      # PS2 / Wii / GCN / etc.
            "hash":        result.get("game_hash", ""),     # for future profile matching
        })

    # ── /scan ─────────────────────────────────────────────────────────────────
    def handle_scan(self, params: dict):
        """
        GET /scan?value=85&size=4&type=int
        Scan emulator RAM for all addresses currently holding `value`.
        Used by Theem-r's scan workflow to narrow down candidates.

        Query params:
          value  — the number to search for
          size   — byte width: 1, 2, 4, or 8
          type   — 'int' or 'float'

        Response: { "count": N, "results": [{ "addr": "0x...", "value": N }, ...] }
        """
        # Extract and validate query parameters
        raw_val  = params.get("value",  ["0"])[0]   # get first value or default "0"
        raw_size = params.get("size",   ["4"])[0]
        raw_type = params.get("type",   ["int"])[0]

        try:
            size  = int(raw_size)
            value = float(raw_val) if raw_type == "float" else int(raw_val)
        except ValueError:
            self.send_json(400, {"error": "Invalid value or size parameter"})
            return

        results = scan_memory(value, size, raw_type)   # TODO: real implementation

        self.send_json(200, {
            "count":   len(results),
            "results": results,
            # Warn the caller that results are empty because the protocol is stubbed
            "_note": "Scan not yet implemented — EMLKV2 packet spec pending" if not results else None,
        })

    # ── /read ─────────────────────────────────────────────────────────────────
    def handle_read(self, params: dict):
        """
        GET /read?addr=0xA2DA04&size=4&type=int
        Read a single memory address and return its current value.
        Used by Theem-r's known-address panel to show live values.

        Response: { "addr": "0xA2DA04", "value": 75000 }
        """
        raw_addr = params.get("addr", ["0x0"])[0]
        raw_size = params.get("size", ["4"])[0]
        raw_type = params.get("type", ["int"])[0]

        try:
            address = int(raw_addr, 16)   # parse hex string → int (e.g. "0xA2DA04" → 10670596)
            size    = int(raw_size)
        except ValueError:
            self.send_json(400, {"error": "Invalid addr or size — addr must be hex e.g. 0xA2DA04"})
            return

        value = read_memory(address, size, raw_type)   # TODO: real implementation

        if value is None:
            self.send_json(503, {"error": "Could not read memory — EMLKV2 read not yet implemented"})
            return

        self.send_json(200, {"addr": raw_addr, "value": value})

    def log_message(self, fmt, *args):
        """Override default logging to print cleaner output (no date/time clutter)."""
        print(f"  {self.address_string()}  {fmt % args}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    print()
    print("  Theem-r Scanner Bridge")
    print("  ──────────────────────────────────────────")
    print(f"  HTTP server  →  http://{HTTP_HOST}:{HTTP_PORT}")
    print(f"  Device UDP   →  {DEVICE_IP}:{DEVICE_PORT}")
    print()
    print("  Make sure you've run:  adb forward tcp:55356 tcp:55356")
    print("  Then in Theem-r:       IP = 127.0.0.1 | Port = 55356 | Test")
    print()
    print("  Press Ctrl+C to stop.")
    print()

    try:
        # Create the HTTP server — it will call BridgeHandler for every request
        server = HTTPServer((HTTP_HOST, HTTP_PORT), BridgeHandler)
        server.serve_forever()   # block here, handling requests until Ctrl+C
    except KeyboardInterrupt:
        print("\n  Bridge stopped.")                # clean exit on Ctrl+C
    except OSError as e:
        # Most likely the port is already in use by another process
        print(f"\n  Error: {e}")
        print(f"  Port {HTTP_PORT} may already be in use.  Close any other bridge instance and try again.")
        sys.exit(1)


# Run main() only when this file is executed directly (not when imported)
if __name__ == "__main__":
    main()
