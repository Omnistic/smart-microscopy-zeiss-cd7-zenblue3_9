ZenLiveScan = LiveScanScriptingPlugin.Instance

config = ZenLiveScan.GetConfiguration()

config.SampleCarrierTypeTemplate = __var0
config.MeasureBottomThickness = __var1
config.DetermineBottonMaterial = __var2
config.SampleCarrierDetection = __var3
config.CreateCarrierOverview = __var4
config.ReadBarcodes = __var5
config.UseLeftBarcode = __var6
config.UseRightBarcode = __var7
config.AutomaticSampleCarrierCalibration = __var8

ZenLiveScan.SetConfiguration(config)

ZenLiveScan.LoadTrayAndPrescan()