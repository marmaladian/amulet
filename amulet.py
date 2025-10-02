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

    t = 0 # for PPU TEST

    running = True
    while running:
        # Host input handling (update ControllerHub here if you have one)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                print("Quit event")
                running = False

        # Your CPU budget per frame (deterministic):
        # Run a reasonable number of CPU steps per frame
        if cpu.running:
            for _ in range(1000):  # Much more reasonable step count per frame
                print(f"PC={cpu.pc:04X} DS={cpu.ds} RS={cpu.rs}, op={bus.read8(cpu.pc):02X}", end='\r')
                cpu.step()
                if not cpu.running:
                    print("CPU halted")
                    running = False
                    break

        # PPU TEST: move a sprite around
        move_sprite_x(ppu, 0, 40 + (t % 100))
        t += 1

        # VBLANK: render and present once per frame
        frame_surface = ppu.render_frame()
        if ppu_scale != 1:
            frame_surface = pygame.transform.scale(frame_surface, (SCREEN_W*ppu_scale, SCREEN_H*ppu_scale))
        window.blit(frame_surface, (0,0))
        pygame.display.flip()
        clock.tick(30)  # 60 FPS

    pygame.quit()

if __name__ == "__main__":

    PRG_ROM = bytes([0x00]*0x4000)
    # replace the start with a simple program that jumps forever
    # 0x01 = LIT8
    # 0x05
    # 0x01 = LIT8
    # 0x02
    # 0x02 = ADD
    # 0x30 = JMP rel8
    # 0xfc = -4
    PRG_ROM = bytes([0x01, 0x05, 0x01, 0x02, 0x02, 0x30, 0xFB]) + PRG_ROM[7:]
    # dump the rom to a binary file
    with open("demo_rom.bin", "wb") as f:
        f.write(PRG_ROM)
    rom = Rom(0x0000, PRG_ROM)
    ram = Ram(0x8000, 0x2000)         # 8KB
    ppu = PPU()
    init_demo_scene(ppu)
    
    pads = ControllerHub()
    bus = Bus([rom, ram, pads, ppu])  # later add PPU/APU devices
    cpu = CPU(bus)
    cpu.reset(0x0000)

    run_demo(cpu, bus, ppu_scale=2)