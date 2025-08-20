import os, re, socket
import napari
import numpy as np
import pandas as pd
from aicspylibczi import CziFile

TCP_IP = os.environ.get('CD7_IP', 'localhost')

OBJECTIVES_AVAILABLE = {
    '5x0.35NA': 2,
    '20x0.7NA': 1,
    '20x0.95NA': 3,
    '50x1.2NA': 4
    }

OPTOVARS_AVAILABLE = {
    '0.5x': 3,
    '1x': 2,
    '2x': 1
    }

SAMPLE_CONFIGURATION = {
    'SampleCarrierTypeTemplate': 'Multiwell 96.czsht',
    'MeasureBottomThickness': False,
    'DetermineBottonMaterial': False,
    'SampleCarrierDetection': False,
    'CreateCarrierOverview': False,
    'ReadBarcodes': False,
    'UseLeftBarcode': False,
    'UseRightBarcode': False,
    'AutomaticSampleCarrierCalibration': False
}

COLORS = {
    'orange': '#E69F00',
    'blue': '#56B4E9',
    'green': '#009E73',
    'yellow': '#F0E442',
    'dark-blue': '#0072B2',
    'dark-orange': '#D55E00',
    'pink': '#CC79A7'
}

class OverviewTilesSetupError(Exception):
    pass

def acquire_overview(tcp_ip, objective, optovar):
    print('Connecting to CD7 LSM ... ', end='', flush=True)
    cd7_lsm = CD7(tcp_ip)
    cd7_lsm.print_last_message()

    print('Loading sample ... ', end='', flush=True)
    cd7_lsm.load_sample(SAMPLE_CONFIGURATION)
    cd7_lsm.print_last_message()

    print('Setting magnification: {} | {} ... '.format(objective, optovar), end='', flush=True)
    cd7_lsm.set_magnification(objective, optovar)
    cd7_lsm.print_last_message()

    experiment = 'smart_overview'
    print('Running experiment: {} ... '.format(experiment), end='', flush=True)
    cd7_lsm.run_experiment(experiment)
    cd7_lsm.print_last_message()

    cd7_lsm.Close()

def analyze_overview(czi_file_path):
    overview = CziFile(czi_file_path)
    metadata = overview.meta

    tile_flag = metadata.find('.//TilesSetup').get('IsActivated')
    if not tile_flag:
        raise OverviewTilesSetupError('TilesSetup is False. Only TilesSetup experiment are supported.')
    
    overview_summary = []
    tile_regions = metadata.findall('.//TileRegion')
    for tile_region in tile_regions:
        tile_name = tile_region.get('Name')
        tile_center = np.array(tile_region.find('CenterPosition').text.split(','), dtype=float)
        tile_cols = int(tile_region.find('Columns').text)
        tile_rows = int(tile_region.find('Rows').text)
        overview_summary.append({
            'TileName': tile_name,
            'TileCenterX': tile_center[0],
            'TileCenterY': tile_center[1],
            'TileCols': tile_cols,
            'TileRows': tile_rows
        })

    overview_summary = pd.DataFrame(overview_summary)
    print(overview_summary)

    test_img, _ = overview.read_image(S=0, M=0)
    test_img = np.squeeze(test_img)

    viewer = napari.Viewer()
    image_layer = viewer.add_image(test_img)
    points_layer = viewer.add_points(
        size=99,
        face_color=[1, 1, 1, 0.5],
        border_color=COLORS['orange'],
        border_width=10,
        border_width_is_relative=False
    )
    points_layer.mode = 'add'
    napari.run()

    target = points_layer.data[0]
    print(target)

class CD7:
    def __init__(self, tcp_ip, tcp_port=52757, buffer_size=1024):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.connect((tcp_ip, tcp_port))
        self.__buffer_size = buffer_size
        self.__last_message = self.__socket.recv(self.__buffer_size).decode().replace('\r\n', '')

    def Close(self):
        self.__socket.close()

    def __encode_macro_from_file(self, macro, args=[]):
        with open(macro, 'r') as f:
            macro = f.read()

        while macro.find('\n\n') != -1:
            macro = macro.replace('\n\n', '\n')
        macro = macro.replace('\n', ';')

        if macro[-1] == ';':
            macro = macro[:-1]

        if type(args) is not list:
            args = [args]

        arg_index = 0
        for arg in args:
            if type(arg) is str:
                macro = re.sub(r'__var'+str(arg_index), '"'+arg+'"', macro, count=1)
            else:
                macro = re.sub(r'__var'+str(arg_index), str(arg), macro, count=1)
            arg_index += 1

        macro = 'EVAL ' + macro

        self.__socket.send(macro.encode())

        self.__last_message = self.__socket.recv(self.__buffer_size).decode().replace('\r\n', '')

    def __encode_macro_from_str(self, macro):
        macro = 'EVAL ' + macro

        self.__socket.send(macro.encode())

        self.__last_message = self.__socket.recv(self.__buffer_size).decode().replace('\r\n', '')

    def print_last_message(self):
        print(self.__last_message)

    def move_to_container(self, container):
        self.__encode_macro_from_file('macros/move_to_container.py', container)

    def load_sample(self, configuration):
        args = []
        args.append(configuration['SampleCarrierTypeTemplate'])
        args.append(configuration['MeasureBottomThickness'])
        args.append(configuration['DetermineBottonMaterial'])
        args.append(configuration['SampleCarrierDetection'])
        args.append(configuration['CreateCarrierOverview'])
        args.append(configuration['ReadBarcodes'])
        args.append(configuration['UseLeftBarcode'])
        args.append(configuration['UseRightBarcode'])
        args.append(configuration['AutomaticSampleCarrierCalibration'])

        self.__encode_macro_from_file('macros/load_sample.py', args)
    
    def set_magnification(self, objective, optovar):
        self.__encode_macro_from_file('macros/set_magnification.py', [OBJECTIVES_AVAILABLE[objective], OPTOVARS_AVAILABLE[optovar]])

    def run_experiment(self, experiment):
        self.__encode_macro_from_file('macros/run_experiment.py', experiment)

    def eject_sample(self):
        macro = 'ZenLiveScan.EjectTray()'

        self.__encode_macro_from_str(macro)

if __name__ == '__main__':
    objective = '5x0.35NA'
    optovar = '1x'
    # acquire_overview(TCP_IP, objective, optovar)

    magnification = float(objective.split('x')[0]) * float(optovar[:-1])
    analyze_overview('overview-01.czi')












    # print('Moving to container B2 ... ', end='', flush=True)
    # cd7_lsm.move_to_container('B2')
    # cd7_lsm.print_last_message()

    # print('Ejecting sample ... ', end='', flush=True)
    # cd7_lsm.eject_sample()
    # cd7_lsm.print_last_message()