#!/usr/bin/env python3
"""
Theem-r Scanner Bridge
======================
Bridges the Theem-r browser app (HTTP) to EmuLnk-compatible emulators (UDP).

WHY THIS EXISTS
  Browsers speak HTTP only — they cannot send or receive UDP packets.
  EmuLnk-compatible emulators (Dolphin-Lnk, PPSSPP-Lnk, RetroArch-Lnk,
  melonDS-Lnk, Azahar-Lnk) communicate over a binary UDP protocol.
  This script sits in the middle: Theem-r sends HTTP to this script,
  this script sends UDP to the emulator, results flow back.

WHEN TO RUN IT
  Only needed when using the Scanner tab in Theem-r from a desktop browser.
  If you open Theem-r directly on the Android device, it auto-connects
  without this bridge.

REQUIREMENTS
  Python 3.6+  —  no extra packages (uses standard library only).
  https://www.python.org/downloads/

HOW TO USE
  1. Connect your Android device via USB, enable USB Debugging
  2. adb forward tcp:55356 tcp:55356
  3. python bridge.py          (keep this terminal open)
  4. Theem-r Scanner tab → IP: 127.0.0.1  Port: 55356 → Test

PROTOCOL REFERENCE
  EmuLnk Batch Protocol:
  https://github.com/EmuLnk/emulnk-repo/wiki/Batch-Protocol
"""

# ── Standard library imports — no pip install needed ──────────────────────────

import json          # encode / decode JSON for HTTP responses and handshake parsing
import socket        # UDP socket for communicating with the emulator
import struct        # pack / unpack binary integers (little-endian u16, u32, etc.)
import sys           # sys.exit on fatal errors
from http.server import HTTPServer, BaseHTTPRequestHandler  # built-in HTTP server
from urllib.parse import urlparse, parse_qs                 # parse URL path + query


# ── Configuration ─────────────────────────────────────────────────────────────

HTTP_HOST    = "127.0.0.1"  # only accept connections from this machine (safe default)
HTTP_PORT    = 55355         # must match the port field in Theem-r's Scanner tab

DEVICE_IP    = "192.168.1.100"  # WHERE IS YOUR EMULATOR RUNNING?
                                #   Desktop use:  set to device's Wi-Fi IP
                                #                 (Settings → About → Status → IP address)
                                #   On-device:    set to "127.0.0.1"
                                #                 (run this script in Termux on the same device)
DEVICE_PORT  = 55355            # UDP port the emulator listens on (EmuLnk default)

UDP_TIMEOUT  = 3.0           # seconds to wait for a UDP reply before giving up


# ── Protocol constants ────────────────────────────────────────────────────────

# 6-byte ASCII string sent to trigger EMLKV2 detection.
# The emulator replies with JSON: { "game_id": "...", "game_hash": "...", "platform": "..." }
EMLKV2_HANDSHAKE = b'EMLKV2'

# 2-byte magic that begins every batch read request and response.
# ASCII "EL" (0x45=E, 0x4C=L).
BATCH_MAGIC = b'\x45\x4C'

# Maximum reads per single batch UDP packet (protocol limit).
BATCH_MAX_ENTRIES = 256

# Maximum bytes to request per single address read (protocol limit).
BATCH_MAX_READ_SIZE = 4096

# Receive buffer for UDP responses (~64 KB, near UDP maximum).
UDP_RECV_BUFFER = 65536


# ── RAM ranges by platform ────────────────────────────────────────────────────
# Used for full first-pass scans.  Each entry is (start_addr, exclusive_end_addr).
# Addresses match what each emulator fork exposes through the batch protocol.

