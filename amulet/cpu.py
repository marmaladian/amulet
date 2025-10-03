from __future__ import annotations
from bus import Bus

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

    def exec_sys(self):
        n = self.fetch8()
        if n == 0x01:                                                     # prz
            hi, lo = self.pop8(), self.pop8()
            addr = (hi << 8) | lo
            out = bytearray()
            while True:
                c = self.bus.read8(addr)
                if c == 0: break
                out.append(c)
                addr = (addr + 1) & 0xFFFF
            print(out.decode('ascii', errors='replace'), end='', flush=True)
        elif n == 0x10:                                                   # trc
            tos = list(self.ds[-4:])
            print(f"[PC={self.pc:04X}] DS={tos}")

    def step(self):
        op = self.fetch8()
        
        # system
        if op == 0x00:                                                    # ZZZ
            pass
        if op == 0x01:                                                    # SYS
            self.exec_sys()
        elif op == 0x0F:                                                  # HLT
            print("HLT!")
            self.running = False

        # stack ops
        elif op == 0x20:                                                  # POP
            self.pop8()
        elif op == 0x21:                                                  # DUP
            if self.ds: self.push8(self.ds[-1])
        elif op == 0x22:                                                  # SWP
            if len(self.ds) >= 2:
                self.ds[-1], self.ds[-2] = self.ds[-2], self.ds[-1]
        elif op == 0x23:                                                  # OVR
            if len(self.ds) >= 2:
                self.push8(self.ds[-2])
        elif op == 0x24:                                                  # ROT
            if len(self.ds) >= 3:
                self.ds[-3], self.ds[-2], self.ds[-1] = self.ds[-2], self.ds[-1], self.ds[-3]
        elif op == 0x25:                                                  # NIP
            raise NotImplementedError("NIP not implemented")
        elif op == 0x26:                                                  # TUC
            raise NotImplementedError("TUC not implemented")
        
        # literals & addressing
        elif op == 0x30:                                                  # ST1
            hi, lo = self.pop8(), self.pop8()
            val = self.pop8()
            self.bus.write8((hi<<8)|lo, val)
        elif op == 0x31:                                                  # ST2
            hi, lo = self.pop8(), self.pop8()
            val_lo, val_hi = self.pop8(), self.pop8()
            self.bus.write8((hi<<8)|lo, val_lo)
            self.bus.write8(((hi<<8)|lo)+1, val_hi)
        elif op == 0x32:                                                  # LD1
            hi, lo = self.pop8(), self.pop8()
            self.push8(self.bus.read8((hi<<8)|lo))
        elif op == 0x33:                                                  # LD2
            hi, lo = self.pop8(), self.pop8()
            val_lo = self.bus.read8((hi<<8)|lo)
            val_hi = self.bus.read8(((hi<<8)|lo)+1)
            self.push8(val_lo)
            self.push8(val_hi)
        elif op == 0x34:                                                  # IM1
            self.push8(self.fetch8())
        elif op == 0x35:                                                  # IM2
            self.push8(self.fetch8()) # lo
            self.push8(self.fetch8()) # hi
        
        # alu (8-bit)
        elif op == 0x40:                                                  # ADD
            b, a = self.pop8(), self.pop8()
            self.push8((a + b) & 0xFF)
        elif op == 0x41:                                                  # SUB
            b, a = self.pop8(), self.pop8()
            self.push8((a - b) & 0xFF)
        elif op == 0x42:                                                  # AND
            b, a = self.pop8(), self.pop8()
            self.push8(a & b)
        elif op == 0x43:                                                  # IOR
            b, a = self.pop8(), self.pop8()
            self.push8(a | b)
        elif op == 0x44:                                                  # XOR
            b, a = self.pop8(), self.pop8()
            self.push8(a ^ b)
        elif op == 0x45:                                                  # NOT
            a = self.pop8()
            self.push8((~a) & 0xFF)
        elif op == 0x46:                                                  # BSL
            raise NotImplementedError("BSL not implemented")
        elif op == 0x47:                                                  # BRL
            raise NotImplementedError("BRL not implemented")
        
        # control flow
        elif op == 0x50:                                                  # JSR
            hi, lo = self.fetch8(), self.fetch8()
            self.rs.append((self.pc >> 8) & 0xFF)
            self.rs.append(self.pc & 0xFF)
            self.pc = (hi << 8) | lo
        elif op == 0x51:                                                  # RTN
            if self.rs:
                lo = self.rs.pop()
                hi = self.rs.pop()
                self.pc = (hi << 8) | lo
            else:
                raise RuntimeError("Stack underflow")
                # self.running = False  # underflow
        elif op == 0x52:                                                  # RTZ
            cond = self.pop8()
            if cond == 0:
                if self.rs:
                    lo = self.rs.pop()
                    hi = self.rs.pop()
                    self.pc = (hi << 8) | lo
                else:
                    raise RuntimeError("Stack underflow")
                    # self.running = False  # underflow
        elif op == 0x53:                                                  # RET
            if self.rs:
                lo = self.rs.pop()
                hi = self.rs.pop()
                self.pc = (hi << 8) | lo
            else:
                raise RuntimeError("Stack underflow")
                # self.running = False  # underflow
        elif op == 0x54:                                                  # HOP
            offset = self.fetch8()
            if offset & 0x80: offset -= 0x100  # sign extend
            self.pc = (self.pc + offset) & 0xFFFF
        elif op == 0x55:                                                  # SKP
            hi, lo = self.pop8(), self.pop8()
            self.pc = (hi << 8) | lo
        elif op == 0x56:                                                  # JMP
            hi, lo = self.fetch8(), self.fetch8()
            self.pc = (hi << 8) | lo
        elif op == 0x57:                                                  # RSW
            # write to return stack from data stack
            raise NotImplementedError("RSW not implemented")
        elif op == 0x58:                                                  # RSR
            # read from return stack to data stack
            raise NotImplementedError("RSR not implemented")

        # io & timing
        elif op == 0x60:                                                  # VBL
            # blocks until VBLANK flag set (then clears)
            raise NotImplementedError("VBL not implemented")
        elif op == 0x61:                                                  # PUT
            raise NotImplementedError("PUT not implemented")
        elif op == 0x62:                                                  # GET
            raise NotImplementedError("GET not implemented")

        # unhandled
        else:
            raise NotImplementedError(f"Unknown opcode {op:02X} at PC={self.pc-1:04X}")
            # self.running = False

    def run(self, max_steps=10_000_000):
        for _ in range(max_steps):
            if not self.running: break
            self.step()    