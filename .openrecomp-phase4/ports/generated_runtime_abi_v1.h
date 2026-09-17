/* OpenRecomp generated-code <-> runtime ABI V1 (P4-01). Architecture-neutral. */
/* abi_name: openrecomp-generated-runtime-abi */
/* abi_version: 1.0.0 */
/* This header is emitted deterministically from .openrecomp-phase4/src/p4_runtime_abi_v1.py. */
#ifndef OPENRECOMP_GENERATED_RUNTIME_ABI_V1_H
#define OPENRECOMP_GENERATED_RUNTIME_ABI_V1_H
#include <stdint.h>
#include <stddef.h>

/* Architecture-neutral failure codes (P2-08 order). */
enum {
    OR_RT_OK = 0,
    OR_RT_MEMORY_OUT_OF_RANGE = 1,
    OR_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    OR_RT_MEMORY_ADDRESS_OVERFLOW = 3,
    OR_RT_MEMORY_ENDIANNESS_UNSUPPORTED = 4,
    OR_RT_MEMORY_SEGMENT_OVERLAP = 5,
    OR_RT_UNKNOWN_HOST_SERVICE = 6,
    OR_RT_HOST_SERVICE_FAILED = 7,
    OR_RT_HOST_CALL_ARITY = 8,
    OR_RT_INPUT_INVALID = 9,
    OR_RT_FRAME_INVALID = 10,
    OR_RT_AUDIO_INVALID = 11,
    OR_RT_ABI_VERSION_MISMATCH = 12,
    OR_RT_UNSUPPORTED_OPERATION = 13,
    OR_RT_TRAP = 14,
};

/* Entries the runtime must provide to generated code. */
/* Read width_bits (8/16/32/64) at a guest address into *out_value; returns OR_RT_OK or a memory failure code; out_value must not be null. */
extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
/* Write the low width_bits of value at a guest address; returns OR_RT_OK or a memory failure code. */
extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
/* Synchronous typed service call; unknown services, wrong argument counts, version mismatches and handler failures return a stable failure code and never call undeclared host functionality. */
extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
/* Stable, host-path-free failure name for a failure code; empty string for OR_RT_OK; bounded for unknown codes. */
extern const char *or_rt_failure_reason(int code);

/* Accessors generated code must provide to the runtime. */
/* Execute the generated program from its entry state. */
void openrecomp_run(void);
/* 1 once the run latched a failure, else 0. */
int openrecomp_failed(void);
/* Empty string while no failure is latched; otherwise the stable failure name. */
const char *openrecomp_error(void);
/* Number of executed guest steps. */
uint64_t openrecomp_steps(void);
/* Current program counter (target-profile width). */
uint32_t openrecomp_pc(void);
/* Size of the guest register file (architecture-neutral vector). */
size_t openrecomp_register_count(void);
/* Value of guest register index; out-of-range index fails closed. */
uint32_t openrecomp_register_value(size_t index);
/* Start of the immutable loaded guest image. */
const uint8_t *openrecomp_image(void);
/* Byte length of the loaded guest image. */
uint32_t openrecomp_image_size(void);
/* Number of declared guest memory regions. */
uint32_t openrecomp_region_count(void);
/* Region index bounds (end exclusive) and permission flags; out-of-range index fails closed. */
void openrecomp_region(uint32_t index, uint32_t *start, uint32_t *end, uint32_t *flags);

/* Reserved core service namespace (typed, versioned): */
/* or.runtime.exit v1.0.0: args=(u32) result=none terminates-run - Terminate the run with a 32-bit exit status; a second termination request fails closed. */

/* Entry-return policy: returning from the generated entry function without a declared termination is a FAULT fault. */

/* Observable digest contract: fnv1a-64 over fnv1a64 over: ascii 'OROBS1' | u32le image_length | image bytes | u32le register_count | each register u32le | u32le aux_count | each aux value u32le in profile order | u32le pc | u64le steps | u32le exit_status (0xffffffff when absent) | u32le external_output_length | external_output bytes */

#endif
