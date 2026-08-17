<?php
declare(strict_types=1);
/**
 * Feedback intake endpoint for pdoom1.com.
 *
 * Implements docs/decisions/FEEDBACK_INTAKE_CONTRACT.md. Supersedes
 * public/bug-submit.php, which mailed first and had no store at all -- a
 * mail() that returned false lost the visitor's words with a 502.
 *
 * THE INVARIANT (contract §0)
 * --------------------------
 *   INV-1  No success state is ever shown to a visitor without a durable write
 *          having completed.
 *
 * Everything below is arranged around that one sentence, so the ORDER of this
 * file is load-bearing and not a matter of taste:
 *
 *   1. method                      -> 405
 *   2. read body, hard byte cap    -> 413
 *   3. resolve + prove the store   -> 507   (BEFORE parsing: a store we cannot
 *                                            write to is a 507 no matter how
 *                                            well-formed the request is, and a
 *                                            store inside the docroot must be
 *                                            refused before anything is created)
 *   4. parse JSON                  -> 400
 *   5. validate kind/rid/page/caps -> 400 / 413
 *   6. spam signals                -> FLAGS ONLY, never a drop
 *   7. throttle                    -> 429   (retryable; the outbox holds the
 *                                            message and it goes out later)
 *   8. append + fsync              -> 507 on any failure
 *   9. notify                      -> CANNOT change the status code
 *  10. 200 {ok, rid, receipt, stored_at}
 *
 * Step 9 is after step 10's precondition on purpose. mail() returning true is
 * not a durable write (INV-1a) and mail() returning false must not turn a
 * stored record into an error (contract §6 row F5).
 *
 * SECURITY POSTURE (each line here is a defect this repo has already paid for)
 * ---------------------------------------------------------------------------
 * - The recipient is a hardcoded constant, never taken from input. There is no
 *   open relay here; the worst an attacker gets is spam into our own inbox,
 *   which the throttle blunts.
 * - EVERY mail header is a constant. All visitor text goes in the BODY only.
 *   The Subject carries the kind (drawn from an allowlist) and the receipt
 *   (drawn from the base32 alphabet), so no header component can contain a CR,
 *   an LF, or anything the visitor typed. That removes header injection by
 *   construction rather than by escaping.
 * - The response is JSON and nothing else. This endpoint has no HTML sink, so
 *   escape.js's rules do not apply to it -- do not give it one.
 * - The raw IP is never logged or stored. Only sha256(ip + a salt that rotates
 *   daily), which is what makes the row unlinkable after 24h (contract §10).
 * - `kind` is checked against an allowlist and an unknown value is REJECTED.
 *   bug-submit.php fell back to 'bug', and its own comments record that this
 *   mislabelled every "General Feedback" and "Question" that came through it.
 *
 * WHY THE STORE MUST LIVE ABOVE THE DOCROOT (contract §3, INV-1c)
 * --------------------------------------------------------------
 * Two independent reasons, either sufficient on its own:
 *   a) `rsync --delete` from public/ runs ~4x/day (CLAUDE.md, Deploy). A store
 *      under the docroot is deleted by a deploy nobody is watching.
 *   b) The record carries reporter-supplied contact details. Under the docroot
 *      that is publicly fetchable.
 * So a store_root that resolves inside the docroot is a 507 and NEVER a
 * fallback. "Helpfully" writing somewhere else is how the PII got published
 * the last three times.
 *
 * TEST SEAMS (contract §11.1) -- inert in production, both unset
 * -------------------------------------------------------------
 *   PDOOM_MAIL_SINK   path. When set, mail() is NOT called; one JSON line per
 *                     notification is appended instead: {rid, receipt, kind,
 *                     ok, deferred, ts}.
 *   PDOOM_MAIL_FAIL   "1" forces that notification to report ok:false, exactly
 *                     as mail() returning false would.
 *   PDOOM_THROTTLE_BURST  overrides the burst allowance for both classes
 *                     (contract §11.3). PDOOM_THROTTLE_BURST_PROSE and
 *                     PDOOM_THROTTLE_BURST_THUMB override one class each and
 *                     take precedence; see throttle_check() for why one knob
 *                     is not enough.
 *
 * The notification sink is deliberately NOT a *.jsonl file inside the store
 * root: every reader in this system globs `<store>/*.jsonl` to mean "records",
 * and a second .jsonl in there would be counted as feedback that nobody sent.
 *
 * CLI NOTE, MEASURED not assumed (PHP 8.3.33, 2026-08-16)
 * ------------------------------------------------------
 * Under the CLI SAPI `php://input` reads back EMPTY -- the request body arrives
 * on stdin. scripts/fixtures/php_cli_shim.php runs this file under CLI, so
 * read_body() falls through to php://stdin when php://input is empty and the
 * SAPI is cli. Under a web SAPI php://input is authoritative and stdin is never
 * touched. http_response_code() was verified to work as both getter and setter
 * under CLI in the same measurement.
 */

