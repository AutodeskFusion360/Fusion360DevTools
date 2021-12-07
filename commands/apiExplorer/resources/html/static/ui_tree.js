$(document).ready(function () {
    $("#js_tree_demo_div").jstree({
        "core": {
            "check_callback": true,
            "data": "Select Something"
        },
        "checkbox": {
            "three_state": true,
            "whole_node": false,
            "tie_selection": false
        },
        "types": tree_icon_types,
        "plugins": ["types"],
        // "plugins": ["checkbox", "types", "sort", "search", "contextmenu"],
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


function get_node_data(node) {
    return {
        node_id: node.id,
        node_text: node.text,
        node_type: node.type,
        param_name: node.original.param_name,
        clickable: node.original.clickable,
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

function go_back() {
    const args = {
        arg1: "Sample argument 1",
        arg2: "Sample argument 2"
    };
    adsk.fusionSendData("go_back", JSON.stringify(args));
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
        msg = `Select something to begin exploring`;
    } else {
        msg = "Pick a Component to see UI data";
    }
    js_tree.settings.core.data = [{
        text: msg,
        type: "0-empty"
    }];
    setMainTitle("", "");
    setTreeTitle("");
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

function updateAllTitles(title_string) {
    // Message is sent as string but intended to be parsed as JSON
    let title_object = JSON.parse(title_string);
    if (title_object.object_path) {
        setMainTitle(title_object.original_selection_name, title_object.object_path)
    }
    if (title_object.object_name) {
        setTreeTitle(title_object.object_name)
    }
}

function setMainTitle(original_selection_name, object_path) {
    // Update a paragraph with the data passed in.
    document.getElementById("explorerTitle").innerHTML =
        // FIXME What is proper way to do this?
        `<div><b>Selected Entity</b>: ${original_selection_name} <br/><br/></div>` +
        `<div>${object_path} <br/></div>`;
}

function setTreeTitle(object_name) {
    document.getElementById("currentObject").innerHTML =
        // FIXME What is proper way to do this?
        `<div><b>${object_name}</b></div>`;
}


function do_action(action, data_in) {
    let js_tree = $("#js_tree_demo_div").jstree(true);
    if (data_in.filter_check && js_tree) {
        js_tree.filter_check = data_in.filter_check;
    }
    if (data_in.title_string) {
        updateAllTitles(data_in.title_string);
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
