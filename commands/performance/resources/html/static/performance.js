/*
 * Copyright 2022 by Autodesk, Inc.
 * Permission to use, copy, modify, and distribute this software in object code form
 * for any purpose and without fee is hereby granted, provided that the above copyright
 * notice appears in all copies and that both that copyright notice and the limited
 * warranty and restricted rights notice below appear in all supporting documentation.
 *
 * AUTODESK PROVIDES THIS PROGRAM "AS IS" AND WITH ALL FAULTS. AUTODESK SPECIFICALLY
 * DISCLAIMS ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR USE.
 * AUTODESK, INC. DOES NOT WARRANT THAT THE OPERATION OF THE PROGRAM WILL BE
 * UNINTERRUPTED OR ERROR FREE.
 */

/* Rendering and the Fusion bridge.  The calculations live in perf_model.js. */

(function () {
    const M = PerfModel;

    const state = {
        capture: null,
        history: [],
        categories: [],
        options: {},
        fusionTheme: 'light',
        selectedId: null,
        trail: [],              // function ids, for the detail breadcrumbs
        expanded: {},           // call tree, keyed by node path
        hiddenCategories: {},
        treeRoots: null,
        diff: null,
        visibleRows: []
    };

    // ------------------------------------------------------------------ bridge

    /*
     * The palette's browser injects the adsk object some time after the page has loaded,
     * so the first request has to wait for it instead of assuming it is there.  Without
     * the wait every request quietly took the fixture path and the palette came up empty.
     */
    const BRIDGE_TIMEOUT_MS = 10000;
    let bridgePromise = null;

    function whenBridgeReady() {
        if (bridgePromise) return bridgePromise;

        bridgePromise = new Promise(function (resolve) {
            if (window.adsk && window.adsk.fusionSendData) {
                resolve('fusion');
                return;
            }
            let waited = 0;
            const waiter = setInterval(function () {
                if (window.adsk && window.adsk.fusionSendData) {
                    clearInterval(waiter);
                    resolve('fusion');
                } else if ((waited += 100) >= BRIDGE_TIMEOUT_MS) {
                    // Not running inside a palette, so this is a browser preview.
                    clearInterval(waiter);
                    console.warn('No Fusion bridge after ' + BRIDGE_TIMEOUT_MS +
                        ' ms, falling back to static/fixture.json');
                    resolve('fixture');
                }
            }, 100);
        });
        return bridgePromise;
    }

    // Fusion resolves adsk.fusionSendData with whatever palette.py put in returnData.
    function send(action, data) {
        return whenBridgeReady().then(function (mode) {
            if (mode === 'fusion') {
                return adsk.fusionSendData(action, JSON.stringify(data || {}))
                    .then(function (raw) {
                        try {
                            return raw ? JSON.parse(raw) : {};
                        } catch (error) {
                            console.warn('Could not parse the response to ' + action, raw);
                            return {error: 'The add-in sent back something unreadable.'};
                        }
                    })
                    .catch(function (error) {
                        console.error('Request ' + action + ' failed', error);
                        return {error: 'The add-in did not answer the ' + action + ' request.'};
                    });
            }
            return fixtureRequest(action);
        });
    }

    // Outside Fusion, serve this folder over http with a capture saved as
    // static/fixture.json beside it to work on the palette without restarting the add-in.
    function fixtureRequest(action) {
        return fetch('static/fixture.json')
            .then(function (response) { return response.json(); })
            .then(function (fixture) {
                if (action === 'get_state') {
                    return {
                        theme: 'light',
                        options: {},
                        history: (fixture.dev_history || [{
                            id: fixture.id, label: fixture.label, created: fixture.created,
                            total_time: fixture.total_time, total_calls: fixture.total_calls,
                            function_count: fixture.function_count
                        }]),
                        active_capture_id: fixture.id,
                        categories: fixture.categories
                    };
                }
                if (action === 'get_capture') return fixture;
                if (action === 'get_diff') {
                    return fetch('static/fixture_diff.json').then(function (response) {
                        return response.json();
                    });
                }
                return {};
            })
            .catch(function () {
                return {error: 'No Fusion bridge and no static/fixture.json to fall back on.'};
            });
    }

    // Fusion pushes here when a new capture is taken while the palette is open.
    window.fusionJavaScriptHandler = {
        handle: function (action, raw) {
            try {
                if (action === 'capture_added') {
                    loadState();
                } else if (action === 'debugger') {
                    debugger;
                }
            } catch (error) {
                console.error('performance palette failed to handle ' + action, error);
            }
            return 'OK';
        }
    };

    // ------------------------------------------------------------------ helpers

    function $(id) {
        return document.getElementById(id);
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function clear(node) {
        while (node.firstChild) node.removeChild(node.firstChild);
    }

    function categoryColor(categoryId) {
        const value = getComputedStyle(document.documentElement.querySelector('.viz-root'))
            .getPropertyValue('--cat-' + categoryId);
        return (value || '').trim() || 'var(--accent)';
    }

    function categoryName(categoryId) {
        for (let i = 0; i < state.categories.length; i++) {
            if (state.categories[i].id === categoryId) return state.categories[i].name;
        }
        return categoryId;
    }

    function dot(categoryId) {
        const node = el('span', 'cat-dot');
        node.style.background = categoryColor(categoryId);
        node.title = categoryName(categoryId);
        return node;
    }

    // A label sitting inside a colored fill takes whichever of ink or white has the better
    // contrast against that fill, so it stays legible on every slot in both themes.
    function inkOn(color) {
        const match = color.match(/(\d+(\.\d+)?)/g);
        if (!match || match.length < 3) return '#ffffff';
        const channel = function (value) {
            const scaled = value / 255;
            return scaled <= 0.04045 ? scaled / 12.92 : Math.pow((scaled + 0.055) / 1.055, 2.4);
        };
        const luminance = 0.2126 * channel(+match[0]) + 0.7152 * channel(+match[1]) + 0.0722 * channel(+match[2]);
        const againstWhite = 1.05 / (luminance + 0.05);
        const againstInk = (luminance + 0.05) / (0.0074 + 0.05);
        return againstInk > againstWhite ? '#0b0b0b' : '#ffffff';
    }

    const measure = document.createElement('canvas').getContext('2d');

    function textWidth(text, font) {
        measure.font = font || '600 10px system-ui, -apple-system, sans-serif';
        return measure.measureText(text).width;
    }

    let toastTimer = null;

    function toast(message) {
        const node = $('toast');
        node.textContent = message;
        node.style.display = 'block';
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { node.style.display = 'none'; }, 4000);
    }

    const tooltip = {
        show: function (event, lines) {
            const node = $('tooltip');
            clear(node);
            node.appendChild(el('div', 'tooltip-title', lines[0]));
            for (let i = 1; i < lines.length; i++) {
                node.appendChild(el('div', 'tooltip-row', lines[i]));
            }
            node.style.display = 'block';
            const width = node.offsetWidth;
            const height = node.offsetHeight;
            let left = event.clientX + 12;
            let top = event.clientY + 14;
            if (left + width > window.innerWidth - 8) left = event.clientX - width - 12;
            if (top + height > window.innerHeight - 8) top = event.clientY - height - 14;
            node.style.left = Math.max(4, left) + 'px';
            node.style.top = Math.max(4, top) + 'px';
        },
        hide: function () {
            $('tooltip').style.display = 'none';
        }
    };

    function attachTooltip(node, linesFactory) {
        node.addEventListener('mousemove', function (event) { tooltip.show(event, linesFactory()); });
        node.addEventListener('mouseleave', tooltip.hide);
    }

    function barCell(percentage) {
        const cell = el('td', 'bar-cell');
        const track = el('div', 'bar-track');
        const fill = el('div', 'bar-fill');
        fill.style.width = percentage.toFixed(1) + '%';
        track.appendChild(fill);
        cell.appendChild(track);
        return cell;
    }

    function functionById(id) {
        if (!state.capture) return null;
        const functions = state.capture.functions;
        for (let i = 0; i < functions.length; i++) {
            if (functions[i].id === id) return functions[i];
        }
        return null;
    }

    // ------------------------------------------------------------------ options

    // The compare table is a reading list, not a ranking, so it gets a plain cap.
    const COMPARE_ROW_LIMIT = 200;

    const DEFAULT_OPTIONS = {
        tab: 'hotspots',
        sort: 'cumtime',
        descending: true,
        limit: 20,
        search: '',
        strip_dirs: true,
        hide_imports: true,
        hide_python: false,
        editor: 'vscode',
        theme: 'auto'
    };

    let persistTimer = null;

    function persistOptions() {
        if (persistTimer) clearTimeout(persistTimer);
        persistTimer = setTimeout(function () {
            send('set_options', state.options);
        }, 350);
    }

    function readOptionsFromControls() {
        state.options.search = $('search').value;
        state.options.sort = $('sort_select').value;
        state.options.limit = parseInt($('limit').value, 10) || 0;
        state.options.strip_dirs = $('strip_dirs').checked;
        state.options.hide_imports = $('hide_imports').checked;
        state.options.hide_python = $('hide_python').checked;
        state.options.editor = $('editor_select').value;
    }

    function writeControlsFromOptions() {
        $('search').value = state.options.search || '';
        $('sort_select').value = state.options.sort;
        $('limit').value = state.options.limit;
        $('strip_dirs').checked = !!state.options.strip_dirs;
        $('hide_imports').checked = !!state.options.hide_imports;
        $('hide_python').checked = !!state.options.hide_python;
        $('editor_select').value = state.options.editor || 'vscode';
    }

    function applyTheme() {
        const choice = state.options.theme || 'auto';
        const theme = choice === 'auto' ? state.fusionTheme : choice;
        document.documentElement.dataset.theme = theme;
        $('theme_toggle').textContent = theme === 'dark' ? 'Light' : 'Dark';
        $('theme_toggle').title = 'Switch to the ' + (theme === 'dark' ? 'light' : 'dark') + ' palette';
    }

    // ------------------------------------------------------------------ loading

    function setEmptyState(title, detail) {
        const panel = $('hotspot_empty');
        clear(panel);
        panel.appendChild(el('h2', null, title));
        panel.appendChild(el('div', null, detail));
        panel.style.display = 'flex';
        $('hotspot_table').style.display = 'none';
    }

    function loadState() {
        send('get_state').then(function (result) {
            if (result.error) {
                setEmptyState('Could not read the capture', result.error);
                return;
            }
            state.history = result.history || [];
            state.categories = result.categories || [];
            state.fusionTheme = result.theme || 'light';
            state.options = Object.assign({}, DEFAULT_OPTIONS, result.options || {});
            writeControlsFromOptions();
            applyTheme();
            renderCaptureSelect(result.active_capture_id);
            selectTab(state.options.tab || 'hotspots');
            if (result.active_capture_id) {
                loadCapture(result.active_capture_id);
            } else {
                setEmptyState('No capture yet',
                    'Run Start Performance Capture, use the commands you want to measure, '
                    + 'then run Stop Performance Capture.');
            }
        });
    }

    function loadCapture(captureId) {
        send('get_capture', {id: captureId}).then(function (capture) {
            if (!capture || !capture.functions) {
                setEmptyState('That capture is not available',
                    capture && capture.error
                        ? capture.error
                        : 'The add-in no longer has data for ' + captureId + '.');
                return;
            }
            state.capture = capture;
            state.selectedId = null;
            state.trail = [];
            state.expanded = {};
            state.treeRoots = null;
            $('capture_select').value = capture.id;
            renderAll();
        });
    }

    function renderCaptureSelect(activeId) {
        const select = $('capture_select');
        clear(select);
        state.history.forEach(function (item) {
            const option = el('option', null,
                item.label + ' · ' + M.seconds(item.total_time) + ' · ' + item.created);
            option.value = item.id;
            select.appendChild(option);
        });
        if (activeId) select.value = activeId;

        [['compare_before', 1], ['compare_after', 0]].forEach(function (pair) {
            const compareSelect = $(pair[0]);
            const previous = compareSelect.value;
            clear(compareSelect);
            state.history.forEach(function (item) {
                const option = el('option', null, item.label + ' · ' + M.seconds(item.total_time));
                option.value = item.id;
                compareSelect.appendChild(option);
            });
            if (previous && functionInHistory(previous)) {
                compareSelect.value = previous;
            } else if (state.history.length > pair[1]) {
                compareSelect.value = state.history[pair[1]].id;
            }
        });
    }

    function functionInHistory(captureId) {
        return state.history.some(function (item) { return item.id === captureId; });
    }

    // ------------------------------------------------------------------ rendering

    function renderAll() {
        renderHeader();
        renderSummary();
        renderActiveView();
    }

    function renderHeader() {
        const capture = state.capture;
        if (!capture) return;

        // The hero figure: total time, in the same sans as everything else.
        const total = M.seconds(capture.total_time).split(' ');
        $('hero_value').textContent = total[0];
        $('hero_label').textContent = 'Total time' + (total[1] ? ' (' + total[1] + ')' : '');

        $('kpi_calls').textContent = M.count(capture.total_calls);
        $('kpi_calls_note').textContent = capture.primitive_calls === capture.total_calls
            ? 'no recursion'
            : M.count(capture.primitive_calls) + ' primitive';

        $('kpi_functions').textContent = M.count(capture.function_count);
        $('kpi_functions_note').textContent = capture.created ? 'captured at ' + capture.created : '';

        const slowest = M.sortFunctions(capture.functions, 'tottime', true)[0];
        if (slowest) {
            $('kpi_slowest').textContent = M.seconds(slowest.tottime);
            $('kpi_slowest_note').textContent = slowest.name + ' · ' + M.percent(slowest.tottime_pct);
        }
    }

    function renderSummary() {
        const capture = state.capture;
        const bar = $('summary_bar');
        const legend = $('summary_legend');
        clear(bar);
        clear(legend);
        if (!capture) return;

        const categories = capture.categories.filter(function (category) { return category.tottime > 0; });
        const accounted = categories.reduce(function (sum, category) { return sum + category.tottime; }, 0);

        $('summary_note').textContent = M.seconds(accounted) + ' of self time across '
            + categories.length + ' kinds of code';

        const segments = [];
        categories.forEach(function (category) {
            const share = accounted > 0 ? (category.tottime / accounted) * 100 : 0;
            const segment = el('div', 'summary-segment');
            segment.style.flex = '0 0 ' + share.toFixed(2) + '%';
            segment.style.background = categoryColor(category.id);
            if (state.hiddenCategories[category.id]) segment.classList.add('dim');
            attachTooltip(segment, function () {
                return [
                    category.name,
                    M.seconds(category.tottime) + ' of self time · ' + M.percent(category.tottime_pct) + ' of the capture',
                    M.count(category.count) + (category.count === 1 ? ' function' : ' functions')
                ];
            });
            segment.addEventListener('click', function () { toggleCategory(category.id); });
            bar.appendChild(segment);
            segments.push({node: segment, category: category, share: share});

            // Legend always present, and it is what carries the values for the segments
            // too narrow to label.
            const item = el('li');
            if (state.hiddenCategories[category.id]) item.classList.add('off');
            const swatch = el('span', 'swatch');
            swatch.style.background = categoryColor(category.id);
            item.appendChild(swatch);
            item.appendChild(el('span', null, category.name));
            item.appendChild(el('span', 'legend-value', M.percent(category.tottime_pct)));
            item.appendChild(el('span', 'legend-time', M.seconds(category.tottime)));
            item.title = 'Click to show or hide this kind of code';
            item.addEventListener('click', function () { toggleCategory(category.id); });
            legend.appendChild(item);
        });

        // Label a segment only once it is measured wide enough to hold the text.
        requestAnimationFrame(function () {
            segments.forEach(function (entry) {
                const text = M.percent(entry.category.tottime_pct);
                const width = entry.node.clientWidth;
                if (width >= textWidth(text) + 14) {
                    const label = el('span', 'inline-label', text);
                    label.style.color = inkOn(getComputedStyle(entry.node).backgroundColor);
                    entry.node.appendChild(label);
                }
            });
        });
    }

    function toggleCategory(categoryId) {
        if (state.hiddenCategories[categoryId]) {
            delete state.hiddenCategories[categoryId];
        } else {
            state.hiddenCategories[categoryId] = true;
        }
        state.treeRoots = null;
        renderSummary();
        renderActiveView();
    }

    function filterOptions() {
        return {
            search: state.options.search,
            hide_imports: state.options.hide_imports,
            hide_python: state.options.hide_python,
            hidden_categories: Object.keys(state.hiddenCategories)
        };
    }

    // ------------------------------------------------------------------ hot spots

    function renderHotspots() {
        const body = $('hotspot_body');
        clear(body);
        if (!state.capture) return;   // an empty state is already on screen

        const filtered = M.filterFunctions(state.capture.functions, filterOptions());
        const sorted = M.sortFunctions(filtered, state.options.sort, state.options.descending);
        const rows = M.limitRows(sorted, state.options.limit);
        state.visibleRows = rows;

        const scale = M.barScale(rows, state.options.sort === 'tottime' ? 'tottime' : 'cumtime');
        const barField = state.options.sort === 'tottime' ? 'tottime' : 'cumtime';

        rows.forEach(function (row) {
            const tr = el('tr');
            tr.tabIndex = 0;
            if (row.id === state.selectedId) tr.classList.add('selected');

            const nameCell = el('td', 'text');
            const wrapper = el('div', 'func-cell');
            wrapper.appendChild(dot(row.category));
            wrapper.appendChild(el('span', 'func-name', row.name));
            wrapper.appendChild(el('span', 'func-where', M.label(row, state.options.strip_dirs)));
            if (row.is_recursive) {
                const flag = el('span', 'recursive-flag', '↻');
                flag.title = 'Recursive: ' + M.count(row.calls) + ' calls, '
                    + M.count(row.primitive_calls) + ' primitive';
                wrapper.appendChild(flag);
            }
            nameCell.appendChild(wrapper);
            attachTooltip(nameCell, function () {
                return [
                    row.name,
                    (row.file === '~' ? 'built-in' : row.file + ':' + row.line),
                    categoryName(row.category) + ' · ' + M.calls(row) + ' calls'
                ];
            });
            tr.appendChild(nameCell);

            tr.appendChild(el('td', null, M.calls(row)));
            tr.appendChild(el('td', null, M.seconds(row.tottime)));
            tr.appendChild(el('td', null, M.seconds(row.percall_tottime)));
            tr.appendChild(el('td', null, M.seconds(row.cumtime)));
            tr.appendChild(el('td', null, M.seconds(row.percall_cumtime)));
            tr.appendChild(barCell(scale(row[barField])));
            tr.appendChild(el('td', null, M.percent(barField === 'tottime' ? row.tottime_pct : row.cumtime_pct)));

            tr.addEventListener('click', function () { selectFunction(row.id, true); });
            tr.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    selectFunction(row.id, true);
                }
            });
            body.appendChild(tr);
        });

        if (rows.length) {
            $('hotspot_empty').style.display = 'none';
            $('hotspot_table').style.display = '';
        } else {
            setEmptyState('Nothing matches those filters',
                'Clear the search box, or turn off "Hide imports" and "Hide Python internals".');
        }

        const total = state.capture.functions.length;
        // A very large capture is trimmed before it is sent, which the reader should know.
        const trimmed = state.capture.truncated
            ? ' · ' + M.count(state.capture.truncated) + ' quietest not shown'
            : '';
        $('row_count').textContent = (rows.length === filtered.length
            ? rows.length + ' of ' + total + ' functions'
            : 'top ' + rows.length + ' of ' + filtered.length + ' matching · ' + total + ' captured') + trimmed;

        renderSortIndicator();
    }

    function renderSortIndicator() {
        const headers = document.querySelectorAll('#hotspot_table thead th[data-sort]');
        for (let i = 0; i < headers.length; i++) {
            const header = headers[i];
            const isSorted = header.dataset.sort === state.options.sort;
            header.classList.toggle('sorted', isSorted);
            header.classList.toggle('ascending', isSorted && !state.options.descending);
        }
    }

    function selectFunction(functionId, resetTrail) {
        state.selectedId = functionId;
        if (resetTrail) {
            state.trail = [functionId];
        } else {
            const existing = state.trail.indexOf(functionId);
            if (existing === -1) {
                state.trail.push(functionId);
            } else {
                state.trail = state.trail.slice(0, existing + 1);
            }
        }
        renderDetail();
        const body = $('hotspot_body');
        for (let i = 0; i < body.children.length; i++) {
            body.children[i].classList.remove('selected');
        }
        state.visibleRows.forEach(function (row, index) {
            if (row.id === functionId && body.children[index]) {
                body.children[index].classList.add('selected');
            }
        });
    }

    function renderDetail() {
        const panel = $('detail');
        clear(panel);
        const row = functionById(state.selectedId);
        if (!row) {
            panel.classList.add('empty');
            return;
        }
        panel.classList.remove('empty');

        // Breadcrumbs: where the reader has walked through the call graph.
        const crumbs = el('div', 'breadcrumbs');
        state.trail.forEach(function (id, index) {
            const crumbRow = functionById(id);
            if (!crumbRow) return;
            if (index > 0) crumbs.appendChild(el('span', null, '›'));
            if (id === state.selectedId) {
                crumbs.appendChild(el('span', null, crumbRow.name));
            } else {
                const button = el('button', null, crumbRow.name);
                button.addEventListener('click', function () {
                    state.trail = state.trail.slice(0, index + 1);
                    state.selectedId = id;
                    renderDetail();
                });
                crumbs.appendChild(button);
            }
        });
        panel.appendChild(crumbs);

        const head = el('div', 'detail-head');
        const heading = el('div');
        const title = el('div', 'detail-title');
        title.appendChild(dot(row.category));
        title.appendChild(el('span', null, row.name));
        heading.appendChild(title);
        heading.appendChild(el('div', 'detail-sub',
            (row.file === '~' ? 'built-in function' : row.file + ':' + row.line)
            + ' · ' + categoryName(row.category)));
        head.appendChild(heading);

        if (row.file && row.file !== '~' && row.file.charAt(0) !== '<') {
            const open = el('button', null, 'Open source');
            open.addEventListener('click', function () {
                send('open_source', {file: row.file, line: row.line}).then(function (result) {
                    toast(result && result.ok
                        ? 'Opening ' + result.path
                        : (result && result.reason) || 'Could not open that file.');
                });
            });
            head.appendChild(open);
        }
        panel.appendChild(head);

        const stats = el('div', 'detail-stats');
        [
            ['Calls', M.calls(row)],
            ['Tottime', M.seconds(row.tottime) + '  (' + M.percent(row.tottime_pct) + ')'],
            ['Cumtime', M.seconds(row.cumtime) + '  (' + M.percent(row.cumtime_pct) + ')'],
            ['Per call', M.seconds(row.percall_cumtime)]
        ].forEach(function (pair) {
            const stat = el('div');
            stat.appendChild(el('div', 'detail-stat-label', pair[0]));
            stat.appendChild(el('div', 'detail-stat-value', pair[1]));
            stats.appendChild(stat);
        });
        panel.appendChild(stats);

        const columns = el('div', 'edge-columns');
        columns.appendChild(edgeColumn('Called by', row.callers, 'Nothing in Python called this — it is an entry point.'));
        columns.appendChild(edgeColumn('Calls', row.callees, 'This function calls nothing else that was profiled.'));
        panel.appendChild(columns);
    }

    function edgeColumn(heading, edges, emptyMessage) {
        const column = el('div', 'edge-column');
        column.appendChild(el('div', 'edge-heading', heading + (edges.length ? ' (' + edges.length + ')' : '')));

        if (!edges.length) {
            column.appendChild(el('div', 'edge-empty', emptyMessage));
            return column;
        }

        const list = el('ul', 'edge-list');
        edges.forEach(function (edge) {
            const row = functionById(edge.id);
            if (!row) return;
            const item = el('li');
            item.appendChild(dot(row.category));
            const name = el('span', 'edge-name', row.name);
            name.appendChild(el('span', 'func-where', ' ' + M.label(row, state.options.strip_dirs)));
            item.appendChild(name);
            item.appendChild(el('span', 'edge-time', M.count(edge.calls) + '×'));
            item.appendChild(el('span', 'edge-time', M.seconds(edge.cumtime)));
            attachTooltip(item, function () {
                return [
                    row.name,
                    'On this call path: ' + M.seconds(edge.cumtime) + ' cumulative, '
                    + M.seconds(edge.tottime) + ' in the function itself',
                    M.count(edge.calls) + ' calls'
                ];
            });
            item.addEventListener('click', function () { selectFunction(edge.id, false); });
            list.appendChild(item);
        });
        column.appendChild(list);
        return column;
    }

    // ------------------------------------------------------------------ call tree

    function renderTree() {
        const container = $('tree_body');
        clear(container);
        if (!state.capture) return;

        if (!state.treeRoots) {
            const hidden = filterOptions();
            state.treeRoots = M.assignPaths(M.buildCallTree(state.capture, {
                max_depth: 14,
                min_share: 0.002,
                exclude: function (row) {
                    if (hidden.hidden_categories.indexOf(row.category) !== -1) return true;
                    if (hidden.hide_imports && row.category === 'imports') return true;
                    if (hidden.hide_python && row.category === 'python') return true;
                    return false;
                }
            }));
        }

        const rows = M.flattenTree(state.treeRoots, state.expanded, 2);
        $('row_count').textContent = rows.length + (rows.length === 1 ? ' branch shown' : ' branches shown');

        rows.forEach(function (node) {
            const row = el('div', 'tree-row');
            row.tabIndex = 0;
            if (node.id === state.selectedId) row.classList.add('selected');

            // The measures stay in a fixed gutter, so bars are comparable at any depth.
            const gutter = el('span', 'tree-gutter');
            gutter.appendChild(el('span', 'tree-share', M.percent(node.share * 100)));

            const bar = el('span', 'tree-bar');
            const track = el('div', 'bar-track');
            const fill = el('div', 'bar-fill');
            fill.style.width = Math.max(0, Math.min(100, node.share * 100)).toFixed(1) + '%';
            track.appendChild(fill);
            bar.appendChild(track);
            gutter.appendChild(bar);
            gutter.appendChild(el('span', 'tree-time', M.seconds(node.cumtime)));
            row.appendChild(gutter);

            const twisty = el('span', 'twisty', node.children.length ? (node.is_open ? '▾' : '▸') : '');
            twisty.addEventListener('click', function (event) {
                event.stopPropagation();
                if (!node.children.length) return;
                state.expanded[M.nodePath(node)] = !node.is_open;
                renderTree();
            });

            const label = el('span', 'tree-label');
            label.style.paddingLeft = (node.depth * 15) + 'px';
            label.appendChild(twisty);
            label.appendChild(dot(node.row.category));
            label.appendChild(el('span', 'func-name', node.row.name));
            label.appendChild(el('span', 'func-where', M.label(node.row, state.options.strip_dirs)));
            if (node.calls > 1) label.appendChild(el('span', 'func-where', '· ' + M.count(node.calls) + '×'));
            if (node.recursive) {
                const flag = el('span', 'recursive-flag', '↻');
                flag.title = 'This function is already on this branch, so the tree stops here.';
                label.appendChild(flag);
            }
            row.appendChild(label);

            attachTooltip(row, function () {
                return [
                    node.row.name,
                    M.seconds(node.cumtime) + ' on this branch · ' + M.percent(node.share * 100) + ' of the capture',
                    M.count(node.calls) + ' calls from its caller'
                ];
            });

            row.addEventListener('click', function () {
                selectFunction(node.id, true);
                renderTree();
            });
            row.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    if (node.children.length) {
                        state.expanded[M.nodePath(node)] = !node.is_open;
                        renderTree();
                    }
                }
            });
            container.appendChild(row);
        });

        if (!container.children.length) {
            container.appendChild(el('div', 'empty-state',
                'Nothing here is above 0.2% of the capture. Try turning off "Hide imports" '
                + 'and "Hide Python internals".'));
        }
    }

    // ------------------------------------------------------------------ modules

    function renderModules() {
        const body = $('module_body');
        clear(body);
        if (!state.capture) return;

        const filtered = M.filterFunctions(state.capture.functions, filterOptions());
        const modules = M.buildModules(filtered);
        const scale = M.barScale(modules, 'tottime');

        $('row_count').textContent = modules.length + (modules.length === 1 ? ' file · ' : ' files · ')
            + filtered.length + ' functions';

        modules.forEach(function (module) {
            const tr = el('tr');
            tr.tabIndex = 0;

            const nameCell = el('td', 'text');
            const wrapper = el('div', 'func-cell');
            const twisty = el('span', 'twisty', '▸');
            wrapper.appendChild(twisty);
            wrapper.appendChild(dot(module.category));
            wrapper.appendChild(el('span', 'func-name', module.module));
            if (!state.options.strip_dirs && module.file !== '~') {
                wrapper.appendChild(el('span', 'func-where', module.file));
            }
            nameCell.appendChild(wrapper);
            tr.appendChild(nameCell);

            tr.appendChild(el('td', null, M.count(module.functions.length)));
            tr.appendChild(el('td', null, M.count(module.calls)));
            tr.appendChild(el('td', null, M.seconds(module.tottime)));
            tr.appendChild(el('td', null, M.seconds(module.cumtime)));
            tr.appendChild(barCell(scale(module.tottime)));
            tr.appendChild(el('td', null, M.percent(module.tottime_pct)));

            const children = [];
            module.functions.forEach(function (row) {
                const childRow = el('tr', 'muted');
                const childName = el('td', 'text');
                const childWrapper = el('div', 'func-cell');
                childWrapper.style.paddingLeft = '26px';
                childWrapper.appendChild(el('span', 'func-name', row.name));
                childWrapper.appendChild(el('span', 'func-where', 'line ' + row.line));
                childName.appendChild(childWrapper);
                childRow.appendChild(childName);
                childRow.appendChild(el('td', null, M.calls(row)));
                childRow.appendChild(el('td', null, ''));
                childRow.appendChild(el('td', null, M.seconds(row.tottime)));
                childRow.appendChild(el('td', null, M.seconds(row.cumtime)));
                childRow.appendChild(el('td', null, ''));
                childRow.appendChild(el('td', null, M.percent(row.tottime_pct)));
                childRow.style.display = 'none';
                childRow.addEventListener('click', function () {
                    selectTab('hotspots');
                    selectFunction(row.id, true);
                });
                children.push(childRow);
            });

            let open = false;
            const toggle = function () {
                open = !open;
                twisty.textContent = open ? '▾' : '▸';
                children.forEach(function (child) { child.style.display = open ? '' : 'none'; });
            };
            tr.addEventListener('click', toggle);
            tr.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    toggle();
                }
            });

            body.appendChild(tr);
            children.forEach(function (child) { body.appendChild(child); });
        });
    }

    // ------------------------------------------------------------------ compare

    function renderCompare() {
        const body = $('compare_body');
        const summary = $('compare_summary');
        clear(body);
        clear(summary);

        if (!state.diff || !state.diff.rows) {
            $('compare_empty').style.display = 'flex';
            $('compare_table').style.display = 'none';
            return;
        }

        $('compare_empty').style.display = 'none';
        $('compare_table').style.display = '';

        const diff = state.diff;
        const faster = diff.delta_total_time < 0;

        [
            ['Before', diff.before.label + ' · ' + M.seconds(diff.before.total_time), ''],
            ['After', diff.after.label + ' · ' + M.seconds(diff.after.total_time), ''],
            ['Total time', (faster ? '▼ ' : '▲ ') + M.signedSeconds(diff.delta_total_time),
                faster ? 'delta-better' : 'delta-worse'],
            ['Calls', (diff.delta_total_calls <= 0 ? '▼ ' : '▲ ') + M.signedCount(diff.delta_total_calls),
                diff.delta_total_calls <= 0 ? 'delta-better' : 'delta-worse']
        ].forEach(function (entry) {
            const tile = el('div');
            tile.appendChild(el('div', 'detail-stat-label', entry[0]));
            tile.appendChild(el('div', 'detail-stat-value ' + entry[2], entry[1]));
            summary.appendChild(tile);
        });

        const matching = M.filterDiffRows(diff.rows, {
            search: $('compare_search').value,
            only_changed: $('only_changed').checked
        });
        const rows = matching.slice(0, COMPARE_ROW_LIMIT);
        $('compare_count').textContent = rows.length === matching.length
            ? matching.length + ' functions'
            : 'first ' + rows.length + ' of ' + matching.length + ' functions';

        rows.forEach(function (row) {
            const tr = el('tr');
            const nameCell = el('td', 'text');
            const wrapper = el('div', 'func-cell');
            wrapper.appendChild(dot(row.category));
            wrapper.appendChild(el('span', 'func-name', row.name));
            wrapper.appendChild(el('span', 'func-where',
                M.label({module: row.module, file: row.file, line: row.line}, state.options.strip_dirs)));
            if (row.state !== 'changed') {
                wrapper.appendChild(el('span', 'state-pill', row.state === 'added' ? 'new' : 'gone'));
            }
            nameCell.appendChild(wrapper);
            tr.appendChild(nameCell);

            tr.appendChild(el('td', null, M.count(row.before_calls)));
            tr.appendChild(el('td', null, M.count(row.after_calls)));
            tr.appendChild(el('td', null, M.seconds(row.before_cumtime)));
            tr.appendChild(el('td', null, M.seconds(row.after_cumtime)));

            const better = row.delta_cumtime < 0;
            const delta = el('td', better ? 'delta-better' : (row.delta_cumtime > 0 ? 'delta-worse' : ''));
            delta.textContent = (row.delta_cumtime === 0 ? '' : (better ? '▼ ' : '▲ '))
                + M.signedSeconds(row.delta_cumtime);
            tr.appendChild(delta);

            body.appendChild(tr);
        });
    }

    function runCompare() {
        const before = $('compare_before').value;
        const after = $('compare_after').value;
        if (!before || !after) {
            toast('Record two captures first.');
            return;
        }
        if (before === after) {
            toast('Pick two different captures.');
            return;
        }
        send('get_diff', {before: before, after: after}).then(function (diff) {
            state.diff = diff;
            renderCompare();
        });
    }

    // ------------------------------------------------------------------ tabs

    function selectTab(name) {
        state.options.tab = name;
        const tabs = document.querySelectorAll('.tab');
        for (let i = 0; i < tabs.length; i++) {
            tabs[i].classList.toggle('active', tabs[i].dataset.tab === name);
        }
        ['hotspots', 'calltree', 'modules', 'compare'].forEach(function (view) {
            $('view_' + view).classList.toggle('active', view === name);
        });
        // Sort and Top only mean anything for the flat table; the other views bring
        // their own controls.
        $('filter_row').style.display = name === 'compare' ? 'none' : '';
        $('table_only_controls').style.display = name === 'hotspots' ? '' : 'none';
        $('search').style.display = name === 'calltree' ? 'none' : '';
        renderActiveView();
    }

    function renderActiveView() {
        const tab = state.options.tab;
        if (tab === 'hotspots') {
            renderHotspots();
            renderDetail();
        } else if (tab === 'calltree') {
            renderTree();
        } else if (tab === 'modules') {
            renderModules();
        } else if (tab === 'compare') {
            renderCompare();
        }
    }

    // ------------------------------------------------------------------ events

    function onFiltersChanged() {
        readOptionsFromControls();
        persistOptions();
        state.treeRoots = null;
        renderActiveView();
    }

    let searchTimer = null;

    function wire() {
        $('search').addEventListener('input', function () {
            if (searchTimer) clearTimeout(searchTimer);
            searchTimer = setTimeout(onFiltersChanged, 160);
        });
        ['sort_select', 'limit', 'strip_dirs', 'hide_imports', 'hide_python'].forEach(function (id) {
            $(id).addEventListener('change', onFiltersChanged);
        });
        $('editor_select').addEventListener('change', function () {
            readOptionsFromControls();
            persistOptions();
        });

        const headers = document.querySelectorAll('#hotspot_table thead th[data-sort]');
        for (let i = 0; i < headers.length; i++) {
            headers[i].addEventListener('click', function () {
                const field = this.dataset.sort;
                if (state.options.sort === field) {
                    state.options.descending = !state.options.descending;
                } else {
                    state.options.sort = field;
                    state.options.descending = field !== 'name' && field !== 'module';
                }
                $('sort_select').value = state.options.sort;
                persistOptions();
                renderHotspots();
            });
        }

        const tabs = document.querySelectorAll('.tab');
        for (let i = 0; i < tabs.length; i++) {
            tabs[i].addEventListener('click', function () {
                selectTab(this.dataset.tab);
                persistOptions();
            });
        }

        $('capture_select').addEventListener('change', function () {
            loadCapture(this.value);
        });

        $('theme_toggle').addEventListener('click', function () {
            const current = (state.options.theme === 'auto' ? state.fusionTheme : state.options.theme);
            state.options.theme = current === 'dark' ? 'light' : 'dark';
            applyTheme();
            persistOptions();
            renderAll();
        });

        $('log_text').addEventListener('click', function () {
            if (!state.capture) return;
            send('log_text', {id: state.capture.id}).then(function (result) {
                toast(result && result.ok
                    ? 'Written to the TEXT COMMANDS palette.'
                    : (result && result.reason) || 'Could not write the text report.');
            });
        });

        $('export_button').addEventListener('click', function () {
            if (!state.capture) return;
            send('export_capture', {id: state.capture.id, format: $('export_format').value})
                .then(function (result) {
                    if (result && result.ok) {
                        toast('Saved ' + result.path);
                    } else if (result && result.cancelled) {
                        toast('Export cancelled.');
                    } else {
                        toast((result && result.reason) || 'Could not save that capture.');
                    }
                });
        });

        $('compare_run').addEventListener('click', runCompare);
        $('only_changed').addEventListener('change', renderCompare);
        $('compare_search').addEventListener('input', function () {
            if (searchTimer) clearTimeout(searchTimer);
            searchTimer = setTimeout(renderCompare, 160);
        });

        window.addEventListener('scroll', tooltip.hide, true);
    }

    document.addEventListener('DOMContentLoaded', function () {
        wire();
        // Something to look at while the palette's bridge is being injected.
        setEmptyState('Reading the capture…', 'Waiting for the add-in to hand over the results.');
        loadState();
    });
})();
