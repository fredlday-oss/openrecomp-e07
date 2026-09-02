#include "OpenRecompPluginExampleActor.h"

#include "OpenRecompSubsystem.h"

#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/Paths.h"

namespace {

constexpr uint32 ProofWidth = 4;
constexpr uint32 ProofHeight = 4;
constexpr uint32 ProofChannels = 3;
constexpr uint32 ProofAudioSamples = 16;
constexpr uint32 ProofAudioStep = 257;
constexpr uint32 ProofSystemBias = 7;
constexpr uint32 ExpectedChecksum = 122010428u;
constexpr uint64 ExpectedObservedState = 48u;
constexpr uint64 ExpectedOperations = 3866u;
const uint32 ProofInputs[] = {4u, 7u, 1u, 9u, 2u, 6u, 3u, 8u};

}  // namespace

AOpenRecompPluginExampleActor::AOpenRecompPluginExampleActor()
{
    PrimaryActorTick.bCanEverTick = false;

    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
    RootComponent = SceneRoot;

    TextComponent = CreateDefaultSubobject<UTextRenderComponent>(TEXT("TextComponent"));
    TextComponent->SetupAttachment(SceneRoot);
    TextComponent->SetHorizontalAlignment(EHTA_Center);
    TextComponent->SetTextRenderColor(FColor::White);
    TextComponent->SetWorldSize(42.0f);
}

void AOpenRecompPluginExampleActor::BeginPlay()
{
    Super::BeginPlay();
    RunPluginProof();
}

void AOpenRecompPluginExampleActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (UGameInstance* GameInstance = GetGameInstance())
    {
        if (UOpenRecompSubsystem* Subsystem = GameInstance->GetSubsystem<UOpenRecompSubsystem>())
        {
            Subsystem->ClearHostCallHandler();
            Subsystem->UnloadNativeModule();
        }
    }
    Super::EndPlay(EndPlayReason);
}

void AOpenRecompPluginExampleActor::ResetDeterministicHost()
{
    TickCount = 0;
    GraphicsCalls = 0;
    AudioCalls = 0;
    InputCalls = 0;
    SystemCalls = 0;
    Framebuffer.Init(0, ProofWidth * ProofHeight * ProofChannels);
    AudioBuffer.Init(0, ProofAudioSamples);
}

bool AOpenRecompPluginExampleActor::HandleHostCall(
    const FString& Symbol,
    TArrayView<const uint64> Args,
    uint64& OutValue,
    bool& bOutHasValue)
{
    OutValue = 0;
    bOutHasValue = false;

    if (Symbol == TEXT("host_graphics"))
    {
        if (Args.Num() != 3)
        {
            return false;
        }
        ++GraphicsCalls;
        const uint64 X = Args[0];
        const uint64 Y = Args[1];
        const uint8 Byte = static_cast<uint8>(Args[2] & 0xffu);
        if (X < ProofWidth && Y < ProofHeight)
        {
            const int32 Index = static_cast<int32>((Y * ProofWidth + X) * ProofChannels);
            Framebuffer[Index] = Byte;
            Framebuffer[Index + 1] = static_cast<uint8>(Byte ^ 0x55u);
            Framebuffer[Index + 2] = static_cast<uint8>(Byte ^ 0xaau);
        }
        return true;
    }

    if (Symbol == TEXT("host_audio"))
    {
        if (Args.Num() != 1)
        {
            return false;
        }
        ++AudioCalls;
        const uint32 Sample = static_cast<uint32>(Args[0]);
        for (uint32 Index = 0; Index < ProofAudioSamples; ++Index)
        {
            AudioBuffer[static_cast<int32>(Index)] =
                static_cast<uint16>((Sample + Index * ProofAudioStep) & 0xffffu);
        }
        return true;
    }

    if (Symbol == TEXT("host_input"))
    {
        if (Args.Num() != 1)
        {
            return false;
        }
        ++InputCalls;
        const uint64 Index = Args[0] % static_cast<uint64>(UE_ARRAY_COUNT(ProofInputs));
        OutValue = ProofInputs[static_cast<int32>(Index)];
        bOutHasValue = true;
        return true;
    }

    if (Symbol == TEXT("host_system"))
    {
        if (Args.Num() != 2)
        {
            return false;
        }
        ++SystemCalls;
        const uint32 A = static_cast<uint32>(Args[0]);
        const uint32 B = static_cast<uint32>(Args[1]);
        OutValue = A + B + ProofSystemBias + TickCount;
        ++TickCount;
        bOutHasValue = true;
        return true;
    }

    return false;
}

uint32 AOpenRecompPluginExampleActor::ComputeProofChecksum(uint64 Observed) const
{
    uint32 Hash =
        static_cast<uint32>(Observed) ^
        TickCount ^
        (GraphicsCalls << 4) ^
        (AudioCalls << 8) ^
        (InputCalls << 12) ^
        (SystemCalls << 16);

    for (const uint8 Byte : Framebuffer)
    {
        Hash = (Hash * 16777619u) ^ Byte;
    }
    for (const uint16 Sample : AudioBuffer)
    {
        Hash = (Hash * 16777619u) ^ static_cast<uint32>(Sample);
    }
    return Hash;
}

