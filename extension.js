const path = require('path');
const vscode = require('vscode');

const {
    LanguageClient,
    TransportKind
} = require('vscode-languageclient/node');

let client;

function activate(context) {

    const serverModule = path.join(
        context.extensionPath,
        'lsp_server.py'
    );

    const pythonPath = path.join(
        context.extensionPath,
        '.venv',
        'Scripts',
        'python.exe'
    );

    const serverOptions = {
        run: {
            command: pythonPath,
            args: [serverModule],
            transport: TransportKind.stdio
        },
        debug: {
            command: pythonPath,
            args: [serverModule],
            transport: TransportKind.stdio
        }
    };

    const clientOptions = {
        documentSelector: [
            {
                scheme: 'file',
                language: 'testdatagen'
            }
        ],
        synchronize: {
            fileEvents:
                vscode.workspace.createFileSystemWatcher(
                    '**/*.{tdata,tdg}'
                )
        }
    };

    client = new LanguageClient(
        'testdatagenLsp',
        'TestDataGen Language Server',
        serverOptions,
        clientOptions
    );

    client.start();
}

function deactivate() {
    if (!client) {
        return undefined;
    }

    return client.stop();
}

module.exports = {
    activate,
    deactivate
};
