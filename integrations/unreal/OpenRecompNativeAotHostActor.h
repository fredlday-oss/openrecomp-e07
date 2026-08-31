#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OpenRecompNativeAotHostActor.generated.h"

class USceneComponent;
class UTextRenderComponent;

UCLASS()
class OPENRECOMPHOST_API AOpenRecompNativeAotHostActor : public AActor
{
    GENERATED_BODY()

public:
    AOpenRecompNativeAotHostActor();

    virtual void BeginPlay() override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Native AOT")
    USceneComponent* SceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Native AOT")
    UTextRenderComponent* TextComponent;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="OpenRecomp|Native AOT")
    FString NativeModulePath;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Native AOT")
    bool bNativeAotPassed = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Native AOT")
    int64 ObservedState = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Native AOT")
    int64 Operations = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Native AOT")
    int64 ProofChecksum = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Native AOT")
    FString LoadedModuleId;

    UFUNCTION(CallInEditor, BlueprintCallable, Category="OpenRecomp|Native AOT")
    void RunNativeAotProof();

private:
    static int32 NativeHostCall(
        void* UserData,
        const char* Symbol,
        const uint64_t* Args,
        uint64_t Argc,
        uint64_t* OutValue,
        uint32_t* OutHasValue);

    int32 HandleHostCall(
        const char* Symbol,
        const uint64_t* Args,
        uint64_t Argc,
        uint64_t* OutValue,
        uint32_t* OutHasValue);

    void ResetDeterministicHost();
    uint32 ComputeProofChecksum(uint64 Observed) const;
    void SetStatusText(const FString& Text, const FColor& Color);

    uint32 TickCount = 0;
    uint32 GraphicsCalls = 0;
    uint32 AudioCalls = 0;
    uint32 InputCalls = 0;
    uint32 SystemCalls = 0;
    TArray<uint8> Framebuffer;
    TArray<uint16> AudioBuffer;
};
