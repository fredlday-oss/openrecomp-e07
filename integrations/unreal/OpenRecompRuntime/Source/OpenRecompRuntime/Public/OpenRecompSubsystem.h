#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"

#include "OpenRecompNativeAotModule.h"

#include "OpenRecompSubsystem.generated.h"

UCLASS()
class OPENRECOMPRUNTIME_API UOpenRecompSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    UFUNCTION(BlueprintCallable, Category = "OpenRecomp")
    bool LoadNativeAotModule(
        const FString& ModulePath,
        FOpenRecompModuleInfo& OutModuleInfo,
        FString& OutError);

    UFUNCTION(BlueprintCallable, Category = "OpenRecomp")
    bool ExecuteLoadedModule(
        FOpenRecompExecutionResult& OutResult,
        FString& OutError);

    UFUNCTION(BlueprintCallable, Category = "OpenRecomp")
    void UnloadNativeAotModule();

    UFUNCTION(BlueprintPure, Category = "OpenRecomp")
    bool IsNativeAotModuleLoaded() const;

    UFUNCTION(BlueprintPure, Category = "OpenRecomp")
    FOpenRecompModuleInfo GetLoadedModuleInfo() const;

    UFUNCTION(BlueprintCallable, Category = "OpenRecomp")
    bool RegisterHostService(UObject* Service, FString& OutError);

    UFUNCTION(BlueprintCallable, Category = "OpenRecomp")
    void ClearHostService();

private:
    static int32 NativeHostCall(
        void* UserData,
        const char* Symbol,
        const uint64_t* Args,
        uint64_t Argc,
        uint64_t* OutValue,
        uint32_t* OutHasValue);

    void RunCommandLineProofIfRequested();
    FString GetPackagedProofModulePath() const;

    TUniquePtr<FOpenRecompNativeAotModule> LoadedModule;

    UPROPERTY(Transient)
    TObjectPtr<UObject> HostService;

    bool bExecuting = false;
};
