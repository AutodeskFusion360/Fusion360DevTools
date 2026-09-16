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

"""Turns a cProfile capture into the data the results palette renders.

A capture is snapshotted once, when profiling stops, and everything after that reads
the snapshot.  pstats.Stats() empties the profiler it is built from, so consulting the
live profiler more than once is not reliable.
"""

import csv
import datetime
import io
import json
import marshal
import os
import pstats
import sys

# How many captures to keep so they can be compared against each other.
HISTORY_LIMIT = 8

# A long capture can hold thousands of functions, which makes for a payload the palette
# has no use for: the tail is all sub-microsecond rows.  The cut only affects what the
# palette is sent; text reports and exports still use the whole capture.
MAX_PALETTE_FUNCTIONS = 1500

# Captures made this session, newest last.
captures = []

# Never reused, so a capture id stays unique even after the history is trimmed.
_capture_count = 0

# Where the add-in itself lives, used to tell its own overhead apart from the code
# being measured.  report.py is <add-in>/commands/performance/report.py.
ADDIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Category ids are also palette color slots, so the order here is the legend order.
CATEGORIES = [
    ('your_code', 'Your code'),
    ('fusion_api', 'Fusion API'),
    ('adsk_python', 'adsk wrappers'),
    ('python', 'Python'),
    ('imports', 'Imports'),
    ('dev_tools', 'Dev Tools'),
]


def category_of(file_name: str, func_name: str) -> str:
    """Buckets a profiled function by the kind of code it is."""
    # Built-in and C functions are recorded with '~' as their file name.
    if file_name == '~':
        if 'adsk.' in func_name:
            return 'fusion_api'
        return 'python'

    if file_name.startswith('<'):
        # <frozen importlib._bootstrap> and friends, i.e. the cost of importing.
        if 'importlib' in file_name:
            return 'imports'
        return 'python'

    normalized = file_name.replace('\\', '/')

    # The Fusion API's own Python modules, e.g. .../Api/Python/packages/adsk/fusion.py.
    if '/api/python/packages/adsk/' in normalized.lower():
        return 'adsk_python'

    if normalized.startswith(ADDIN_DIR.replace('\\', '/')):
        return 'dev_tools'

    if normalized.startswith(sys.prefix.replace('\\', '/')) or '/lib/python3' in normalized:
        return 'python'

    return 'your_code'


def module_name(file_name: str) -> str:
    """A short, readable name for the file a function lives in."""
    if file_name == '~':
        return 'built-in'
    if file_name.startswith('<'):
        return file_name.strip('<>')

    base_name = os.path.basename(file_name)
    if base_name.startswith('__init__.'):
        # Every package has one, so keep the directory that tells them apart.
        return os.path.join(os.path.basename(os.path.dirname(file_name)), base_name)
    return base_name


# The profiler's clock is nowhere near nanosecond accurate, and full float repr makes
# the palette payload several times larger than it needs to be.
def _time(value: float) -> float:
    return round(value, 9)


def _percent(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100, 2)


def take_snapshot(profiler, label: str = None) -> dict:
    """Builds a capture from a profiler and adds it to the session history.

    Raises a TypeError, from pstats, when the capture recorded no calls at all.
    """
    global _capture_count

    stats = pstats.Stats(profiler)
    stats.calc_callees()

    # Stable ids let the palette reference functions without sending tuples around.
    ids = {key: f'f{index}' for index, key in enumerate(stats.stats.keys())}

    total_time = stats.total_tt
    functions = []
    category_totals = {category_id: {'tottime': 0.0, 'count': 0} for category_id, _ in CATEGORIES}

    for key, (primitive_calls, calls, tottime, cumtime, callers) in stats.stats.items():
        file_name, line_number, func_name = key
        category = category_of(file_name, func_name)
        category_totals[category]['tottime'] += tottime
        category_totals[category]['count'] += 1

        functions.append({
            'id': ids[key],
            'name': func_name,
            'file': file_name,
            'module': module_name(file_name),
            'line': line_number,
            'category': category,
            'calls': calls,
            'primitive_calls': primitive_calls,
            'is_recursive': calls != primitive_calls,
            'tottime': _time(tottime),
            'cumtime': _time(cumtime),
            'percall_tottime': _time(tottime / calls) if calls else 0.0,
            'percall_cumtime': _time(cumtime / primitive_calls) if primitive_calls else 0.0,
            'tottime_pct': _percent(tottime, total_time),
            'cumtime_pct': _percent(cumtime, total_time),
            'callers': _edges(callers, ids),
            'callees': _edges(stats.all_callees.get(key, {}), ids),
        })

    # Roots are the functions nothing else called, which is where the call tree starts.
    roots = [function for function in functions if not function['callers']]
    roots.sort(key=lambda function: -function['cumtime'])

    _capture_count += 1
    capture = {
        'id': f'capture_{_capture_count}',
        'label': label or f'Capture {_capture_count}',
        'created': datetime.datetime.now().strftime('%H:%M:%S'),
        'total_time': _time(total_time),
        'total_calls': stats.total_calls,
        'primitive_calls': stats.prim_calls,
        'function_count': len(functions),
        'categories': [
            {
                'id': category_id,
                'name': name,
                'tottime': _time(category_totals[category_id]['tottime']),
                'tottime_pct': _percent(category_totals[category_id]['tottime'], total_time),
                'count': category_totals[category_id]['count'],
            }
            for category_id, name in CATEGORIES
        ],
        'functions': functions,
        'roots': [function['id'] for function in roots],
    }

    # Kept out of the palette payload, this is what gets written by a .prof export.
    capture['_raw_stats'] = stats.stats

    captures.append(capture)
    del captures[:-HISTORY_LIMIT]
    return capture


