#include "OpenRecompProofActor.h"

#include "Camera/CameraActor.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Math/RotationMatrix.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"


AOpenRecompProofActor::AOpenRecompProofActor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;

    // ---------------------------------------------------------------------
    // Visible proof mesh
    // ---------------------------------------------------------------------

    MeshComponent =
        CreateDefaultSubobject<UStaticMeshComponent>(TEXT("MeshComponent"));

    RootComponent = MeshComponent;

    static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMeshAsset(
        TEXT("StaticMesh'/Engine/BasicShapes/Cube.Cube'")
    );

    if (CubeMeshAsset.Succeeded())
    {
        MeshComponent->SetStaticMesh(CubeMeshAsset.Object);
    }

    // ---------------------------------------------------------------------
    // Runtime state text
    // ---------------------------------------------------------------------

    TextComponent =
        CreateDefaultSubobject<UTextRenderComponent>(TEXT("TextComponent"));

    TextComponent->SetupAttachment(RootComponent);

    TextComponent->SetRelativeLocation(
        FVector(0.0f, 0.0f, 150.0f)
    );

    TextComponent->SetHorizontalAlignment(EHTA_Center);
    TextComponent->SetTextRenderColor(FColor::White);

    TextComponent->SetXScale(2.0f);
    TextComponent->SetYScale(2.0f);
}


void AOpenRecompProofActor::BeginPlay()
{
    Super::BeginPlay();

    // ---------------------------------------------------------------------
    // Demo camera
    // ---------------------------------------------------------------------

    if (UWorld* World = GetWorld())
    {
        FActorSpawnParameters SpawnParams;

        ACameraActor* CameraActor =
            World->SpawnActor<ACameraActor>(
                FVector(375.0f, -1000.0f, 500.0f),
                FRotator(-15.0f, 90.0f, 0.0f),
                SpawnParams
            );

        if (CameraActor)
        {
            if (APlayerController* PC =
                UGameplayStatics::GetPlayerController(World, 0))
            {
                PC->SetViewTarget(CameraActor);
            }
        }
    }

    // ---------------------------------------------------------------------
    // AUTHORITATIVE GATE B PROOF
    //
    // Do not replace this with the visual replay.
    // This executes the complete deterministic workload immediately and
    // independently validates the expected final state.
    // ---------------------------------------------------------------------

    RunSyntheticTranslatedProof();

    // ---------------------------------------------------------------------
    // Presentation replay
    // ---------------------------------------------------------------------

    StartVisualDemo();
}


void AOpenRecompProofActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    // ---------------------------------------------------------------------
    // Keep TextRender facing the active demo camera while remaining upright.
    //
    // Previous code used:
    //
    //     DirectionToCamera.Rotation();
    //     TextRotation.Roll += 90.0f;
    //
    // That caused the TextRenderComponent to appear sideways.
    //
    // MakeFromXZ explicitly defines:
    //
    //     local X = direction toward camera
    //     local Z = world up
    //
    // This prevents arbitrary roll and keeps the text horizontal/upright.
    // ---------------------------------------------------------------------

    if (!TextComponent)
    {
        return;
    }

    UWorld* World = GetWorld();

    if (!World)
    {
        return;
    }

    APlayerController* PC =
        UGameplayStatics::GetPlayerController(World, 0);

    if (!PC)
    {
        return;
    }

    AActor* ViewTarget = PC->GetViewTarget();

    if (!ViewTarget)
    {
        return;
    }

    const FVector TextLocation =
        TextComponent->GetComponentLocation();

    const FVector CameraLocation =
        ViewTarget->GetActorLocation();

    const FVector DirectionToCamera =
        (CameraLocation - TextLocation).GetSafeNormal();

    if (DirectionToCamera.IsNearlyZero())
    {
        return;
    }

    const FRotator UprightTextRotation =
        FRotationMatrix::MakeFromXZ(
            DirectionToCamera,
            FVector::UpVector
        ).Rotator();

    TextComponent->SetWorldRotation(UprightTextRotation);
}


void AOpenRecompProofActor::StepSyntheticProof(
    int32& InX,
    int32& InY,
    FColor& InColor,
    int32& InFrame,
    uint32 Input
)
{
    if (Input & 1u)
    {
        InX += 3;
    }

    if (Input & 2u)
    {
        InY += 2;
    }

    if ((InFrame & 1) == 0)
    {
        InColor.R ^= 0x0f;
        InColor.G ^= 0x0f;
    }

    InFrame++;
}


void AOpenRecompProofActor::RunSyntheticTranslatedProof()
{
    // ---------------------------------------------------------------------
    // Initial deterministic guest state
    // ---------------------------------------------------------------------

    GuestX = 0;
    GuestY = 0;

    GuestColor =
        FColor(
            255,
            58,
            167,
            255
        );

    GuestFrame = 0;

    // ---------------------------------------------------------------------
    // Authoritative deterministic input sequence
    // ---------------------------------------------------------------------

    const uint32 Inputs[] =
    {
        1,
        1,
        3,
        0,
        2,
        3,
        1,
        0
    };

    for (uint32 Input : Inputs)
    {
        StepSyntheticProof(
            GuestX,
            GuestY,
            GuestColor,
            GuestFrame,
            Input
        );
    }

    // ---------------------------------------------------------------------
    // Validate final translated state
    // ---------------------------------------------------------------------

    const bool bPassed =
        GuestX == 15 &&
        GuestY == 6 &&
        GuestFrame == 8 &&
        GuestColor.R == 0xff &&
        GuestColor.G == 0x3a &&
        GuestColor.B == 0xa7 &&
        GuestColor.A == 0xff;

    if (bPassed)
    {
        UE_LOG(
            LogTemp,
            Display,
            TEXT(
                "OPENRECOMP_GATE_B PASS "
                "x=%d y=%d "
                "rgba=%02x%02x%02x%02x "
                "frame=%d"
            ),
            GuestX,
            GuestY,
            GuestColor.R,
            GuestColor.G,
            GuestColor.B,
            GuestColor.A,
            GuestFrame
        );
    }
    else
    {
        UE_LOG(
            LogTemp,
            Error,
            TEXT("OPENRECOMP_GATE_B FAIL")
        );
    }
}


