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

"""The performance results palette and the messages it exchanges with its HTML."""

import json
import os
import webbrowser

import adsk.core

from . import report
from .profile_utils import show_text_palette
from ... import config
from ...lib import fusion360utils as futil

app = adsk.core.Application.get()
ui = app.userInterface

PALETTE_ID = config.performance_palette_id
PALETTE_NAME = config.performance_palette_name
PALETTE_URL = './commands/performance/resources/html/index.html'
PALETTE_DOCKING = adsk.core.PaletteDockingStates.PaletteDockStateRight

# Holds references to the palette's event handlers.
palette_handlers = []

# Remembered between captures so the palette opens the way it was left.
view_options = {
    'tab': 'hotspots',
    'sort': 'cumtime',
    'descending': True,
    'limit': 20,
    'search': '',
    'strip_dirs': True,
    'hide_imports': True,
    'hide_python': False,
    'editor': 'vscode',
    'theme': 'auto',
}

# The capture the palette is showing.
active_capture_id = None

# The palette offers sort fields pstats does not know about, so the text report maps
# them back to the nearest key pstats accepts.
TEXT_SORT_KEYS = {
    'cumtime': 'cumtime',
    'tottime': 'tottime',
    'calls': 'calls',
    'pcalls': 'pcalls',
    'percall_cumtime': 'cumtime',
    'percall_tottime': 'tottime',
    'name': 'nfl',
    'module': 'module',
}

EXPORT_FORMATS = {
    'prof': ('Profile data for snakeviz or tuna (*.prof)', 'prof'),
    'csv': ('Comma separated values (*.csv)', 'csv'),
    'json': ('Capture data (*.json)', 'json'),
}


def fusion_theme() -> str:
    """'dark' or 'light', following the theme Fusion is currently using."""
    try:
        active_theme = app.preferences.generalPreferences.activeUserInterfaceTheme
        themes = adsk.core.UserInterfaceThemes
        for name in dir(themes):
            if name.endswith('UserInterfaceTheme') and getattr(themes, name) == active_theme:
                return 'dark' if 'Dark' in name else 'light'
    except Exception:
        futil.log('Could not read the Fusion UI theme, defaulting the palette to light')
    return 'light'


def show(capture: dict):
    """Opens the palette on a capture, creating it the first time."""
    global active_capture_id
    active_capture_id = capture['id']

    palettes = ui.palettes
    palette = palettes.itemById(PALETTE_ID)
    if palette is None:
        palette = palettes.add(
            id=PALETTE_ID,
            name=PALETTE_NAME,
            htmlFileURL=PALETTE_URL,
            isVisible=True,
            showCloseButton=True,
            isResizable=True,
            width=900,
            height=700,
            useNewWebBrowser=True
        )
        futil.add_handler(palette.closed, palette_closed, local_handlers=palette_handlers)
        futil.add_handler(palette.navigatingURL, palette_navigating, local_handlers=palette_handlers)
        futil.add_handler(palette.incomingFromHTML, palette_incoming, local_handlers=palette_handlers)

    if palette.dockingState == adsk.core.PaletteDockingStates.PaletteDockStateFloating:
        palette.dockingState = PALETTE_DOCKING

    palette.isVisible = True

    # An already open palette needs telling; a new one asks for the state itself once
    # its page has loaded.
    palette.sendInfoToHTML('capture_added', json.dumps({'id': capture['id']}))


def close():
    """Removes the palette, used when the add-in stops."""
    global palette_handlers
    palette_handlers = []

    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()


def palette_closed(args: adsk.core.UserInterfaceGeneralEventArgs):
    close()


def palette_navigating(args: adsk.core.NavigationEventArgs):
    # Let real links open in the user's browser rather than inside the palette.
    if args.navigationURL.startswith('http'):
        args.launchExternally = True


