# Repository instructions

This repo holds a single LG Energy Saving automation, a new-install helper/fan example, and a patch against the pinned unsigned webOS override. Read README.md and WORK_LOG.md before changing behavior.

Keep the public files free of real device IDs, pairing keys, LAN addresses, host paths, and Home Assistant storage or logs. Use `media_player.lg_tv` as the TV placeholder. Preserve the five label/value mappings, physical readback, queued writes, failure notification, restored helper selection, and online reconciliation when editing the automation.

Run the configuration, Script, and SSDP checks from README.md with the supported Home Assistant runtime. Verify a patch against the pinned upstream commit before changing its provenance or installation steps. Report physical-device evidence separately from tests with fake responses.

For live TV tests, use only Off and Minimum unless the user explicitly authorizes another mode. Restore the starting selection when it is one of those two modes. Mock tests may cover all five mappings.
