#!/usr/bin/env node
/**
 * init-claude.js — bootstrap Claude Code project settings.
 *
 * Reads `.claude/settings.example.json` (committed to the repo),
 * substitutes every `$PWD` inside `command` strings with the absolute
 * path of `.claude/`, validates that each referenced hook script
 * actually exists on disk, and writes the result to
 * `.claude/settings.local.json` (which should be gitignored).
 *
 * Each team member runs this once after cloning, and again any time
 * `.claude/settings.example.json` changes:
 *
 *     node scripts/init-claude.js
 *
 * Exit codes:
 *   0  — written, or already up to date
 *   1  — error (missing files, invalid JSON, broken hook reference)
 *
 * No external dependencies. Cross-platform (Windows / Linux / macOS).
 */

'use strict';

const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..');
const CLAUDE_DIR = path.join(REPO_ROOT, '.claude');
const EXAMPLE = path.join(CLAUDE_DIR, 'settings.example.json');
const TARGET = path.join(CLAUDE_DIR, 'settings.local.json');

// Forward-slash form of the .claude path. Forward slashes work in every
// shell we care about (bash, zsh, PowerShell, cmd, Git Bash on Windows)
// and avoid having to JSON-escape backslashes.
const CLAUDE_DIR_POSIX = CLAUDE_DIR.replace(/\\/g, '/');

const RED = '\x1b[31m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const RESET = '\x1b[0m';

const tag = (color, label) => `[init-claude] ${color}${label}${RESET}`;
const info = (msg) => console.log(`[init-claude] ${msg}`);
const ok = (msg) => console.log(`${tag(GREEN, 'ok')} ${msg}`);
const warn = (msg) => console.warn(`${tag(YELLOW, 'warn')} ${msg}`);
const fail = (msg) => {
  console.error(`${tag(RED, 'error')} ${msg}`);
  process.exit(1);
};

const rel = (p) => path.relative(REPO_ROOT, p).replace(/\\/g, '/');

if (!fs.existsSync(EXAMPLE)) {
  fail(
    `Missing ${rel(EXAMPLE)}. ` +
      `Are you running this from a clone that includes the .claude/ scaffold?`
  );
}

let exampleObj;
try {
  exampleObj = JSON.parse(fs.readFileSync(EXAMPLE, 'utf8'));
} catch (e) {
  fail(`${rel(EXAMPLE)} is not valid JSON: ${e.message}`);
}

/**
 * Replace `$PWD` (optionally followed by `/some/path`) with the absolute
 * path of `.claude/`, wrapped in double quotes so the shell handles
 * spaces in user paths correctly.
 *
 * For every `$PWD/<rel>` reference, we also assert that the resolved
 * path exists on disk — this catches typos in the example file at
 * bootstrap time instead of when Claude Code tries to run the hook.
 */
function rewriteCommand(cmd) {
  return cmd.replace(/\$PWD(\/[^\s"]+)?/g, (_match, relPart) => {
    const r = relPart || '';
    const abs = path.join(CLAUDE_DIR, r).replace(/\\/g, '/');
    if (r && !fs.existsSync(abs)) {
      fail(`Hook references missing path: ${rel(abs)} (from ${rel(EXAMPLE)})`);
    }
    return `"${abs}"`;
  });
}

/** Walk the parsed JSON, rewriting every string-valued `command` field. */
function walk(node) {
  if (Array.isArray(node)) {
    for (const child of node) walk(child);
    return;
  }
  if (node && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) {
      if (key === 'command' && typeof value === 'string') {
        node[key] = rewriteCommand(value);
      } else {
        walk(value);
      }
    }
  }
}

walk(exampleObj);

const rendered = JSON.stringify(exampleObj, null, 2) + '\n';

if (fs.existsSync(TARGET)) {
  const existing = fs.readFileSync(TARGET, 'utf8');
  if (existing === rendered) {
    ok(`${rel(TARGET)} already up to date.`);
    process.exit(0);
  }
  warn(`Overwriting existing ${rel(TARGET)}.`);
}

fs.writeFileSync(TARGET, rendered, 'utf8');
ok(`Wrote ${rel(TARGET)}.`);
info(`$PWD resolved to: ${CLAUDE_DIR_POSIX}`);
info(`Make sure ${rel(TARGET)} is in .gitignore (it is per-machine).`);
