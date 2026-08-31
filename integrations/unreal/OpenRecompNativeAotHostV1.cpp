#include "OpenRecompNativeAotHostV1.h"

#include "HAL/PlatformProcess.h"

namespace {

static FString Utf8Field(const char* Value)
{
    return Value != nullptr ? FString(UTF8_TO_TCHAR(Value)) : FString();
}

}  // namespace

bool FOpenRecompNativeAotHostV1::ExecuteModule(
    const FString& ModulePath,
    const openrecomp_native_aot_host_v1* Host,
    FOpenRecompNativeAotExecutionV1& OutResult,
    FString& OutError)
{
    OutResult = FOpenRecompNativeAotExecutionV1();
    OutError.Reset();

    if (ModulePath.IsEmpty())
    {
        OutError = TEXT("Native AOT module path is empty");
        return false;
    }

    void* DllHandle = FPlatformProcess::GetDllHandle(*ModulePath);
    if (DllHandle == nullptr)
    {
        OutError = FString::Printf(
            TEXT("Failed to load Native AOT module: %s"),
            *ModulePath);
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

    const openrecomp_native_aot_query_fn_v1 Query =
        reinterpret_cast<openrecomp_native_aot_query_fn_v1>(QuerySymbol);

    openrecomp_unreal_native_aot_result_v1 RawResult{};
    char ErrorText[512]{};

    const bool bExecuted =
        openrecomp_unreal_native_aot_execute_v1(
            Query,
            Host,
            &RawResult,
            ErrorText,
            sizeof(ErrorText)) != 0;

    if (!bExecuted)
    {
        OutError = ErrorText[0] != '\0'
            ? FString(UTF8_TO_TCHAR(ErrorText))
            : TEXT("Native AOT ABI V1 execution failed");
        FPlatformProcess::FreeDllHandle(DllHandle);
        return false;
    }

    OutResult.CapabilityFlags = RawResult.capability_flags;
    OutResult.ObservedState = RawResult.observed_state;
    OutResult.FunctionReturn = RawResult.function_return;
    OutResult.bHasFunctionReturn = RawResult.function_has_return != 0;
    OutResult.Operations = RawResult.operations;
    OutResult.SourceAddressBits = RawResult.source_address_bits;
    OutResult.SourceEndianness = RawResult.source_endianness;
    OutResult.ModuleId = Utf8Field(RawResult.module_id);
    OutResult.ModuleFormatVersion = Utf8Field(RawResult.module_format_version);
    OutResult.IrVersion = Utf8Field(RawResult.ir_version);
    OutResult.HostContractVersion = Utf8Field(RawResult.host_contract_version);
    OutResult.SourceArchitecture = Utf8Field(RawResult.source_architecture);
    OutResult.SourceInputSha256 = Utf8Field(RawResult.source_input_sha256);

    FPlatformProcess::FreeDllHandle(DllHandle);
    return true;
}
