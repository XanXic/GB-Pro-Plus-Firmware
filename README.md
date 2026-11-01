# GB Pro+ firmware (v5)

A modified version of the firmware for the GB Pro+ Game Boy flash cartridge. The cart seems to be a clone of the original EverDrive GB, and its shipped firmware is a modified one of the EverDrive GB OS (v4) with no documentation. This version makes the cart boot straight into the last game you loaded, plus a few small fixes.

The untouched stock v4 firmware I received is included in case you want to go back or just want a copy.

Tested on a GB Pro+ cartridge marked **Rev. H**.

## What's different in v5

- **Auto-start.** If a game has been loaded before, the cart boots straight into it. Hold **B** during boot to get to the menu instead. "Hold B for menu" shows on screen while it boots.
- **Shows what it's starting.** "Auto starting:" and the game's file name are shown before launching.
- **Save backup on every start.** Before the game starts, its save is copied to the SD card (`/EDGB/SAVE/<game>.srm`). The stock firmware only did this when you switched to a different game, so with auto-start your saves would otherwise never get backed up. If you don't want this, use the `v5-no-backup` build instead; it's the same in every other way.
- **Version** in Device Info is 5.

Everything else works the same as stock.

## Installing

The microSD card needs to be formatted as FAT32.

1. Back up the `/EDGB/GBOS.GB` that's currently on your SD card.
2. Copy `firmware/v5/GBOS.GB` (or `firmware/v5-no-backup/GBOS.GB`) onto the card as `/EDGB/GBOS.GB`.
3. Load a game once from the menu. From then on it auto-starts.

To go back, put your backup (or `firmware/stock-v4/GBOS.GB`) in its place.

## Using the cart

The stock firmware has no manual, so here's what we know.

Buttons below are the defaults. The **Swap Key** option swaps A and B. Holding any button at boot gets you to the menu, so that part isn't affected.

**In the file browser**

| Button | Does |
|---|---|
| SELECT | Main menu |
| START | Start the game that's loaded in the cart |

**File menu (B on a ROM)**

- **Load And Start** loads the game into the cart and starts it.
- **Load Only** loads it without starting. Press START later to play it.

Loading a game also backs up the previous game's save to the SD card, then loads the new game's save from `/EDGB/SAVE/` if there is one.

**Main menu (SELECT)**

- **Options**: the loaded game's Mapper, ROM Size, RAM Size, Save RAM and Swap Key settings.
- **Cheats**
- **Device Info**: CPLD, BIOS and OS versions.
- **About**

**Save files**

Saves live on the cart while you play and get copied to `/EDGB/SAVE/<game name>.srm`. Pressing B on a `.srm` file in the browser gives options to copy it into the cart's save memory, or the cart's save into the file.

To restore an older save in v5: put the old `.srm` on the card, hold B at boot, find the `.srm` in `/EDGB/SAVE/`, press B and pick **Copy File To SRAM**, then press START. Don't just overwrite the file and reboot, because auto-start backs up the cart's current save over it first.

| File | SHA-1 |
|---|---|
| `firmware/stock-v4/GBOS.GB` | `92c3c445a4f99511df2b4c047035c94c2d7e340b` |
| `firmware/v5/GBOS.GB` | `cb4003e4ecab3fe0a227874922eccb2511bfdfa6` |
| `firmware/v5-no-backup/GBOS.GB` | `984a6c5ca29faafe6c73af465897c9666c3fa3a6` |

## Disclaimer

Use at your own risk. This is unofficial firmware for an unofficial cartridge. It's been tested on one cart revision. Back up your SD card and saves before installing. Not affiliated with krikzz or EverDrive.

## Credits

Original EverDrive GB OS by I. Golubovskiy (krikzz). v5 changes by XanXic.
