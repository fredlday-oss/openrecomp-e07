#pragma once

#include "CoreMinimal.h"
#include "Templates/UniquePtr.h"

#include "OpenRecompRuntimeTypes.h"
#include "openrecomp/native_aot_abi_v1.h"

class OPENRECOMPRUNTIME_API FOpenRecompNativeAotModule
{
public:
    FOpenRecompNativeAotModule();
    ~FOpenRecompNativeAotModule();

    FOpenRecompNativeAotModule(const FOpenRecompNativeAotModule&) = delete;
    FOpenRecompNativeAotModule& operator=(const FOpenRecompNativeAotModule&) = delete;

    FOpenRecompNativeAotModule(FOpenRecompNativeAotModule&& Other) noexcept;
    FOpenRecompNativeAotModule& operator=(FOpenRecompNativeAotModule&& Other) noexcept;

    bool Load(const FString& ModulePath, FString& OutError);
    void Unload();

    bool IsLoaded() const;
    const FString& GetLoadedPath() const;
    const FOpenRecompModuleInfo& GetModuleInfo() const;

    bool Execute(
        const openrecomp_native_aot_host_v1* Host,
        FOpenRecompExecutionResult& OutResult,
        FString& OutError);

private:
    struct FImpl;
    TUniquePtr<FImpl> Impl;
};
