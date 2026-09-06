import struct
import os

OUT_DIR = 'artifacts/mips32_ingestion_v1'
os.makedirs(OUT_DIR, exist_ok=True)

def build_elf(
    magic=b'\x7fELF',
    elfclass=1,
    endian=1,
    version=1,
    machine=8,
    entry=0x1000,
    phoff=52,
    phentsize=32,
    phnum=1,
    phdrs=None,
    file_data=b'',
    skip_padding=False
):
    header = struct.pack('<4sBBBBQ', magic, elfclass, endian, version, 0, 0)
    header = header[:16]
    
    ehsize = 52
    header += struct.pack('<HHIIIIIHHHHHH',
        2, machine, version, entry, phoff, 0, 0, ehsize, phentsize, phnum, 0, 0, 0)
        
    res = bytearray(header)
    
    if phdrs is None:
        phdrs = []
        
    for p in phdrs:
        ptype, poffset, pvaddr, ppaddr, pfilesz, pmemsz, pflags, palign = p
        ph = struct.pack('<IIIIIIII', ptype, poffset, pvaddr, ppaddr, pfilesz, pmemsz, pflags, palign)
        res.extend(ph)
        
    if not skip_padding and len(res) < phoff + phnum * phentsize:
        res.extend(b'\0' * (phoff + phnum * phentsize - len(res)))
        
    if file_data:
        current_len = len(res)
        for p in phdrs:
            poffset = p[1]
            if not skip_padding and poffset > current_len:
                res.extend(b'\0' * (poffset - current_len))
                current_len = poffset
        res.extend(file_data)
        
    return res

def save(name, data):
    with open(os.path.join(OUT_DIR, name + '.elf'), 'wb') as f:
        f.write(data)
    print(f"Saved {name}")

save('VALID_01', build_elf(
    phdrs=[(1, 84, 0x1000, 0x1000, 16, 16, 5, 4)],
    file_data=b'\x09\xf8\x20\x03' * 4
))
save('VALID_02', build_elf(
    phnum=2,
    phdrs=[
        (1, 116, 0x1000, 0x1000, 16, 16, 5, 4),
        (1, 132, 0x2000, 0x2000, 16, 16, 6, 4)
    ],
    file_data=b'\x09\xf8\x20\x03' * 4 + b'\x00' * 16
))
save('INVALID_MAGIC', build_elf(magic=b'BADF'))
save('INVALID_CLASS', build_elf(elfclass=2))
save('INVALID_MACHINE', build_elf(machine=243))
save('INVALID_ENDIAN', build_elf(endian=2))
save('TRUNCATED_HEADER', build_elf()[:30])
save('TRUNCATED_PHDR', build_elf(phnum=2, phdrs=[(1, 52, 0x1000, 0x1000, 16, 16, 5, 4)])[:60])
save('PHDR_COUNT_OVERFLOW', build_elf(phnum=0xFFFF, phoff=0xFFFFFFF0, skip_padding=True))
save('SEGMENT_OUT_OF_FILE', build_elf(phdrs=[(1, 1000, 0x1000, 0x1000, 1000, 1000, 5, 4)], skip_padding=True))
save('SEGMENT_RANGE_OVERFLOW', build_elf(phdrs=[(1, 84, 0xFFFFFFF0, 0xFFFFFFF0, 16, 32, 5, 4)], file_data=b'\x00'*16))
save('FILESZ_GT_MEMSZ', build_elf(phdrs=[(1, 84, 0x1000, 0x1000, 32, 16, 5, 4)], file_data=b'\x00'*32))
d = build_elf(phdrs=[(1, 84, 0x1000, 0x1000, 0, 16, 5, 4)]) + b'\x00'*100
save('NOBITS_EXEC_TRAP', d)
save('OVERLAPPING_EXEC', build_elf(phnum=2, phdrs=[(1, 116, 0x1000, 0x1000, 16, 16, 5, 4), (1, 116, 0x1008, 0x1008, 16, 16, 5, 4)], file_data=b'\x09\xf8\x20\x03' * 4))
