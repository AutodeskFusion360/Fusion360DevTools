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

/*
 * Everything the results palette computes, with no DOM in sight, so it can be
 * exercised on its own.  performance.js owns the rendering and the Fusion bridge.
 */

const PerfModel = (function () {

    // ---------------------------------------------------------------- formatting

    // Profiles span milliseconds to minutes, so the unit follows the magnitude.
    function seconds(value) {
        if (value === null || value === undefined) return '';
        const time = Math.abs(value);
        if (time === 0) return '0';
        if (time < 5e-7) return '<1 µs';
        if (time < 0.0005) return (value * 1e6).toFixed(0) + ' µs';
        if (time < 1) return (value * 1000).toFixed(time < 0.01 ? 2 : 1) + ' ms';
        if (time < 60) return value.toFixed(3) + ' s';
        return Math.floor(value / 60) + 'm ' + (value % 60).toFixed(1) + 's';
    }

    function signedSeconds(value) {
        if (!value) return '±0';
        return (value > 0 ? '+' : '−') + seconds(Math.abs(value));
    }

    function count(value) {
        return (value || 0).toLocaleString('en-US');
    }

    function signedCount(value) {
        if (!value) return '±0';
        return (value > 0 ? '+' : '−') + count(Math.abs(value));
    }

    // pstats writes recursive calls as total/primitive, which is worth keeping.
    function calls(row) {
        if (row.calls === row.primitive_calls) return count(row.calls);
        return count(row.calls) + '/' + count(row.primitive_calls);
    }

    function percent(value) {
        if (!value) return '0%';
        if (value < 0.1) return '<0.1%';
        return value.toFixed(1) + '%';
    }

    // The file name a row shows: bare name, or the trailing directories for context.
    function location(row, stripDirs) {
        if (row.file === '~' || !row.file) return row.module;
        if (stripDirs) return row.module;
        const parts = row.file.replace(/\\/g, '/').split('/');
        return parts.slice(-3).join('/');
    }

    function label(row, stripDirs) {
        const where = location(row, stripDirs);
        return row.line ? where + ':' + row.line : where;
    }

    // ---------------------------------------------------------------- filtering

    const HIDDEN_WHEN_QUIET = 0.0;

    function matchesSearch(row, search) {
        if (!search) return true;
        const needle = search.toLowerCase();
        return row.name.toLowerCase().indexOf(needle) !== -1 ||
            row.module.toLowerCase().indexOf(needle) !== -1 ||
            (row.file || '').toLowerCase().indexOf(needle) !== -1;
    }

    function filterFunctions(functions, options) {
        const hidden = {};
        (options.hidden_categories || []).forEach(function (id) { hidden[id] = true; });
        if (options.hide_imports) hidden.imports = true;
        if (options.hide_python) hidden.python = true;

        return functions.filter(function (row) {
            if (hidden[row.category]) return false;
            if (!matchesSearch(row, options.search)) return false;
            if (row.cumtime < HIDDEN_WHEN_QUIET) return false;
            return true;
        });
    }

    // ---------------------------------------------------------------- sorting

    const SORT_FIELDS = {
        cumtime: function (row) { return row.cumtime; },
        tottime: function (row) { return row.tottime; },
        calls: function (row) { return row.calls; },
        pcalls: function (row) { return row.primitive_calls; },
        percall_cumtime: function (row) { return row.percall_cumtime; },
        percall_tottime: function (row) { return row.percall_tottime; },
        name: function (row) { return row.name.toLowerCase(); },
        module: function (row) { return row.module.toLowerCase() + ':' + row.line; }
    };

    function sortFunctions(rows, sort, descending) {
        const read = SORT_FIELDS[sort] || SORT_FIELDS.cumtime;
        const direction = descending ? -1 : 1;
        return rows.slice().sort(function (left, right) {
            const a = read(left);
            const b = read(right);
            if (a === b) return left.name < right.name ? -1 : 1;
            return a < b ? -direction : direction;
        });
    }

    function limitRows(rows, limit) {
        if (!limit || limit <= 0) return rows;
        return rows.slice(0, limit);
    }

    // ---------------------------------------------------------------- call tree

    /*
     * cProfile records a call graph, not call stacks, so a tree has to be walked out
     * of the callee edges.  A function reached by two different callers contributes to
     * both branches, which is why the tree is an approximation and says so on screen.
     */
    function buildCallTree(capture, options) {
        const byId = {};
        capture.functions.forEach(function (row) { byId[row.id] = row; });

        const maxDepth = (options && options.max_depth) || 12;
        const minShare = (options && options.min_share) || 0.001;   // 0.1% of the capture
        const total = capture.total_time || 1;
        // Filtering a hierarchy has to take the branch with it, otherwise children show
        // up under a parent that is not on screen.
        const exclude = (options && options.exclude) || function () { return false; };

        function node(id, cumtime, callCount, depth, ancestors) {
            const row = byId[id];
            if (!row || exclude(row)) return null;

            const repeated = ancestors.indexOf(id) !== -1;
            const result = {
                id: id,
                row: row,
                depth: depth,
                cumtime: cumtime,
                calls: callCount,
                share: cumtime / total,
                recursive: repeated,
                children: []
            };

            // Stopping at a repeat is what keeps a cycle from unrolling forever.
            if (repeated || depth >= maxDepth) return result;

            /*
             * A callee edge holds that callee's time across every path into this function,
             * while this node only represents one of those paths.  Scaling the edge by the
             * fraction of the function's own total that this branch accounts for is what
             * keeps a child from claiming more time than its parent.
             */
            const branchScale = row.cumtime > 0 ? Math.min(1, cumtime / row.cumtime) : 0;

            const nextAncestors = ancestors.concat([id]);
            row.callees.forEach(function (edge) {
                const scaled = Math.min(edge.cumtime * branchScale, cumtime);
                if (scaled / total < minShare) return;
                const child = node(edge.id, scaled, edge.calls, depth + 1, nextAncestors);
                if (child) result.children.push(child);
            });
            result.children.sort(function (left, right) { return right.cumtime - left.cumtime; });
            return result;
        }

        const roots = [];
        capture.roots.forEach(function (id) {
            const row = byId[id];
            if (!row || exclude(row) || row.cumtime / total < minShare) return;
            const built = node(id, row.cumtime, row.calls, 0, []);
            if (built) roots.push(built);
        });
        roots.sort(function (left, right) { return right.cumtime - left.cumtime; });
        return roots;
    }

    // Depth-first order, honouring which nodes the reader has expanded.  Nodes that have
    // not been touched follow defaultDepth, so the tree opens partly expanded.
    function flattenTree(roots, expanded, defaultDepth) {
        const rows = [];
        const openToDepth = defaultDepth === undefined ? 1 : defaultDepth;

        function isOpen(node) {
            const path = nodePath(node);
            if (Object.prototype.hasOwnProperty.call(expanded, path)) return expanded[path];
            return node.depth < openToDepth;
        }

        function visit(node) {
            node.is_open = node.children.length > 0 && isOpen(node);
            rows.push(node);
            if (node.is_open) node.children.forEach(visit);
        }

        roots.forEach(visit);
        return rows;
    }

    // A node's identity in the tree is its path, since one function can appear twice.
    function nodePath(node) {
        return node.path || node.id;
    }

    function assignPaths(roots) {
        function visit(node, prefix) {
            node.path = prefix ? prefix + '/' + node.id : node.id;
            node.children.forEach(function (child) { visit(child, node.path); });
        }
        roots.forEach(function (root) { visit(root, ''); });
        return roots;
    }

    // ---------------------------------------------------------------- modules

    function buildModules(functions) {
        const groups = {};

        functions.forEach(function (row) {
            const key = row.file + '|' + row.module;
            if (!groups[key]) {
                groups[key] = {
                    key: key,
                    module: row.module,
                    file: row.file,
                    category: row.category,
                    tottime: 0,
                    cumtime: 0,
                    calls: 0,
                    tottime_pct: 0,
                    functions: []
                };
            }
            const group = groups[key];
            group.tottime += row.tottime;
            group.calls += row.calls;
            // cumtime does not sum across a module: a caller's cumtime already contains
            // its callees, so the largest single function is the honest figure here.
            group.cumtime = Math.max(group.cumtime, row.cumtime);
            group.tottime_pct += row.tottime_pct;
            group.functions.push(row);
        });

        const rows = Object.keys(groups).map(function (key) {
            const group = groups[key];
            group.functions.sort(function (left, right) { return right.tottime - left.tottime; });
            group.tottime_pct = Math.round(group.tottime_pct * 100) / 100;
            return group;
        });

        rows.sort(function (left, right) { return right.tottime - left.tottime; });
        return rows;
    }

    // ---------------------------------------------------------------- comparison

    function filterDiffRows(rows, options) {
        const search = (options && options.search) || '';
        const onlyChanged = options && options.only_changed;
        return rows.filter(function (row) {
            if (!matchesSearch(row, search)) return false;
            if (onlyChanged && Math.abs(row.delta_cumtime) < 1e-9 && row.state === 'changed') return false;
            return true;
        });
    }

    // ---------------------------------------------------------------- bar scaling

    // In-cell bars are scaled against the biggest value on screen, so the longest bar
    // always fills the cell and the rest stay comparable to it.
    function barScale(rows, field) {
        let max = 0;
        rows.forEach(function (row) {
            const value = row[field] || 0;
            if (value > max) max = value;
        });
        return function (value) {
            if (max <= 0) return 0;
            return Math.max(0, Math.min(100, (value / max) * 100));
        };
    }

    return {
        seconds: seconds,
        signedSeconds: signedSeconds,
        count: count,
        signedCount: signedCount,
        calls: calls,
        percent: percent,
        location: location,
        label: label,
        matchesSearch: matchesSearch,
        filterFunctions: filterFunctions,
        sortFunctions: sortFunctions,
        limitRows: limitRows,
        buildCallTree: buildCallTree,
        assignPaths: assignPaths,
        flattenTree: flattenTree,
        nodePath: nodePath,
        buildModules: buildModules,
        filterDiffRows: filterDiffRows,
        barScale: barScale,
        SORT_FIELDS: SORT_FIELDS
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = PerfModel;
}
