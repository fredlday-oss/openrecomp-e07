#include "OpenRecompNativeModuleV1.h"

#include "HAL/PlatformProcess.h"
#include "Misc/Paths.h"

namespace {

static FString Utf8Field(const char* Value)
{
    return Value != nullptr ? FString(UTF8_TO_TCHAR(Value)) : FString();
}

static bool RequiredPointersPresent(const openrecomp_native_aot_api_v1* Candidate)
{
    return Candidate != nullptr &&
        Candidate->set_host != nullptr &&
        Candidate->run != nullptr &&
        Candidate->observed_state != nullptr &&
        Candidate->function_return != nullptr &&
        Candidate->function_has_return != nullptr &&
        Candidate->operations != nullptr &&
        Candidate->error != nullptr &&
        Candidate->state_count != nullptr &&
        Candidate->state_name != nullptr &&
        Candidate->state_value != nullptr &&
        Candidate->memory_size != nullptr &&
        Candidate->memory_read != nullptr;
}

static bool RequiredMetadataPresent(const openrecomp_native_aot_api_v1* Candidate)
{
    return Candidate != nullptr &&
        Candidate->module_id != nullptr &&
        Candidate->module_format_version != nullptr &&
        Candidate->ir_version != nullptr &&
        Candidate->host_contract_version != nullptr &&
        Candidate->source_architecture != nullptr &&
        Candidate->source_input_sha256 != nullptr;
}

}  // namespace

FOpenRecompNativeModuleV1::~FOpenRecompNativeModuleV1()
{
    Unload();
}

void FOpenRecompNativeModuleV1::SetError(const FString& Error)
{
    LastError = Error;
}

bool FOpenRecompNativeModuleV1::ValidateApi(const openrecomp_native_aot_api_v1* Candidate)
{
    if (Candidate == nullptr)
    {
        SetError(TEXT("Native AOT ABI V1 query rejected version/size"));
        return false;
    }
    if (Candidate->abi_version != OPENRECOMP_NATIVE_AOT_ABI_V1)
    {
        SetError(TEXT("Native AOT ABI V1 version mismatch"));
        return false;
    }
    if (Candidate->struct_size != OPENRECOMP_NATIVE_AOT_API_V1_SIZE)
    {
        SetError(TEXT("Native AOT ABI V1 structure size mismatch"));
        return false;
    }
    if (!RequiredPointersPresent(Candidate))
    {
        SetError(TEXT("Native AOT ABI V1 function table is incomplete"));
        return false;
    }
    if (!RequiredMetadataPresent(Candidate))
    {
        SetError(TEXT("Native AOT ABI V1 metadata is incomplete"));
        return false;
    }
    if (Candidate->source_endianness != OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE &&
        Candidate->source_endianness != OPENRECOMP_NATIVE_AOT_ENDIAN_BIG)
    {
        SetError(TEXT("Native AOT ABI V1 source endianness is invalid"));
        return false;
    }
    return true;
}

void FOpenRecompNativeModuleV1::CaptureMetadata()
{
    Metadata = FOpenRecompModuleMetadataV1();
    if (Api == nullptr)
    {
        return;
    }

    Metadata.CapabilityFlags = Api->capability_flags;
    Metadata.SourceAddressBits = Api->source_address_bits;
    Metadata.SourceEndianness = Api->source_endianness;
    Metadata.ModuleId = Utf8Field(Api->module_id);
    Metadata.ModuleFormatVersion = Utf8Field(Api->module_format_version);
    Metadata.IrVersion = Utf8Field(Api->ir_version);
    Metadata.HostContractVersion = Utf8Field(Api->host_contract_version);
    Metadata.SourceArchitecture = Utf8Field(Api->source_architecture);
    Metadata.SourceInputSha256 = Utf8Field(Api->source_input_sha256);
}

bool FOpenRecompNativeModuleV1::Load(const FString& ModulePath)
{
    Unload();
    LastError.Reset();

    if (ModulePath.IsEmpty())
    {
        SetError(TEXT("Native AOT module path is empty"));
        return false;
    }

    LoadedPath = FPaths::ConvertRelativePathToFull(ModulePath);
    DllHandle = FPlatformProcess::GetDllHandle(*LoadedPath);
    if (DllHandle == nullptr)
    {
        SetError(FString::Printf(TEXT("Failed to load Native AOT module: %s"), *LoadedPath));
        LoadedPath.Reset();
        return false;
    }

    void* QuerySymbol = FPlatformProcess::GetDllExport(DllHandle, TEXT("openrecomp_native_aot_query"));
    if (QuerySymbol == nullptr)
    {
        SetError(TEXT("Native AOT ABI V1 query symbol is missing"));
        Unload();
        return false;
    }

    const auto Query = reinterpret_cast<const openrecomp_native_aot_api_v1* (*)(uint32_t, uint32_t)>(QuerySymbol);
    const openrecomp_native_aot_api_v1* Candidate = Query(
        OPENRECOMP_NATIVE_AOT_ABI_V1,
        OPENRECOMP_NATIVE_AOT_API_V1_SIZE);
    if (!ValidateApi(Candidate))
    {
        Unload();
        return false;
    }

    Api = Candidate;
    CaptureMetadata();
    LastExecution = FOpenRecompExecutionResultV1();
    return true;
}

void FOpenRecompNativeModuleV1::Unload()
{
    if (Api != nullptr)
    {
        (void)Api->set_host(nullptr);
    }
    Api = nullptr;

    if (DllHandle != nullptr)
    {
        FPlatformProcess::FreeDllHandle(DllHandle);
        DllHandle = nullptr;
    }

    Metadata = FOpenRecompModuleMetadataV1();
    LastExecution = FOpenRecompExecutionResultV1();
    LoadedPath.Reset();
}

