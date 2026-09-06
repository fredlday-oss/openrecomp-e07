#!/usr/bin/env python3
import hashlib
import json
import struct
import sys
import subprocess
from pathlib import Path

ELF_MAGIC = b'\x7fELF'
EM_MIPS = 8
ET_EXEC = 2
PT_LOAD = 1
PF_X = 1
PF_W = 2
PF_R = 4

class ELFError(ValueError): pass

def get_git_commit():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode('utf-8').strip()
    except Exception:
        return "unknown"

def load_mips32_elf(path):
    path = Path(path)
    b = path.read_bytes()
    if len(b) < 52 or b[:4] != ELF_MAGIC:
        raise ELFError('not ELF (INVALID_MAGIC)')
    if b[4] != 1:
        raise ELFError('expected ELFCLASS32 (UNSUPPORTED_CLASS)')
    if b[5] != 1:
        raise ELFError('expected little-endian ELF (UNSUPPORTED_ENDIANNESS)')
    
    e = struct.unpack_from('<16sHHIIIIIHHHHHH', b, 0)
    _, etype, machine, version, entry, phoff, shoff, flags, ehsize, phentsize, phnum, shentsize, shnum, shstrndx = e
    
    if machine != EM_MIPS:
        raise ELFError(f'expected EM_MIPS({EM_MIPS}), got {machine} (WRONG_MACHINE)')
    if version != 1:
        raise ELFError('bad ELF header version')
    if ehsize < 52:
        raise ELFError('header too small (TRUNCATED_HEADER)')
    
    if phnum > 0 and phentsize < 32:
        raise ELFError('program header entry size too small')
    
    ph_table_size = phnum * phentsize
    if ph_table_size < 0 or phoff + ph_table_size > len(b) or phoff + ph_table_size < phoff:
        raise ELFError('program header table out of bounds (INVALID_HEADER_TABLE)')
    
    regions = []
    
    for i in range(phnum):
        ph_start = phoff + i * phentsize
        ptype, poffset, pvaddr, ppaddr, pfilesz, pmemsz, pflags, palign = struct.unpack_from('<IIIIIIII', b, ph_start)
        
        if ptype != PT_LOAD:
            continue
            
        if pfilesz > pmemsz:
            raise ELFError('p_filesz > p_memsz (INVALID_SEGMENT_SIZE)')
            
        if (pflags & PF_X) != 0 and pmemsz > pfilesz:
            raise ELFError('executable segment has memsz > filesz (NOBITS_EXEC_TRAP)')
            
        if poffset + pfilesz < poffset or poffset + pfilesz > len(b):
            raise ELFError('segment file range out of bounds (OUT_OF_FILE_RANGE)')
            
        if pvaddr + pmemsz < pvaddr or pvaddr + pmemsz > 0xFFFFFFFF:
            raise ELFError('segment memory range overflows 32-bit (INTEGER_OVERFLOW)')
            
        if (pflags & PF_X) != 0:
            if pmemsz > 0:
                regions.append({
                    'vaddr': pvaddr,
                    'memsz': pmemsz,
                    'offset': poffset,
                    'filesz': pfilesz,
                    'flags': pflags
                })
                
    if not regions:
        raise ELFError('no executable regions found')
        
    regions.sort(key=lambda r: r['vaddr'])
    for i in range(len(regions) - 1):
        if regions[i]['vaddr'] + regions[i]['memsz'] > regions[i+1]['vaddr']:
            raise ELFError('overlapping executable regions (OVERLAPPING_EXEC_REGION)')
            
    entry_valid = False
    for r in regions:
        if r['vaddr'] <= entry < r['vaddr'] + r['memsz']:
            entry_valid = True
            break
    if not entry_valid:
        raise ELFError('entry point outside executable regions')
        
    source_sha256 = hashlib.sha256(b).hexdigest()
    commit = get_git_commit()
    
    normalized = []
    for r in regions:
        region_bytes = b[r['offset']:r['offset']+r['filesz']]
        if r['memsz'] > r['filesz']:
            region_bytes += b'\0' * (r['memsz'] - r['filesz'])
            
        normalized.append({
            'architecture': 'mips32',
            'endianness': 'little',
            'elf_class': 'ELF32',
            'source_file_size': len(b),
            'source_sha256': source_sha256,
            'entry_point': entry,
            'virtual_address': r['vaddr'],
            'file_offset': r['offset'],
            'file_size': r['filesz'],
            'memory_size': r['memsz'],
            'permissions': r['flags'],
            'region_sha256': hashlib.sha256(region_bytes).hexdigest(),
            'extraction_tool': 'mips32_elf_loader.py v1',
            'openrecomp_commit': commit,
            '_bytes': region_bytes.hex()
        })
        
    return {
        'source_sha256': source_sha256,
        'entry_point': entry,
        'regions': normalized
    }

if __name__ == '__main__':
    try:
        meta = load_mips32_elf(sys.argv[1])
        for r in meta['regions']:
            if '_bytes' in r:
                del r['_bytes']
        print(json.dumps(meta, indent=2, sort_keys=True))
    except Exception as e:
        print(f'ELF_REJECT: {e}', file=sys.stderr)
        sys.exit(2)
