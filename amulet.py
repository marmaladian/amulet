# create a new pcu
import pygame
from device import Device
from ppu import PPU, SCREEN_W, SCREEN_H, init_demo_scene, move_sprite_x
from rom import Rom
from ram import Ram
from bus import Bus
from cpu import CPU
from pad import ControllerHub

def run_demo(cpu, bus, ppu_scale=3):
    pygame.init()
    window = pygame.display.set_mode((SCREEN_W*ppu_scale, SCREEN_H*ppu_scale))
    clock = pygame.time.Clock()

    running = True
    while running:
        # TODO: add controller handling
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                print("Quit event")
                running = False

        if cpu.running:
            for _ in range(1000):  # i.e. 1000 ops per frame
                # print(f"PC={cpu.pc:04X} DS={cpu.ds} RS={cpu.rs}, op={bus.read8(cpu.pc):02X}", end='\r')
                cpu.step()
                if not cpu.running:
                    print("CPU halted")
                    running = False
                    break

        # vblank!
        frame_surface = ppu.render_frame()
        if ppu_scale != 1:
            frame_surface = pygame.transform.scale(frame_surface, (SCREEN_W*ppu_scale, SCREEN_H*ppu_scale))
        window.blit(frame_surface, (0,0))
        pygame.display.flip()
        clock.tick(30) # cap to 30 fps

    pygame.quit()

if __name__ == "__main__":

    PRG_ROM = bytes([0x00]*0x4000)
    # 0x34 = IM1
    # 0x05
    # 0x01 = SYS
    # 0x10 = trc
    # 0x34 = IM1
    # 0x02
    # 0x40 = ADD
    # 0x01 = SYS
    # 0x10 = trc
    # 0x54 = HOP rel8
    # 0xF9 = -6
    PRG_ROM = bytes([0x34, 0x05, 0x01, 0x10, 0x34, 0x02, 0x40,  0x01, 0x10, 0x54, 0xF9]) + PRG_ROM[11:]
    # dump the rom to a binary file
    # with open("demo_rom.bin", "wb") as f:
    #     f.write(PRG_ROM)
    rom = Rom(0x0000, PRG_ROM)
    ram = Ram(0x8000, 0x2000)         # 8KB
    ppu = PPU()
    init_demo_scene(ppu)
    
    pads = ControllerHub()
    bus = Bus([rom, ram, pads, ppu])
    cpu = CPU(bus)
    cpu.reset(0x0000)

    run_demo(cpu, bus, ppu_scale=2)