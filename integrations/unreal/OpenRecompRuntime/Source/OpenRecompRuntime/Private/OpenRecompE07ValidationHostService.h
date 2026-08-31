#pragma once

#include "CoreMinimal.h"

#include "OpenRecompHostService.h"

#include "OpenRecompE07ValidationHostService.generated.h"

// Internal, opt-in validation helper used only by -OpenRecompPluginProof.
// It is intentionally not part of the public plugin API.
UCLASS(Transient)
class UOpenRecompE07ValidationHostService final
    : public UObject
    , public IOpenRecompHostService
{
    GENERATED_BODY()

public:
    UOpenRecompE07ValidationHostService();

    virtual bool HandleOpenRecompHostCall_Implementation(
        const FString& Symbol,
        const TArray<int64>& Arguments,
        int64& OutValue,
        bool& bOutHasValue) override;

    void ResetValidationState();
    uint32 ComputeProofChecksum(int64 ObservedState) const;
    bool AllExpectedCallbacksExercised() const;

private:
    uint32 TickCount = 0;
    uint32 GraphicsCalls = 0;
    uint32 AudioCalls = 0;
    uint32 InputCalls = 0;
    uint32 SystemCalls = 0;
    TArray<uint8> Framebuffer;
    TArray<uint16> AudioBuffer;
};
