// TODO add ctrl+c navigator.clipboard
$(document).ready(function () {
    $(".search-input").keyup(function () {
        let searchString = $(this).val();
        $("#js_tree_demo_div").jstree("search", searchString);
    });
    $("#js_tree_demo_div").jstree({
        "core": {
            // "expand_selected_onload" : false,
            "check_callback": true,
            "data": "Select Something"
        },
        "checkbox": {
            "three_state": true,
            "whole_node": false,
            "tie_selection": false,
            // "keep_selected_style" : false
        },
        "types": tree_icon_types,
        "sort": function (a, b) {
            let a1 = this.get_node(a);
            let b1 = this.get_node(b);
            if (a1.icon === b1.icon) {
                return (a1.text > b1.text) ? 1 : -1;
            } else {
                return (a1.icon > b1.icon) ? 1 : -1;
            }
        },
        "search": {
            "case_sensitive": false,
            "show_only_matches": false,
            "search_leaves_only": true
        },
        // Possibly a way to deal with copy to clipboard
        // "contextmenu": {
        //     "items": function ($node) {
        //         var tree = $("#SimpleJSTree").jstree(true);
        //         return {
        //             "Copy": {
        //                 "separator_before": false,
        //                 "separator_after": false,
        //                 "label": "Copy",
        //                 "action": function (obj) {
        //                     let msg = get_node_rmb_copy_msg($node);
        //                     navigator.clipboard.writeText(msg).then(function () {
        //                         console.log(msg);
        //                     }, function (err) {
        //                         console.error("Async: Could not copy text: ", err);
        //                         console.log(msg);
        //                     });
        //
        //                 },
        //             },
        //         };
        //     }
        // },
        "plugins": ["types"],
        // "plugins": ["types", "contextmenu"],
        // "plugins": ["checkbox", "types", "sort", "search"],
        // "plugins": ["checkbox", "sort", "search"],
        // "plugins": ["types", "search"],

        "filter_check": "Collapse"
    }).on({
        "activate_node.jstree": function (e, data) {
            let args = get_node_data(data.node);
            adsk.fusionSendData("pick_node", JSON.stringify(args));
        },
        "refresh.jstree": (e, data) => do_filter_check(),

    });
    tree_clear();
});

// Not used, would be for copy to clipboard
function get_node_rmb_copy_msg(node) {
    let node_data = get_node_data(node);
    let msg = `WORKSPACE_NAME = ${node_data.workspace_name}\n`;
    if (node_data.workspace_id) {
        msg += `WORKSPACE_ID = ${node_data.workspace_id}\n`;
    }
    if (node_data.tab_id) {
        msg += `TAB_ID = ${node_data.tab_id}\n`;
    }
    if (node_data.tab_name) {
        msg += `TAB_NAME = ${node_data.tab_name}\n`;
    }
    if (node_data.panel_id) {
        msg += `PANEL_ID = ${node_data.panel_id}\n`;
    }
    if (node_data.panel_name) {
        msg += `PANEL_NAME = ${node_data.panel_name}\n`;
    }
    return msg;
}

function find_prop_or_in_parent(node, prop_name) {
    if (node.original && node.original[prop_name]) {
        return node.original[prop_name]
    } else {
        let js_tree = $("#js_tree_demo_div").jstree(true);
        let parent_id = js_tree.get_parent(node);
        if (parent_id) {
            return find_prop_or_in_parent(js_tree.get_node(parent_id), prop_name)
            //    return find_prop_or_in_parent(node.parentNode, prop_name)
        } else {
            return ''
        }
    }
}


function get_node_data(node) {
    return {
        node_id: node.id,
        node_text: node.text,
        node_type: node.type,
        workspace_id: find_prop_or_in_parent(node, "workspace_id"),
        workspace_name: find_prop_or_in_parent(node, "workspace_name"),
        tab_id: find_prop_or_in_parent(node, "tab_id"),
        tab_name: find_prop_or_in_parent(node, "tab_name"),
        panel_id: find_prop_or_in_parent(node, "panel_id"),
        panel_name: find_prop_or_in_parent(node, "panel_name"),
        control_id: find_prop_or_in_parent(node, "control_id"),
        control_name: find_prop_or_in_parent(node, "control_name"),
    };
}


function filter_tree() {
    // alert("refresh");
    const args = {
        arg1: "Sample argument 1",
        arg2: "Sample argument 2"
    };
    adsk.fusionSendData("filter_tree", JSON.stringify(args))
}

function refresh_tree() {
    const args = {
        arg1: "Sample argument 1",
        arg2: "Sample argument 2"
    };
    adsk.fusionSendData("refresh_tree", JSON.stringify(args));
}

function expand_tree() {
    let js_tree = $("#js_tree_demo_div").jstree(true);
    js_tree.open_all();
    js_tree.filter_check = "Expand";
}

function collapse_tree() {
    let js_tree = $("#js_tree_demo_div").jstree(true);
    js_tree.close_all();
    js_tree.filter_check = "Collapse";
}

function tree_clear() {
    let js_tree = $("#js_tree_demo_div").jstree(true);
    let msg = "";
    if (document.getElementById("buttons") !== null) {
        msg = `Click <b>Get Data</b> to see UI data`;
    } else {
        msg = "Pick a Component to see UI data";
    }
    js_tree.settings.core.data = [{
        text: msg,
        type: "workspace"
    }];
    js_tree.refresh();
}

function do_filter_check() {
    let js_tree = $("#js_tree_demo_div").jstree(true);
    if (js_tree && js_tree.filter_check) {
        if (js_tree.filter_check === "Collapse") {
            collapse_tree();
        } else if (js_tree.filter_check === "Expand") {
            expand_tree();
        }
    }
}

function update_tree(data_in) {
    let js_tree = $("#js_tree_demo_div").jstree(true);
    js_tree.settings.core.data = data_in.core;
    js_tree.refresh(true, true);
}

function do_action(action, data_in) {
    let js_tree = $("#js_tree_demo_div").jstree(true);
    if (data_in.filter_check && js_tree) {
        js_tree.filter_check = data_in.filter_check;
    }

    if (action === "tree_refresh") {
        update_tree(data_in);
    } else if (action === "filter_check") {
        do_filter_check();
    } else if (action === "tree_clear") {
        tree_clear();
    } else {
        return "Unexpected command type: " + action;
    }
}

window.fusionJavaScriptHandler = {
    handle: function (action, data) {
        try {
            if (!data) {
                return "No data Received";
            }
            console.log("Command Received: " + action);
            let data_in = JSON.parse(data);
            console.log(data_in);
            do_action(action, data_in);
        } catch (e) {
            console.log(e);
            console.log("exception caught with command: " + action);
        }
        let js_tree = $("#js_tree_demo_div").jstree(true);
        return "OK";
    }
};
