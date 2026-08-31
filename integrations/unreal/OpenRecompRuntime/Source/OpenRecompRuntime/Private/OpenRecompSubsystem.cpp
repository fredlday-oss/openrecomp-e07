#include "OpenRecompSubsystem.h"

#include "OpenRecompE07ValidationHostService.h"
#include "OpenRecompHostService.h"

#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

DEFINE_LOG_CATEGORY_STATIC(LogOpenRecompRuntime, Log, All);

namespace
{

constexpr int64 ExpectedObservedState = 48;
constexpr int64 ExpectedOperations = 3866;
constexpr uint32 ExpectedChecksum = 122010428u;

static int64 RawU64ToInt64(uint64 Value)
{
    int64 Result = 0;
    static_assert(sizeof(Result) == sizeof(Value), "OpenRecomp requires 64-bit reflected values");
    FMemory::Memcpy(&Result, &Value, sizeof(Result));
    return Result;
}

static uint64 RawInt64ToU64(int64 Value)
{
    uint64 Result = 0;
    static_assert(sizeof(Result) == sizeof(Value), "OpenRecomp requires 64-bit reflected values");
    FMemory::Memcpy(&Result, &Value, sizeof(Result));
    return Result;
}

} // namespace

void UOpenRecompSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    LoadedModule = MakeUnique<FOpenRecompNativeAotModule>();
    RunCommandLineProofIfRequested();
}

void UOpenRecompSubsystem::Deinitialize()
{
    bExecuting = false;
    HostService = nullptr;
    if (LoadedModule)
    {
        LoadedModule->Unload();
        LoadedModule.Reset();
    }
    Super::Deinitialize();
}

bool UOpenRecompSubsystem::LoadNativeAotModule(
    const FString& ModulePath,
    FOpenRecompModuleInfo& OutModuleInfo,
    FString& OutError)
{
    OutModuleInfo = FOpenRecompModuleInfo();
    OutError.Reset();

    if (bExecuting)
    {
        OutError = TEXT("Cannot load a Native AOT module during execution");
        return false;
    }
    if (!IsInGameThread())
    {
        OutError = TEXT("OpenRecomp Unreal module loading must run on the game thread");
        return false;
    }

    if (!LoadedModule)
    {
        LoadedModule = MakeUnique<FOpenRecompNativeAotModule>();
    }

    if (!LoadedModule->Load(ModulePath, OutError))
    {
        return false;
    }

    OutModuleInfo = LoadedModule->GetModuleInfo();
    return true;
}

bool UOpenRecompSubsystem::ExecuteLoadedModule(
    FOpenRecompExecutionResult& OutResult,
    FString& OutError)
{
    OutResult = FOpenRecompExecutionResult();
    OutError.Reset();

    if (bExecuting)
    {
        OutError = TEXT("Recursive OpenRecomp module execution is not supported");
        return false;
    }
    if (!IsInGameThread())
    {
        OutError = TEXT("OpenRecomp Unreal module execution must run on the game thread");
        return false;
    }
    if (!LoadedModule || !LoadedModule->IsLoaded())
    {
        OutError = TEXT("No Native AOT ABI V1 module is loaded");
        return false;
    }

    openrecomp_native_aot_host_v1 NativeHost{};
    const openrecomp_native_aot_host_v1* HostPtr = nullptr;
    if (HostService != nullptr)
    {
        NativeHost.struct_size = OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE;
        NativeHost.abi_version = OPENRECOMP_NATIVE_AOT_ABI_V1;
        NativeHost.user_data = this;
        NativeHost.call = &UOpenRecompSubsystem::NativeHostCall;
        HostPtr = &NativeHost;
    }

    bExecuting = true;
    const bool bSucceeded = LoadedModule->Execute(HostPtr, OutResult, OutError);
    bExecuting = false;
    return bSucceeded;
}

void UOpenRecompSubsystem::UnloadNativeAotModule()
{
    if (bExecuting)
    {
        UE_LOG(
            LogOpenRecompRuntime,
            Warning,
            TEXT("Ignoring Native AOT unload request during execution"));
        return;
    }

    if (LoadedModule)
    {
        LoadedModule->Unload();
    }
}

bool UOpenRecompSubsystem::IsNativeAotModuleLoaded() const
{
    return LoadedModule && LoadedModule->IsLoaded();
}

FOpenRecompModuleInfo UOpenRecompSubsystem::GetLoadedModuleInfo() const
{
    return IsNativeAotModuleLoaded()
        ? LoadedModule->GetModuleInfo()
        : FOpenRecompModuleInfo();
}

bool UOpenRecompSubsystem::RegisterHostService(
    UObject* Service,
    FString& OutError)
{
    OutError.Reset();

    if (bExecuting)
    {
        OutError = TEXT("Cannot replace the OpenRecomp host service during execution");
        return false;
    }
    if (Service == nullptr)
    {
        OutError = TEXT("OpenRecomp host service is null");
        return false;
    }
    if (!Service->GetClass()->ImplementsInterface(UOpenRecompHostService::StaticClass()))
    {
        OutError = TEXT("Object does not implement OpenRecompHostService");
        return false;
    }

    HostService = Service;
    return true;
}

void UOpenRecompSubsystem::ClearHostService()
{
    if (bExecuting)
    {
        UE_LOG(
            LogOpenRecompRuntime,
            Warning,
            TEXT("Ignoring host-service clear request during execution"));
        return;
    }
    HostService = nullptr;
}

