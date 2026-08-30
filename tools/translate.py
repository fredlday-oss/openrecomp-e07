#!/usr/bin/env python3
import json, sys
import jsonschema
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HOSTS={'host_graphics','host_audio','host_input','host_system'}

def load_checked(ir_path):
    ir=json.loads(Path(ir_path).read_text())
    schema=json.loads((ROOT/'schema'/'ir.schema.json').read_text()); jsonschema.validate(ir,schema)
    c=json.loads((ROOT/'contracts'/'host_contract.json').read_text())
    if c['system']['wall_clock'] or c['system']['randomness']: raise ValueError('nondeterministic host contract')
    if c['memory']['oob_policy']!='deterministic fault': raise ValueError('memory contract must fail closed')
    missing=HOSTS-{x['name'] for x in ir['symbols']}
    if missing: raise ValueError('missing host symbols: '+','.join(sorted(missing)))
    return ir,c

def emit(ir,c):
    syms={s['name']:s['value'] for s in ir['symbols']}
    host_addr={syms[k]:k for k in HOSTS if k in syms}
    lines=[]; A=lines.append
    A(f'/* Generated deterministically by OpenRecomp E07 translator v0.1.1; host contract {c["contract_version"]}. */')
    A('#include <stdint.h>')
    A('#ifndef __wasm__\n#include <stdio.h>\n#include <string.h>\n#endif')
    A(f'#define MEM_SIZE {c["memory"]["size_bytes"]}u')
    A('static uint8_t mem[MEM_SIZE]; static uint32_t r[32]; static uint32_t mem_fault;')
    A('static uint32_t tick_count, gfx_calls, audio_calls, input_calls, system_calls;')
    A('static uint8_t framebuffer[4*4*3]; static int16_t audio_buf[16];')
    A('static const uint32_t scripted_input[%du]={%s};' % (len(c['input']['values']),','.join(map(str,c['input']['values']))))
    A('static int mem_ok(uint32_t a,uint32_t n){if(a>MEM_SIZE||n>MEM_SIZE-a){mem_fault=1;return 0;}return 1;}')
    A('static uint32_t rd32(uint32_t a){if(!mem_ok(a,4))return 0;return (uint32_t)mem[a]|((uint32_t)mem[a+1]<<8)|((uint32_t)mem[a+2]<<16)|((uint32_t)mem[a+3]<<24);}')
    A('static uint32_t rd16(uint32_t a){if(!mem_ok(a,2))return 0;return (uint32_t)mem[a]|((uint32_t)mem[a+1]<<8);}')
    A('static void wr32(uint32_t a,uint32_t v){if(!mem_ok(a,4))return;mem[a]=v;mem[a+1]=v>>8;mem[a+2]=v>>16;mem[a+3]=v>>24;}')
    A('static void host_graphics_c(uint32_t x,uint32_t y,uint32_t v){gfx_calls++; if(x<4&&y<4){uint32_t p=(y*4+x)*3; framebuffer[p]=v;framebuffer[p+1]=(uint8_t)(v^0x55u);framebuffer[p+2]=(uint8_t)(v^0xaau);}}')
    A('static void host_audio_c(uint32_t s){audio_calls++; for(uint32_t i=0;i<16;i++) audio_buf[i]=(int16_t)((s+(i*257u))&0xffffu);}')
    A('static uint32_t host_input_c(uint32_t i){input_calls++; return scripted_input[i%%%du];}' % len(c['input']['values']))
    A('static uint32_t host_system_c(uint32_t op,uint32_t v){system_calls++; uint32_t out=op+v+%du+tick_count; tick_count++; return out;}' % c['system']['deterministic_bias'])
    A('static void init_mem(void){for(uint32_t i=0;i<MEM_SIZE;i++)mem[i]=0;')
    for sec in ir['alloc_sections']:
        if sec['name']=='.text': continue
        data=bytes.fromhex(sec['data_hex'])
        for i,v in enumerate(data):
            if v: A(f'mem[0x{sec["addr"]+i:x}u]=0x{v:02x}u;')
    A('}')
    A('uint32_t memory_safety_selftest(void){mem_fault=0;(void)rd16(MEM_SIZE-1);if(!mem_fault)return 1;mem_fault=0;(void)rd32(MEM_SIZE-3);if(!mem_fault)return 2;mem_fault=0;wr32(MEM_SIZE-2,0x1234u);if(!mem_fault)return 3;return 0;}')
    A('uint32_t run_fixture(void){init_mem();for(int i=0;i<32;i++)r[i]=0;mem_fault=0;tick_count=gfx_calls=audio_calls=input_calls=system_calls=0; for(int i=0;i<48;i++)framebuffer[i]=0;for(int i=0;i<16;i++)audio_buf[i]=0;')
    A('r[2]=0x30000u; r[1]=0xfffffffcu; uint32_t pc=0x%08xu; uint32_t steps=0;' % ir['fixture_entry'])
    A('while(pc!=0xfffffffcu && steps++<200000u){ r[0]=0; switch(pc){')
    for d in ir['instructions']:
        a=d['address']; op=d['op']; rd=d['rd']; rs1=d['rs1']; rs2=d['rs2']; nxt=a+4
        A(f'case 0x{a:08x}u:')
        if op=='addi': A(f'r[{rd}]=r[{rs1}]+(uint32_t)({d["imm"]}); pc=0x{nxt:x}u; break;')
        elif op=='andi': A(f'r[{rd}]=r[{rs1}]&(uint32_t)({d["imm"]}); pc=0x{nxt:x}u; break;')
        elif op=='slli': A(f'r[{rd}]=r[{rs1}]<<{d["imm"]}; pc=0x{nxt:x}u; break;')
        elif op=='srli': A(f'r[{rd}]=r[{rs1}]>>{d["imm"]}; pc=0x{nxt:x}u; break;')
        elif op=='add': A(f'r[{rd}]=r[{rs1}]+r[{rs2}]; pc=0x{nxt:x}u; break;')
        elif op=='xor': A(f'r[{rd}]=r[{rs1}]^r[{rs2}]; pc=0x{nxt:x}u; break;')
        elif op=='lui': A(f'r[{rd}]=0x{d["imm"]&0xffffffff:x}u; pc=0x{nxt:x}u; break;')
        elif op=='lw': A(f'r[{rd}]=rd32(r[{rs1}]+(uint32_t)({d["imm"]})); if(mem_fault)return 0xdeada001u; pc=0x{nxt:x}u; break;')
        elif op=='lhu': A(f'r[{rd}]=rd16(r[{rs1}]+(uint32_t)({d["imm"]})); if(mem_fault)return 0xdeada002u; pc=0x{nxt:x}u; break;')
        elif op=='sw': A(f'wr32(r[{rs1}]+(uint32_t)({d["imm"]}),r[{rs2}]); if(mem_fault)return 0xdeada003u; pc=0x{nxt:x}u; break;')
        elif op in ('bltu','bgeu','beq','bne'):
            cmp={'bltu':'<','bgeu':'>=','beq':'==','bne':'!='}[op]
            A(f'pc=(r[{rs1}]{cmp}r[{rs2}])?0x{d["target"]:x}u:0x{nxt:x}u; break;')
        elif op=='jal':
            tgt=d['target']; name=host_addr.get(tgt)
            if name:
                if name=='host_graphics': call='host_graphics_c(r[10],r[11],r[12]);'
                elif name=='host_audio': call='host_audio_c(r[10]);'
                elif name=='host_input': call='r[10]=host_input_c(r[10]);'
                else: call='r[10]=host_system_c(r[10],r[11]);'
                A(f'r[{rd}]=0x{nxt:x}u; {call} pc=0x{nxt:x}u; break;')
            else: A(f'r[{rd}]=0x{nxt:x}u; pc=0x{tgt:x}u; break;')
        elif op=='jalr': A(f'{{uint32_t t=(r[{rs1}]+(uint32_t)({d["imm"]}))&~1u; r[{rd}]=0x{nxt:x}u; pc=t;}} break;')
        else: raise ValueError(op)
    A('default:return 0xdeadc0deu; }}')
    A('if(steps>=200000u)return 0xdeaddeadu;')
    A('uint32_t h=r[10]^tick_count^(gfx_calls<<4)^(audio_calls<<8)^(input_calls<<12)^(system_calls<<16); for(int i=0;i<48;i++)h=(h*16777619u)^framebuffer[i];for(int i=0;i<16;i++)h=(h*16777619u)^(uint16_t)audio_buf[i]; return h;}')
    A('#ifndef __wasm__')
    A('static void put16(FILE*f,uint16_t v){fputc(v&255,f);fputc(v>>8,f);} static void put32(FILE*f,uint32_t v){put16(f,v&65535);put16(f,v>>16);}')
    A('static int write_outputs(uint32_t checksum){FILE*f=fopen("frame.ppm","wb");if(!f)return 2;fprintf(f,"P6\\n4 4\\n255\\n");fwrite(framebuffer,1,48,f);fclose(f); f=fopen("audio.wav","wb");if(!f)return 3;fwrite("RIFF",1,4,f);put32(f,36+32);fwrite("WAVEfmt ",1,8,f);put32(f,16);put16(f,1);put16(f,1);put32(f,8000);put32(f,16000);put16(f,2);put16(f,16);fwrite("data",1,4,f);put32(f,32);fwrite(audio_buf,2,16,f);fclose(f); f=fopen("state.json","wb");if(!f)return 4;fprintf(f,"{\\n  \\"return_a0\\": %u,\\n  \\"tick_count\\": %u,\\n  \\"graphics_calls\\": %u,\\n  \\"audio_calls\\": %u,\\n  \\"input_calls\\": %u,\\n  \\"system_calls\\": %u,\\n  \\"checksum\\": %u\\n}\\n",r[10],tick_count,gfx_calls,audio_calls,input_calls,system_calls,checksum);fclose(f);return 0;}')
    A('int main(void){uint32_t m=memory_safety_selftest();if(m)return 5;uint32_t c=run_fixture();int e=write_outputs(c);if(e)return e;printf("CHECKSUM=%u\\n",c);return 0;}')
    A('#endif')
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    try:
        ir,c=load_checked(sys.argv[1]); Path(sys.argv[2]).write_text(emit(ir,c))
    except (ValueError,KeyError,json.JSONDecodeError,jsonschema.ValidationError) as e:
        print(f'TRANSLATE_REJECT: {e}',file=sys.stderr); raise SystemExit(2)