def _edges(edge_stats: dict, ids: dict) -> list:
    """Converts a pstats callers/callees mapping into rows the palette can use."""
    edges = []
    for key, value in edge_stats.items():
        edge_id = ids.get(key)
        if edge_id is None:
            continue
        # A caller/callee entry is (total calls, primitive calls, tottime, cumtime) for
        # this edge only, so it shows what that one call path contributed.
        calls, primitive_calls, tottime, cumtime = value if isinstance(value, tuple) else (value, value, 0.0, 0.0)
        edges.append({
            'id': edge_id,
            'calls': calls,
            'primitive_calls': primitive_calls,
            'tottime': _time(tottime),
            'cumtime': _time(cumtime),
        })
    edges.sort(key=lambda edge: -edge['cumtime'])
    return edges


def capture_by_id(capture_id: str):
    for capture in captures:
        if capture['id'] == capture_id:
            return capture
    return None


def palette_payload(capture: dict) -> dict:
    """The capture as the palette sees it: no private keys, and not unboundedly large."""
    payload = {key: value for key, value in capture.items() if not key.startswith('_')}

    functions = payload['functions']
    if len(functions) > MAX_PALETTE_FUNCTIONS:
        kept = sorted(functions, key=lambda function: -function['cumtime'])[:MAX_PALETTE_FUNCTIONS]
        kept_ids = {function['id'] for function in kept}
        payload['functions'] = kept
        payload['roots'] = [root for root in payload['roots'] if root in kept_ids]
        payload['truncated'] = len(functions) - len(kept)
    else:
        payload['truncated'] = 0

    return payload


def history() -> list:
    """Summaries of every capture this session, newest first."""
    return [
        {
            'id': capture['id'],
            'label': capture['label'],
            'created': capture['created'],
            'total_time': capture['total_time'],
            'total_calls': capture['total_calls'],
            'function_count': capture['function_count'],
        }
        for capture in reversed(captures)
    ]


def compare(before_id: str, after_id: str) -> dict:
    """Matches two captures function by function and reports what moved."""
    before = capture_by_id(before_id)
    after = capture_by_id(after_id)
    if before is None or after is None:
        return {}

    def index(capture):
        return {(f['file'], f['line'], f['name']): f for f in capture['functions']}

    before_index = index(before)
    after_index = index(after)

    rows = []
    for key in set(before_index) | set(after_index):
        before_function = before_index.get(key)
        after_function = after_index.get(key)
        reference = after_function or before_function

        before_tottime = before_function['tottime'] if before_function else 0.0
        after_tottime = after_function['tottime'] if after_function else 0.0
        before_cumtime = before_function['cumtime'] if before_function else 0.0
        after_cumtime = after_function['cumtime'] if after_function else 0.0

        if before_function is None:
            state = 'added'
        elif after_function is None:
            state = 'removed'
        else:
            state = 'changed'

        rows.append({
            'name': reference['name'],
            'module': reference['module'],
            'file': reference['file'],
            'line': reference['line'],
            'category': reference['category'],
            'state': state,
            'before_calls': before_function['calls'] if before_function else 0,
            'after_calls': after_function['calls'] if after_function else 0,
            'before_tottime': before_tottime,
            'after_tottime': after_tottime,
            'delta_tottime': after_tottime - before_tottime,
            'before_cumtime': before_cumtime,
            'after_cumtime': after_cumtime,
            'delta_cumtime': after_cumtime - before_cumtime,
        })

    rows.sort(key=lambda row: -abs(row['delta_cumtime']))

    return {
        'before': {'id': before['id'], 'label': before['label'], 'total_time': before['total_time']},
        'after': {'id': after['id'], 'label': after['label'], 'total_time': after['total_time']},
        'delta_total_time': after['total_time'] - before['total_time'],
        'delta_total_calls': after['total_calls'] - before['total_calls'],
        'rows': rows,
    }


def as_text(capture: dict, sort_by: str = 'cumtime', limit: int = 20, strip_dirs: bool = True) -> str:
    """The classic pstats text report, for the TEXT COMMANDS palette and the clipboard."""
    stream = io.StringIO()
    stats = pstats.Stats(stream=stream)
    stats.stats = dict(capture['_raw_stats'])
    stats.files = []
    stats.top_level = set()
    stats.get_top_level_stats()

    if strip_dirs:
        stats.strip_dirs()
    stats.sort_stats(sort_by)
    if limit > 0:
        stats.print_stats(limit)
    else:
        stats.print_stats()
    return stream.getvalue()


def export(capture: dict, file_path: str, export_format: str) -> str:
    """Writes a capture to disk as .prof, .csv or .json.  Returns the path written."""
    if export_format == 'prof':
        with open(file_path, 'wb') as output_file:
            # The same format cProfile.dump_stats writes, so snakeviz and tuna can read it.
            marshal.dump(capture['_raw_stats'], output_file)

    elif export_format == 'csv':
        columns = ['name', 'module', 'file', 'line', 'category', 'calls', 'primitive_calls',
                   'tottime', 'percall_tottime', 'cumtime', 'percall_cumtime',
                   'tottime_pct', 'cumtime_pct']
        with open(file_path, 'w', newline='') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            for function in sorted(capture['functions'], key=lambda f: -f['cumtime']):
                writer.writerow(function)

    elif export_format == 'json':
        with open(file_path, 'w') as output_file:
            json.dump(palette_payload(capture), output_file, indent=2)

    else:
        raise ValueError(f'Unknown export format: {export_format}')

    return file_path
