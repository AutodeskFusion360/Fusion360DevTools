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
attributes_panel_name = 'Attributes'
attributes_panel_id = f'{ADDIN_NAME}_attributes_panel'
attributes_panel_after = ''

data_panel_name = 'Data'
data_panel_id = f'{ADDIN_NAME}_data_panel'
data_panel_after = attributes_panel_id

dev_panel_name = 'API Tools'
dev_panel_id = f'{ADDIN_NAME}_dev_panel'
dev_panel_after = data_panel_id

# Palettes
ui_palette_name = 'User Interface Details'
ui_palette_id = f'{ADDIN_NAME}_ui_palette'

api_palette_name = 'API Explorer'
api_palette_id = f'{ADDIN_NAME}_api_palette'

appearance_palette_name = 'Appearance Explorer'
appearance_palette_id = f'{ADDIN_NAME}_appearance_palette'

# Reference for use in some commands
all_workspace_names = [
    'FusionSolidEnvironment', 'GenerativeEnvironment', 'PCBEnvironment', 'PCB3DEnvironment', 'Package3DEnvironment',
    'FusionRenderEnvironment', 'Publisher3DEnvironment', 'SimulationEnvironment', 'CAMEnvironment', 'DebugEnvironment',
    'FusionDocumentationEnvironment', 'ElectronEmptyLbrEnvironment', 'ElectronDeviceEnvironment',
    'ElectronFootprintEnvironment', 'ElectronSymbolEnvironment', 'ElectronPackageEnvironment'
]
