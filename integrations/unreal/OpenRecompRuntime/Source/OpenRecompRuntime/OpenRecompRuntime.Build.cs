using System.IO;
using UnrealBuildTool;

public class OpenRecompRuntime : ModuleRules
{
    public OpenRecompRuntime(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "Projects"
        });

        if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            string ProofDll = Path.Combine(
                PluginDirectory,
                "Binaries",
                "Win64",
                "openrecomp-e07-rv32i.dll");

            // The plugin itself does not require the synthetic proof DLL.
            // The installer supplies it for the packaged V1 validation gate.
            if (File.Exists(ProofDll))
            {
                RuntimeDependencies.Add(ProofDll, StagedFileType.NonUFS);
            }
        }
    }
}
