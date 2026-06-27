"""
WiiStreamClient + WiiSource

WiiStreamClient is a drop-in replacement for SlippstreamClient that speaks
the Nintendont-Slippi TCP/UBJSON protocol instead of Dolphin's ENet/JSON
protocol. It exposes the same interface so WiiSource stays as thin as
DolphinSource.

Wire protocol (Nintendont-Slippi, TCP port 51441):
  [4-byte big-endian length][UBJSON payload]

Message types:
  1 = HANDSHAKE  (client sends cursor+token, Wii replies with nick/version)
  2 = REPLAY     (Wii streams raw .slp bytes in payload["data"])
  3 = KEEPALIVE
"""

from .base import BaseSource

import logging
import os
import socket
import struct

import ubjson

logger = logging.getLogger(__name__)

_TYPE_HANDSHAKE = 1
_TYPE_REPLAY = 2
_TYPE_KEEPALIVE = 3


class WiiStreamClient:
    """
    Drop-in replacement for SlippstreamClient that connects to a Wii
    running Slippi Nintendont over TCP/51441 instead of Dolphin over ENet/51441.

    Exposes the same attributes and dispatch() method so it can slot directly
    into melee.Console in place of SlippstreamClient.
    """

    # Default sizes for events we might see before a PAYLOADS event
    _PAYLOAD_CMD = 0x35
    _GAME_START_CMD = 0x36
    _BOOKEND_CMD = 0x3C

    def __init__(self, address: str = "127.0.0.1", port: int = 51441):
        self.address = address
        self.port = port
        self.running = False

        self._sock: socket.socket | None = None

        # Maps command byte → total event length (including command byte)
        self._eventsize: dict[int, int] = {}
        # Carry-over bytes from a previous REPLAY message that didn't end on a
        # frame boundary. Prepended to the next REPLAY message's data.
        self._carry: bytes = b""
        # Frames translated from a single REPLAY message but not yet returned
        self._pending: list[dict] = []

        # Attributes console.py reads from slippstream
        self.playedOn = "wii"
        self.timestamp = ""
        self.consoleNick = ""
        self.players = {}

    def _send_handshake(self):
        payload = {
            "type": _TYPE_HANDSHAKE,
            "payload": {
                "cursor": b"\xff" * 8,  # start from end of buffer (live data only)
                "clientToken": os.urandom(4),
            },
        }
        self._send(payload)

    def _send(self, msg: dict):
        data = ubjson.dumpb(msg)
        self._sock.sendall(struct.pack(">I", len(data)) + data)

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Wii disconnected")
            buf.extend(chunk)
        return bytes(buf)

    def _recv_message(self) -> dict:
        header = self._recv_exact(4)
        length = struct.unpack(">I", header)[0]
        if length == 0:
            return {"type": _TYPE_KEEPALIVE, "payload": {}}
        return ubjson.loadb(self._recv_exact(length))

    def _translate(self, wii_msg: dict) -> list[dict]:
        t = wii_msg.get("type")
        p = wii_msg.get("payload", {})

        if t == _TYPE_HANDSHAKE:
            # New connection: reset carry-over state
            self._carry = b""
            self._eventsize = {}
            return [
                {
                    "type": "connect_reply",
                    "nick": p.get("nick", ""),
                    "version": p.get("version", ""),
                    "cursor": 0,
                }
            ]

        elif t == _TYPE_REPLAY:
            raw = p.get("data", b"")
            if not raw:
                return []
            return self._split_into_frames(raw)

        return []

    def _split_into_frames(self, data: bytes) -> list[dict]:
        """
        Walk the raw .slp byte stream event-by-event, carrying over any
        incomplete frame across REPLAY message boundaries, and emit one
        game_event dict per complete frame (i.e. per FRAME_BOOKEND).

        Bytes are accumulated in self._carry between calls so that a frame
        split across two TCP messages is never emitted until it's complete.

        When a GAME_START event is detected, any frames accumulated from the
        previous game are discarded so the engine sees only the new game.
        """
        data = self._carry + data
        self._carry = b""

        out: list[dict] = []
        frame_start = 0
        i = 0
        payloads_start: int | None = None

        while i < len(data):
            cmd = data[i]

            # Learn event sizes from the PAYLOADS event (0x35)
            if cmd == self._PAYLOAD_CMD:
                if i + 1 >= len(data):
                    break
                payload_size = data[i + 1]
                total = payload_size + 1
                if i + total > len(data):
                    break
                num_commands = (payload_size - 1) // 3
                cursor = i + 2
                for _ in range(num_commands):
                    if cursor + 2 >= i + total:
                        break
                    c = data[cursor]
                    clen = struct.unpack_from(">H", data, cursor + 1)[0]
                    self._eventsize[c] = clen + 1
                    cursor += 3
                self._eventsize[cmd] = total
                payloads_start = i
                i += total
                continue

            size = self._eventsize.get(cmd)
            if size is None or size == 0:
                logger.warning(
                    "WiiStreamClient: unknown command byte 0x%02x at offset %d; "
                    "carrying %d bytes forward",
                    cmd,
                    i,
                    len(data) - frame_start,
                )
                self._carry = data[frame_start:]
                return out

            if i + size > len(data):
                break

            i += size

            if cmd == self._GAME_START_CMD:
                # New game: discard stale frames from the previous game and
                # reset the frame window to start from the preceding PAYLOADS
                # block so console.py can re-learn event sizes.
                out.clear()
                self._pending.clear()
                frame_start = payloads_start if payloads_start is not None else i - size

            elif cmd == self._BOOKEND_CMD:
                out.append(
                    {
                        "type": "game_event",
                        "payload": data[frame_start:i],
                    }
                )
                frame_start = i

        self._carry = data[frame_start:]
        return out

    def connect(self) -> bool:
        try:
            self._sock = socket.create_connection(
                (self.address, self.port), timeout=5.0
            )
            self._sock.settimeout(None)
        except OSError as e:
            logger.error("WiiStreamClient: connect failed: %s", e)
            return False

        try:
            self._send_handshake()
        except OSError as e:
            logger.error("WiiStreamClient: handshake send failed: %s", e)
            return False

        self.running = True
        return True

    def shutdown(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self.running = False

    def dispatch(self, polling_mode: bool, timeout: float = 0):
        assert self.running, "Can only dispatch while running."

        # Return any frames buffered from the previous REPLAY message first
        if self._pending:
            return self._pending.pop(0)

        while True:
            try:
                if polling_mode:
                    self._sock.settimeout(timeout)
                    try:
                        wii_msg = self._recv_message()
                    except socket.timeout:
                        return None
                    finally:
                        self._sock.settimeout(None)
                else:
                    wii_msg = self._recv_message()
            except (ConnectionError, OSError):
                from melee.slippstream import EnetDisconnected

                raise EnetDisconnected()

            msgs = self._translate(wii_msg)
            if not msgs:
                if polling_mode:
                    return None
                continue

            self._pending.extend(msgs[1:])
            return msgs[0]


class WiiSource(BaseSource):
    def __init__(self, ip: str, port: int = 51441, debug=False):
        import melee

        if debug:
            self.log = melee.Logger()
        else:
            self.log = None

        self.console = melee.Console(
            is_dolphin=False,
            slippi_address=ip,
            slippi_port=port,
        )
        # Swap out the slippstream client Console just created with ours
        self.console._slippstream = WiiStreamClient(ip, port)

    def connect(self):
        if not self.console.connect():
            raise RuntimeError(
                f"Failed to connect to Wii at "
                f"{self.console.slippi_address}:{self.console.slippi_port}"
            )

    def get_state(self):
        gamestate = self.console.step()
        if self.log:
            self.log.logframe(gamestate)
            self.log.writeframe()
        return gamestate

    def stop(self):
        self.console._slippstream.shutdown()
        self.console.stop()