// ---- config -------------------------------------------------------------

const RECIPIENT = 'team@pdoom1.com';   // hardcoded on purpose (see above)
const FROM      = 'team@pdoom1.com';   // envelope sender; see mail()'s 5th param
const SCHEMA    = 1;

// A whole-body cap, checked on bytes before anything is parsed. The per-field
// caps below are the ones a visitor can act on; this one only exists so a
// multi-megabyte body cannot be decoded into memory.
const MAX_BODY_BYTES = 131072;

// Per-field caps, contract §2. Measured in CHARACTERS (mb_strlen), because
// "5000 characters" is what a visitor-facing counter can honestly display.
const CAP_TEXT    = 5000;
const CAP_CONTACT = 200;
const CAP_CREDIT  = 80;
const CAP_PAGE    = 512;

const KINDS       = ['thumb', 'comment', 'bug', 'feature', 'question', 'feedback'];
const PROSE_KINDS = ['comment', 'bug', 'feature', 'question', 'feedback'];

// Fill-time floors for the bot signal. A trip TAGS the record; it never drops
// it (INV-1e). Separate floors because a thumb is one click and prose is not:
// one floor would either tag every honest thumb or catch no bot at all.
const MIN_FILL_MS_PROSE = 1500;
const MIN_FILL_MS_THUMB = 200;

// Throttle, contract §11.3. A token bucket: `burst` is the bucket, `per_hour`
// is the refill. A 429 is retryable and the client's outbox holds the message,
// so this paces a visitor -- it never drops one.
const RATE_THUMB_PER_HOUR = 120;
const RATE_THUMB_BURST    = 20;
const RATE_PROSE_PER_HOUR = 10;
const RATE_PROSE_BURST    = 5;

// A file-size limit (RLIMIT_FSIZE) raises SIGXFSZ, whose default disposition
// kills the process mid-append -- which would leave a partial line and no
// response at all. Ignoring it downgrades that to a short write, which
// append_record() detects and rolls back. pcntl is CLI-only and absent on most
// shared hosting, so this is a no-op there.
if (function_exists('pcntl_signal') && defined('SIGXFSZ')) {
    @pcntl_signal(SIGXFSZ, SIG_IGN);
}

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

// ---- response helpers ---------------------------------------------------

/**
 * The ONLY way this file answers. Status is set before any output so that a web
 * SAPI has not already flushed headers by the time we know the code.
 */
function respond(int $code, array $payload): void
{
    http_response_code($code);
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($json === false) {
        // Cannot happen with the payloads below, but a silent empty body would
        // read to the client as "unparseable" and therefore as retryable-true,
        // which is the correct reading anyway. Say so explicitly.
        $json = '{"ok":false,"error":"response could not be encoded","retryable":true}';
    }
    echo $json;
    exit;
}

/** Every non-200 answer states `retryable` EXPLICITLY (contract §2). */
function fail(int $code, string $error, bool $retryable, array $extra = []): void
{
    respond($code, array_merge(
        ['ok' => false, 'error' => $error, 'retryable' => $retryable],
        $extra
    ));
}

// ---- path plumbing ------------------------------------------------------

/**
 * Normalise a path that MAY NOT EXIST YET.
 *
 * realpath() returns false for a missing path, and the containment check has to
 * work before the store directory has ever been created -- otherwise the very
 * first request of a new deploy is the one that skips the check. So: resolve the
 * deepest ancestor that does exist, then re-append the components that do not.
 */
