#include "OpenRecompSubsystem.h"

#include "OpenRecompPackagedProofV1.h"

#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

void UOpenRecompSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);

    if (FParse::Param(FCommandLine::Get(), TEXT("OpenRecompPackagedProof")))
    {
        RunOpenRecompPackagedProofV1(*this);
    }
}

void UOpenRecompSubsystem::Deinitialize()
{
    NativeModule.ClearHostCallHandler();
    NativeModule.Unload();
    Super::Deinitialize();
}

bool UOpenRecompSubsystem::LoadNativeModule(const FString& ModulePath)
{
    return NativeModule.Load(ModulePath);
}

void UOpenRecompSubsystem::UnloadNativeModule()
{
    NativeModule.Unload();
}

bool UOpenRecompSubsystem::RunNativeModule()
{
    return NativeModule.Run();
}

bool UOpenRecompSubsystem::IsNativeModuleLoaded() const
{
    return NativeModule.IsLoaded();
}

FString UOpenRecompSubsystem::GetLastError() const
{
    return NativeModule.GetLastError();
}

FString UOpenRecompSubsystem::GetModuleId() const
{
    return NativeModule.GetMetadata().ModuleId;
}

FString UOpenRecompSubsystem::GetSourceArchitecture() const
{
    return NativeModule.GetMetadata().SourceArchitecture;
}

int64 UOpenRecompSubsystem::GetObservedState() const
{
    return static_cast<int64>(NativeModule.GetLastExecution().ObservedState);
}

int64 UOpenRecompSubsystem::GetOperationCount() const
{
    return static_cast<int64>(NativeModule.GetLastExecution().Operations);
}

bool UOpenRecompSubsystem::ReadMemory(int64 Address, int32 Size, TArray<uint8>& OutBytes)
{
    OutBytes.Reset();
    if (Address < 0 || Size < 0)
    {
        return false;
    }
    return NativeModule.ReadMemory(
        static_cast<uint64>(Address),
        static_cast<uint64>(Size),
        OutBytes);
}

void UOpenRecompSubsystem::SetHostCallHandler(FOpenRecompHostCallHandlerV1 Handler)
{
    NativeModule.SetHostCallHandler(MoveTemp(Handler));
}

void UOpenRecompSubsystem::ClearHostCallHandler()
{
    NativeModule.ClearHostCallHandler();
}

const FOpenRecompModuleMetadataV1& UOpenRecompSubsystem::GetMetadataV1() const
{
    return NativeModule.GetMetadata();
}

const FOpenRecompExecutionResultV1& UOpenRecompSubsystem::GetLastExecutionV1() const
{
    return NativeModule.GetLastExecution();
}
