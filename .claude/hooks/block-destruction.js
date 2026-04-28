/* =========================================================================
 * block-destruction.js — Claude Code PreToolUse hook for the Bash tool.
 *
 * THREAT MODEL
 * ------------
 * Allow Claude Code to delete files freely — without that, the agent
 * cannot do normal work (rebuild venvs, clean caches, remove generated
 * artifacts, fix typos by deleting). Block ONLY operations whose blast
 * radius is unacceptable: wholesale repo wipes, history rewrite,
 * remote destruction, database wipes, disk-level damage.
 *
 * BLOCKED (irreversible / catastrophic):
 *   - Recursive delete of dangerous targets: /, ~, $HOME, .., . (cwd),
 *     * (everything in cwd), .git (kills history), drive roots (C:\).
 *     Covered for bash `rm`, PowerShell `Remove-Item`, cmd `rd`/`rmdir`/`del`.
 *   - Disk-level destruction (dd of=/dev/, mkfs, fdisk, parted, shred,
 *     fork bombs, chmod 000 /, chown -R / ...).
 *   - Git history rewrite (filter-branch, filter-repo, update-ref -d).
 *   - Force-push to protected branches (main, master, develop, production).
 *   - Remote destruction (gh repo delete, gh release delete, gh secret delete).
 *   - DB wholesale wipes (DROP DATABASE/SCHEMA, TRUNCATE TABLE,
 *     DELETE FROM <t> without a WHERE clause).
 *
 * ALLOWED (recoverable / scoped):
 *   - `rm <file>`, `rm -rf <subfolder>` (e.g. .venv, node_modules, dist)
 *   - PowerShell `Remove-Item` of specific files or subfolders
 *   - `git reset --hard`, `git clean -fdx`, `git branch -D`
 *     (recoverable via reflog within ~90 days)
 *   - `git push --force` on feature branches
 *   - `DROP TABLE <single>`, `DELETE FROM <t> WHERE ...`
 * ======================================================================= */

// Dangerous targets, ordered MOST-SPECIFIC first so `\.git` is tried before
// `\.` (regex alternation is left-to-right). Putting `\.` first would make
// it match the `.` in `.git` and then fail the lookahead, blocking valid
// matches via incomplete backtracking in some engines.
const TARGET_UNIX = String.raw`(\.git|\.\.|\$HOME|\$\{HOME\}|\/|~|\.|\*)`;
const TARGET_WIN = String.raw`(\.git|\.\.|\$HOME|C:\\?|\/|~|\.|\*)`;

const PATTERNS = [
  // ── Filesystem: wholesale wipes via Unix rm ─────────────────────────────
  // Match `rm -[Rrf]+ <dangerous-target>` where target is /, ~, $HOME, .., .,
  // *, or .git, optionally followed by a trailing slash or `/*`.
  // Lookahead `(?=\s|$)` requires the target to be a *complete* argument,
  // so `rm -rf ./venv`, `rm -rf /tmp/foo`, `rm -rf .gitignore` are NOT blocked.
  new RegExp(
    String.raw`\brm\s+-[a-zA-Z]*[rRfF][a-zA-Z]*\s+${TARGET_UNIX}(\/|\/\*)?(?=\s|$)`,
    'm'
  ),

  // ── Filesystem: wholesale wipes via PowerShell ──────────────────────────
  // Note: `\s-Recurse` (whitespace before flag) — `\b` does NOT work here
  // because there is no word boundary between space and `-`.
  new RegExp(
    String.raw`\bRemove-Item\b[^;|]*?\s-Recurse\b[^;|]*?[\s'"]${TARGET_WIN}(\\|\/|\\\*|\/\*)?(?=['"]|\s|$)`,
    'im'
  ),
  new RegExp(
    String.raw`\bRemove-Item\b[^;|]*?-Path\s+["']?${TARGET_WIN}["']?(\\|\/|\\\*|\/\*)?(?=\s|$)`,
    'im'
  ),

  // ── Filesystem: wholesale wipes via cmd.exe ────────────────────────────
  /\brd\s+\/[sS](\s+\/[qQ])?\s+(\.git|\\|C:\\?|\.\.)(?=\s|$)/i,
  /\brmdir\s+\/[sS](\s+\/[qQ])?\s+(\.git|\\|C:\\?|\.\.)(?=\s|$)/i,
  /\bdel\s+\/[sSqQfF\s\/]*\s(\.git|\\|C:\\?|\*\.\*)(?=\s|$)/i,

  // ── Filesystem: disk-level destruction ─────────────────────────────────
  /:\(\)\s*\{\s*:\|\s*:\s*&\s*\}\s*;\s*:/, // fork bomb
  /\bdd\s+[^|;]*\bof=\/dev\//,
  /\b(mkfs|fdisk|parted)\b/,
  /\bshred\s+/,
  /\bchmod\s+-R\s+0*0\s+\//,
  /\bchown\s+-R\s+\S+\s+\//,
  />\s*\/dev\/sd[a-z]\b/,

  // ── Git: history rewrite (irreversible, no reflog escape) ──────────────
  /\bgit\s+filter-branch\b/,
  /\bgit\s+filter-repo\b/,
  /\bgit\s+update-ref\s+-d\b/,
  // Force push to protected branches (feature branches are fine).
  // `--force\b` works because `\b` is between word `e` and the following
  // non-word char. Before `--` we use `[^;|]*?` (no leading-boundary needed).
  /\bgit\s+push\b[^;|]*?(--force\b|--force=|-f\b)[^;|]*?\b(main|master|develop|production)\b/,
  /\bgit\s+push\b[^;|]*?\b(main|master|develop|production)\b[^;|]*?(--force\b|--force=|-f\b)/,

  // ── GitHub CLI: remote destruction (cannot undo from local) ────────────
  /\bgh\s+repo\s+delete\b/,
  /\bgh\s+repo\s+archive\b/,
  /\bgh\s+release\s+delete\b/,
  /\bgh\s+secret\s+delete\b/,

  // ── Database: wholesale wipes ──────────────────────────────────────────
  // SQL is case-insensitive; the /i flag handles uppercase/lowercase.
  /\bDROP\s+(DATABASE|SCHEMA)\b/i,
  /\bTRUNCATE\s+(TABLE\s+)?["`']?\w+["`']?/i,
  // DELETE FROM <table> with no WHERE clause (allow DELETE ... WHERE ...).
  /\bDELETE\s+FROM\s+["`']?\w+["`']?\s*(;|--|$)/im,
];

async function main() {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  const args = JSON.parse(Buffer.concat(chunks).toString());
  const cmd = args.tool_input?.command || '';

  for (const re of PATTERNS) {
    if (re.test(cmd)) {
      console.error(
        `Blocked destructive command: matched ${re}\n` +
          `Command was: ${cmd}\n` +
          `If this is intentional, run it manually outside Claude Code.`
      );
      process.exit(2);
    }
  }
}

main();