bool FOpenRecompNativeModuleV1::IsLoaded() const
{
    return DllHandle != nullptr && Api != nullptr;
}

void FOpenRecompNativeModuleV1::SetHostCallHandler(FOpenRecompHostCallHandlerV1 Handler)
{
    HostCallHandler = MoveTemp(Handler);
}

void FOpenRecompNativeModuleV1::ClearHostCallHandler()
{
    HostCallHandler = FOpenRecompHostCallHandlerV1();
    if (Api != nullptr)
    {
        (void)Api->set_host(nullptr);
    }
}

int32 FOpenRecompNativeModuleV1::HostCallThunk(
    void* UserData,
    const char* Symbol,
    const uint64_t* Args,
    uint64_t Argc,
    uint64_t* OutValue,
    uint32_t* OutHasValue)
{
    if (UserData == nullptr || Symbol == nullptr || OutValue == nullptr || OutHasValue == nullptr)
    {
        return 0;
    }
    if (Argc > static_cast<uint64_t>(MAX_int32) || (Argc != 0 && Args == nullptr))
    {
        return 0;
    }

    auto* Self = static_cast<FOpenRecompNativeModuleV1*>(UserData);
    if (!Self->HostCallHandler)
    {
        return 0;
    }

    uint64 Value = 0;
    bool bHasValue = false;
    const TArrayView<const uint64> ArgsView(
        Args,
        static_cast<int32>(Argc));
    if (!Self->HostCallHandler(Utf8Field(Symbol), ArgsView, Value, bHasValue))
    {
        return 0;
    }

    *OutValue = Value;
    *OutHasValue = bHasValue ? 1u : 0u;
    return 1;
}

bool FOpenRecompNativeModuleV1::Run()
{
    LastExecution = FOpenRecompExecutionResultV1();
    LastError.Reset();

    if (!IsLoaded())
    {
        SetError(TEXT("Native AOT module is not loaded"));
        return false;
    }

    const bool bRequiresHost =
        (Api->capability_flags & OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS) != 0;
    if (bRequiresHost && !HostCallHandler)
    {
        SetError(TEXT("module requires a Native AOT ABI V1 host binding"));
        return false;
    }

    bool bHostBound = false;
    openrecomp_native_aot_host_v1 Host{};
    if (HostCallHandler)
    {
        Host.struct_size = OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE;
        Host.abi_version = OPENRECOMP_NATIVE_AOT_ABI_V1;
        Host.user_data = this;
        Host.call = &FOpenRecompNativeModuleV1::HostCallThunk;
        if (!Api->set_host(&Host))
        {
            SetError(TEXT("module rejected Native AOT ABI V1 host binding"));
            return false;
        }
        bHostBound = true;
    }

    if (!Api->run())
    {
        const char* ModuleError = Api->error();
        SetError(
            ModuleError != nullptr
                ? FString(UTF8_TO_TCHAR(ModuleError))
                : TEXT("Native AOT module execution failed"));
        if (bHostBound)
        {
            (void)Api->set_host(nullptr);
        }
        return false;
    }

    LastExecution.ObservedState = Api->observed_state();
    LastExecution.bHasFunctionReturn = Api->function_has_return() != 0;
    LastExecution.FunctionReturn =
        LastExecution.bHasFunctionReturn ? Api->function_return() : 0;
    LastExecution.Operations = Api->operations();

    if (bHostBound && !Api->set_host(nullptr))
    {
        LastExecution = FOpenRecompExecutionResultV1();
        SetError(TEXT("module rejected Native AOT ABI V1 host unbind"));
        return false;
    }

    return true;
}

bool FOpenRecompNativeModuleV1::ReadMemory(uint64 Address, uint64 Size, TArray<uint8>& OutBytes)
{
    OutBytes.Reset();
    LastError.Reset();

    if (!IsLoaded())
    {
        SetError(TEXT("Native AOT module is not loaded"));
        return false;
    }
    if ((Api->capability_flags & OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ) == 0)
    {
        SetError(TEXT("Native AOT module does not expose memory reads"));
        return false;
    }
    if (Size > static_cast<uint64>(MAX_int32))
    {
        SetError(TEXT("Requested memory read is too large for Unreal array storage"));
        return false;
    }
    if (Size == 0)
    {
        return true;
    }

    OutBytes.SetNumUninitialized(static_cast<int32>(Size));
    if (!Api->memory_read(Address, Size, OutBytes.GetData()))
    {
        OutBytes.Reset();
        SetError(TEXT("Native AOT module memory read failed"));
        return false;
    }
    return true;
}

bool FOpenRecompNativeModuleV1::GetStateValue(const FString& StateName, uint64& OutValue) const
{
    OutValue = 0;
    if (!IsLoaded() ||
        (Api->capability_flags & OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION) == 0)
    {
        return false;
    }

    const uint64 Count = Api->state_count();
    for (uint64 Index = 0; Index < Count; ++Index)
    {
        const char* Name = Api->state_name(Index);
        if (Name != nullptr && StateName == FString(UTF8_TO_TCHAR(Name)))
        {
            OutValue = Api->state_value(Index);
            return true;
        }
    }
    return false;
}

const FOpenRecompModuleMetadataV1& FOpenRecompNativeModuleV1::GetMetadata() const
{
    return Metadata;
}

const FOpenRecompExecutionResultV1& FOpenRecompNativeModuleV1::GetLastExecution() const
{
    return LastExecution;
}

const FString& FOpenRecompNativeModuleV1::GetLastError() const
{
    return LastError;
}

const FString& FOpenRecompNativeModuleV1::GetLoadedPath() const
{
    return LoadedPath;
}
