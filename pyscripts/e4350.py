#!/usr/bin/python3
import argparse
import math
import serial
import sys
import time

class E4350Exception(Exception):
    pass

class E4350:
    def __init__(self, ser, addr):
        self.ser, self.addr = ser, addr
        self.send('++mode 1')
        self.send('++addr {}'.format(addr))
        resp = self.send('*IDN?')
        idn = resp.split(b',')
        if len(idn) < 2 or idn[:2] != [b'HEWLETT-PACKARD', b'E4350A']:
            raise E4350Exception('does not seem to be an E4350A: ' + str(resp))

    def send(self, msg):
        # writes the message, terminates it with a newline,
        #  reads and returns a response
        self.ser.write(bytes(msg + '\n', 'ascii'))
        time.sleep(0.3)
        return self.ser.read_all()

    def output_off(self):
        self.send('OUTP:STAT OFF')

    def output_on(self):
        self.send('OUTP:STAT ON')

    def pt_mode(self):
        self.send('SOUR:CURR:MODE TABL')

    def set_pts(self, ptlist):
        # ptlist is [(float, float)...] of v,i points
        self.send('MEM:DEL:NAME frompython') # no problem if it's not there
        self.send('MEM:TABL:SEL frompython')
        # limitation is that we need to do <=100 pts at a time
        for i in range(0, math.ceil(len(ptlist) / 100)):
            pts = ptlist[i * 100 : (i + 1) * 100]
            self.send('MEM:VOLT ' + ','.join(['{:.2f}'.format(v)
                                              for v,i in pts]))
            self.send('MEM:CURR ' + ','.join(['{:.2f}'.format(i)
                                              for v,i in pts]))

    def sim_mode(self):
        self.send('SOUR:CURR:MODE SAS')
    
    def sim_pts(self, isc, vmp, imp, voc):
        self.send('SOUR:CURR:SAS:ISC {}'.format(isc))
        self.send('SOUR:CURR:SAS:IMP {}'.format(imp))
        self.send('SOUR:VOLT:SAS:VOC {}'.format(voc))
        self.send('SOUR:VOLT:SAS:VMP {}'.format(vmp))

    def get_telem(self):
        # returns {'v': float, 'i': float} volts and amps
        return {'v': float(self.send('MEAS:VOLT?')),
                'i': float(self.send('MEAS:CURR?'))
               }
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='prologix port', required=True)
    parser.add_argument('-a', '--address', help='E4350A address on GPIB bus', required=True)
    parser.add_argument('-f', '--infile',
                        help='IV curve input file ("V_in_Volts,I_in_A\\n")')
    parser.add_argument('--sim', help='Simulator settings as --sim=Isc,Vmp,Imp,Voc')
    parser.add_argument('-t', '--period', type=float, default=5,
                        help='logging period (seconds)')
    args = parser.parse_args()
    if ((not (args.infile or args.sim)) or
        (args.infile and args.sim)):
        print('must provide one and only one of --sim or --infile')
        sys.exit(-1)

    ser = serial.Serial(args.port, 9600)
    sas = E4350(ser, args.address)
    sas.output_off()

    if args.infile:
        with open(args.infile) as f:
            datlines = [line.strip().split(',') for line in f.readlines()
                        if len(line.strip()) and not line.startswith('#')]
            ivcurve = [(float(v.strip()), float(i.strip())) for v,i in datlines]
        try:
            sas.pt_mode()
            sas.set_pts(ivcurve)
            sas.output_on()
        except Exception as e:
            sas.output_off()
            raise e
    else:
        try:
            sas.sim_mode()
            isc, vmp, imp, voc = [float(s) for s in args.sim.split(',')]
            sas.sim_pts(isc, vmp, imp, voc)
            sas.output_on()
        except Exception as e:
            sas.output_off()
            raise e

    while True:
        try:
            dat = sas.get_telem()
            print('{}: {:.3f}V {:.3f}A'.format(time.time(), dat['v'], dat['i']))
            time.sleep(args.period)
        except KeyboardInterrupt as e:
            sas.output_off()
            break
        except Exception as e:
            sas.output_off()
            raise e

