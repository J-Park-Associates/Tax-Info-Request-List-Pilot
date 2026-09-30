// The harness server (SPEC-shell 14.4): serves app/renderer as the app's own
// files, and index.html with app.js swapped for the double and the harness's
// scripts added. Never part of the app; nothing here is packaged.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const renderer = path.resolve(here, "..", "..", "app", "renderer");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".json": "application/json" };

// mode "double": app.js is the double, the pages are the stand-in.
// mode "real": the real app.js runs, on the stub tracker (a smoke test).
export function page(mode) {
  let html = fs.readFileSync(path.join(renderer, "index.html"), "utf-8");
  const stubs = '<script src="/harness/vocab.js"></script>\n  <script src="/harness/stub.js"></script>\n';
  if (mode === "double") {
    html = html.replace('<script src="app.js"></script>', `${stubs}  <script src="/harness/app-stub.js"></script>`);
    html = html.replace('<script src="shell.js"></script>', '<script src="/harness/pages-stub.js"></script>\n  <script src="shell.js"></script>');
    html = html.replace("</body>", '  <script src="/harness/boot.js"></script>\n</body>');
  } else {
    html = html.replace('<script src="app.js"></script>', `${stubs}  <script src="app.js"></script>`);
  }
  return html;
}

export function serve(vocabJson, port = 0) {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    const send = (body, type, status = 200) => {
      res.writeHead(status, { "content-type": type });
      res.end(body);
    };
    if (url.pathname === "/" || url.pathname === "/index.html") return send(page(url.searchParams.get("mode") || "double"), TYPES[".html"]);
    if (url.pathname === "/harness/vocab.js") return send(`window.__VOCAB__ = ${vocabJson};`, TYPES[".js"]);
    const file = url.pathname.startsWith("/harness/")
      ? path.join(here, path.basename(url.pathname)) : path.join(renderer, ...url.pathname.split("/").filter((part) => part && part !== ".." && part !== "."));
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) return send("not found", "text/plain", 404);
    return send(fs.readFileSync(file), TYPES[path.extname(file)] || "application/octet-stream");
  });
  return new Promise((resolve) => server.listen(port, "127.0.0.1", () => resolve({ server, port: server.address().port })));
}
