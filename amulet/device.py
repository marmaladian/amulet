class Device:
    def read8(self, addr: int) -> int: raise NotImplementedError
    def write8(self, addr: int, val: int): raise NotImplementedError
    def handles(self, addr: int) -> bool: raise NotImplementedError