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

import cProfile

DEBUG = True

# ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
ADDIN_NAME = "DEV TOOLS"
COMPANY_NAME = "Autodesk"

# Name for a directory in user home to store data
user_dir_name = f'{ADDIN_NAME}'

# Design Workspace
design_workspace = 'FusionSolidEnvironment'

# Tabs
design_tab_id = f'{ADDIN_NAME}_design_tab'
design_tab_name = f'{ADDIN_NAME}'

# Panels
attributes_panel_name = 'ATTRIBUTES'
attributes_panel_id = f'{ADDIN_NAME}_attributes_panel'
attributes_panel_after = ''

data_panel_name = 'DATA'
data_panel_id = f'{ADDIN_NAME}_data_panel'
data_panel_after = attributes_panel_id

info_panel_name = 'INFO'
info_panel_id = f'{ADDIN_NAME}_dev_panel'
info_panel_after = data_panel_id

test_panel_name = 'TEST'
test_panel_id = f'{ADDIN_NAME}_test_panel'
test_panel_after = info_panel_id

addins_panel_name = 'ADD-INS'
addins_panel_id = f'{ADDIN_NAME}_addins_panel'
addins_panel_after = test_panel_id


help_panel_name = 'HELP'
help_panel_id = f'{ADDIN_NAME}_help_panel'
help_panel_after = addins_panel_id

# Palettes
ui_palette_name = 'Fusion 360 Dev Tools - User Interface Details'
ui_palette_id = f'{ADDIN_NAME}_ui_palette'

api_palette_name = 'Fusion 360 Dev Tools - API Explorer'
api_palette_id = f'{ADDIN_NAME}_api_palette'

appearance_palette_name = 'Fusion 360 Dev Tools - Appearance Explorer'
appearance_palette_id = f'{ADDIN_NAME}_appearance_palette'

command_stream_palette_name = 'Fusion 360 Dev Tools - Command Stream'
command_stream_palette_id = f'{ADDIN_NAME}_command_stream_palette'

# Reference for use in some commands
all_workspace_names = [
    'FusionSolidEnvironment', 'GenerativeEnvironment', 'PCBEnvironment', 'PCB3DEnvironment', 'Package3DEnvironment',
    'FusionRenderEnvironment', 'Publisher3DEnvironment', 'SimulationEnvironment', 'CAMEnvironment', 'DebugEnvironment',
    'FusionDocumentationEnvironment', 'ElectronEmptyLbrEnvironment', 'ElectronDeviceEnvironment',
    'ElectronFootprintEnvironment', 'ElectronSymbolEnvironment', 'ElectronPackageEnvironment'
]

# Testing
IS_RECORDING = False
PROFILER = None
