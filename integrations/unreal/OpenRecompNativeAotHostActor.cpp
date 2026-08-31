#include "OpenRecompNativeAotHostActor.h"

#include "OpenRecompNativeAotHostV1.h"

#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
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

AOpenRecompNativeAotHostActor::AOpenRecompNativeAotHostActor()
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

void AOpenRecompNativeAotHostActor::BeginPlay()
{
    Super::BeginPlay();
    RunNativeAotProof();
}

void AOpenRecompNativeAotHostActor::ResetDeterministicHost()
{
    TickCount = 0;
    GraphicsCalls = 0;
    AudioCalls = 0;
    InputCalls = 0;
    SystemCalls = 0;
    Framebuffer.Init(0, ProofWidth * ProofHeight * ProofChannels);
    AudioBuffer.Init(0, ProofAudioSamples);
}

int32 AOpenRecompNativeAotHostActor::NativeHostCall(
    void* UserData,
    const char* Symbol,
    const uint64_t* Args,
    uint64_t Argc,
    uint64_t* OutValue,
    uint32_t* OutHasValue)
{
    if (UserData == nullptr)
    {
        return 0;
    }

    return static_cast<AOpenRecompNativeAotHostActor*>(UserData)->HandleHostCall(
        Symbol,
        Args,
        Argc,
        OutValue,
        OutHasValue);
}

int32 AOpenRecompNativeAotHostActor::HandleHostCall(
    const char* Symbol,
    const uint64_t* Args,
    uint64_t Argc,
    uint64_t* OutValue,
    uint32_t* OutHasValue)
{
    if (Symbol == nullptr || OutValue == nullptr || OutHasValue == nullptr)
    {
        return 0;
    }

    *OutValue = 0;
    *OutHasValue = 0;

    if (FCStringAnsi::Strcmp(Symbol, "host_graphics") == 0)
    {
        if (Argc != 3 || Args == nullptr)
        {
            return 0;
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
        return 1;
    }

    if (FCStringAnsi::Strcmp(Symbol, "host_audio") == 0)
    {
        if (Argc != 1 || Args == nullptr)
        {
            return 0;
        }

        ++AudioCalls;
        const uint32 Sample = static_cast<uint32>(Args[0]);
        for (uint32 Index = 0; Index < ProofAudioSamples; ++Index)
        {
            AudioBuffer[static_cast<int32>(Index)] =
                static_cast<uint16>((Sample + Index * ProofAudioStep) & 0xffffu);
        }
        return 1;
    }

    if (FCStringAnsi::Strcmp(Symbol, "host_input") == 0)
    {
        if (Argc != 1 || Args == nullptr)
        {
            return 0;
        }

        ++InputCalls;
        const uint64 Index = Args[0] % static_cast<uint64>(UE_ARRAY_COUNT(ProofInputs));
        *OutValue = ProofInputs[static_cast<int32>(Index)];
        *OutHasValue = 1;
        return 1;
    }

    if (FCStringAnsi::Strcmp(Symbol, "host_system") == 0)
    {
        if (Argc != 2 || Args == nullptr)
        {
            return 0;
        }

        ++SystemCalls;
        const uint32 A = static_cast<uint32>(Args[0]);
        const uint32 B = static_cast<uint32>(Args[1]);
        const uint32 Value = A + B + ProofSystemBias + TickCount;
        ++TickCount;
        *OutValue = Value;
        *OutHasValue = 1;
        return 1;
    }

    return 0;
}

uint32 AOpenRecompNativeAotHostActor::ComputeProofChecksum(uint64 Observed) const
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

void AOpenRecompNativeAotHostActor::SetStatusText(const FString& Text, const FColor& Color)
{
    if (TextComponent != nullptr)
    {
        TextComponent->SetText(FText::FromString(Text));
        TextComponent->SetTextRenderColor(Color);
    }
}

void AOpenRecompNativeAotHostActor::RunNativeAotProof()
{
    bNativeAotPassed = false;
    ObservedState = 0;
    Operations = 0;
    ProofChecksum = 0;
    LoadedModuleId.Reset();
    ResetDeterministicHost();

    FString EffectiveModulePath = NativeModulePath;
    if (EffectiveModulePath.IsEmpty())
    {
        EffectiveModulePath = FPaths::Combine(
            FPaths::ProjectDir(),
            TEXT("Binaries/Win64/openrecomp-e07-rv32i.dll"));
    }

    openrecomp_native_aot_host_v1 Host{};
    Host.struct_size = OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE;
    Host.abi_version = OPENRECOMP_NATIVE_AOT_ABI_V1;
    Host.user_data = this;
    Host.call = &AOpenRecompNativeAotHostActor::NativeHostCall;

    FOpenRecompNativeAotExecutionV1 Result;
    FString Error;
    if (!FOpenRecompNativeAotHostV1::ExecuteModule(
            EffectiveModulePath,
            &Host,
            Result,
            Error))
    {
        SetStatusText(
            FString::Printf(TEXT("OPENRECOMP NATIVE AOT FAIL\n%s"), *Error),
            FColor::Red);
        UE_LOG(
            LogTemp,
            Error,
            TEXT("OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 FAIL reason=%s"),
            *Error);
        return;
    }

    const uint32 Checksum = ComputeProofChecksum(Result.ObservedState);
    ObservedState = static_cast<int64>(Result.ObservedState);
    Operations = static_cast<int64>(Result.Operations);
    ProofChecksum = static_cast<int64>(Checksum);
    LoadedModuleId = Result.ModuleId;

    const bool bMetadataPassed =
        Result.ModuleId == TEXT("e07.rv32i.fixture-full.ir-v1") &&
        Result.SourceArchitecture == TEXT("riscv32-rv32i") &&
        Result.HostContractVersion == TEXT("0.1.1") &&
        Result.SourceAddressBits == 32u &&
        Result.SourceEndianness == OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE &&
        (Result.CapabilityFlags & OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS) != 0;

    const bool bExecutionPassed =
        Result.ObservedState == ExpectedObservedState &&
        Result.Operations == ExpectedOperations &&
        Checksum == ExpectedChecksum;

    bNativeAotPassed = bMetadataPassed && bExecutionPassed;
    if (bNativeAotPassed)
    {
        SetStatusText(
            FString::Printf(
                TEXT("OPENRECOMP NATIVE AOT PASS\na0=%llu\nchecksum=%u\noperations=%llu"),
                static_cast<unsigned long long>(Result.ObservedState),
                Checksum,
                static_cast<unsigned long long>(Result.Operations)),
            FColor::Green);
        UE_LOG(
            LogTemp,
            Display,
            TEXT(
                "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS "
                "module=%s arch=%s observed_state=%llu checksum=%u operations=%llu"),
            *Result.ModuleId,
            *Result.SourceArchitecture,
            static_cast<unsigned long long>(Result.ObservedState),
            Checksum,
            static_cast<unsigned long long>(Result.Operations));
        return;
    }

    SetStatusText(
        FString::Printf(
            TEXT("OPENRECOMP NATIVE AOT FAIL\na0=%llu\nchecksum=%u\noperations=%llu"),
            static_cast<unsigned long long>(Result.ObservedState),
            Checksum,
            static_cast<unsigned long long>(Result.Operations)),
        FColor::Red);
    UE_LOG(
        LogTemp,
        Error,
        TEXT(
            "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 FAIL "
            "metadata=%d execution=%d"),
        bMetadataPassed ? 1 : 0,
        bExecutionPassed ? 1 : 0);
}
