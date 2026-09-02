#pragma once

#include "CoreMinimal.h"

#include "OpenRecompRuntimeTypes.generated.h"

UENUM(BlueprintType)
enum class EOpenRecompEndianness : uint8
{
    Little UMETA(DisplayName = "Little Endian"),
    Big UMETA(DisplayName = "Big Endian"),
    Unknown UMETA(DisplayName = "Unknown")
};

USTRUCT(BlueprintType)
struct OPENRECOMPRUNTIME_API FOpenRecompModuleInfo
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    FString ModuleId;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    FString ModuleFormatVersion;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    FString IrVersion;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    FString HostContractVersion;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    FString SourceArchitecture;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    FString SourceInputSha256;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    int32 SourceAddressBits = 0;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    EOpenRecompEndianness SourceEndianness = EOpenRecompEndianness::Unknown;

    // Native AOT ABI V1 uses uint64 capability flags. The Blueprint-facing
    // field is int64 so the value is representable by reflected UE types; V1
    // currently assigns only low positive bits.
    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    int64 CapabilityFlags = 0;
};

USTRUCT(BlueprintType)
struct OPENRECOMPRUNTIME_API FOpenRecompExecutionResult
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    FOpenRecompModuleInfo Module;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    int64 ObservedState = 0;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    int64 FunctionReturn = 0;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    bool bHasFunctionReturn = false;

    UPROPERTY(BlueprintReadOnly, Category = "OpenRecomp")
    int64 Operations = 0;
};
