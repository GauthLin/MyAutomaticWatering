#!/usr/bin/python
# -*- coding: utf-8 -*-

GPIO = {
    'btn': {
        'right': ("in", 29),
        'left': ("in", 31),
        'bottom': ("in", 33),
        'up': ("in", 35),
        'emergency': ("in", 37)
    },
    'led': {
        'green': ("out", 36),
        'red': ("out", 38)
    },
    'relay': ('out', 40)
}

"""
==============
LCD param
=============
pin_rs=15
pin_rw=None
pin_e=16
pins_data=[
    21 => D4,
    22 => D5,
    23 => D6,
    24 => D7
]
"""