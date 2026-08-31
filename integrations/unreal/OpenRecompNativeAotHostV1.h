#pragma once

#include "CoreMinimal.h"

#include "OpenRecompNativeAotHostCoreV1.h"

struct FOpenRecompNativeAotExecutionV1
{
    uint64 CapabilityFlags = 0;
    uint64 ObservedState = 0;
    uint64 FunctionReturn = 0;
    bool bHasFunctionReturn = false;
    uint64 Operations = 0;
    uint32 SourceAddressBits = 0;
    uint32 SourceEndianness = 0;
    FString ModuleId;
    FString ModuleFormatVersion;
    FString IrVersion;
    FString HostContractVersion;
    FString SourceArchitecture;
    FString SourceInputSha256;
};

class OPENRECOMPHOST_API FOpenRecompNativeAotHostV1
{
public:
    static bool ExecuteModule(
        const FString& ModulePath,
        const openrecomp_native_aot_host_v1* Host,
        FOpenRecompNativeAotExecutionV1& OutResult,
        FString& OutError);
};
