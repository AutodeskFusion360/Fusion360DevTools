# Author-Patrick Rainsberry
# Description-Collection of useful utilities to aid in the development of a Fusion 360 Add-in.

#  Copyright 2022 by Autodesk, Inc.
#  Permission to use, copy, modify, and distribute this software in object code form
#  for any purpose and without fee is hereby granted, provided that the above copyright
#  notice appears in all copies and that both that copyright notice and the limited
#  warranty and restricted rights notice below appear in all supporting documentation.
#
#  AUTODESK PROVIDES THIS PROGRAM "AS IS" AND WITH ALL FAULTS. AUTODESK SPECIFICALLY
#  DISCLAIMS ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR USE.
#  AUTODESK, INC. DOES NOT WARRANT THAT THE OPERATION OF THE PROGRAM WILL BE
#  UNINTERRUPTED OR ERROR FREE.

from . import commands
from .lib import fusion360utils as futil


def run(context):
    try:
        commands.start()
    except:
        futil.handle_error('run')


def stop(context):
    try:
        futil.clear_handlers()
        commands.stop()

    except:
        futil.handle_error('stop')