function norm_path(string $path): string
{
    $path = str_replace('\\', '/', trim($path));
    if ($path === '') {
        return '';
    }
    $tail  = [];
    $probe = $path;
    for ($guard = 0; $guard < 64; $guard++) {
        $real = @realpath($probe);
        if ($real !== false) {
            $real = rtrim(str_replace('\\', '/', $real), '/');
            if ($tail) {
                $real .= '/' . implode('/', array_reverse($tail));
            }
            return $real;
        }
        $parent = dirname($probe);
        if ($parent === $probe || $parent === '' || $parent === '.') {
            break;
        }
        $tail[]  = basename($probe);
        $probe   = $parent;
    }
    // Nothing on the path exists at all. Lexical normalisation is weaker than
    // realpath (it cannot see through a symlink), so it fails toward "inside":
    // an unresolvable path that merely LOOKS outside is not proof.
    return rtrim($path, '/');
}

/** True when $child is $parent or lives under it. Case-folded on Windows. */
function path_inside(string $child, string $parent): bool
{
    if ($child === '' || $parent === '') {
        return false;
    }
    $c = rtrim($child, '/');
    $p = rtrim($parent, '/');
    if (DIRECTORY_SEPARATOR === '\\') {
        $c = strtolower($c);
        $p = strtolower($p);
    }
    if ($c === $p) {
        return true;
    }
    // The trailing slash matters: without it, docroot "/srv/public" would
    // swallow the sibling "/srv/public-store".
    return strncmp($c, $p . '/', strlen($p) + 1) === 0;
}

function docroot(): string
{
    $d = isset($_SERVER['DOCUMENT_ROOT']) ? (string)$_SERVER['DOCUMENT_ROOT'] : '';
    if (trim($d) === '') {
        $d = (string)getenv('PDOOM_DOCROOT');
    }
    if (trim($d) === '') {
        // This file IS in the docroot in every deployment we control.
        $d = __DIR__;
    }
    return $d;
}

/** ['path' => string, 'source' => 'env'|'derived'] -- contract §3. */
function store_root(string $docroot): array
{
    $env = getenv('PDOOM_FEEDBACK_STORE');
    if (is_string($env) && trim($env) !== '') {
        return ['path' => trim($env), 'source' => 'env'];
    }
    return ['path' => dirname($docroot) . '/feedback-store', 'source' => 'derived'];
}

/**
 * Create the store directory and prove it is writable, per contract §3's
 * `<store_root>/.probe` canary.
 *
 * The canary is a PRE-check, not the authority: F2 makes the month file
 * unappendable while leaving the directory writable, so the append itself is
 * the thing that decides 200 vs 507. A canary that passed and an append that
 * failed is still a 507.
 */
function ensure_store(string $root): bool
{
    if (!is_dir($root)) {
        @mkdir($root, 0700, true);
    }
    if (!is_dir($root)) {
        return false;
    }
    return @file_put_contents($root . '/.probe', gmdate('c') . "\n") !== false;
}

// ---- identity ------------------------------------------------------------

/**
 * The daily salt, contract §10.
 *
 * A hash of the bare IP would be reversible by brute force over a 32-bit space,
 * so the salt has to be secret AND has to rotate, which is what makes the row
 * unlinkable after 24h without deleting anything. Created atomically: write a
 * uniquely-named temp file, then rename() onto the day's path. Two racing
 * processes both succeed -- one renames, the other loses the race, re-reads and
 * uses the winner's salt.
 *
 * Returns ['salt' => string, 'weak' => bool]. `weak` is true when the salt
 * could not be persisted; the record is FLAGGED in that case rather than
 * pretending a keyed hash happened.
 */
function daily_salt(string $root): array
{
    $day  = gmdate('Y-m-d');
    $dir  = $root . '/.salt';
    $path = $dir . '/' . $day;
    for ($attempt = 0; $attempt < 3; $attempt++) {
        $existing = @file_get_contents($path);
        if (is_string($existing) && strlen(trim($existing)) >= 32) {
            return ['salt' => trim($existing), 'weak' => false];
        }
        if (!is_dir($dir)) {
            @mkdir($dir, 0700, true);
        }
        $salt = bin2hex(random_bytes(32));
        $tmp  = $path . '.' . bin2hex(random_bytes(6)) . '.tmp';
        if (@file_put_contents($tmp, $salt) !== false) {
            if (@rename($tmp, $path)) {
                return ['salt' => $salt, 'weak' => false];
            }
            @unlink($tmp);
        }
    }
    // Still rotates daily, but it is not secret. Never silently substitute this
    // for the real thing -- the caller tags the record 'weak-ip-salt'.
    return ['salt' => 'unsalted-' . $day, 'weak' => true];
}

