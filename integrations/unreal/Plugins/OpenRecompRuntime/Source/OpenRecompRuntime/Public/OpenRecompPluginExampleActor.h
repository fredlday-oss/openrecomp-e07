#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"

#include "OpenRecompPluginExampleActor.generated.h"

class USceneComponent;
class UTextRenderComponent;

UCLASS()
class OPENRECOMPRUNTIME_API AOpenRecompPluginExampleActor : public AActor
{
    GENERATED_BODY()

public:
    AOpenRecompPluginExampleActor();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Plugin V1")
    USceneComponent* SceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Plugin V1")
    UTextRenderComponent* TextComponent;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="OpenRecomp|Plugin V1")
    FString NativeModulePath;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Plugin V1")
    bool bPluginProofPassed = false;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Plugin V1")
    int64 ObservedState = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Plugin V1")
    int64 Operations = 0;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp|Plugin V1")
    int64 ProofChecksum = 0;

    UFUNCTION(CallInEditor, BlueprintCallable, Category="OpenRecomp|Plugin V1")
    void RunPluginProof();

private:
    bool HandleHostCall(
        const FString& Symbol,
        TArrayView<const uint64> Args,
        uint64& OutValue,
        bool& bOutHasValue);

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
