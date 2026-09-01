#pragma once

#include "CoreMinimal.h"

struct FOpenRecompModuleMetadataV1
{
    uint64 CapabilityFlags = 0;
    uint32 SourceAddressBits = 0;
    uint32 SourceEndianness = 0;
    FString ModuleId;
    FString ModuleFormatVersion;
    FString IrVersion;
    FString HostContractVersion;
    FString SourceArchitecture;
    FString SourceInputSha256;
};

struct FOpenRecompExecutionResultV1
{
    uint64 ObservedState = 0;
    uint64 FunctionReturn = 0;
    bool bHasFunctionReturn = false;
    uint64 Operations = 0;
};
