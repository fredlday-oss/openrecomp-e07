#include "OpenRecompE07ValidationHostService.h"

namespace
{

constexpr uint32 ProofWidth = 4;
constexpr uint32 ProofHeight = 4;
constexpr uint32 ProofChannels = 3;
constexpr uint32 ProofAudioSamples = 16;
constexpr uint32 ProofAudioStep = 257;
constexpr uint32 ProofSystemBias = 7;

const uint32 ProofInputs[] = {4u, 7u, 1u, 9u, 2u, 6u, 3u, 8u};

static uint64 RawInt64ToU64(int64 Value)
{
    uint64 Result = 0;
    static_assert(sizeof(Result) == sizeof(Value), "OpenRecomp requires 64-bit reflected values");
    FMemory::Memcpy(&Result, &Value, sizeof(Result));
    return Result;
}

} // namespace

UOpenRecompE07ValidationHostService::UOpenRecompE07ValidationHostService()
{
    ResetValidationState();
}

void UOpenRecompE07ValidationHostService::ResetValidationState()
{
    TickCount = 0;
    GraphicsCalls = 0;
    AudioCalls = 0;
    InputCalls = 0;
    SystemCalls = 0;
    Framebuffer.Init(0, ProofWidth * ProofHeight * ProofChannels);
    AudioBuffer.Init(0, ProofAudioSamples);
}

bool UOpenRecompE07ValidationHostService::HandleOpenRecompHostCall_Implementation(
    const FString& Symbol,
    const TArray<int64>& Arguments,
    int64& OutValue,
    bool& bOutHasValue)
{
    OutValue = 0;
    bOutHasValue = false;

    if (Symbol == TEXT("host_graphics"))
    {
        if (Arguments.Num() != 3)
        {
            return false;
        }

        ++GraphicsCalls;
        const uint64 X = RawInt64ToU64(Arguments[0]);
        const uint64 Y = RawInt64ToU64(Arguments[1]);
        const uint8 Byte = static_cast<uint8>(RawInt64ToU64(Arguments[2]) & 0xffu);

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
        if (Arguments.Num() != 1)
        {
            return false;
        }

        ++AudioCalls;
        const uint32 Sample = static_cast<uint32>(RawInt64ToU64(Arguments[0]));
        for (uint32 Index = 0; Index < ProofAudioSamples; ++Index)
        {
            AudioBuffer[static_cast<int32>(Index)] =
                static_cast<uint16>((Sample + Index * ProofAudioStep) & 0xffffu);
        }
        return true;
    }

    if (Symbol == TEXT("host_input"))
    {
        if (Arguments.Num() != 1)
        {
            return false;
        }

        ++InputCalls;
        const uint64 Index = RawInt64ToU64(Arguments[0]) % UE_ARRAY_COUNT(ProofInputs);
        OutValue = static_cast<int64>(ProofInputs[Index]);
        bOutHasValue = true;
        return true;
    }

    if (Symbol == TEXT("host_system"))
    {
        if (Arguments.Num() != 2)
        {
            return false;
        }

        ++SystemCalls;
        const uint32 A = static_cast<uint32>(RawInt64ToU64(Arguments[0]));
        const uint32 B = static_cast<uint32>(RawInt64ToU64(Arguments[1]));
        const uint32 Value = A + B + ProofSystemBias + TickCount;
        ++TickCount;
        OutValue = static_cast<int64>(Value);
        bOutHasValue = true;
        return true;
    }

    return false;
}

uint32 UOpenRecompE07ValidationHostService::ComputeProofChecksum(int64 ObservedState) const
{
    uint32 Hash =
        static_cast<uint32>(RawInt64ToU64(ObservedState)) ^
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

bool UOpenRecompE07ValidationHostService::AllExpectedCallbacksExercised() const
{
    return GraphicsCalls != 0 &&
        AudioCalls != 0 &&
        InputCalls != 0 &&
        SystemCalls != 0;
}
