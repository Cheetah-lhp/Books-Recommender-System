#!/usr/bin/env node
/**
 * Windows Host Dual-Stack Reverse Proxy
 *
 * Bridges Windows host browser requests (http://127.0.0.1:3000, http://localhost:3000,
 * and http://[::1]:3000) to the containerized frontend exposed on TARGET_PORT (default 3001).
 *
 * Solves WSL2 mirrored networking mode socket drops (WSAETIMEDOUT 10060 / ERR_CONNECTION_TIMED_OUT)
 * by establishing a native Windows WinSock dual-stack listener.
 *
 * Zero dependencies: uses only Node.js core modules ('http', 'net', 'fs', 'path').
 */

const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');

// Parse CLI flags or fallback to environment variables
function getArg(flag, envVar, fallback) {
    for (let i = 2; i < process.argv.length; i++) {
        const arg = process.argv[i];
        if (arg === flag && i + 1 < process.argv.length) {
            return process.argv[i + 1];
        }
        if (arg.startsWith(`${flag}=`)) {
            return arg.split('=')[1];
        }
    }
    return process.env[envVar] || fallback;
}

const LISTEN_PORT = parseInt(getArg('--port', 'FRONTEND_PORT', getArg('--listen-port', 'PORT', '3000')), 10);
const TARGET_PORT = parseInt(getArg('--target', 'TARGET_PORT', getArg('--target-port', 'DOCKER_FRONTEND_PORT', '3001')), 10);
const TARGET_HOST = getArg('--host', 'TARGET_HOST', '127.0.0.1');
const PID_FILE = getArg('--pid-file', 'PID_FILE', path.resolve(__dirname, '..', '.windows-host-proxy.pid'));

const server = http.createServer((clientReq, clientRes) => {
    // Basic internal health ping for orchestrator/scripts
    if (clientReq.url === '/__proxy_health') {
        clientRes.writeHead(200, { 'Content-Type': 'application/json' });
        clientRes.end(JSON.stringify({
            status: 'ok',
            proxy: 'windows-host-proxy',
            listenPort: LISTEN_PORT,
            targetHost: TARGET_HOST,
            targetPort: TARGET_PORT,
            uptime: process.uptime()
        }));
        return;
    }

    const headers = { ...clientReq.headers };
    // Set Host header to target
    headers.host = `${TARGET_HOST}:${TARGET_PORT}`;
    headers['x-forwarded-for'] = clientReq.socket.remoteAddress || '127.0.0.1';
    headers['x-forwarded-proto'] = 'http';
    headers['x-forwarded-port'] = String(LISTEN_PORT);

    const proxyReq = http.request({
        hostname: TARGET_HOST,
        port: TARGET_PORT,
        path: clientReq.url,
        method: clientReq.method,
        headers: headers
    }, (proxyRes) => {
        clientRes.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(clientRes, { end: true });
    });

    proxyReq.on('error', (err) => {
        if (!clientRes.headersSent) {
            clientRes.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' });
            clientRes.end(`502 Bad Gateway: Windows host proxy unable to connect to ${TARGET_HOST}:${TARGET_PORT} (${err.code || err.message})\n`);
        }
    });

    clientReq.on('error', () => {
        proxyReq.destroy();
    });

    clientRes.on('error', () => {
        proxyReq.destroy();
    });

    clientReq.pipe(proxyReq, { end: true });
});

// Support WebSocket Upgrade
server.on('upgrade', (clientReq, clientSocket, head) => {
    const targetSocket = net.connect({ host: TARGET_HOST, port: TARGET_PORT }, () => {
        let rawReq = `${clientReq.method} ${clientReq.url} HTTP/${clientReq.httpVersion}\r\n`;
        for (let i = 0; i < clientReq.rawHeaders.length; i += 2) {
            const key = clientReq.rawHeaders[i];
            const val = clientReq.rawHeaders[i + 1];
            if (key.toLowerCase() === 'host') {
                rawReq += `Host: ${TARGET_HOST}:${TARGET_PORT}\r\n`;
            } else {
                rawReq += `${key}: ${val}\r\n`;
            }
        }
        rawReq += `X-Forwarded-For: ${clientSocket.remoteAddress || '127.0.0.1'}\r\n`;
        rawReq += `X-Forwarded-Port: ${LISTEN_PORT}\r\n`;
        rawReq += '\r\n';

        targetSocket.write(rawReq);
        if (head && head.length > 0) {
            targetSocket.write(head);
        }
        targetSocket.pipe(clientSocket);
        clientSocket.pipe(targetSocket);
    });

    clientSocket.on('error', () => {
        targetSocket.destroy();
    });

    targetSocket.on('error', (err) => {
        clientSocket.end(`HTTP/1.1 502 Bad Gateway\r\n\r\n${err.message}`);
    });
});

function writePidFile() {
    try {
        fs.writeFileSync(PID_FILE, String(process.pid), 'utf-8');
    } catch (err) {
        console.warn(`[windows-host-proxy] Notice: Could not write PID file (${err.message})`);
    }
}

function cleanupAndExit() {
    try {
        if (fs.existsSync(PID_FILE)) {
            const currentPid = fs.readFileSync(PID_FILE, 'utf-8').trim();
            if (currentPid === String(process.pid)) {
                fs.unlinkSync(PID_FILE);
            }
        }
    } catch (_) {}
    server.close(() => {
        process.exit(0);
    });
    // Hard exit after 1s if connections stall
    setTimeout(() => process.exit(0), 1000);
}

process.on('SIGINT', cleanupAndExit);
process.on('SIGTERM', cleanupAndExit);
process.on('exit', () => {
    try {
        if (fs.existsSync(PID_FILE)) {
            const currentPid = fs.readFileSync(PID_FILE, 'utf-8').trim();
            if (currentPid === String(process.pid)) {
                fs.unlinkSync(PID_FILE);
            }
        }
    } catch (_) {}
});

// Bind dual-stack (IPv6 :: with ipv6Only: false covers both IPv4 and IPv6)
server.listen({ port: LISTEN_PORT, host: '::', ipv6Only: false }, () => {
    writePidFile();
    console.log(`[windows-host-proxy] Listening on [::]:${LISTEN_PORT} (dual-stack) -> forwarding to http://${TARGET_HOST}:${TARGET_PORT} (PID: ${process.pid})`);
});

server.on('error', (err) => {
    if (err.code === 'EAFNOSUPPORT' || err.code === 'ENOPROTOOPT') {
        // Fall back to 0.0.0.0 if dual-stack IPv6 is not supported
        console.warn(`[windows-host-proxy] Dual-stack IPv6 unsupported (${err.code}), falling back to 0.0.0.0`);
        server.listen({ port: LISTEN_PORT, host: '0.0.0.0' }, () => {
            writePidFile();
            console.log(`[windows-host-proxy] Listening on 0.0.0.0:${LISTEN_PORT} -> forwarding to http://${TARGET_HOST}:${TARGET_PORT} (PID: ${process.pid})`);
        });
    } else {
        console.error(`[windows-host-proxy] Fatal server error:`, err);
        process.exit(1);
    }
});