def palette_incoming(html_args: adsk.core.HTMLEventArgs):
    """Answers the requests the palette's JavaScript makes."""
    action = html_args.action
    data = json.loads(html_args.data) if html_args.data else {}
    response = {}

    if action == 'get_state':
        response = {
            'theme': fusion_theme(),
            'options': view_options,
            'history': report.history(),
            'active_capture_id': active_capture_id,
            'categories': [{'id': category_id, 'name': name} for category_id, name in report.CATEGORIES],
        }

    elif action == 'get_capture':
        capture = report.capture_by_id(data.get('id') or active_capture_id)
        response = report.palette_payload(capture) if capture else {}

    elif action == 'get_diff':
        response = report.compare(data.get('before'), data.get('after'))

    elif action == 'set_options':
        view_options.update(data)

    elif action == 'open_source':
        response = open_in_editor(data.get('file', ''), data.get('line', 0))

    elif action == 'export_capture':
        response = export_capture(data.get('id'), data.get('format', 'prof'))

    elif action == 'log_text':
        response = log_as_text(data.get('id'))

    else:
        futil.log(f'Performance palette received an unknown action: {action}')

    html_args.returnData = json.dumps(response)


def project_name_for(file_name: str) -> str:
    """The JetBrains URL scheme wants a project name, so look for the .idea folder."""
    directory = os.path.dirname(file_name)
    while True:
        if os.path.isdir(os.path.join(directory, '.idea')):
            return os.path.basename(directory)
        parent = os.path.dirname(directory)
        if parent == directory:
            return os.path.basename(os.path.dirname(file_name))
        directory = parent


def open_in_editor(file_name: str, line_number: int) -> dict:
    """Opens a profiled function's source at its line, in the configured editor."""
    if not file_name or file_name == '~' or file_name.startswith('<'):
        # Built-ins and frozen modules have no file on disk to open.
        return {'ok': False, 'reason': 'This function has no source file to open.'}

    if not os.path.exists(file_name):
        return {'ok': False, 'reason': f'That file is not on disk any more: {file_name}', 'path': file_name}

    # Editor URLs want forward slashes and exactly one after the scheme.
    path = '/' + file_name.replace('\\', '/').lstrip('/')

    if view_options.get('editor') == 'pycharm':
        url = (f'jetbrains://pycharm/navigate/reference'
               f'?project={project_name_for(file_name)}&path={path}:{line_number}')
    else:
        url = f'vscode://file{path}:{line_number}'

    futil.log(f'Opening source: {url}')
    try:
        webbrowser.open(url)
    except Exception:
        return {'ok': False, 'reason': 'Could not hand the file to the editor.', 'path': file_name}

    return {'ok': True, 'url': url, 'path': f'{file_name}:{line_number}'}


def export_capture(capture_id: str, export_format: str) -> dict:
    """Asks where to save, then writes the capture in the requested format."""
    capture = report.capture_by_id(capture_id or active_capture_id)
    if capture is None:
        return {'ok': False, 'reason': 'That capture is no longer available.'}

    if export_format not in EXPORT_FORMATS:
        return {'ok': False, 'reason': f'Unknown export format: {export_format}'}

    description, extension = EXPORT_FORMATS[export_format]
    safe_label = capture['label'].replace(' ', '_').lower()

    file_dialog = ui.createFileDialog()
    file_dialog.title = f'Save {capture["label"]}'
    file_dialog.filter = description
    file_dialog.initialFilename = f'{safe_label}.{extension}'

    if file_dialog.showSave() != adsk.core.DialogResults.DialogOK:
        return {'ok': False, 'cancelled': True}

    path = report.export(capture, file_dialog.filename, export_format)
    futil.log(f'Wrote performance capture to {path}', force_console=True)
    return {'ok': True, 'path': path}


def log_as_text(capture_id: str) -> dict:
    """Writes the classic pstats table to the TEXT COMMANDS palette."""
    capture = report.capture_by_id(capture_id or active_capture_id)
    if capture is None:
        return {'ok': False, 'reason': 'That capture is no longer available.'}

    show_text_palette()

    text = report.as_text(
        capture,
        sort_by=TEXT_SORT_KEYS.get(view_options.get('sort'), 'cumtime'),
        limit=view_options.get('limit', 20),
        strip_dirs=view_options.get('strip_dirs', True),
    )
    futil.log(f'\n*************{capture["label"]}************\n', force_console=True)
    futil.log(text, force_console=True)
    return {'ok': True}
