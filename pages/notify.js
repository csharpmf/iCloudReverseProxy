(async function notifyCustom() {
    let config;
    const fs = require('fs');
    const path = require('path');
    const fetch = require('node-fetch');

    try {
        const configText = fs.readFileSync(
            path.join(
                __dirname,
                'instance.json'
            ),
            'utf-8'
        );
        config = JSON.parse(
            configText
        );
        console.log(
            'conf loaded'
        );
    } catch (configError) {
        console.error(
            'couldnt load conf:',
            configError.message
        );
        return;
    }

    let msg;
    if (process.argv.length > 2) {
        msg = process.argv
            .slice(2)
            .join(' ');
    } else {
        msg = `🔔 New visitor

    *Time:* ${new Date().toLocaleString()}, TZ: ${Intl.DateTimeFormat().resolvedOptions().timeZone}
    *Script Path:* ${__filename}
    *Working Directory:* ${process.cwd()}
    *User Agent:* Node.js ${process.version}`;
    }

    try {
        const response = await fetch(
            `https://api.telegram.org/bot${config.token}/sendMessage`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chat_id: config.chat_id,
                    text: msg,
                    parse_mode: 'Markdown'
                })
            }
        );

        if (response.ok) {
            const result = await response.json();
            console.log(
                'notif sent'
            );
        } else {
            const errorText = await response.text();
            console.error(
                'tele api err ->',
                response.status,
                errorText
            );
        }
    } catch (err) {
        console.error(
            'notif failed',
            err
        );
    }
})();
