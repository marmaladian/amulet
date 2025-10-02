import torch
from device import Device

class Ram(Device):
    def __init__(self, start, size):
        self.start, self.size = start, size
        self.mem = torch.zeros(size, dtype=torch.uint8)
    def handles(self, addr): return self.start <= addr < self.start + self.size
    def read8(self, addr):   return int(self.mem[addr - self.start].item())
    def write8(self, addr, v): self.mem[addr - self.start] = v & 0xFF
