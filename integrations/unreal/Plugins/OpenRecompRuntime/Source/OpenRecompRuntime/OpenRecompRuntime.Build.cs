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
            string SyntheticModule = Path.Combine(
                PluginDirectory,
                "Binaries",
                "Win64",
                "openrecomp-e07-rv32i.dll");
            if (File.Exists(SyntheticModule))
            {
                RuntimeDependencies.Add(SyntheticModule, StagedFileType.NonUFS);
            }
        }
    }
}