/**
 * receipt = "F-" + base32(first 30 bits of rid), uppercase, 6 chars (§1).
 *
 * Display-only and MAY collide; nothing keys on it. RFC 4648 alphabet, so every
 * character is [A-Z2-7] -- which is also why the receipt is safe to put in a
 * mail Subject.
 */
function receipt_from_rid(string $rid): string
{
    $hex = preg_replace('/[^0-9a-fA-F]/', '', $rid);
    if (!is_string($hex) || strlen($hex) < 8) {
        $hex = str_pad(bin2hex(substr($rid . '00000000', 0, 4)), 8, '0');
    }
    $top    = (int)hexdec(substr($hex, 0, 8));      // 32 bits
    $bits30 = ($top >> 2) & 0x3FFFFFFF;             // the first 30 of them
    $alpha  = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    $out    = '';
    for ($i = 5; $i >= 0; $i--) {
        $out .= $alpha[($bits30 >> ($i * 5)) & 31];
    }
    return 'F-' . $out;
}

// ---- throttle ------------------------------------------------------------

/**
 * Token bucket per (ip_hash, class). Returns
 * ['allowed' => bool, 'retry_after' => int, 'note' => string].
 *
 * FAILS OPEN. If the state file cannot be opened, the request is allowed. A
 * rate limiter that cannot read its own state must not become a way to lose a
 * message -- that trade is the whole contract.
 *
 * State lives in <store_root>/.throttle/, i.e. above the docroot with the
 * records. It deliberately does NOT live in sys_get_temp_dir() the way
 * bug-submit.php's did: a system-wide temp path is shared by every site and
 * every test run on the box, so the limit one visitor hits depends on what
 * somebody else did.
 */
function throttle_check(string $root, string $ipHash, string $class): array
{
    $perHour = ($class === 'thumb') ? (float)RATE_THUMB_PER_HOUR : (float)RATE_PROSE_PER_HOUR;
    $burst   = ($class === 'thumb') ? (float)RATE_THUMB_BURST    : (float)RATE_PROSE_BURST;

    // Test-only overrides (§11.3 names PDOOM_THROTTLE_BURST). The per-class
    // forms are ADDITIVE and change no production default; they exist because
    // the single knob has two incompatible users. §6 row F9 reads
    // PDOOM_THROTTLE_BURST as "how many requests to SEND" and needs the
    // endpoint's burst to stay BELOW it, while rows F3 and F4 need the prose
    // burst RAISED ABOVE the 18 and 16 requests they issue. One knob cannot
    // satisfy both; PDOOM_THROTTLE_BURST_PROSE can lift prose alone and leave
    // F9's thumb bucket at its contract value.
    foreach ([
        'PDOOM_THROTTLE_BURST_' . strtoupper($class),
        'PDOOM_THROTTLE_BURST',
    ] as $name) {
        $override = getenv($name);
        if (is_string($override) && is_numeric($override) && (float)$override > 0) {
            $burst = (float)$override;
            // Raise the refill with it, or the bucket empties and never comes
            // back and the override only moves the failure later.
            $perHour = max($perHour, $burst);
            break;
        }
    }

    $dir = $root . '/.throttle';
    if (!is_dir($dir)) {
        @mkdir($dir, 0700, true);
    }
    $path = $dir . '/' . substr($ipHash, 0, 32) . '.json';
    $fh   = @fopen($path, 'c+b');
    if (!$fh) {
        return ['allowed' => true, 'retry_after' => 0, 'note' => 'throttle-state-unavailable'];
    }
    if (!@flock($fh, LOCK_EX)) {
        fclose($fh);
        return ['allowed' => true, 'retry_after' => 0, 'note' => 'throttle-lock-unavailable'];
    }

    $raw   = stream_get_contents($fh);
    $state = json_decode(is_string($raw) ? $raw : '', true);
    if (!is_array($state)) {
        $state = [];
    }
    $now    = microtime(true);
    $bucket = (isset($state[$class]) && is_array($state[$class]))
        ? $state[$class]
        : ['tokens' => $burst, 'ts' => $now];

    $refill = $perHour / 3600.0;
    $elapsed = max(0.0, $now - (float)($bucket['ts'] ?? $now));
    $tokens  = min($burst, (float)($bucket['tokens'] ?? $burst) + $elapsed * $refill);

    $allowed = ($tokens >= 1.0);
    if ($allowed) {
        $tokens -= 1.0;
    }
    $state[$class] = ['tokens' => $tokens, 'ts' => $now];

    @ftruncate($fh, 0);
    @rewind($fh);
    @fwrite($fh, (string)json_encode($state));
    @fflush($fh);
    @flock($fh, LOCK_UN);
    @fclose($fh);

    $retryAfter = 0;
    if (!$allowed) {
        $retryAfter = ($refill > 0) ? (int)max(1, (int)ceil((1.0 - $tokens) / $refill)) : 3600;
    }
    return ['allowed' => $allowed, 'retry_after' => $retryAfter, 'note' => ''];
}

