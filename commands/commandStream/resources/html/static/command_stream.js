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