void AOpenRecompPluginExampleActor::SetStatusText(const FString& Text, const FColor& Color)
{
    if (TextComponent != nullptr)
    {
        TextComponent->SetText(FText::FromString(Text));
        TextComponent->SetTextRenderColor(Color);
    }
}

void AOpenRecompPluginExampleActor::RunPluginProof()
{
    bPluginProofPassed = false;
    ObservedState = 0;
    Operations = 0;
    ProofChecksum = 0;
    ResetDeterministicHost();

    UGameInstance* GameInstance = GetGameInstance();
    UOpenRecompSubsystem* Subsystem =
        GameInstance != nullptr ? GameInstance->GetSubsystem<UOpenRecompSubsystem>() : nullptr;
    if (Subsystem == nullptr)
    {
        SetStatusText(TEXT("OPENRECOMP PLUGIN FAIL\nsubsystem unavailable"), FColor::Red);
        UE_LOG(LogTemp, Error, TEXT("OPENRECOMP_UNREAL_PLUGIN_V1 FAIL reason=subsystem-unavailable"));
        return;
    }

    FString EffectiveModulePath = NativeModulePath;
    if (EffectiveModulePath.IsEmpty())
    {
        const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("OpenRecompRuntime"));
        if (!Plugin.IsValid())
        {
            SetStatusText(TEXT("OPENRECOMP PLUGIN FAIL\nplugin path unavailable"), FColor::Red);
            UE_LOG(LogTemp, Error, TEXT("OPENRECOMP_UNREAL_PLUGIN_V1 FAIL reason=plugin-path-unavailable"));
            return;
        }
        EffectiveModulePath = FPaths::Combine(
            Plugin->GetBaseDir(),
            TEXT("Binaries/Win64/openrecomp-e07-rv32i.dll"));
    }

    const TWeakObjectPtr<AOpenRecompPluginExampleActor> WeakThis(this);
    Subsystem->SetHostCallHandler(
        [WeakThis](
            const FString& Symbol,
            TArrayView<const uint64> Args,
            uint64& OutValue,
            bool& bOutHasValue) -> bool
        {
            return WeakThis.IsValid() &&
                WeakThis->HandleHostCall(Symbol, Args, OutValue, bOutHasValue);
        });

    if (!Subsystem->LoadNativeModule(EffectiveModulePath) || !Subsystem->RunNativeModule())
    {
        const FString Error = Subsystem->GetLastError();
        Subsystem->ClearHostCallHandler();
        SetStatusText(FString::Printf(TEXT("OPENRECOMP PLUGIN FAIL\n%s"), *Error), FColor::Red);
        UE_LOG(LogTemp, Error, TEXT("OPENRECOMP_UNREAL_PLUGIN_V1 FAIL reason=%s"), *Error);
        return;
    }

    const FOpenRecompModuleMetadataV1& Metadata = Subsystem->GetMetadataV1();
    const FOpenRecompExecutionResultV1& Result = Subsystem->GetLastExecutionV1();
    const uint32 Checksum = ComputeProofChecksum(Result.ObservedState);

    ObservedState = static_cast<int64>(Result.ObservedState);
    Operations = static_cast<int64>(Result.Operations);
    ProofChecksum = static_cast<int64>(Checksum);

    const bool bMetadataPassed =
        Metadata.ModuleId == TEXT("e07.rv32i.fixture-full.ir-v1") &&
        Metadata.SourceArchitecture == TEXT("riscv32-rv32i") &&
        Metadata.HostContractVersion == TEXT("0.1.1") &&
        Metadata.SourceAddressBits == 32u &&
        Metadata.SourceEndianness == OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE &&
        (Metadata.CapabilityFlags & OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS) != 0;

    const bool bExecutionPassed =
        Result.ObservedState == ExpectedObservedState &&
        Result.Operations == ExpectedOperations &&
        Checksum == ExpectedChecksum;

    bPluginProofPassed = bMetadataPassed && bExecutionPassed;
    Subsystem->ClearHostCallHandler();

    if (bPluginProofPassed)
    {
        SetStatusText(
            FString::Printf(
                TEXT("OPENRECOMP PLUGIN PASS\na0=%llu\nchecksum=%u\noperations=%llu"),
                static_cast<unsigned long long>(Result.ObservedState),
                Checksum,
                static_cast<unsigned long long>(Result.Operations)),
            FColor::Green);
        UE_LOG(
            LogTemp,
            Display,
            TEXT(
                "OPENRECOMP_UNREAL_PLUGIN_V1 PASS "
                "module=%s arch=%s observed_state=%llu checksum=%u operations=%llu"),
            *Metadata.ModuleId,
            *Metadata.SourceArchitecture,
            static_cast<unsigned long long>(Result.ObservedState),
            Checksum,
            static_cast<unsigned long long>(Result.Operations));
        return;
    }

    SetStatusText(TEXT("OPENRECOMP PLUGIN FAIL\nvalidation mismatch"), FColor::Red);
    UE_LOG(
        LogTemp,
        Error,
        TEXT("OPENRECOMP_UNREAL_PLUGIN_V1 FAIL metadata=%d execution=%d"),
        bMetadataPassed ? 1 : 0,
        bExecutionPassed ? 1 : 0);
}