int32 UOpenRecompSubsystem::NativeHostCall(
    void* UserData,
    const char* Symbol,
    const uint64_t* Args,
    uint64_t Argc,
    uint64_t* OutValue,
    uint32_t* OutHasValue)
{
    if (UserData == nullptr ||
        Symbol == nullptr ||
        OutValue == nullptr ||
        OutHasValue == nullptr ||
        Argc > static_cast<uint64>(MAX_int32))
    {
        return 0;
    }

    UOpenRecompSubsystem* Subsystem = static_cast<UOpenRecompSubsystem*>(UserData);
    if (Subsystem->HostService == nullptr)
    {
        return 0;
    }
    if (Argc != 0 && Args == nullptr)
    {
        return 0;
    }

    TArray<int64> Arguments;
    Arguments.SetNumUninitialized(static_cast<int32>(Argc));
    for (int32 Index = 0; Index < Arguments.Num(); ++Index)
    {
        Arguments[Index] = RawU64ToInt64(Args[Index]);
    }

    int64 ReflectedValue = 0;
    bool bHasValue = false;
    const bool bHandled = IOpenRecompHostService::Execute_HandleOpenRecompHostCall(
        Subsystem->HostService,
        FString(UTF8_TO_TCHAR(Symbol)),
        Arguments,
        ReflectedValue,
        bHasValue);
    if (!bHandled)
    {
        return 0;
    }

    *OutValue = RawInt64ToU64(ReflectedValue);
    *OutHasValue = bHasValue ? 1u : 0u;
    return 1;
}

FString UOpenRecompSubsystem::GetPackagedProofModulePath() const
{
#if PLATFORM_WINDOWS
    const TSharedPtr<IPlugin> Plugin =
        IPluginManager::Get().FindPlugin(TEXT("OpenRecompRuntime"));
    if (!Plugin.IsValid())
    {
        return FString();
    }

    return FPaths::Combine(
        Plugin->GetBaseDir(),
        TEXT("Binaries"),
        FPlatformProcess::GetBinariesSubdirectory(),
        TEXT("openrecomp-e07-rv32i.dll"));
#else
    return FString();
#endif
}

void UOpenRecompSubsystem::RunCommandLineProofIfRequested()
{
    if (!FParse::Param(FCommandLine::Get(), TEXT("OpenRecompPluginProof")))
    {
        return;
    }

    FString ModulePath;
    if (!FParse::Value(
            FCommandLine::Get(),
            TEXT("OpenRecompModule="),
            ModulePath))
    {
        ModulePath = GetPackagedProofModulePath();
    }

    FOpenRecompModuleInfo ModuleInfo;
    FString Error;
    if (!LoadNativeAotModule(ModulePath, ModuleInfo, Error))
    {
        UE_LOG(
            LogOpenRecompRuntime,
            Error,
            TEXT("OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_FAIL stage=load reason=%s"),
            *Error);
        FPlatformMisc::RequestExit(false);
        return;
    }

    UOpenRecompE07ValidationHostService* ProofHost =
        NewObject<UOpenRecompE07ValidationHostService>(this);
    ProofHost->ResetValidationState();
    if (!RegisterHostService(ProofHost, Error))
    {
        UE_LOG(
            LogOpenRecompRuntime,
            Error,
            TEXT("OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_FAIL stage=host reason=%s"),
            *Error);
        UnloadNativeAotModule();
        FPlatformMisc::RequestExit(false);
        return;
    }

    FOpenRecompExecutionResult Result;
    if (!ExecuteLoadedModule(Result, Error))
    {
        UE_LOG(
            LogOpenRecompRuntime,
            Error,
            TEXT("OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_FAIL stage=execute reason=%s"),
            *Error);
        ClearHostService();
        UnloadNativeAotModule();
        FPlatformMisc::RequestExit(false);
        return;
    }

    const uint32 Checksum = ProofHost->ComputeProofChecksum(Result.ObservedState);
    const bool bMetadataPassed =
        Result.Module.ModuleId == TEXT("e07.rv32i.fixture-full.ir-v1") &&
        Result.Module.ModuleFormatVersion == TEXT("1.0.0") &&
        Result.Module.IrVersion == TEXT("1.0.0") &&
        Result.Module.HostContractVersion == TEXT("0.1.1") &&
        Result.Module.SourceArchitecture == TEXT("riscv32-rv32i") &&
        Result.Module.SourceAddressBits == 32 &&
        Result.Module.SourceEndianness == EOpenRecompEndianness::Little &&
        (Result.Module.CapabilityFlags &
            static_cast<int64>(OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS)) != 0;

    const bool bExecutionPassed =
        Result.ObservedState == ExpectedObservedState &&
        Result.bHasFunctionReturn &&
        Result.FunctionReturn == ExpectedObservedState &&
        Result.Operations == ExpectedOperations &&
        Checksum == ExpectedChecksum &&
        ProofHost->AllExpectedCallbacksExercised();

    if (bMetadataPassed && bExecutionPassed)
    {
        UE_LOG(
            LogOpenRecompRuntime,
            Display,
            TEXT(
                "OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS "
                "module=%s arch=%s observed_state=%lld checksum=%u operations=%lld"),
            *Result.Module.ModuleId,
            *Result.Module.SourceArchitecture,
            static_cast<long long>(Result.ObservedState),
            Checksum,
            static_cast<long long>(Result.Operations));
    }
    else
    {
        UE_LOG(
            LogOpenRecompRuntime,
            Error,
            TEXT(
                "OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_FAIL "
                "stage=validate metadata=%d execution=%d"),
            bMetadataPassed ? 1 : 0,
            bExecutionPassed ? 1 : 0);
    }

    ClearHostService();
    UnloadNativeAotModule();
    FPlatformMisc::RequestExit(false);
}
