import os, re, socket
from aicspylibczi import CziFile

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

class OverviewTilesSetupError(Exception):
    pass

def analyze_overview(czi_file_path):
    overview = CziFile(czi_file_path)
    metadata = overview.meta

    tile_flag = metadata.find('.//TilesSetup').get("IsActivated")
    if not tile_flag:
        raise OverviewTilesSetupError('TilesSetup is False. Only TilesSetup experiment are supported.')

class CD7:
    def __init__(self, tcp_ip, tcp_port=52757, buffer_size=1024):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.connect((tcp_ip, tcp_port))
        self.__last_message = self.__socket.recv(buffer_size).decode().replace('\r\n', '')

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

        self.__last_message = self.__socket.recv(buffer_size).decode().replace('\r\n', '')

    def __encode_macro_from_str(self, macro):
        macro = 'EVAL ' + macro

        self.__socket.send(macro.encode())

        self.__last_message = self.__socket.recv(buffer_size).decode().replace('\r\n', '')

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
    tcp_ip = os.environ.get('CD7_IP', 'localhost')
    tcp_port = 52757
    buffer_size = 1024

    sample_configuration = {
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

    # print('Connecting to CD7 LSM ... ', end='', flush=True)
    # cd7_lsm = CD7(tcp_ip, tcp_port, buffer_size)
    # cd7_lsm.print_last_message()

    # print('Loading sample ... ', end='', flush=True)
    # cd7_lsm.load_sample(sample_configuration)
    # cd7_lsm.print_last_message()

    # objective = '5x0.35NA'
    # optovar = '1x'
    # print('Setting magnification: {} | {} ... '.format(objective, optovar), end='', flush=True)
    # cd7_lsm.set_magnification(objective, optovar)
    # cd7_lsm.print_last_message()

    # experiment = 'smart_overview'
    # print('Running experiment: {} ... '.format(experiment), end='', flush=True)
    # cd7_lsm.run_experiment(experiment)
    # cd7_lsm.print_last_message()

    analyze_overview('overview-01.czi')

    # print('Moving to container B2 ... ', end='', flush=True)
    # cd7_lsm.move_to_container('B2')
    # cd7_lsm.print_last_message()

    # print('Ejecting sample ... ', end='', flush=True)
    # cd7_lsm.eject_sample()
    # cd7_lsm.print_last_message()