
if __name__ == '__main__':
    from GridCal.Engine.Importers.matpower_parser import *

    fname = '/home/santi/Descargas/matpower6.0/case_illinois200.m'


    parse_matpower_file(fname)