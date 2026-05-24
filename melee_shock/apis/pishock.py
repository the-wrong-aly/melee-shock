import json
import logging

import serial
import serial.tools.list_ports
import time

from melee_shock.apis.base import BaseAPI

logger = logging.getLogger(__name__)


class PiShockSerialAPI(BaseAPI):
    def __init__(self):
        self.ser = None
        for port in serial.tools.list_ports.comports():
            if port.vid == 0x1A86 and port.pid == 0x7523:
                self.ser = serial.Serial(port.device, 115200)

        if not self.ser:
            raise RuntimeError("Cannot find PiShock hub")

        # Find the shocker ids
        self.ser.write((json.dumps({"cmd": "info"}) + "\n").encode())
        time.sleep(1)
        response = self.ser.read(self.ser.in_waiting).decode().strip()
        logger.debug("PiShock info: %s", response)

        info_line = next(
            (
                line
                for line in response.splitlines()
                if line.startswith("TERMINALINFO:")
            ),
            None,
        )
        if info_line is None:
            raise RuntimeError("No TERMINALINFO in PiShock response")
        info = json.loads(info_line.removeprefix("TERMINALINFO:").strip())

        self.shocker_ids: list[int] = [s["id"] for s in info["shockers"]]
        logger.info("Found shockers: %s", self.shocker_ids)

    def _send(self, player_id: int, op: str, intensity: int | None, duration: int):
        # TODO: map player_id to shocker_id
        shocker_id = self.shocker_ids[0]
        value = {"id": shocker_id, "op": op, "duration": duration}
        if intensity is not None:
            value["intensity"] = intensity
        self.ser.write((json.dumps({"cmd": "operate", "value": value}) + "\n").encode())

        logger.debug(
            f"player={player_id} op={op} intensity={intensity} duration={duration}"
        )

    def beep(self, player_id: int, duration: int):
        self._send(player_id, "beep", None, duration)

    def vibrate(self, player_id: int, intensity: int, duration: int):
        self._send(player_id, "vibrate", intensity, duration)

    def shock(self, player_id: int, intensity: int, duration: int):
        self._send(player_id, "shock", intensity, duration)
