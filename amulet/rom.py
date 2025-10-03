import torch
from device import Device

class Rom(Device):
    def __init__(self, start, data: bytes):
        self.start, self.size = start, len(data)
        self.mem = torch.tensor(list(data), dtype=torch.uint8)
    def handles(self, addr): return self.start <= addr < self.start + self.size
    def read8(self, addr):   return int(self.mem[addr - self.start].item())
    def write8(self, addr, v): pass  # should this raise an error?