#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"

#include "OpenRecompNativeModuleV1.h"
#include "OpenRecompSubsystem.generated.h"

UCLASS()
class OPENRECOMPRUNTIME_API UOpenRecompSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    UFUNCTION(BlueprintCallable, Category="OpenRecomp")
    bool LoadNativeModule(const FString& ModulePath);

    UFUNCTION(BlueprintCallable, Category="OpenRecomp")
    void UnloadNativeModule();

    UFUNCTION(BlueprintCallable, Category="OpenRecomp")
    bool RunNativeModule();

    UFUNCTION(BlueprintPure, Category="OpenRecomp")
    bool IsNativeModuleLoaded() const;

    UFUNCTION(BlueprintPure, Category="OpenRecomp")
    FString GetLastError() const;

    UFUNCTION(BlueprintPure, Category="OpenRecomp")
    FString GetModuleId() const;

    UFUNCTION(BlueprintPure, Category="OpenRecomp")
    FString GetSourceArchitecture() const;

    UFUNCTION(BlueprintPure, Category="OpenRecomp")
    int64 GetObservedState() const;

    UFUNCTION(BlueprintPure, Category="OpenRecomp")
    int64 GetOperationCount() const;

    UFUNCTION(BlueprintCallable, Category="OpenRecomp")
    bool ReadMemory(int64 Address, int32 Size, TArray<uint8>& OutBytes);

    void SetHostCallHandler(FOpenRecompHostCallHandlerV1 Handler);
    void ClearHostCallHandler();

    const FOpenRecompModuleMetadataV1& GetMetadataV1() const;
    const FOpenRecompExecutionResultV1& GetLastExecutionV1() const;

private:
    FOpenRecompNativeModuleV1 NativeModule;
};
