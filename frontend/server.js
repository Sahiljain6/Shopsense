const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const root = __dirname;
const port = Number(process.env.PORT || 3000);
const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const contentTypes = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8" };

function send(response, status, body, type = "text/plain; charset=utf-8") {
  response.writeHead(status, { "Content-Type": type, "Cache-Control": "no-store" });
  response.end(body);
}

http.createServer((request, response) => {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  if (url.pathname === "/config.js") {
    send(response, 200, `window.SHOPSENSE_API_URL = ${JSON.stringify(apiUrl)};\n`, "application/javascript; charset=utf-8");
    return;
  }

  const requestedPath = url.pathname === "/" || url.pathname === "/chat" ? "/index.html" : url.pathname;
  const filePath = path.join(root, path.normalize(requestedPath));
  if (!filePath.startsWith(root)) {
    send(response, 403, "Forbidden");
    return;
  }

  fs.readFile(filePath, (error, data) => {
    if (error) {
      fs.readFile(path.join(root, "index.html"), (fallbackError, fallbackData) => {
        if (fallbackError) send(response, 404, "Not found");
        else send(response, 200, fallbackData, contentTypes[".html"]);
      });
      return;
    }
    send(response, 200, data, contentTypes[path.extname(filePath)] || "application/octet-stream");
  });
}).listen(port, "0.0.0.0", () => {
  console.log(`ShopSense static frontend running on http://0.0.0.0:${port}`);
});
