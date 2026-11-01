"""Patch GBOS.GB (EverDrive GB clone OS) for the GB Pro+ cartridge.

Usage: python tools/patch_autoboot.py [--no-backup] [input GBOS.GB] [output path]
Defaults to firmware/stock-v4/GBOS.GB -> firmware/v5/GBOS.GB (firmware/v5-no-backup/ with
--no-backup, which leaves out the save backup on auto-start).

Changes:
  1. Auto-start the last loaded game.
     main ($08E5) calls init ($490A). Stock firmware already boots the last
     game when init returns $C0. We redirect that call to a hook in free space
     ($7CA1) that runs the real init, then returns $C0 only if:
       - init succeeded (SD card mounted),
       - a game has been loaded before (settings filename at [$D859]+5),
       - no button is held during a ~1 s window at the end of boot.
     When it auto-starts it prints "Auto starting:" and the game's file name
     (read from the settings at runtime, capped at 40 chars = 2 screen lines,
     because the print routine has no length limit).
     Before starting, the save RAM is backed up to /EDGB/SAVE/<game>.srm with
     the stock backup routine (skipped for games without a battery save or
     with blank save RAM). Stock firmware only backs up when a different game
     is loaded, which auto-start would otherwise almost never do. A failed
     backup doesn't block the game; the save is still in cart SRAM.
     --no-backup builds without this step (no room for a runtime toggle).
  2. "Hold B for menu" replaces "init..." as the first boot line, so the
     prompt is on screen for the whole boot.
  3. About screen: "EverDrive GB" becomes "GB Pro+", the Support section
     (email, website) is skipped and its strings blanked, and "Developed by:"
     becomes "Based on code by:" (too long to fit in place, so it's written
     into the freed Support string space and the pointer at $5993 moved).
     "LEF/RIG-switch page" becomes "Left/Right: page". In place of the
     Support section it prints "v5 by XanXic" and a blank line, then jumps
     to Control; the rest of that code space holds "Hold B for menu".
  4. OS version shown in Device Info is bumped from 4 to 5.

Firmware routines used (SDCC calling convention: args pushed right to left,
caller pops, 8/16-bit result in e/de):
  $490A init()               -> e: 0 ok, $C0 no SD, else error
  $65E0 print_line(str)      next line of the boot log
  $0864 refresh_screen()     copies the text buffer to VRAM
  $08B8 read_joypad()        -> e: pressed bits (clobbers a, e only)
  $4A78 alloc(size)          -> de: buffer (stack-style heap)
  $4AB6 free(size)
  $5D1B backup_save(file)    -> e: 0 ok / nothing to do, else error
"""
import os
import sys

HOOK = 0x7CA1
FREE_END = 0x7D00
CALL_SITE = 0x08E6
INIT_MSG_PTR = 0x4935  # operand of "ld de,$49E6" ("init...") in init
OS_VERSION = 0x0800    # shown as "OS Version" in Device Info, read only there
NEW_OS_VERSION = 5
POLL_COUNT = 0x3600    # ~72 us per poll -> ~1 s window
FILE_SIZE = 0x00E5     # file object size the stock code allocates
NAME_MAX = 40          # game name chars shown on the boot screen
HOLD_MSG = b"Hold B for menu\x00"
AUTO_MSG = b"Auto starting:\x00"

ABOUT_TITLE = 0x5A40       # "EverDrive GB\0"
ABOUT_SUPPORT_CODE = 0x59B2  # Support heading, email, site, blank line...
ABOUT_SUPPORT_END = 0x59E2   # ...up to the Control heading
ABOUT_SUPPORT_STRINGS = (0x5A6B, 0x5A98)  # "Support:", email, site
ABOUT_CREDIT = 0x5A4E        # "Developed by:\0"
ABOUT_CREDIT_PTR = 0x5993    # operand of "ld de,$5A4E", its only reference
NEW_CREDIT = b"Based on code by:\x00"
ABOUT_CONTROLS = 0x5AA1      # "LEF/RIG-switch page\0"
NEW_CONTROLS = b"Left/Right: page\x00"
ABOUT_BLANK = 0x5A4D         # "" string the About screen prints as a blank line
CREDIT_V5 = b"v5 by XanXic\x00"

# Freed string space: old "Developed by:" (14 bytes) and the tail of the
# Support strings after NEW_CREDIT.
CREDIT_V5_AT = ABOUT_CREDIT
AUTO_MSG_AT = ABOUT_SUPPORT_STRINGS[0] + len(NEW_CREDIT)


