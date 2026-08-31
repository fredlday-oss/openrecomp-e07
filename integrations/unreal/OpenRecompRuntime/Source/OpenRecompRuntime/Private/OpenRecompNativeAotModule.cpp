#include "OpenRecompNativeAotModule.h"

#include "HAL/PlatformProcess.h"
#include "Misc/Paths.h"

namespace
{

typedef const openrecomp_native_aot_api_v1* (*FOpenRecompNativeAotQueryV1)(
    uint32_t requested_abi,
    uint32_t minimum_api_size);

static FString Utf8Field(const char* Value)
{
    return Value != nullptr ? FString(UTF8_TO_TCHAR(Value)) : FString();
}

static int64 RawU64ToInt64(uint64 Value)
{
    int64 Result = 0;
    static_assert(sizeof(Result) == sizeof(Value), "OpenRecomp requires 64-bit reflected values");
    FMemory::Memcpy(&Result, &Value, sizeof(Result));
    return Result;
}

static bool RequiredPointersPresent(const openrecomp_native_aot_api_v1* Api)
{
    return Api != nullptr &&
        Api->set_host != nullptr &&
        Api->run != nullptr &&
        Api->observed_state != nullptr &&
        Api->function_return != nullptr &&
        Api->function_has_return != nullptr &&
        Api->operations != nullptr &&
        Api->error != nullptr &&
        Api->state_count != nullptr &&
        Api->state_name != nullptr &&
        Api->state_value != nullptr &&
        Api->memory_size != nullptr &&
        Api->memory_read != nullptr;
}

static bool RequiredMetadataPresent(const openrecomp_native_aot_api_v1* Api)
{
    return Api != nullptr &&
        Api->module_id != nullptr &&
        Api->module_format_version != nullptr &&
        Api->ir_version != nullptr &&
        Api->host_contract_version != nullptr &&
        Api->source_architecture != nullptr &&
        Api->source_input_sha256 != nullptr;
}

static EOpenRecompEndianness ToEndianness(uint32_t Raw)
{
    if (Raw == OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE)
    {
        return EOpenRecompEndianness::Little;
    }
    if (Raw == OPENRECOMP_NATIVE_AOT_ENDIAN_BIG)
    {
        return EOpenRecompEndianness::Big;
    }
    return EOpenRecompEndianness::Unknown;
}

static bool ValidateHostBinding(
    const openrecomp_native_aot_host_v1* Host,
    FString& OutError)
{
    if (Host == nullptr)
    {
        OutError = TEXT("Native AOT ABI V1 host binding is null");
        return false;
    }
    if (Host->struct_size != OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE ||
        Host->abi_version != OPENRECOMP_NATIVE_AOT_ABI_V1 ||
        Host->call == nullptr)
    {
        OutError = TEXT("Native AOT ABI V1 host binding is malformed");
        return false;
    }
    return true;
}

} // namespace

struct FOpenRecompNativeAotModule::FImpl
{
    void* DllHandle = nullptr;
    const openrecomp_native_aot_api_v1* Api = nullptr;
    FString LoadedPath;
    FOpenRecompModuleInfo ModuleInfo;
};

FOpenRecompNativeAotModule::FOpenRecompNativeAotModule()
    : Impl(MakeUnique<FImpl>())
{
}

FOpenRecompNativeAotModule::~FOpenRecompNativeAotModule()
{
    Unload();
}

FOpenRecompNativeAotModule::FOpenRecompNativeAotModule(
    FOpenRecompNativeAotModule&& Other) noexcept
    : Impl(MoveTemp(Other.Impl))
{
    if (!Impl)
    {
        Impl = MakeUnique<FImpl>();
    }
}

FOpenRecompNativeAotModule& FOpenRecompNativeAotModule::operator=(
    FOpenRecompNativeAotModule&& Other) noexcept
{
    if (this != &Other)
    {
        Unload();
        Impl = MoveTemp(Other.Impl);
        if (!Impl)
        {
            Impl = MakeUnique<FImpl>();
        }
    }
    return *this;
}