RAM_RANGES = {
    'PS2':    [(0x00000000, 0x02000000)],         # 32 MB  — EE main RAM
    'PS1':    [(0x00000000, 0x00200000)],          # 2 MB   — main RAM
    'PSP':    [(0x08000000, 0x0A000000)],          # 32 MB  — user RAM
    'GCN':    [(0x80000000, 0x81800000)],          # 24 MB  — MEM1
    'Wii':    [(0x80000000, 0x81800000),           # 24 MB  — MEM1
               (0x90000000, 0x94000000)],          # 64 MB  — MEM2
    'SNES':   [(0x7E0000,   0x800000)],            # 128 KB — WRAM
    'NES':    [(0x000000,   0x000800)],            # 2 KB   — CPU RAM
    'GB':     [(0xC000,     0xE000)],              # 8 KB   — WRAM
    'GBC':    [(0xC000,     0xE000)],              # 8 KB   — WRAM (banks 0-1)
    'GBA':    [(0x02000000, 0x02040000),           # 256 KB — EWRAM
               (0x03000000, 0x03008000)],          # 32 KB  — IWRAM
    'NDS':    [(0x02000000, 0x02400000)],          # 4 MB   — main RAM
    '3DS':    [(0x14000000, 0x1C000000)],          # 128 MB — linear heap (approx)
    'Genesis':[(0xFF0000,   0x1000000)],           # 64 KB  — 68K RAM
}
# Fallback when platform is unknown or not listed above.
DEFAULT_RAM_RANGE = [(0x00000000, 0x02000000)]

# Scan state persists across HTTP requests for the same session.
# Holds candidate addresses from the most recent scan.
_scan_state: dict = {}   # keys: 'candidates' (list[int]), 'platform' (str)


# ── UDP helpers ───────────────────────────────────────────────────────────────

def udp_exchange(packet: bytes) -> bytes | None:
    """
    Send a single UDP datagram to the configured device and return the
    raw response bytes.  Returns None on timeout or network error.
    """
    # SOCK_DGRAM = UDP — connectionless, one packet out, one packet back.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(UDP_TIMEOUT)   # avoid blocking indefinitely

    try:
        sock.sendto(packet, (DEVICE_IP, DEVICE_PORT))
        data, _ = sock.recvfrom(UDP_RECV_BUFFER)
        return data
    except socket.timeout:
        return None    # emulator not responding (not running / wrong port)
    except OSError:
        return None    # network-level error
    finally:
        sock.close()   # always release the socket


# ── EMLKV2 handshake ──────────────────────────────────────────────────────────

def do_handshake() -> dict | None:
    """
    Send the 6-byte EMLKV2 identify string.
    On success the emulator replies with a UTF-8 JSON string:
        { "game_id": "SLUS-20946", "game_hash": "abc123", "platform": "PS2" }
    Returns that dict, or None if the emulator isn't reachable or not running.
    """
    raw = udp_exchange(EMLKV2_HANDSHAKE)   # send b'EMLKV2', wait for reply
    if raw is None:
        return None

    try:
        return json.loads(raw.decode('utf-8'))   # decode UTF-8 JSON string
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None   # received something but it wasn't valid JSON


# ── Batch protocol helpers ────────────────────────────────────────────────────

def build_batch_request(reads: list[tuple[int, int]]) -> bytes:
    """
    Construct a batch read request packet.

    Wire format (from EmuLnk Batch Protocol spec):
        [0x45 0x4C]           2 bytes  magic "EL"
        [count : u16le]       2 bytes  number of (addr, size) pairs that follow
        [addr  : u32le]  ┐
        [size  : u32le]  ┘ × count    8 bytes per entry

    Args:
        reads: list of (address, byte_count) tuples
    Returns:
        bytes object ready to send over UDP
    """
    count = len(reads)
    # Start with magic + count packed as little-endian unsigned 16-bit int
    packet = BATCH_MAGIC + struct.pack('<H', count)
    for addr, size in reads:
        # Each entry: address (u32le) then byte count (u32le)
        packet += struct.pack('<II', addr, size)
    return packet


def parse_batch_response(data: bytes) -> list[bytes]:
    """
    Decode a batch response packet back into a list of raw byte blobs.

    Wire format (from spec):
        [0x45 0x4C]           2 bytes  magic "EL"
        [count : u16le]       2 bytes  number of entries that follow
        [len   : u16le]  ┐
        [data  : len bytes] ┘ × count  length-prefixed blobs
                                       len == 0 means that entry failed (bad address)

    Returns a list of bytes; empty bytes b'' marks a failed read.
    """
    if len(data) < 4:
        return []
    if data[0:2] != BATCH_MAGIC:
        return []   # not a valid batch response

    count = struct.unpack_from('<H', data, 2)[0]   # number of entries

    results: list[bytes] = []
    pos = 4   # byte offset — start after the 4-byte header

    for _ in range(count):
        if pos + 2 > len(data):
            break   # truncated packet

        length = struct.unpack_from('<H', data, pos)[0]   # 16-bit length prefix
        pos += 2

        if length == 0:
            results.append(b'')   # emulator signalled a read error at this address
        else:
            if pos + length > len(data):
                break   # truncated entry
            results.append(data[pos : pos + length])   # slice out the data bytes
            pos += length

    return results


