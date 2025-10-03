# Amulet
A fantasy console.
This is a work in progress, spec is not finalised.

## Overview
Stack-machine, 8-bit words, 16-bit addresses? 20-bit? (MMU allows access to 1MB).
PPU with internal VRAM. Tile based display.

## Instruction set

# Opcodes
| category | hex | name | desc |
| --- | --- | --- | -- |
| **system**                   | 00 | ZZZ | no operation
|                              | 01 | SYS | `SYS n` system call
|                              | 0F | HLT | break/halt
| **stack operations**         | 20 | POP | drop/pop<br>`(a -- )`
|                              | 21 | DUP | duplicate<br>`(a -- a a)`
|                              | 22 | SWP | swap<br>`(a b -- b a)`
|                              | 23 | OVR | over<br>`(a b -- a b a)` 
|                              | 24 | ROT | rotate left<br>`(a b c -- b c a)`<br>for `-ROT` use `rot rot`
|                              | ?? | NIP | nip<br>`(a b --)`<br>aka `SWP POP`
|                              | ?? | TUC | tuck<br>`(a b -- b a b)`<br>aka `SWP OVR`
| **literals & addressing**    | 30 | ST1 | store<br>`(a lo hi -- )`<br>could be named `POKE`
|                              | 31 | ST2 | store 16
|                              | 32 | LD1 | load<br>`(lo hi -- a)`<br>could be named `PEEK`
|                              | 33 | LD2 | load 16 bits lo hi
|                              | 34 | IM1 | literal, push next byte to stack<br>`( -- a)`
|                              | 35 | IM2 | literal, push next 2 bytes to stack<br>`( -- lo hi)`<br>could be named `PICK`
| **alu (8-bit unless noted)** | 40 | ADD | add<br>`(a b -- c)`
|                              | 41 | SUB | subtract<br>`(a b -- c)`
|                              | 42 | AND | bitwise and<br>`(a b -- c)`
|                              | 43 | IOR | bitwise or<br>`(a b -- c)`
|                              | 44 | XOR | bitwise xor<br>`(a b -- c)`
|                              | 45 | NOT | bitwise not<br>`(a -- ~a)
|                              | ?? | BSL | bit shift left
|                              | ?? | BRL | bit roll left
| **control flow**             | 50 | CAL | perform subroutine call to address in next 2 bytes<br>maybe `JSR` jump subroutine?
|                              | 51 | RTN | return non-zero<br>`(cond -- )`
|                              | 52 | RTZ | return zero<br>`(cond -- )`
|                              | 53 | RET | unconditional return
|                              | 54 | HOP | rel jump 8 bit (next byte)
|                              | 55 | SKP | indirect jump (lo hi -- )
|                              | 56 | JMP | jump 16 bit (next 2 bytes)
| undecided                    | ?? | RSW | push/write to return stack<br>`(lo hi --)`
| undecided                    | ?? | RSR | pop/read from return stack to data stack<br>`( -- a)`
| **io & timing**              | 60 | VBL | blocks until VBLANK flag set (then clears)
|                              | ?? | PUT | `PUT n` write val to io port n? (val -- )
|                              | ?? | GET | `GET n` get byte from port number push to stack

37	SYS n	emulator syscall hook (dev only)
40	IN port	( -- val8)
41	OUT port	(val8 --)
42	WAIT_VBL	blocks until VBLANK flag set (and clears it)