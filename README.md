# Solar Cell and Battery Scripts

Here are a small number of scripts used for working with batteries and solar cells in spacecraft design.

## notebooks/
`sys design.ipynb` is a quick example of sizing battery packs vs solar arrays.
`Orbiter Power.ipynb` is a bit more look at a notional orbiter specifically.
`Solar Cells.ipynb` is an in-depth look at predicting cell and array performance with only spec sheet info.
`TVC Sizing.ipynb` is an exploration of the design space for powering a fairly demanding subsystem.

## scripts/
`e4350.py` allows control of some features of an HP (Agilent) E4350 Solar Array Simulator, using a Prologix USB to GPIB adapter.
`talke4350.py` will let you scroll out messages on an E4350. Because it's important to still have fun.
`pvcells.py` is more work for predicting and simulating PV cell performance.

## About
Written by patrickyeon while working for the Open Lunar Foundation. Published in the hopes that it saves someone a week of work someday.

This software is MIT Licensed