def batch_read(reads: list[tuple[int, int]]) -> list[bytes]:
    """
    Execute one or more (addr, size) reads using the batch protocol.
    Automatically splits into chunks of BATCH_MAX_ENTRIES if needed.

    Returns a list of bytes objects in the same order as `reads`.
    Entries that failed return b''.
    """
    results: list[bytes] = []

    # Send up to 256 reads per UDP packet — the protocol maximum.
    for start in range(0, len(reads), BATCH_MAX_ENTRIES):
        chunk = reads[start : start + BATCH_MAX_ENTRIES]
        packet = build_batch_request(chunk)
        raw = udp_exchange(packet)

        if raw is None:
            # No response for this entire chunk — mark all as failed
            results.extend([b''] * len(chunk))
        else:
            parsed = parse_batch_response(raw)
            # Pad with failures if the emulator returned fewer entries than requested
            while len(parsed) < len(chunk):
                parsed.append(b'')
            results.extend(parsed)

    return results


# ── Value encoding / decoding ─────────────────────────────────────────────────

def decode_value(raw: bytes, data_type: str, size: int) -> int | float | None:
    """
    Interpret `raw` bytes as a numeric value of the given type and size.

    data_type: 'int' or 'float'
    size:      1, 2, 4, or 8 bytes
    Returns int or float, or None if raw is too short / type is unknown.
    """
    if not raw or len(raw) < size:
        return None
    try:
        if data_type == 'float':
            fmt = '<f' if size == 4 else '<d'         # 32-bit or 64-bit float, LE
            return struct.unpack_from(fmt, raw)[0]
        else:
            fmt = {1: '<B', 2: '<H', 4: '<I', 8: '<Q'}.get(size)  # unsigned int LE
            if fmt is None:
                return None
            return struct.unpack_from(fmt, raw)[0]
    except struct.error:
        return None


def encode_value(value: int | float, data_type: str, size: int) -> bytes:
    """
    Pack a Python number into the raw bytes a scan comparison needs.
    Inverse of decode_value.
    """
    try:
        if data_type == 'float':
            fmt = '<f' if size == 4 else '<d'
            return struct.pack(fmt, value)
        else:
            fmt = {1: '<B', 2: '<H', 4: '<I', 8: '<Q'}.get(size, '<I')
            return struct.pack(fmt, int(value))
    except (struct.error, OverflowError):
        return b''


def values_match(raw: bytes, target_bytes: bytes) -> bool:
    """Return True if raw bytes start with (or equal) target_bytes."""
    return len(raw) >= len(target_bytes) and raw[:len(target_bytes)] == target_bytes


# ── Memory scanning ───────────────────────────────────────────────────────────

def full_scan(platform: str, data_type: str, size: int,
              target: int | float) -> list[dict]:
    """
    Scan the full RAM of the running game for addresses containing `target`.

    Strategy:
      - Read RAM in BATCH_MAX_READ_SIZE (4096 byte) chunks.
      - Pack up to BATCH_MAX_ENTRIES chunks per UDP round-trip (= ~1 MB per packet).
      - Slide a window of `size` bytes across each chunk to find matches.

    This means a 32 MB PS2 scan takes roughly 32 UDP round-trips — fast.

    Returns list of { "addr": "0x...", "value": N } dicts.
    """
    target_bytes = encode_value(target, data_type, size)
    if not target_bytes:
        return []

    ranges   = RAM_RANGES.get(platform, DEFAULT_RAM_RANGE)
    matches: list[dict] = []

    for (range_start, range_end) in ranges:
        addr = range_start

        while addr < range_end:
            # Build a batch of up to 256 consecutive 4096-byte reads
            reads: list[tuple[int, int]] = []
            batch_base = addr

            while addr < range_end and len(reads) < BATCH_MAX_ENTRIES:
                chunk_size = min(BATCH_MAX_READ_SIZE, range_end - addr)
                reads.append((addr, chunk_size))
                addr += chunk_size   # advance to next chunk

            raw_chunks = batch_read(reads)

            # Search each returned chunk for the target byte pattern
            for i, (chunk_addr, _) in enumerate(reads):
                chunk = raw_chunks[i]
                if not chunk:
                    continue   # read failed for this address range — skip

                # Slide through the chunk by `size` bytes at a time
                for offset in range(0, len(chunk) - size + 1, size):
                    candidate = chunk[offset : offset + size]
                    if values_match(candidate, target_bytes):
                        candidate_addr = chunk_addr + offset
                        matches.append({
                            'addr':  hex(candidate_addr),
                            'value': decode_value(candidate, data_type, size),
                        })

    return matches


