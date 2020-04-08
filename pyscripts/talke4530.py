#!/usr/bin/python3
import argparse
import serial
import time
import e4350

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', required=True)
    parser.add_argument('-a', '--address', required=True)
    parser.add_argument('-m', '--message')
    parser.add_argument('-s', '--scroll', action='store_true')
    args = parser.parse_args()

    ser = serial.Serial(args.port, 9600)
    sas = e4350.E4350(ser, args.address, debug=True, cautious=False)
    if args.message:
        sas.set_display(args.message)
        if args.scroll:
            i = 1
            while True:
                sas.set_display(args.message[i:] + '  ' + args.message)
                i = (i + 1) % len(args.message)
    else:
        sas.set_display()
