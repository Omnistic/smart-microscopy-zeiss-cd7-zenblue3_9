experiment_name = __var0
experiment = ZenExperiment()
experiment.Load(experiment_name, ZenSettingDirectory.User)
experiment.ClearTileRegionsAndPositions(0)
experiment.AddSinglePosition(0, __var1, __var2, __var3)
experiment.Save()
experiment.Load(experiment_name, ZenSettingDirectory.User)
experiment.SetActive()

outputexperiment = Zen.Acquisition.Execute(experiment)

retstring = ZenLiveScan.GetCurrentError()
print(retstring)