const TREE_DIV = "#appearance_tree";

$(document).ready(function () {
    $(".search-input").keyup(function () {
        const searchString = $(this).val();
        $(TREE_DIV).jstree("search", searchString);
    });
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
    adsk.fusionSendData("get_tree_data", '').then((response) => {
        const tree_data = JSON.parse(response);
        $(TREE_DIV).jstree({
            "core": {
                "check_callback": true,
                "data": tree_data.core
            },
            "checkbox": {
                "three_state": true,
                "whole_node": false,
                "tie_selection": false
            },
            "types": tree_icon_types,
            "sort": function (a, b) {
                const a1 = this.get_node(a);
                const b1 = this.get_node(b);
                if (a1.icon === b1.icon) {
                    return (a1.text > b1.text) ? 1 : -1;
                } else {
                    return (a1.icon > b1.icon) ? 1 : -1;
                }
            },
            "search": {
                "case_sensitive": false,
                "show_only_matches": true
            },
            "plugins":
                ["checkbox", "types", "sort", "search"]
        }).on({
            "check_node.jstree": handle_check_box,
            "uncheck_node.jstree": handle_check_box,
            "select_node.jstree": handle_node_select
        }).bind("ready.jstree", function (event, data) {
            const $tree = $(this);
            $($tree.jstree().get_json($tree, {
                flat: true
            })).each(function () {
                const node = $(TREE_DIV).jstree(true).get_node(this.id);
                if (node.type === "1-root_appearance") {
                    document.getElementById("tree_messages")
                        .innerHTML =
                        "<b>Note:</b> <i>There is an appearance " +
                        "applied to the root component " +
                        "of this design.\n" +
                        "You must remove this appearance using the " +
                        "standard appearnce command in Fusion 360</i>";
                }
            });
        });
    });
}

function handle_check_box(e, data) {
    const args = {
        node_id: data.node.id,
        node_text: data.node.text,
        remove_material: data.node.state.checked,
        node_type: data.node.type
    };
    adsk.fusionSendData("check_node", JSON.stringify(args));
}

function handle_node_select(e, data) {
    document.getElementById("tree_messages")
        .innerHTML = `Selecting ${data.node.text}`;
}

function refresh_tree() {
    adsk.fusionSendData("get_tree_data", "")
        .then(response => update_tree_data(JSON.parse(response)));
}

function expand_tree() {
    $(TREE_DIV).jstree(true).open_all();
}

function collapse_tree() {
    $(TREE_DIV).jstree(true).close_all();
}

function update_tree_data(data_in) {
    let js_tree = $(TREE_DIV).jstree(true);
    js_tree.settings.core.data = data_in.core;
    js_tree.refresh(true, true);
}

window.fusionJavaScriptHandler = {
    handle: function (action, data) {
        try {
            if (!data || data.length === 0) {
                return false;
            }
            const data_in = JSON.parse(data);
            if (action === "debugger") {
                debugger;
            } else if (action === "update_tree_data") {
                update_tree_data(data_in);
            } else {
                return "Unexpected command type: " + action;
            }
        } catch
            (e) {
            console.log(e);
            console.log("exception caught with command: " + action + ", data: " + data);
        }
        return "OK";
    }
};

