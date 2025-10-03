class Bus:
    def __init__(self, devices):
        self.devices = devices
    
    def _dev(self, addr):
        for d in self.devices:
            if d.handles(addr): return d
        raise KeyError(f"No device for address {addr:04X}")
    
    def read8(self, addr):  return self._dev(addr).read8(addr)
    
    def write8(self, addr, v): self._dev(addr).write8(addr, v & 0xFF)
    
    # def read16(self, addr): return self.read8(addr) | (self.read8((addr+1)&0xFFFF)<<8)
    
    # def write16(self, addr, v):
    #     self.write8(addr, v & 0xFF)
    #     self.write8((addr+1)&0xFFFF, (v>>8) & 0xFF)

    def dump(self, start=0, end=0xFFFF):
        for addr in range(start, end+1, 16):
            chunk = [self.read8(a) for a in range(addr, min(addr+16, end+1))]
            print(f"{addr:04X}: " + " ".join(f"{b:02X}" for b in chunk))