bool FOpenRecompNativeAotModule::Load(
    const FString& ModulePath,
    FString& OutError)
{
    OutError.Reset();
    Unload();

    if (!Impl)
    {
        Impl = MakeUnique<FImpl>();
    }

    if (ModulePath.IsEmpty())
    {
        OutError = TEXT("Native AOT module path is empty");
        return false;
    }

    const FString FullPath = FPaths::ConvertRelativePathToFull(ModulePath);
    if (!FPaths::FileExists(FullPath))
    {
        OutError = FString::Printf(
            TEXT("Native AOT module does not exist: %s"),
            *FullPath);
        return false;
    }

    void* DllHandle = FPlatformProcess::GetDllHandle(*FullPath);
    if (DllHandle == nullptr)
    {
        OutError = FString::Printf(
            TEXT("Failed to load Native AOT module: %s"),
            *FullPath);
        return false;
    }

    void* QuerySymbol = FPlatformProcess::GetDllExport(
        DllHandle,
        TEXT("openrecomp_native_aot_query"));
    if (QuerySymbol == nullptr)
    {
        FPlatformProcess::FreeDllHandle(DllHandle);
        OutError = TEXT("Native AOT ABI V1 query symbol is missing");
        return false;
    }

    const FOpenRecompNativeAotQueryV1 Query =
        reinterpret_cast<FOpenRecompNativeAotQueryV1>(QuerySymbol);
    const openrecomp_native_aot_api_v1* Api = Query(
        OPENRECOMP_NATIVE_AOT_ABI_V1,
        OPENRECOMP_NATIVE_AOT_API_V1_SIZE);

    if (Api == nullptr)
    {
        FPlatformProcess::FreeDllHandle(DllHandle);
        OutError = TEXT("Native AOT ABI V1 query rejected version/size");
        return false;
    }
    if (Api->abi_version != OPENRECOMP_NATIVE_AOT_ABI_V1)
    {
        FPlatformProcess::FreeDllHandle(DllHandle);
        OutError = TEXT("Native AOT ABI V1 version mismatch");
        return false;
    }
    if (Api->struct_size != OPENRECOMP_NATIVE_AOT_API_V1_SIZE)
    {
        FPlatformProcess::FreeDllHandle(DllHandle);
        OutError = TEXT("Native AOT ABI V1 structure size mismatch");
        return false;
    }
    if (!RequiredPointersPresent(Api))
    {
        FPlatformProcess::FreeDllHandle(DllHandle);
        OutError = TEXT("Native AOT ABI V1 function table is incomplete");
        return false;
    }
    if (!RequiredMetadataPresent(Api))
    {
        FPlatformProcess::FreeDllHandle(DllHandle);
        OutError = TEXT("Native AOT ABI V1 metadata is incomplete");
        return false;
    }

    FOpenRecompModuleInfo Info;
    Info.ModuleId = Utf8Field(Api->module_id);
    Info.ModuleFormatVersion = Utf8Field(Api->module_format_version);
    Info.IrVersion = Utf8Field(Api->ir_version);
    Info.HostContractVersion = Utf8Field(Api->host_contract_version);
    Info.SourceArchitecture = Utf8Field(Api->source_architecture);
    Info.SourceInputSha256 = Utf8Field(Api->source_input_sha256);
    Info.SourceAddressBits = static_cast<int32>(Api->source_address_bits);
    Info.SourceEndianness = ToEndianness(Api->source_endianness);
    Info.CapabilityFlags = RawU64ToInt64(Api->capability_flags);

    Impl->DllHandle = DllHandle;
    Impl->Api = Api;
    Impl->LoadedPath = FullPath;
    Impl->ModuleInfo = MoveTemp(Info);
    return true;
}

void FOpenRecompNativeAotModule::Unload()
{
    if (!Impl)
    {
        return;
    }

    Impl->Api = nullptr;
    if (Impl->DllHandle != nullptr)
    {
        FPlatformProcess::FreeDllHandle(Impl->DllHandle);
        Impl->DllHandle = nullptr;
    }
    Impl->LoadedPath.Reset();
    Impl->ModuleInfo = FOpenRecompModuleInfo();
}

bool FOpenRecompNativeAotModule::IsLoaded() const
{
    return Impl && Impl->DllHandle != nullptr && Impl->Api != nullptr;
}

const FString& FOpenRecompNativeAotModule::GetLoadedPath() const
{
    static const FString Empty;
    return Impl ? Impl->LoadedPath : Empty;
}

const FOpenRecompModuleInfo& FOpenRecompNativeAotModule::GetModuleInfo() const
{
    static const FOpenRecompModuleInfo Empty;
    return Impl ? Impl->ModuleInfo : Empty;
}

bool FOpenRecompNativeAotModule::Execute(
    const openrecomp_native_aot_host_v1* Host,
    FOpenRecompExecutionResult& OutResult,
    FString& OutError)
{
    OutResult = FOpenRecompExecutionResult();
    OutError.Reset();

    if (!IsLoaded())
    {
        OutError = TEXT("No Native AOT ABI V1 module is loaded");
        return false;
    }

    const openrecomp_native_aot_api_v1* Api = Impl->Api;
    const bool bRequiresHost =
        (Api->capability_flags & OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS) != 0;
    bool bHostBound = false;

    if (bRequiresHost && Host == nullptr)
    {
        OutError = TEXT("Module requires a Native AOT ABI V1 host binding");
        return false;
    }

    if (Host != nullptr)
    {
        if (!ValidateHostBinding(Host, OutError))
        {
            return false;
        }
        if (!Api->set_host(Host))
        {
            OutError = TEXT("Module rejected Native AOT ABI V1 host binding");
            return false;
        }
        bHostBound = true;
    }

    if (!Api->run())
    {
        const FString ModuleError = Api->error() != nullptr
            ? Utf8Field(Api->error())
            : TEXT("Native AOT module execution failed");
        if (bHostBound)
        {
            (void)Api->set_host(nullptr);
        }
        OutError = ModuleError;
        return false;
    }

    OutResult.Module = Impl->ModuleInfo;
    OutResult.ObservedState = RawU64ToInt64(Api->observed_state());
    OutResult.bHasFunctionReturn = Api->function_has_return() != 0;
    OutResult.FunctionReturn = OutResult.bHasFunctionReturn
        ? RawU64ToInt64(Api->function_return())
        : 0;
    OutResult.Operations = RawU64ToInt64(Api->operations());

    if (bHostBound && !Api->set_host(nullptr))
    {
        OutResult = FOpenRecompExecutionResult();
        OutError = TEXT("Module rejected Native AOT ABI V1 host unbind");
        return false;
    }

    return true;
}
