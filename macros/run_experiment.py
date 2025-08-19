experiment = ZenExperiment()
experiment.Load(__var0, ZenSettingDirectory.User)
experiment.SetActive()
outputexperiment = Zen.Acquisition.Execute(experiment)

retstring = ZenLiveScan.GetCurrentError()
print(retstring)