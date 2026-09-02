#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"

#include "OpenRecompHostService.generated.h"

UINTERFACE(BlueprintType)
class OPENRECOMPRUNTIME_API UOpenRecompHostService : public UInterface
{
    GENERATED_BODY()
};

class OPENRECOMPRUNTIME_API IOpenRecompHostService
{
    GENERATED_BODY()

public:
    // Arguments and return values carry the raw 64-bit Native AOT ABI V1 bit
    // pattern through reflected int64 values. Implementations should treat the
    // value according to the host contract for the named symbol.
    UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "OpenRecomp")
    bool HandleOpenRecompHostCall(
        const FString& Symbol,
        const TArray<int64>& Arguments,
        int64& OutValue,
        bool& bOutHasValue);
};
