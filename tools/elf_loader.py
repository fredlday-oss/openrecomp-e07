#!/usr/bin/env python3
import hashlib, json, struct, sys
from pathlib import Path

ELF_MAGIC=b'\x7fELF'; EM_RISCV=243; ET_EXEC=2
SHT_SYMTAB=2; SHT_NOBITS=8; SHF_ALLOC=2

class ELFError(ValueError): pass

def cstr(blob, off):
    end=blob.find(b'\0',off)
    return blob[off:(len(blob) if end<0 else end)].decode('utf-8','replace')

def load_elf(path):
    path=Path(path); b=path.read_bytes()
    if len(b)<52 or b[:4]!=ELF_MAGIC: raise ELFError('not ELF')
    if b[4]!=1: raise ELFError('expected ELF32')
    if b[5]!=1: raise ELFError('expected little-endian ELF')
    e=struct.unpack_from('<16sHHIIIIIHHHHHH',b,0)
    _,etype,machine,version,entry,phoff,shoff,flags,ehsize,phentsize,phnum,shentsize,shnum,shstrndx=e
    if etype!=ET_EXEC: raise ELFError(f'expected ET_EXEC, got {etype}')
    if machine!=EM_RISCV: raise ELFError(f'expected EM_RISCV({EM_RISCV}), got {machine}')
    if version!=1 or ehsize<52: raise ELFError('bad ELF header version/size')
    if shoff==0 or shnum==0 or shentsize<40: raise ELFError('missing section table')
    if shoff+shnum*shentsize>len(b): raise ELFError('section table out of bounds')
    raw=[]
    for i in range(shnum):
        vals=struct.unpack_from('<IIIIIIIIII',b,shoff+i*shentsize)
        raw.append(dict(name_off=vals[0],type=vals[1],flags=vals[2],addr=vals[3],offset=vals[4],size=vals[5],link=vals[6],info=vals[7],addralign=vals[8],entsize=vals[9]))
    if shstrndx>=shnum: raise ELFError('bad shstrndx')
    ss=raw[shstrndx]
    if ss['offset']+ss['size']>len(b): raise ELFError('string table out of bounds')
    names=b[ss['offset']:ss['offset']+ss['size']]
    sections=[]
    for i,s in enumerate(raw):
        name=cstr(names,s['name_off']) if s['name_off']<len(names) else '<bad-name>'
        if s['type'] != SHT_NOBITS and (s['offset'] > len(b) or s['size'] > len(b) - s['offset']): raise ELFError(f'section {name} out of bounds')
        q=dict(s); q.update(index=i,name=name)
        sections.append(q)
    symbols=[]
    for s in sections:
        if s['type']!=SHT_SYMTAB or not s['entsize']: continue
        if s['link']>=len(sections): raise ELFError('symtab bad string link')
        st=sections[s['link']]
        strings=b[st['offset']:st['offset']+st['size']]
        if s['offset']+s['size']>len(b): raise ELFError('symtab out of bounds')
        count=s['size']//s['entsize']
        for i in range(count):
            off=s['offset']+i*s['entsize']
            if off+16>len(b): raise ELFError('symbol out of bounds')
            no,val,size,info,other,shndx=struct.unpack_from('<IIIBBH',b,off)
            name=cstr(strings,no) if no<len(strings) else ''
            if name:
                symbols.append(dict(name=name,value=val,size=size,bind=info>>4,type=info&15,shndx=shndx))
    alloc=[]
    for s in sections:
        if s['flags']&SHF_ALLOC and s['size']:
            data=(b[s['offset']:s['offset']+s['size']] if s['type']!=SHT_NOBITS else b'\0'*s['size'])
            alloc.append(dict(name=s['name'],addr=s['addr'],size=s['size'],data_hex=data.hex()))
    meta={
        'format':'ELF32','endianness':'little','architecture':'riscv32-rv32i','machine':machine,
        'entry_point':entry,'input_size':len(b),'input_sha256':hashlib.sha256(b).hexdigest(),
        'sections':[{k:s[k] for k in ('name','type','flags','addr','offset','size','addralign')} for s in sections],
        'symbols':symbols,'alloc_sections':alloc
    }
    text=next((s for s in sections if s['name']=='.text'),None)
    if not text or not text['size'] or text['size']%4: raise ELFError('missing/alignment-invalid .text')
    if text['type'] == SHT_NOBITS: raise ELFError('.text must be file-backed; SHT_NOBITS rejected')
    if text['offset'] > len(b) or text['size'] > len(b)-text['offset']: raise ELFError('.text out of bounds')
    if entry < text['addr'] or entry >= text['addr']+text['size']: raise ELFError('entry outside .text')
    meta['_bytes']=b; meta['_text']=text
    return meta

def public(meta): return {k:v for k,v in meta.items() if not k.startswith('_')}

if __name__=='__main__':
    try:
        m=load_elf(sys.argv[1]); print(json.dumps(public(m),indent=2,sort_keys=True))
    except Exception as e:
        print(f'ELF_REJECT: {e}',file=sys.stderr); raise SystemExit(2)