void AOpenRecompProofActor::StartVisualDemo()
{
    // ---------------------------------------------------------------------
    // Reset PRESENTATION state.
    //
    // This does not alter the authoritative GuestX/GuestY/etc state that
    // was already validated by RunSyntheticTranslatedProof().
    // ---------------------------------------------------------------------

    DemoStepIndex = 0;

    DemoGuestX = 0;
    DemoGuestY = 0;

    DemoGuestColor =
        FColor(
            255,
            58,
            167,
            255
        );

    DemoGuestFrame = 0;

    UpdateDemoVisuals();

    // ---------------------------------------------------------------------
    // Replay one deterministic state transition every 0.5 seconds.
    // ---------------------------------------------------------------------

    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimer(
            DemoTimerHandle,
            this,
            &AOpenRecompProofActor::OnDemoStep,
            0.5f,
            true
        );
    }
}


void AOpenRecompProofActor::OnDemoStep()
{
    const uint32 Inputs[] =
    {
        1,
        1,
        3,
        0,
        2,
        3,
        1,
        0
    };

    // ---------------------------------------------------------------------
    // Execute next presentation step
    // ---------------------------------------------------------------------

    if (DemoStepIndex < 8)
    {
        StepSyntheticProof(
            DemoGuestX,
            DemoGuestY,
            DemoGuestColor,
            DemoGuestFrame,
            Inputs[DemoStepIndex]
        );

        DemoStepIndex++;

        UpdateDemoVisuals();
    }

    // ---------------------------------------------------------------------
    // Presentation complete
    // ---------------------------------------------------------------------

    if (DemoStepIndex >= 8)
    {
        if (UWorld* World = GetWorld())
        {
            World->GetTimerManager().ClearTimer(
                DemoTimerHandle
            );
        }

        if (TextComponent)
        {
            TextComponent->SetText(
                FText::FromString(
                    FString::Printf(
                        TEXT(
                            "OPENRECOMP DEMO PASS\n"
                            "x=%d\n"
                            "y=%d\n"
                            "frame=%d\n"
                            "rgba=%02x%02x%02x%02x"
                        ),
                        DemoGuestX,
                        DemoGuestY,
                        DemoGuestFrame,
                        DemoGuestColor.R,
                        DemoGuestColor.G,
                        DemoGuestColor.B,
                        DemoGuestColor.A
                    )
                )
            );
        }

        UE_LOG(
            LogTemp,
            Display,
            TEXT(
                "OPENRECOMP_DEMO PASS "
                "x=%d y=%d "
                "rgba=%02x%02x%02x%02x "
                "frame=%d"
            ),
            DemoGuestX,
            DemoGuestY,
            DemoGuestColor.R,
            DemoGuestColor.G,
            DemoGuestColor.B,
            DemoGuestColor.A,
            DemoGuestFrame
        );
    }
}


void AOpenRecompProofActor::UpdateDemoVisuals()
{
    // ---------------------------------------------------------------------
    // Map deterministic guest coordinates to an obvious visual distance.
    // ---------------------------------------------------------------------

    constexpr float VisualScale = 50.0f;

    SetActorLocation(
        FVector(
            static_cast<float>(DemoGuestX) * VisualScale,
            static_cast<float>(DemoGuestY) * VisualScale,
            200.0f
        )
    );

    // ---------------------------------------------------------------------
    // Update mesh presentation colour.
    // ---------------------------------------------------------------------

    if (MeshComponent)
    {
        UMaterialInstanceDynamic* DynMaterial =
            MeshComponent->CreateAndSetMaterialInstanceDynamic(0);

        if (DynMaterial)
        {
            const FLinearColor LinearGuestColor(
                DemoGuestColor
            );

            DynMaterial->SetVectorParameterValue(
                TEXT("Color"),
                LinearGuestColor
            );

            DynMaterial->SetVectorParameterValue(
                TEXT("BaseColor"),
                LinearGuestColor
            );
        }
    }

    // ---------------------------------------------------------------------
    // Update visible guest-state text while replay is active.
    // ---------------------------------------------------------------------

    if (TextComponent && DemoStepIndex < 8)
    {
        TextComponent->SetText(
            FText::FromString(
                FString::Printf(
                    TEXT(
                        "OPENRECOMP\n"
                        "x=%d\n"
                        "y=%d\n"
                        "frame=%d\n"
                        "rgba=%02x%02x%02x%02x"
                    ),
                    DemoGuestX,
                    DemoGuestY,
                    DemoGuestFrame,
                    DemoGuestColor.R,
                    DemoGuestColor.G,
                    DemoGuestColor.B,
                    DemoGuestColor.A
                )
            )
        );
    }
}