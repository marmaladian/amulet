class Bus:
    def __init__(self, devices):
        self.devices = devices
    def _dev(self, addr):
        for d in self.devices:
            if d.handles(addr): return d
        raise KeyError(f"No device for address {addr:04X}")
    def read8(self, addr):  return self._dev(addr).read8(addr)
    def write8(self, addr, v): self._dev(addr).write8(addr, v & 0xFF)
