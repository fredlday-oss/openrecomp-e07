#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"

#include "OpenRecompRuntimeTypes.h"
#include "openrecomp/native_aot_abi_v1.h"

using FOpenRecompHostCallHandlerV1 = TFunction<
    bool(const FString& Symbol, TArrayView<const uint64> Args, uint64& OutValue, bool& bOutHasValue)>;

class OPENRECOMPRUNTIME_API FOpenRecompNativeModuleV1
{
public:
    FOpenRecompNativeModuleV1() = default;
    ~FOpenRecompNativeModuleV1();

    FOpenRecompNativeModuleV1(const FOpenRecompNativeModuleV1&) = delete;
    FOpenRecompNativeModuleV1& operator=(const FOpenRecompNativeModuleV1&) = delete;

    bool Load(const FString& ModulePath);
    void Unload();
    bool IsLoaded() const;

    void SetHostCallHandler(FOpenRecompHostCallHandlerV1 Handler);
    void ClearHostCallHandler();

    bool Run();
    bool ReadMemory(uint64 Address, uint64 Size, TArray<uint8>& OutBytes);
    bool GetStateValue(const FString& StateName, uint64& OutValue) const;

    const FOpenRecompModuleMetadataV1& GetMetadata() const;
    const FOpenRecompExecutionResultV1& GetLastExecution() const;
    const FString& GetLastError() const;
    const FString& GetLoadedPath() const;

private:
    static int32 HostCallThunk(
        void* UserData,
        const char* Symbol,
        const uint64_t* Args,
        uint64_t Argc,
        uint64_t* OutValue,
        uint32_t* OutHasValue);

    bool ValidateApi(const openrecomp_native_aot_api_v1* Candidate);
    void CaptureMetadata();
    void SetError(const FString& Error);

    void* DllHandle = nullptr;
    const openrecomp_native_aot_api_v1* Api = nullptr;
    FOpenRecompHostCallHandlerV1 HostCallHandler;
    FOpenRecompModuleMetadataV1 Metadata;
    FOpenRecompExecutionResultV1 LastExecution;
    FString LastError;
    FString LoadedPath;
};
