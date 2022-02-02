let lastCommands = [];
window.fusionJavaScriptHandler = {
    handle: function (action, raw_data) {
        try {
            console.log("received");
            let data = JSON.parse(raw_data);
            if (action === 'debugger') {
                debugger;
            } else if (action === 'command') {
                const command_string = `${data.cmd_name} - ${data.cmd_id}`

                lastCommands.unshift(command_string);
                lastCommands = lastCommands.slice(0, 20);
                document.getElementById('commands').innerHTML = lastCommands.map(
                    (item) => '<li>' + item + '</li>'
                ).join('');
            } else if (action === 'selection') {
                document.getElementById('selections').innerHTML = data.selection_list.map(
                    (item) => '<li>' + item + '</li>'
                ).join('');
            } else {
                return 'Unexpected command type: ' + action;
            }
        } catch (e) {
            alert('exception caught with command: ' + action + ', data: ' + data + ', exception: ' + e);
        }
        return 'OK';
    }
};
