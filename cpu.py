from __future__ import annotations
from bus import Bus

# op codes

# stack operations
# 00 NOP      
# 01 BRK/HLT
# 02 DROP
# 03 DUP
# 04 SWAP
# 05 OVER
# 06 ROT
# 07 NIP
# 08 PICK n     (next byte n)

# literals & addressing
# 10 LIT8 imm8
# 11 LIT16 lo hi
# 12 LDA8       (addr16 -- val8)
# 13 STA8       (val8 addr16 --)
# 14 LDA16      (addr16 -- lo hi)
# 15 STA16      (lo hi addr16 --)

# alu (8-bit unless noted)
# 20 ADD
# 21 SUB
# 22 AND
# 23 OR
# 24 XOR
# 25 NOT
# 26 SHL1
# 27 SHR1
# 28 ROL1
# 29 ROR1
# 2A CMP         ; (a b --) sets Z/N/C based on a-b, leaves nothing
# 2B ADD16       ; (lo1 hi1 lo2 hi2 -- lo hi) unsigned, sets C
# 2C INC         ; (x -- x+1)
# 2D DEC

# control flow
# 30 JMP rel8
# 31 JZ  rel8   ; if Z
# 32 JNZ rel8
# 33 JC  rel8
# 34 JNC rel8
# 35 CALL abs16
# 36 RET
# 37 SYS n      ; emulator syscall hook (dev only)

# io & timing
# 40 IN  port    ; ( -- val8)
# 41 OUT port    ; (val8 --)
# 42 WAIT_VBL    ; blocks until VBLANK flag set (and clears it)
# 43 PUSHRS      ; (x -- ) to RS
# 44 POPRS       ; ( -- x) from RS


class CPU:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.pc = 0x0000
        self.running = True
        self.ds = []     # data stack (bytes)
        self.rs = []     # return stack
    def reset(self, pc=0x0000):
        self.pc = pc; self.running = True; self.ds.clear(); self.rs.clear()
    def fetch8(self):
        b = self.bus.read8(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return b
    def push8(self, v): self.ds.append(v & 0xFF)
    def pop8(self):     return self.ds.pop() if self.ds else 0  # add underflow checks!
    def step(self):
        op = self.fetch8()
        if op == 0x00:  # NOP
            pass
        elif op == 0x01:  # LIT8
            self.push8(self.fetch8())
        elif op == 0x02:  # ADD
            b, a = self.pop8(), self.pop8()
            self.push8((a + b) & 0xFF)
        elif op == 0x10:  # LD8: (addr_lo addr_hi -- val)
            lo, hi = self.pop8(), self.pop8()
            self.push8(self.bus.read8((hi<<8)|lo))
        elif op == 0x11:  # ST8: (val addr_lo addr_hi --)
            lo, hi = self.pop8(), self.pop8(); val = self.pop8()
            self.bus.write8((hi<<8)|lo, val)
        elif op == 0x30:  # JMP rel8
            offset = self.fetch8()
            if offset & 0x80: offset -= 0x100  # sign extend
            self.pc = (self.pc + offset) & 0xFFFF
        elif op == 0xFF:  # BRK
            self.running = False
        else:
            # Unknown opcode → stop (or trap)
            print(f"Unknown opcode {op:02X} at PC={self.pc-1:04X}")
            self.running = False
    def run(self, max_steps=10_000_000):
        for _ in range(max_steps):
            if not self.running: break
            self.step()    