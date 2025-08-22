import os, re, socket
import napari
import numpy as np
import pandas as pd
from bioio import BioImage

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

PHYSICAL_PIXEL_SIZE_UM = 3.45

SAMPLE_CONFIGURATION = {
    'SampleCarrierTypeTemplate': 'Multiwell 96.czsht',
    'MeasureBottomThickness': True,
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
    cd7_lsm.run_experiment(experiment, type='overview')
    cd7_lsm.print_last_message()

    cd7_lsm.Close()

def analyze_overview(czi_file_path, magnification):
    overview = BioImage(czi_file_path, use_aicspylibczi=True)
    metadata = overview.metadata

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

    # IMPORTANT: the large dimension keeps alternating between scenes
    # and it seems to be coming from the microscope itself (I tried splitting
    # the scenes in ZEN 3.9 and the large dimension was also alternating).
    # If the first scene dimension is (5715, 7782), the second scene will be
    # (5715, 7783), the third (5715, 7782) and so on. I will padd with zeros
    # for now...
    #
    # https://forum.image.sc/t/alternating-scene-sizes-from-zeiss-cd7-zen-blue-3-9/115989
    #
    # DIRTY STUFF HERE
    overview_stack = np.zeros((len(overview.scenes), 5715, 7783))
    for ii in range(len(overview.scenes)):
        overview.set_scene(ii)
        try:
            overview_stack[ii, :, :] = overview.get_image_data('YX')
        except:
            overview_stack[ii, :, :-1] = overview.get_image_data('YX')
    # END OF DIRTY STUFF HERE

    # Test with first scene
    scene_of_interest = 1
    scene_center_um = overview_summary.loc[scene_of_interest, ['TileCenterY', 'TileCenterX']].values
    pixel_size_um = PHYSICAL_PIXEL_SIZE_UM / magnification
    scene_size_px = np.array(overview_stack[0, :, :].shape)
    scene_center_px = np.array((scene_size_px-1) / 2, dtype=int)

    viewer = napari.Viewer()
    image_layer = viewer.add_image(overview_stack[scene_of_interest, :, :])
    points_layer = viewer.add_points(
        size=99,
        face_color=[1, 1, 1, 0.5],
        border_color=COLORS['orange'],
        border_width=10,
        border_width_is_relative=False
    )
    points_layer.mode = 'add'
    napari.run()

    # Pixel coordinates within a scene where (0, 0) is the top-left corner
    target_local_screen_px = points_layer.data[0]
    # Pixel coordinates within a scene where (0, 0) is the center of the scene
    target_local_cartesian_px = target_local_screen_px - scene_center_px
    # Um coordinates within a scene where (0, 0) is the center of the scene
    target_local_cartesian_um = target_local_cartesian_px * pixel_size_um
    # Um coordinates within the template
    target_template_um = scene_center_um + target_local_cartesian_um

    # Um coordinates within the template in 'XY' order
    target_template_um = target_template_um[::-1]

    return target_template_um

def acquire_detail(tcp_ip, objective, optovar, target):
    print('Connecting to CD7 LSM ... ', end='', flush=True)
    cd7_lsm = CD7(tcp_ip)
    cd7_lsm.print_last_message()

    print('Setting magnification: {} | {} ... '.format(objective, optovar), end='', flush=True)
    cd7_lsm.set_magnification(objective, optovar)
    cd7_lsm.print_last_message()

    experiment = 'smart_detail'
    print('Running experiment: {} ... '.format(experiment), end='', flush=True)
    cd7_lsm.run_experiment(experiment, type='detail', target=target)
    cd7_lsm.print_last_message()

    cd7_lsm.Close()

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

    def run_experiment(self, experiment, type, target=None):
        match type:
            case 'overview':
                self.__encode_macro_from_file('macros/run_overview.py', experiment)
            case 'detail':
                target_x, target_y, target_z = target
                self.__encode_macro_from_file('macros/run_detail.py', [experiment, target_x, target_y, target_z])

    def eject_sample(self):
        macro = 'ZenLiveScan.EjectTray()'

        self.__encode_macro_from_str(macro)

if __name__ == '__main__':
    overview_objective = '5x0.35NA'
    overview_optovar = '1x'
    detail_objective = '20x0.95NA'
    detail_optovar = '2x'

    # print(' === Overview Acquisition === ')
    # acquire_overview(TCP_IP, overview_objective, overview_optovar)

    print(' === Overview Analysis === ')
    magnification = float(overview_objective.split('x')[0]) * float(overview_optovar[:-1])
    target = analyze_overview('overview_2_scenes.czi', magnification)
    print(target)

    print(' === Detail Acquisition === ')
    safe_z = 2100.00
    target_x, target_y = target

    target = np.array([target_x, target_y, safe_z])

    acquire_detail(TCP_IP, detail_objective, detail_optovar, target)






    # print('Moving to container B2 ... ', end='', flush=True)
    # cd7_lsm.move_to_container('B2')
    # cd7_lsm.print_last_message()

    # print('Ejecting sample ... ', end='', flush=True)
    # cd7_lsm.eject_sample()
    # cd7_lsm.print_last_message()