// ---- the durable write ---------------------------------------------------

/**
 * Append one record, contract §3. Returns ['ok' => bool, 'why' => string].
 *
 * fopen(ab) / flock(LOCK_EX) / fwrite / fflush / fsync / flock(LOCK_UN) /
 * fclose. ONLY when every one of those succeeded may a 200 be composed.
 *
 * Two details that are not decoration:
 *
 *   stream_set_write_buffer($fh, 0) -- an unbuffered stream hands the whole
 *   line to one write(2), so a kill between two buffered chunks cannot tear a
 *   record in half. F3 kills this process at sampled offsets across its life.
 *
 *   ftruncate back to the pre-write size -- if fwrite returns short, or fflush
 *   or fsync fails, the bytes already on disk are a partial line, and a partial
 *   line is a corrupt store forever. Rolling back is what makes "no partial
 *   line" true rather than hoped for.
 */
function append_record(string $root, array $rec): array
{
    $line = json_encode($rec, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($line === false) {
        return ['ok' => false, 'why' => 'record could not be encoded'];
    }
    $line .= "\n";
    $want = strlen($line);
    $path = $root . '/' . gmdate('Y-m') . '.jsonl';

    $fh = @fopen($path, 'ab');
    if (!$fh) {
        return ['ok' => false, 'why' => 'store file could not be opened for append'];
    }
    if (function_exists('stream_set_write_buffer')) {
        @stream_set_write_buffer($fh, 0);
    }
    if (!@flock($fh, LOCK_EX)) {
        @fclose($fh);
        return ['ok' => false, 'why' => 'store file could not be locked'];
    }

    $stat   = @fstat($fh);
    $before = (is_array($stat) && isset($stat['size'])) ? (int)$stat['size'] : null;

    $written = @fwrite($fh, $line);
    $ok      = ($written === $want);
    $why     = $ok ? '' : sprintf('short write (%s of %d bytes)', var_export($written, true), $want);

    if ($ok && !@fflush($fh)) {
        $ok  = false;
        $why = 'fflush failed';
    }
    if ($ok && function_exists('fsync')) {
        if (!@fsync($fh)) {
            $ok  = false;
            $why = 'fsync failed';
        }
    }

    if (!$ok) {
        if ($before !== null) {
            @ftruncate($fh, $before);
            @fflush($fh);
        }
        @flock($fh, LOCK_UN);
        @fclose($fh);
        return ['ok' => false, 'why' => $why];
    }

    @flock($fh, LOCK_UN);
    if (!@fclose($fh)) {
        // The bytes are already fsynced, so this is very likely durable -- but
        // "very likely" is not the standard. A 507 costs a duplicate on retry;
        // a wrong 200 costs the message.
        return ['ok' => false, 'why' => 'fclose failed after fsync'];
    }
    return ['ok' => true, 'why' => ''];
}

// ---- notification (derived from a completed write; never the record) ------

/**
 * Send or log the notification. The return value is FOR THE LOG ONLY and can
 * never change the HTTP status -- that is INV-1a, and it is the single
 * behaviour bug-submit.php got backwards.
 *
 * D-3: prose is notified per-item, thumbs are deferred to a digest. A deferred
 * thumb is written to the log as deferred:true so reconcile-feedback.py can
 * tell "batched" from "never notified".
 */
function notify(array $rec, string $root): array
{
    $sink     = getenv('PDOOM_MAIL_SINK');
    $forceBad = (getenv('PDOOM_MAIL_FAIL') === '1');
    $deferred = ($rec['kind'] === 'thumb');

    $entry = [
        'rid'      => $rec['rid'],
        'receipt'  => $rec['receipt'],
        'kind'     => $rec['kind'],
        'ok'       => !$forceBad,
        'deferred' => $deferred,
        'ts'       => time(),
    ];

    if (is_string($sink) && trim($sink) !== '') {
        // Test seam (§11.1). mail() is NOT called.
        $entry['channel'] = 'sink';
        @file_put_contents(
            trim($sink),
            json_encode($entry, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n",
            FILE_APPEND | LOCK_EX
        );
        return $entry;
    }

    if ($deferred) {
        $entry['channel'] = 'digest';
    } else {
        $entry['channel'] = 'mail';
        // Every header component is a constant or comes from a fixed alphabet:
        // KINDS is an allowlist, and the receipt is base32 [A-Z2-7]. No visitor
        // text can reach a header, so there is nothing to escape here.
        $subject = 'p(Doom)1 feedback [' . $rec['kind'] . '] ' . $rec['receipt'];
        $headers = 'From: p(Doom)1 site <' . FROM . ">\r\n"
                 . "MIME-Version: 1.0\r\n"
                 . "Content-Type: text/plain; charset=utf-8\r\n"
                 . "Content-Transfer-Encoding: 8bit\r\n"
                 . 'X-Mailer: pdoom1-ingest';
        // 5th parameter sets the envelope sender, which is the ONLY route to
        // SPF alignment for mail leaving the DreamHost box (contract §5, M5).
        $entry['ok'] = $forceBad ? false : (bool)@mail(
            RECIPIENT, $subject, mail_body($rec), $headers, '-f' . FROM
        );
    }

    $dir = $root . '/notifications';
    if (!is_dir($dir)) {
        @mkdir($dir, 0700, true);
    }
    // .log, NOT .jsonl: `<store>/*.jsonl` means "records" to every reader in
    // this system, and a notification counted as a record is a message nobody
    // sent.
    @file_put_contents(
        $dir . '/' . gmdate('Y-m') . '.log',
        json_encode($entry, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n",
        FILE_APPEND | LOCK_EX
    );
    return $entry;
}

function mail_body(array $rec): string
{
    $flags = $rec['flags'] ? implode(', ', $rec['flags']) : '(none)';
    return "New feedback from pdoom1.com.\n"
        . "----------------------------------------\n"
        . 'Receipt: ' . $rec['receipt'] . "\n"
        . 'Kind:    ' . $rec['kind'] . "\n"
        . 'Page:    ' . $rec['page'] . "\n"
        . 'Value:   ' . (($rec['value'] === null) ? '(n/a)' : (string)$rec['value']) . "\n"
        . 'Contact: ' . (($rec['contact'] === '') ? '(none given)' : $rec['contact']) . "\n"
        . 'Credit:  ' . (($rec['credit'] === '')
            ? '(anonymous -- do NOT name this reporter publicly)'
            : $rec['credit'] . '  <-- OK to credit publicly (reporter opted in)') . "\n"
        . 'Flags:   ' . $flags . "\n"
        . ($rec['flags'] ? "         ^ auto-flagged; likely still a real report -- read it.\n" : '')
        . 'When:    ' . gmdate('Y-m-d H:i:s', (int)$rec['server_ts']) . " UTC\n"
        . "----------------------------------------\n\n"
        . (string)$rec['text'] . "\n\n"
        . "This is a notification. The record of record is the JSONL store; if\n"
        . "this email never arrived, scripts/reconcile-feedback.py will say so.\n";
}

// ---- request -------------------------------------------------------------

function read_body(): string
{
    $raw = file_get_contents('php://input');
    if (!is_string($raw)) {
        $raw = '';
    }
    if ($raw === '' && PHP_SAPI === 'cli') {
        // Measured: php://input is empty under the CLI SAPI. The test harness
        // runs this file under CLI and feeds the body on stdin.
        $stdin = file_get_contents('php://stdin');
        if (is_string($stdin)) {
            $raw = $stdin;
        }
    }
    return $raw;
}

/**
 * Character length, WITHOUT depending on mbstring.
 *
 * mbstring is near-universal but it is an extension, and a hard dependency on
 * an extension is a total loss channel: `Call to undefined function mb_strlen()`
 * is a fatal, and a fatal here means the visitor's message is refused with an
 * unparseable 500 that the client reads as retryable-forever. Measured: the
 * plain PHP 8.3 CLI build used to run the destructive suite has no mbstring.
 * PCRE's /u mode is compiled in, so the fallback is always available.
 */
function char_len(string $s): int
{
    if (function_exists('mb_strlen')) {
        return (int)mb_strlen($s, 'UTF-8');
    }
    $n = @preg_match_all('/./us', $s);
    // preg_match_all returns false only on a PCRE failure; falling back to the
    // byte count then OVER-counts, which rejects a little early rather than
    // storing something over cap. Fail toward refusing, never toward editing.
    return ($n === false) ? strlen($s) : (int)$n;
}

/** First $n characters, mbstring-optional. Used only for the User-Agent. */
function char_head(string $s, int $n): string
{
    if (function_exists('mb_substr')) {
        return (string)mb_substr($s, 0, $n, 'UTF-8');
    }
    $m = [];
    if (@preg_match('/^.{0,' . $n . '}/us', $s, $m) === 1) {
        return $m[0];
    }
    return substr($s, 0, $n);
}

/** Read a capped string field. Returns null when it is over its cap. */
function field(array $data, string $key, int $cap): ?string
{
    $v = $data[$key] ?? '';
    if (is_int($v) || is_float($v)) {
        $v = (string)$v;
    }
    if (!is_string($v)) {
        $v = '';
    }
    // NOT trimmed and NOT stripped of anything. Contract §11.4 forbids storing
    // something the visitor did not say, and json_encode escapes control
    // characters, so nothing here can break the JSONL line format.
    return (char_len($v) > $cap) ? null : $v;
}

// ---- 1. method ----------------------------------------------------------

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    fail(405, 'Method not allowed. POST JSON to this endpoint.', false);
}

// ---- 2. body ------------------------------------------------------------

$raw = read_body();
if (strlen($raw) > MAX_BODY_BYTES) {
    fail(413, 'The request body is larger than ' . MAX_BODY_BYTES . ' bytes.', false);
}

// ---- 3. store: resolve, contain, prove writable -------------------------

$docroot = docroot();
$store   = store_root($docroot);
$root    = $store['path'];

if (trim($root) === '' || path_inside(norm_path($root), norm_path($docroot))) {
    // INV-1c. No fallback: a store inside the docroot is deleted by the next
    // deploy and is publicly fetchable until then.
    fail(507, 'The feedback store is misconfigured (it resolves inside the web '
        . 'root). Your message was NOT stored -- please retry shortly.', true,
        ['store_source' => $store['source']]);
}
if (!ensure_store($root)) {
    fail(507, 'The feedback store is not writable. Your message was NOT stored '
        . '-- it is still on your device, please retry shortly.', true,
        ['store_source' => $store['source']]);
}

// ---- 4. parse -----------------------------------------------------------

$data = json_decode($raw, true);
if (!is_array($data) || (array_values($data) === $data && $data !== [])) {
    // A JSON array is not a request object. json_decode also rejects invalid
    // UTF-8, which is why nothing below has to re-validate encoding.
    fail(400, 'The request body was not a JSON object we could read. Your '
        . 'message is still saved on your device -- please report this.', false);
}

// ---- 5. validate --------------------------------------------------------
// Caps first (413 names the offending field, §11.4), then shape (400).

$text = field($data, 'text', CAP_TEXT);
if ($text === null) {
    fail(413, 'Your text is longer than ' . CAP_TEXT . ' characters. Nothing was '
        . 'stored and nothing was shortened -- please trim it and send again.', false);
}
$contact = field($data, 'contact', CAP_CONTACT);
if ($contact === null) {
    fail(413, 'The contact field is longer than ' . CAP_CONTACT . ' characters.', false);
}
$credit = field($data, 'credit', CAP_CREDIT);
if ($credit === null) {
    fail(413, 'The credit field is longer than ' . CAP_CREDIT . ' characters.', false);
}
$page = field($data, 'page', CAP_PAGE);
if ($page === null) {
    fail(413, 'The page field is longer than ' . CAP_PAGE . ' characters.', false);
}

$rid = $data['rid'] ?? '';
if (!is_string($rid) || !preg_match('/^[A-Za-z0-9._:-]{8,128}$/', $rid)) {
    // §1 says UUIDv4. This check is deliberately WIDER than that: a rid is
    // generated by a client we also ship, and rejecting an unfamiliar-but-usable
    // join key would turn a client bug into a permanently unsendable message.
    // What matters is that it is a stable, printable, bounded identifier.
    fail(400, 'The receipt id (rid) is missing or malformed.', false);
}

$kind = $data['kind'] ?? '';
if (!is_string($kind) || !in_array($kind, KINDS, true)) {
    // REJECTED, never defaulted. bug-submit.php defaulted to 'bug' and its own
    // comments record that this mislabelled every question that came through.
    fail(400, 'Unknown feedback kind. Expected one of: ' . implode(', ', KINDS) . '.', false);
}

if ($page === '' || strncmp($page, '/', 1) !== 0 || strncmp($page, '//', 2) === 0) {
    fail(400, 'The page field must be an origin-relative path beginning with "/".', false);
}

$value = null;
if ($kind === 'thumb') {
    $v = $data['value'] ?? null;
    if (!is_int($v) && !(is_string($v) && ($v === '1' || $v === '-1'))) {
        fail(400, 'A thumb needs value 1 or -1.', false);
    }
    $value = (int)$v;
    if ($value !== 1 && $value !== -1) {
        fail(400, 'A thumb needs value 1 or -1.', false);
    }
} elseif (trim($text) === '') {
    fail(400, 'This kind of feedback needs some text.', false);
}

// ---- 6. spam signals: TAG, never drop (INV-1e) --------------------------

$flags = [];
if (isset($data['hp']) && is_string($data['hp']) && $data['hp'] !== '') {
    $flags[] = 'honeypot';
}
$elapsed = isset($data['elapsed_ms']) && is_numeric($data['elapsed_ms'])
    ? (int)$data['elapsed_ms'] : -1;
$floor = ($kind === 'thumb') ? MIN_FILL_MS_THUMB : MIN_FILL_MS_PROSE;
if ($elapsed >= 0 && $elapsed < $floor) {
    $flags[] = 'too-fast';
}
if (!function_exists('fsync')) {
    // PHP < 8.1 has no fsync and no substitute for it. "Written" then means
    // "visible to a reader on this host", not "survives the power going out".
    // Recorded on the record, because a durability claim nobody can check is
    // exactly the kind of quiet lie this contract exists to stop.
    $flags[] = 'no-fsync';
}

// ---- identity -----------------------------------------------------------

$ip   = (string)($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');
$salt = daily_salt($root);
if ($salt['weak']) {
    $flags[] = 'weak-ip-salt';
}
$ipHash = hash('sha256', $ip . $salt['salt']);   // the raw IP is never kept

// ---- 7. throttle --------------------------------------------------------

$class = in_array($kind, PROSE_KINDS, true) ? 'prose' : 'thumb';
$t     = throttle_check($root, $ipHash, $class);
if (!$t['allowed']) {
    fail(429, 'You are sending faster than we can read. Your message is saved on '
        . 'your device and will go out shortly -- nothing has been lost.', true,
        ['retry_after' => $t['retry_after']]);
}
if ($t['note'] !== '') {
    $flags[] = $t['note'];
}

// ---- 8. the durable write ------------------------------------------------

$serverTs = time();
$ua       = (string)($_SERVER['HTTP_USER_AGENT'] ?? '');
$receipt  = receipt_from_rid($rid);

$rec = [
    'rid'       => $rid,
    'receipt'   => $receipt,
    'kind'      => $kind,
    'page'      => $page,
    'value'     => $value,
    'text'      => $text,
    'contact'   => $contact,
    'credit'    => $credit,
    'flags'     => $flags,
    'server_ts' => $serverTs,
    'client_ts' => (isset($data['client_ts']) && is_numeric($data['client_ts']))
        ? (int)$data['client_ts'] : null,
    'attempt'   => (isset($data['attempt']) && is_numeric($data['attempt']))
        ? (int)$data['attempt'] : null,
    'ip_hash'   => $ipHash,
    // A user-agent is a header, not the visitor's words, so bounding it is not
    // editing what they said.
    'ua'        => (char_len($ua) > 512) ? char_head($ua, 512) : $ua,
    'schema'    => SCHEMA,
];

// NOTE: no duplicate check, on purpose. §3 puts dedup at READ time
// (scripts/read-feedback.py). An index lookup here would be a new failure mode
// standing between a visitor and a durable write, and its failure mode is
// dropping a real message to prevent a cheap duplicate. INV-1e forbids it.
$write = append_record($root, $rec);
if (!$write['ok']) {
    fail(507, 'We could not store your message (' . $write['why'] . '). It is '
        . 'still on your device -- please retry shortly.', true);
}

// ---- 9. notify -- CANNOT change the outcome above -----------------------

notify($rec, $root);

// ---- 10. success, and only now ------------------------------------------

respond(200, [
    'ok'        => true,
    'rid'       => $rid,
    'receipt'   => $receipt,
    'stored_at' => $serverTs,
]);