def filter_scan(candidates: list[int], data_type: str, size: int,
                target: int | float) -> list[dict]:
    """
    Re-read a list of candidate addresses and return only those whose current
    value matches `target`.  Used for all scans after the first.

    Much faster than a full scan because we only read known addresses.
    """
    target_bytes = encode_value(target, data_type, size)
    if not target_bytes:
        return []

    reads        = [(addr, size) for addr in candidates]
    raw_values   = batch_read(reads)

    matches: list[dict] = []
    for i, addr in enumerate(candidates):
        raw = raw_values[i]
        if values_match(raw, target_bytes):
            matches.append({
                'addr':  hex(addr),
                'value': decode_value(raw, data_type, size),
            })

    return matches


# ── HTTP request handler ───────────────────────────────────────────────────────

class BridgeHandler(BaseHTTPRequestHandler):
    """
    Handles HTTP requests from the Theem-r browser app.
    Each GET endpoint maps to one emulator operation.
    """

    # Browsers block cross-origin requests by default.
    # These headers allow Theem-r (any origin) to call this localhost server.
    CORS = {
        'Access-Control-Allow-Origin':  '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type':                 'application/json',
    }

    def send_json(self, status: int, payload: dict):
        """Serialize `payload` to JSON and send it with CORS headers."""
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        for k, v in self.CORS.items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()       # blank line marks end of headers
        self.wfile.write(body)   # send the JSON body bytes

    def do_OPTIONS(self, *_):
        """
        Preflight response for CORS.
        Browsers send OPTIONS before a cross-origin request; we just approve it.
        """
        self.send_response(204)
        for k, v in self.CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        """Route the request path to the correct handler."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)   # e.g. "?value=85&size=4" → { 'value': ['85'], ... }

        routes = {
            '/data':  self.handle_data,
            '/scan':  lambda: self.handle_scan(params),
            '/read':  lambda: self.handle_read(params),
            '/reset': self.handle_reset,
        }
        handler = routes.get(parsed.path)
        if handler:
            handler()
        else:
            self.send_json(404, {
                'error':     'Unknown endpoint',
                'available': list(routes.keys()),
            })

    # ── /data ──────────────────────────────────────────────────────────────────

    def handle_data(self):
        """
        GET /data
        Fire the EMLKV2 handshake and return the emulator's current game info.
        Theem-r calls this on connect to auto-fill the Game ID field.

        Success:  { isConnected: true, serial: "SLUS-20946", platform: "PS2", hash: "..." }
        Failure:  { isConnected: false, error: "..." }
        """
        result = do_handshake()

        if result is None:
            self.send_json(503, {
                'isConnected': False,
                'error': (
                    'No response from emulator.  '
                    'Check: (1) emulator is running with a game loaded, '
                    '(2) adb forward tcp:55356 tcp:55356 was run, '
                    f'(3) device UDP port matches DEVICE_PORT={DEVICE_PORT} in bridge.py'
                ),
            })
            return

        # Store the platform for scan range selection
        _scan_state['platform'] = result.get('platform', '')

        self.send_json(200, {
            'isConnected': True,
            'serial':   result.get('game_id',   ''),   # maps to Theem-r's gameId field
            'platform': result.get('platform',  ''),
            'hash':     result.get('game_hash', ''),
        })

    # ── /scan ──────────────────────────────────────────────────────────────────

    def handle_scan(self, params: dict):
        """
        GET /scan?value=85&size=4&type=int
        Search emulator RAM for all addresses currently holding `value`.

        First call  → full RAM scan (slower, reads entire RAM range for the platform).
        Subsequent  → filter scan (fast, re-reads only previous candidates).
        Pass &reset=1 to force a fresh full scan.

        Query params:
          value   — numeric value to search for
          size    — byte width: 1, 2, 4, or 8
          type    — 'int' or 'float'
          reset   — '1' to clear candidates and start fresh

        Response: { count: N, results: [{ addr: "0x...", value: N }, ...] }
        """
        raw_val   = params.get('value',  ['0'])[0]
        raw_size  = params.get('size',   ['4'])[0]
        data_type = params.get('type',   ['int'])[0]
        do_reset  = params.get('reset',  ['0'])[0] == '1'

        try:
            size  = int(raw_size)
            # Parse as float or int depending on requested type
            value = float(raw_val) if data_type == 'float' else int(raw_val)
        except ValueError:
            self.send_json(400, {'error': 'Invalid value or size parameter'})
            return

        if do_reset:
            _scan_state.pop('candidates', None)   # clear stored candidates

        candidates = _scan_state.get('candidates')
        platform   = _scan_state.get('platform', 'PS2')

        if candidates is None:
            # No prior candidates — scan the whole RAM range for this platform
            print(f'  Full scan  value={value}  type={data_type}  size={size}  platform={platform}')
            results = full_scan(platform, data_type, size, value)
        else:
            # Narrow down from previous scan results
            print(f'  Filter scan  value={value}  candidates={len(candidates)}')
            results = filter_scan(candidates, data_type, size, value)

        # Store survivor addresses for the next scan call
        _scan_state['candidates'] = [int(r['addr'], 16) for r in results]

        self.send_json(200, {
            'count':   len(results),
            'results': results[:2000],   # cap response size — UI shows paginated anyway
        })

    # ── /read ──────────────────────────────────────────────────────────────────

    def handle_read(self, params: dict):
        """
        GET /read?addr=0xA2DA04&size=4&type=int
        Read a single memory address and return its decoded value.
        Used by Theem-r's known-address panel for live value display.

        Response: { addr: "0xA2DA04", value: 75000 }
        """
        raw_addr  = params.get('addr', ['0x0'])[0]
        raw_size  = params.get('size', ['4'])[0]
        data_type = params.get('type', ['int'])[0]

        try:
            address = int(raw_addr, 16)   # "0xA2DA04" → integer
            size    = int(raw_size)
        except ValueError:
            self.send_json(400, {'error': 'addr must be hex (e.g. 0xA2DA04), size must be integer'})
            return

        raw_results = batch_read([(address, size)])
        raw         = raw_results[0] if raw_results else b''

        if not raw:
            self.send_json(503, {'error': f'Memory read failed at {raw_addr}'})
            return

        value = decode_value(raw, data_type, size)
        self.send_json(200, {'addr': raw_addr, 'value': value})

    # ── /reset ─────────────────────────────────────────────────────────────────

    def handle_reset(self):
        """
        GET /reset
        Clear scan session state so the next /scan starts a fresh full-RAM pass.
        Theem-r calls this when the user hits the Reset button.
        """
        _scan_state.pop('candidates', None)
        self.send_json(200, {'ok': True, 'message': 'Scan session cleared'})

    def log_message(self, fmt, *args):
        """Cleaner request logging — omit the default timestamp noise."""
        print(f'  {self.address_string()}  {fmt % args}')


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    print()
    print('  Theem-r Scanner Bridge')
    print('  ─────────────────────────────────────────────────────')
    print(f'  HTTP listening on  http://{HTTP_HOST}:{HTTP_PORT}')
    print(f'  Emulator target    udp://{DEVICE_IP}:{DEVICE_PORT}')
    print()
    print(f'  Edit DEVICE_IP in bridge.py to your device\'s Wi-Fi IP.')
    print(f'  (Settings → About → Status → IP address)')
    print()
    print('  In Theem-r Scanner tab:')
    print(f'    IP = 127.0.0.1   Port = {HTTP_PORT}   → Test')
    print()
    print('  Press Ctrl+C to stop.')
    print()

    try:
        server = HTTPServer((HTTP_HOST, HTTP_PORT), BridgeHandler)
        server.serve_forever()   # process requests until Ctrl+C
    except KeyboardInterrupt:
        print('\n  Bridge stopped.')
    except OSError as e:
        print(f'\n  Error: {e}')
        print(f'  Port {HTTP_PORT} may already be in use.')
        print('  Close any other bridge instance and try again.')
        sys.exit(1)


if __name__ == '__main__':
    main()