def build_about_v5():
    """Replacement for the Support section: v5 credit, blank line, jr Control."""
    code = bytearray()
    for s in (CREDIT_V5_AT, ABOUT_BLANK):
        code += bytes([0x11, s & 0xFF, s >> 8,   # ld de,str
                       0xD5, 0xCD, 0xE0, 0x65,   # push de / call print_line
                       0xF1])                    # pop af
    code += bytes([0x18, ABOUT_SUPPORT_END - (ABOUT_SUPPORT_CODE + len(code) + 2)])
    return bytes(code)


# Rest of the skipped Support code holds the boot prompt.
MSG_AREA = ABOUT_SUPPORT_CODE + len(build_about_v5())
HOLD_MSG_AT = MSG_AREA


def build_hook(backup=True):
    code = bytearray()
    labels, fixups = {}, []

    def emit(*b):
        code.extend(b)

    def jr_nz(label):
        emit(0x20, 0)
        fixups.append((len(code) - 1, label))

    def word(v):
        return v & 0xFF, v >> 8

    emit(0xCD, *word(0x490A))       # call init
    emit(0x7B, 0xB7, 0xC0)          # ld a,e / or a / ret nz
    emit(0x21, *word(0xD859))       # ld hl,settings_ptr
    emit(0x2A, 0x66, 0x6F)          # ld a,(hl+) / ld h,(hl) / ld l,a
    emit(0x11, *word(5))            # ld de,5 (last-game filename)
    emit(0x19, 0x7E, 0xB7, 0xC8)    # add hl,de / ld a,(hl) / or a / ret z
    emit(0xE5)                      # push hl (name)

    emit(0x01, *word(POLL_COUNT))   # ld bc,POLL_COUNT
    labels["poll"] = len(code)
    emit(0xCD, *word(0x08B8))       # call read_joypad
    emit(0x7B, 0xB7)                # ld a,e / or a
    jr_nz("menu")                   # button held -> stay in menu
    emit(0x0B, 0x78, 0xB1)          # dec bc / ld a,b / or c
    jr_nz("poll")

    emit(0x11, *word(AUTO_MSG_AT))  # ld de,AUTO_MSG
    emit(0xD5, 0xCD, *word(0x65E0), 0xF1)   # push de / call print_line / pop af
    emit(0xD1)                      # pop de (name)
    emit(0x21, *word(NAME_MAX))     # ld hl,NAME_MAX
    emit(0x19, 0x7E)                # add hl,de / ld a,(hl)
    emit(0xE5, 0xF5)                # push hl / push af (save cut point + byte)
    emit(0x36, 0x00)                # ld (hl),0 (cut name for printing)
    emit(0xD5, 0xCD, *word(0x65E0), 0xF1)   # push de / call print_line / pop af
    emit(0xF1, 0xE1, 0x77)          # pop af / pop hl / ld (hl),a (restore)
    emit(0xCD, *word(0x0864))       # call refresh_screen

    if backup:
        emit(0x21, *word(FILE_SIZE))    # ld hl,FILE_SIZE
        emit(0xE5, 0xCD, *word(0x4A78), 0xE1)   # push hl / call alloc / pop hl
        emit(0xD5, 0xCD, *word(0x5D1B), 0xE1)   # push de / call backup_save / pop hl
        emit(0x21, *word(FILE_SIZE))    # ld hl,FILE_SIZE
        emit(0xE5, 0xCD, *word(0x4AB6), 0xE1)   # push hl / call free / pop hl
    emit(0x1E, 0xC0, 0xC9)          # ld e,$C0 / ret -> main starts game
    labels["menu"] = len(code)
    emit(0xE1)                      # pop hl (drop name)
    emit(0x1E, 0x00, 0xC9)          # ld e,0 / ret -> menu

    for pos, label in fixups:
        rel = labels[label] - (pos + 1)
        assert -128 <= rel <= 127
        code[pos] = rel & 0xFF
    return bytes(code)


