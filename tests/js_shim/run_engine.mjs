// run_engine.mjs — Node shim that runs the browser JS 3-stack engine (fold.js + search.js)
// headlessly so the Python parity test can compare solution sets across engines.
//
// fold.js / search.js are browser IIFEs (`const Fold = (...)()`, `const Search = (...)()`) with
// no module.exports. We read both as text, concatenate them, append assignment lines that copy
// the two consts onto globalThis, and run the whole thing in ONE vm sandbox so the consts are in
// scope when we capture them. search.js's worker-mode block self-skips under Node (no `self`).
//
// CLI: node run_engine.mjs --m M --n N [flags].  Flags mirror the Python opts:
//   --no-rect --no-L --decomp2only --decomp3only --allow-non-corner --no-dedup
// Output (stdout, ONE line): {"count":N,"hashes":[...canonicalHash strings...],"ctx":{...}}
// All diagnostics go to stderr so stdout stays JSON-parseable.

import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url)); // tests/js_shim
const ROOT = join(HERE, "..", ".."); // repo root (two levels up)

/** Parse argv into a Search.run opts dict mirroring the Python side.
 *  I/O: (string[] argv after node+script) -> {m, n, shapes, decomps, allowNonCorner, dedup}. */
function parseArgs(argv) {
  let m = null;
  let n = null;
  const flags = new Set();
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--m") m = Number(argv[++i]);
    else if (a === "--n") n = Number(argv[++i]);
    else if (a.startsWith("--")) flags.add(a);
    else throw new Error(`unexpected arg: ${a}`);
  }
  if (!Number.isInteger(m) || !Number.isInteger(n)) {
    throw new Error("both --m and --n (integers) are required");
  }
  const shapes = { L: !flags.has("--no-L"), Rect: !flags.has("--no-rect") };
  let decomps = { "2+1": true, "1+1+1": true };
  if (flags.has("--decomp2only")) decomps = { "2+1": true, "1+1+1": false };
  if (flags.has("--decomp3only")) decomps = { "2+1": false, "1+1+1": true };
  return {
    m,
    n,
    shapes,
    decomps,
    allowNonCorner: flags.has("--allow-non-corner"),
    dedup: !flags.has("--no-dedup"),
  };
}

/** Load Fold + Search from the repo-root browser IIFEs into one vm sandbox.
 *  I/O: () -> { Search } (the live Search object with .run). */
function loadEngine() {
  const foldSrc = readFileSync(join(ROOT, "fold.js"), "utf8");
  const searchSrc = readFileSync(join(ROOT, "search.js"), "utf8");
  const sandbox = {};
  sandbox.globalThis = sandbox; // so the appended `globalThis.__X = X` resolves to our sandbox
  const ctx = createContext(sandbox);
  // The consts are block-scoped to this single script execution; the trailing assignment lines run
  // in the same scope, so they can see Fold / Search and copy them out onto globalThis.
  const combined =
    foldSrc + "\n" + searchSrc + "\nglobalThis.__Fold = Fold; globalThis.__Search = Search;";
  runInContext(combined, ctx, { filename: "engine.bundle.js" });
  return { Search: sandbox.__Search };
}

/** Run the JS search and collect canonicalHash strings + the onDone ctx.
 *  I/O: (Search obj, opts) -> {count, hashes:[string], ctx:object}. */
function runSearch(Search, opts) {
  const hashes = [];
  let doneCtx = {};
  Search.run(opts, {
    onSolution: (sol) => hashes.push(sol.canonicalHash),
    onDone: (ctx) => {
      // Keep only JSON-friendly primitives from ctx.
      doneCtx = {};
      for (const [k, v] of Object.entries(ctx)) {
        if (typeof v === "number" || typeof v === "boolean") doneCtx[k] = v;
      }
    },
    onError: (e) => process.stderr.write(`[engine error] ${e}\n`),
    onProgress: () => {},
    isCancelled: () => false,
  });
  return { count: hashes.length, hashes, ctx: doneCtx };
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const { Search } = loadEngine();
  if (!Search || typeof Search.run !== "function") {
    throw new Error("failed to load Search.run from search.js");
  }
  const result = runSearch(Search, opts);
  process.stdout.write(JSON.stringify(result) + "\n");
}

try {
  main();
} catch (err) {
  process.stderr.write(`[run_engine] ${err && err.stack ? err.stack : err}\n`);
  process.exit(1);
}
