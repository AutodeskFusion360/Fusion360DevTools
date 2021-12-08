const TREE_DIV = "#ui_tree";

$(document).ready(function () {
    if (window.addEventListener) {
        window.addEventListener("load", checkADSK, false);
    } else if (window.attachEvent) {
        window.attachEvent("onload", checkADSK);
    } else {
        window.onload = checkADSK;
    }
});

function checkADSK() {
    const adskWaiter = setInterval(function () {
        console.log('wait for adsk object');
        if (window.adsk) {
            clearInterval(adskWaiter);
            initialize_tree();
        }
    }, 500);
}

function initialize_tree() {
    adsk.fusionSendData("get_tree_data", '').then(ui_tree_data =>
        $(TREE_DIV).jstree({
            "core": {
                "check_callback": true,
                "data": JSON.parse(ui_tree_data).core
            },
            "types": tree_icon_types,
            "plugins": ["types"],
            "filter_check": "Collapse"
        }).on({
            "activate_node.jstree": function (e, data) {
                let args = get_node_data(data.node);
                adsk.fusionSendData("pick_node", JSON.stringify(args));
            },
        })
    );
}

function find_prop_or_in_parent(node, prop_name) {
    if (node.original && node.original[prop_name]) {
        return node.original[prop_name]
    } else {
        let js_tree = $(TREE_DIV).jstree(true);
        let parent_id = js_tree.get_parent(node);
        if (parent_id) {
            return find_prop_or_in_parent(js_tree.get_node(parent_id), prop_name)
            //    return find_prop_or_in_parent(node.parentNode, prop_name)
        } else {
            return '';
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

function refresh_tree() {
    adsk.fusionSendData("get_tree_data", "")
        .then(response => update_tree_data(JSON.parse(response)));
}

function collapse_tree() {
    let js_tree = $(TREE_DIV).jstree(true);
    js_tree.close_all();
    js_tree.filter_check = "Collapse";
}

function update_tree_data(tree_data) {
    let js_tree = $(TREE_DIV).jstree(true);
    js_tree.settings.core.data = tree_data.core;
    js_tree.refresh(true, true);
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
            if (action === "tree_refresh") {
                update_tree_data(data_in);
            } else {
                return "Unexpected command type: " + action;
            }
        } catch (e) {
            console.log(e);
            console.log("exception caught with command: " + action);
        }
        return "OK";
    }
};
