#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/EngineTypes.h"
#include "OpenRecompProofActor.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class OPENRECOMPHOST_API AOpenRecompProofActor : public AActor
{
    GENERATED_BODY()

public:
    AOpenRecompProofActor();

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp")
    UStaticMeshComponent* MeshComponent;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="OpenRecomp")
    UTextRenderComponent* TextComponent;

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="OpenRecomp")
    int32 GuestX = 0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="OpenRecomp")
    int32 GuestY = 0;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="OpenRecomp")
    FColor GuestColor = FColor(255, 58, 167, 255);

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="OpenRecomp")
    int32 GuestFrame = 0;

    UFUNCTION(CallInEditor, BlueprintCallable, Category="OpenRecomp")
    void RunSyntheticTranslatedProof();

    void StartVisualDemo();
    void OnDemoStep();
    void UpdateDemoVisuals();

    FTimerHandle DemoTimerHandle;
    int32 DemoStepIndex = 0;
    
    int32 DemoGuestX = 0;
    int32 DemoGuestY = 0;
    FColor DemoGuestColor = FColor(255, 58, 167, 255);
    int32 DemoGuestFrame = 0;

    static void StepSyntheticProof(int32& InX, int32& InY, FColor& InColor, int32& InFrame, uint32 Input);
};