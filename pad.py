from device import Device

class ControllerHub(Device):
    PAD1 = 0xE00A
    PAD2 = 0xE00B
    CTRL = 0xE00C
    def __init__(self, num_pads=2):
        self.num = num_pads
        self.live = [0]*num_pads        # updated by host
        self.latched = [0]*num_pads     # visible to CPU
        self.ctrl = 0

    def handles(self, addr):
        return addr in (self.PAD1, self.PAD2, self.CTRL)

    def read8(self, addr):
        if addr == self.PAD1: return self.latched[0]
        if addr == self.PAD2: return self.latched[1] if self.num > 1 else 0
        if addr == self.CTRL: return self.ctrl
        return 0

    def write8(self, addr, val):
        if addr == self.CTRL:
            self.ctrl = val & 0xFF
            if val & 0x01:               # latch on bit0
                self.latched[:] = [x & 0xFF for x in self.live]

    # host API
    def set_state(self, pad_index:int, bits:int):
        if 0 <= pad_index < self.num:
            self.live[pad_index] = bits & 0xFF

    # call this from your VBLANK tick if you prefer automatic latching
    def vblank_latch(self):
        self.latched[:] = [x & 0xFF for x in self.live]
