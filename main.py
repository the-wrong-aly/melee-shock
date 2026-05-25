import logging
import signal
import sys
from pathlib import Path

import melee_shock.config as config
from melee_shock.engine import Engine, OutputMode, Player
from melee_shock.modes.registry import get as get_mode
from melee_shock.apis.pishock import PiShockSerialAPI
from melee_shock.sources.dolphin import DolphinSource

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def build_players(cfg: config.Config) -> dict[int, Player]:
    players = {}
    for port, p in cfg.players.items():
        if p.mode is not None:
            mode_cls, _ = get_mode(p.mode.name)
            mode = mode_cls(p.mode)
        else:
            mode = None
        players[port] = Player(
            output_mode=OutputMode(p.output_mode),
            mode=mode,
        )
        logger.info(
            "Player %d: %s via %s",
            port,
            p.mode.name if p.mode else "none",
            p.output_mode,
        )

    if not players:
        raise RuntimeError("No players configured — nothing to do")

    return players


def main():
    import argparse

    parser = argparse.ArgumentParser(description="PiShock SSBM")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to config file (default: config.toml)",
    )
    args = parser.parse_args()

    logger.info("Loading config from %s", args.config)
    try:
        cfg = config.load(args.config)
        logging.getLogger().setLevel(logging.DEBUG if cfg.debug else logging.INFO)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Config error: %s", e)
        sys.exit(1)

    try:
        players = build_players(cfg)
        api = PiShockSerialAPI(players)
        source = DolphinSource(
            dolphin_path=cfg.dolphin_path,
            iso_path=cfg.iso_path,
            debug=cfg.debug,
        )
        engine = Engine(
            source, players, api, global_max_intensity=cfg.global_max_intensity
        )
    except (ValueError, RuntimeError) as e:
        logger.error("Setup error: %s", e)
        sys.exit(1)

    def handle_sigint(sig, frame):
        logger.info("Shutting down...")
        engine.stop()

    signal.signal(signal.SIGINT, handle_sigint)

    logger.info("Connecting to Dolphin...")
    try:
        source.connect()
    except RuntimeError as e:
        logger.error("Failed to connect: %s", e)
        sys.exit(1)

    logger.info("Running — press ^C to stop")
    engine.run()


if __name__ == "__main__":
    main()