def main():
    args = sys.argv[1:]
    backup = "--no-backup" not in args
    args = [a for a in args if a != "--no-backup"]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = args[0] if len(args) > 0 else os.path.join(root, "firmware", "stock-v4", "GBOS.GB")
    dst = args[1] if len(args) > 1 else os.path.join(
        root, "firmware", "v5" if backup else "v5-no-backup", "GBOS.GB")
    rom = bytearray(open(src, "rb").read())
    hook = build_hook(backup)

    assert len(rom) == 0x8000, "unexpected file size"
    assert rom[CALL_SITE - 1:CALL_SITE + 3] == bytes([0xC5, 0xCD, 0x0A, 0x49]), \
        "call site doesn't match (already patched or different version?)"
    assert rom[INIT_MSG_PTR - 1:INIT_MSG_PTR + 2] == bytes([0x11, 0xE6, 0x49])
    assert rom[OS_VERSION] == 4, "unexpected OS version"
    assert rom[ABOUT_TITLE:ABOUT_TITLE + 13] == b"EverDrive GB\x00"
    assert rom[ABOUT_SUPPORT_CODE:ABOUT_SUPPORT_CODE + 3] == bytes([0x21, 0x01, 0x00])
    assert rom[ABOUT_SUPPORT_END:ABOUT_SUPPORT_END + 3] == bytes([0x21, 0x01, 0x00])
    assert rom[ABOUT_CREDIT:ABOUT_CREDIT + 14] == b"Developed by:\x00"
    assert rom[ABOUT_CREDIT_PTR:ABOUT_CREDIT_PTR + 2] == ABOUT_CREDIT.to_bytes(2, "little")
    assert rom[ABOUT_CONTROLS:ABOUT_CONTROLS + 20] == b"LEF/RIG-switch page\x00"
    assert len(NEW_CONTROLS) <= 20
    assert HOLD_MSG_AT + len(HOLD_MSG) <= ABOUT_SUPPORT_END, "prompt doesn't fit"
    assert AUTO_MSG_AT + len(AUTO_MSG) <= ABOUT_SUPPORT_STRINGS[1], "message doesn't fit"
    assert len(CREDIT_V5) <= 14 and rom[ABOUT_BLANK] == 0
    assert HOOK + len(hook) <= FREE_END, "hook too big for free space"
    assert all(b == 0xFF for b in rom[HOOK:HOOK + len(hook)]), "hook area not free"

    # 1. auto-start hook
    rom[CALL_SITE + 1:CALL_SITE + 3] = HOOK.to_bytes(2, "little")
    rom[HOOK:HOOK + len(hook)] = hook
    # 2. boot prompt as the first line
    rom[INIT_MSG_PTR:INIT_MSG_PTR + 2] = HOLD_MSG_AT.to_bytes(2, "little")
    # 3. About screen
    rom[ABOUT_TITLE:ABOUT_TITLE + 13] = b"GB Pro+".ljust(13, b"\x00")
    about_v5 = build_about_v5()
    rom[ABOUT_SUPPORT_CODE:MSG_AREA] = about_v5
    rom[MSG_AREA:ABOUT_SUPPORT_END] = bytes(ABOUT_SUPPORT_END - MSG_AREA)
    rom[HOLD_MSG_AT:HOLD_MSG_AT + len(HOLD_MSG)] = HOLD_MSG
    lo, hi = ABOUT_SUPPORT_STRINGS
    rom[lo:hi] = bytes(hi - lo)
    rom[ABOUT_CREDIT:ABOUT_CREDIT + 14] = bytes(14)
    rom[CREDIT_V5_AT:CREDIT_V5_AT + len(CREDIT_V5)] = CREDIT_V5
    rom[lo:lo + len(NEW_CREDIT)] = NEW_CREDIT
    rom[AUTO_MSG_AT:AUTO_MSG_AT + len(AUTO_MSG)] = AUTO_MSG
    rom[ABOUT_CREDIT_PTR:ABOUT_CREDIT_PTR + 2] = lo.to_bytes(2, "little")
    rom[ABOUT_CONTROLS:ABOUT_CONTROLS + 20] = NEW_CONTROLS.ljust(20, b"\x00")
    # 4. version
    rom[OS_VERSION] = NEW_OS_VERSION

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    open(dst, "wb").write(rom)
    print(f"wrote {dst} ({len(hook)} byte hook at ${HOOK:04X}, "
          f"{FREE_END - HOOK - len(hook)} bytes free left; "
          f"{ABOUT_SUPPORT_END - HOLD_MSG_AT - len(HOLD_MSG)} + "
          f"{ABOUT_SUPPORT_STRINGS[1] - AUTO_MSG_AT - len(AUTO_MSG)} free in About gaps)")


if __name__ == "__main__":
    main()
