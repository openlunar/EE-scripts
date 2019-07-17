#!/usr/bin/python3
import argparse
import math
import re
import serial
import sys
import time

from pvcells import PVCell

class E4350Exception(Exception):
    pass

class E4350:
    def __init__(self, ser, addr, debug=False, fake=False, cautious=False):
        self.cmax, self.vmax = 5.25, 121. # for the E4350A-J06
        self.ser, self.addr = ser, addr
        self.debug, self.fake, self.cautious = debug, fake, cautious
        if fake:
            return
        self.send('++mode 1')
        self.send('++addr {}'.format(addr))
        resp = self.send('*IDN?')
        idn = resp.split(',')
        if len(idn) < 2 or idn[:2] != ['HEWLETT-PACKARD', 'E4350A']:
            raise E4350Exception('does not seem to be an E4350A: ' + str(resp))

    def send(self, msg):
        if self.fake:
            if self.debug:
                print(msg)
            return ''
        # writes the message, terminates it with a newline,
        #  reads and returns a response
        self.ser.write(bytes(msg + '\n', 'ascii'))
        if self.debug:
            print(msg)
        time.sleep(0.3)
        retval = self.ser.read_all().decode()
        if self.debug:
            print('>> ' + retval)
        if self.cautious:
            maybe_err = ''
            while maybe_err == '':
                self.ser.write(bytes('SYST:ERR?\n', 'ascii'))
                time.sleep(0.3)
                maybe_err = self.ser.read_all().decode()
            non_err = ('+0,"No error"\n',
                       '-420,"Query UNTERMINATED"\n')
            if maybe_err not in non_err:
                raise E4350Exception(maybe_err)
        return retval

    def output_off(self):
        self.send('OUTP OFF')

    def output_on(self):
        self.send('OUTP ON')

    def pt_mode(self):
        self.send('SOUR:CURR:MODE TABL')

    def set_protection(self, voltage=None, current=None):
        if voltage is not None:
            self.send('SOUR:VOLT:PROT {}'.format(min(voltage, self.vmax)))
        if current is not None:
            self.send('SOUR:CURR:PROT {}'.format(min(current, self.cmax)))

    def set_pts(self, ptlist):
        # ptlist is [(float, float)...] of v,i points
        self.send('MEM:TABL:SEL foobar') # need to de-select frompython
        try:
            self.send('MEM:DEL:NAME frompython')
        except E4350Exception as e:
            if not str(e).startswith('-141'):
                # -141 would be "table does not exist", which is fine
                raise e
        self.send('MEM:TABL:SEL frompython')
        # make sure the list is sorted, and there's no repeat of voltage points
        ptlist.sort(key=lambda vi: vi[0])
        trimpts, vpt, n, acc = [], int(100 * ptlist[0][0]), 1, ptlist[0][1]
        for v,i in ptlist[1:]:
            v = int(100 * v)
            if v != vpt:
                trimpts.append((vpt * 0.01, acc / n))
                vpt, n, acc = v, 0, 0
            n += 1
            acc += i
        trimpts.append((vpt * 0.01, acc / n))

        # limitation is that we need to do <=100 pts at a time
        for n in range(0, math.ceil(len(trimpts) / 100)):
            pts = trimpts[n * 100 : (n + 1) * 100]
            self.send('MEM:TABL:VOLT ' + ','.join(['{:.3f}'.format(v)
                                                   for v,i in pts]))
            self.send('MEM:TABL:CURR ' + ','.join(['{:.3f}'.format(i)
                                                   for v,i in pts]))
        self.send('CURR:TABL:NAME frompython')

    def sim_mode(self):
        self.send('SOUR:CURR:MODE SAS')
    
    def sim_pts(self, isc, vmp, imp, voc):
        self.send('SOUR:CURR:SAS:ISC {}'.format(isc))
        self.send('SOUR:CURR:SAS:IMP {}'.format(imp))
        self.send('SOUR:VOLT:SAS:VOC {}'.format(voc))
        self.send('SOUR:VOLT:SAS:VMP {}'.format(vmp))

    def get_telem(self):
        if self.fake:
            self.send('MEAS:VOLT?')
            self.send('MEAS:CURR?')
            return {'v': 3.1415, 'i': 2.71828}
        # returns {'v': float, 'i': float} volts and amps
        return {'v': float(self.send('MEAS:VOLT?')),
                'i': float(self.send('MEAS:CURR?'))
               }
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-n', '--nohardware', action='store_true')
    parser.add_argument('-p', '--port', help='prologix port', required=True)
    parser.add_argument('-a', '--address', help='E4350A address on GPIB bus',
                        required=True)
    parser.add_argument('-f', '--infile',
                        help='IV curve input file ("V_in_Volts,I_in_A\\n")')
    parser.add_argument('--calc', help=('calculate and use an IV curve as '
                                        '--calc=Isc,Vmp,Imp,Voc,a'))
    parser.add_argument('--sim', help=('Simulator settings as '
                                       '--sim=Isc,Vmp,Imp,Voc'))
    parser.add_argument('--multiple', help='array format of style 5s2p',
                        default='1s1p')
    parser.add_argument('-t', '--period', type=float, default=5,
                        help='logging period (seconds)')
    args = parser.parse_args()
    mutex_args = (args.infile, args.sim, args.calc)
    if len([a for a in mutex_args if a is not None]) != 1:
        print('must provide one and only one of --sim or --infile or --calc')
        sys.exit(-1)

    if args.nohardware:
        sas = E4350(None, args.address, debug=args.verbose, fake=True)
    else:
        ser = serial.Serial(args.port, 9600)
        sas = E4350(ser, args.address, debug=args.verbose, cautious=True)
    sas.output_off()

    _, ser, _, par = re.match('((\\d*)s)?((\\d*)p)?', args.multiple).groups()
    if ser is None and par is None:
        raise Exception('argument to --multiple must be form NsMp for N cells '
                        'in series, M in parallel')
    ser = int(ser) if ser is not None else 1
    par = int(par) if par is not None else 1

    if args.sim:
        isc, vmp, imp, voc = [float(s) for s in args.sim.split(',')]
        try:
            sas.sim_mode()
            sas.sim_pts(isc * par, vmp * ser, imp * par, voc * ser)
            sas.set_protection(voc * ser * 1.1, isc * par * 1.1)
            sas.output_on()
        except Exception as e:
            sas.output_off()
            raise e
    else:
        if args.infile:
            with open(args.infile) as f:
                datlines = [line.strip().split(',') for line in f.readlines()
                            if len(line.strip()) and not line.startswith('#')]
                iv = [(float(v.strip()), float(i.strip())) for v,i in datlines]
        else:
            # calc mode
            isc, vmp, imp, voc, a = [float(s) for s in args.calc.split(',')]
            pvcell = PVCell(voc, vmp, imp, isc, a)
            data = pvcell.iv_curve()

            # This is a stupid thing because everything is horrible
            def sigint(sig, frame):
                raise KeyboardInterrupt()
            import signal
            signal.signal(signal.SIGINT, sigint)

            iv = list(zip(data['vout'], data['aout']))
            while len(iv) > 4000:
                # limit on table size in e4350 memory
                # this may look like throwing away a lot of data, but the worst
                # case still gives us 2000 points.
                iv = [iv[n] for n in range(0, len(iv), 2)]
        ivcurve = [(v * ser, i * par) for v,i in iv]

        try:
            sas.send('CURR:MODE FIX')
            sas.set_pts(ivcurve)
            sas.pt_mode()
            sas.set_protection(max([v for v,i in ivcurve]) * 1.1,
                               max([i for v,i in ivcurve]) * 1.1)
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
            print('')
            break
        except Exception as e:
            sas.output_off()
            raise e
