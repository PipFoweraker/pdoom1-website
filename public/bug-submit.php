<?php
/**
 * Bug / feedback intake for pdoom1.com.
 *
 * Receives a JSON POST from public/bug-report/index.html and emails it to the
 * team. Primary path; the form falls back to a prefilled GitHub issue if this
 * ever fails, so a report is never lost.
 *
 * SECURITY POSTURE
 * - The recipient is HARDCODED (below). It is never taken from user input, so
 *   this cannot be turned into an open relay to spam third parties -- the worst
 *   an attacker gets is spam into our own inbox, which the guards below blunt.
 * - All user-supplied text goes in the email BODY only; every header (To, From,
 *   Subject) is a constant. That removes email-header-injection entirely.
 * - Spam guards: a honeypot field, a minimum fill-time, and a per-IP throttle.
 *
 * Runs on DreamHost shared hosting (PHP + mail()). PHP source is executed, not
 * served, so nothing here is visible to a browser.
 */

// ---- config -------------------------------------------------------------
const RECIPIENT   = 'team@pdoom1.com';      // hardcoded on purpose (see above)
// FROM is the same domain as RECIPIENT.
//
// UPDATED 2026-08-17 ~08:53 AEST -- the SPF record LANDED, which this comment
// asked to be recorded here with its verification date. Published in the
// DreamHost panel and confirmed against all three DreamHost nameservers plus
// 8.8.8.8, 1.1.1.1 and 9.9.9.9:
//
//   pdoom1.com          TXT  v=spf1 include:_spf.google.com include:netblocks.dreamhost.com ~all
//   _dmarc.pdoom1.com   TXT  v=DMARC1; p=none; rua=mailto:team@pdoom1.com
//
// Do NOT read that as "the domain now passes". Two corrections to what this
// comment said before, both from the headers of a real delivered message
// (Message-Id 4hNWYX273Bz13YTW, 2026-08-17 08:56 AEST):
//
// 1. "same domain -> passes SPF" was and remains WRONG, and publishing a record
//    does not make it right. SPF authorises the sending IP for the ENVELOPE
//    domain. With no 5th parameter on mail() the envelope sender is
//    pdoom1_dot_com_shell@iad1-shared-b8-18.dreamhost.com, so Google returned
//    `spf=pass` -- for DreamHost -- and `dmarc=fail`, because that domain does
//    not align with the pdoom1.com From: header built below. The fix is the -f
//    parameter at the mail() call, not the DNS record alone.
//
// 2. "mail() succeeds and nothing is delivered" is too strong. Two test
//    messages on 2026-08-17 were DELIVERED to the inbox, each carrying Gmail's
//    yellow "appears to be sent from your account but Gmail couldn't verify
//    this" banner. Delivered-with-a-spoof-warning is a different failure from
//    silently-dropped, and it is the one that is actually observed. What
//    happened to submissions before that date is not established here.
//
// Tracked as pdoom1-website#321. Do not restore the pre-#321 comment.
const FROM        = 'team@pdoom1.com';
const MIN_FILL_MS = 3000;                    // faster than this = a bot
const THROTTLE_S  = 30;                      // seconds between reports per IP
const MAX_TITLE   = 200;
const MAX_DESC    = 5000;
const MAX_EMAIL   = 200;
const MAX_CREDIT  = 80;                      // name the reporter wants crediting as
const MAX_ATTACH_BYTES = 550 * 1024;         // decoded cap; client caps the file at 500 KB
// Allowlist for the `type` key. An unknown value falls back to 'bug' below, which
// is safe but MISLABELS: /issues/ offers "General Feedback" and "Question", and
// both would have arrived subject-lined "p(Doom)1 bug: ...". 'feedback' and
// 'question' were added 2026-08-11 when that form was wired to this endpoint.
// The value only ever reaches the subject line and the body, both after the
// in_array() check, so widening the list adds no injection surface.
const TYPES       = ['bug', 'feature', 'documentation', 'performance', 'feedback', 'question'];

header('Content-Type: application/json; charset=utf-8');

/**
 * Append-only record of every submission this endpoint ACCEPTS.
 *
 * WHY. `mail()` returning true is a handoff receipt from the local MTA, not a
 * delivery confirmation -- delivery to Google happens afterwards and can fail
 * silently, which is exactly what has been happening since at least
 * 2026-07-24. Without this log a lost report is not merely undelivered, it is
 * unrecoverable and invisible: we never learn the sender existed.
 *
 * WHERE. Deliberately OUTSIDE the document root. `public/` IS the docroot on
 * DreamHost and is deployed with `rsync --delete`, so anything written inside
 * it would be both world-readable and erased by the next deploy. The parent
 * directory is neither served nor rsynced.
 *
 * This is a recovery log, not a mailbox. It holds what the reporter typed,
 * including their email if they gave one, so it is created 0700 and carries a
 * deny-all .htaccess in case it is ever relocated somewhere that is served.
 * NOTE: nothing here rotates or expires it. That is a deliberate omission --
 * silent deletion is the failure this file exists to prevent -- but it means
 * retention is an open question, not a solved one.
 */
function submission_log(array $record): void {
    $dir = dirname(__DIR__) . '/feedback-log';
    if (!is_dir($dir)) {
        @mkdir($dir, 0700, true);
        @file_put_contents($dir . '/.htaccess', "Require all denied\n");
    }
    $line = json_encode($record, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if ($line === false) {
        $line = json_encode(['id' => $record['id'] ?? '?',
                             'error' => 'record was not JSON-encodable']);
    }
    // LOCK_EX so two concurrent submissions cannot interleave a half-line.
    @file_put_contents($dir . '/' . gmdate('Y-m') . '.jsonl',
                       $line . "\n", FILE_APPEND | LOCK_EX);
}

function done(int $code, array $payload): void {
    http_response_code($code);
    echo json_encode($payload);
    exit;
}

// ---- method -------------------------------------------------------------
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    done(405, ['ok' => false, 'error' => 'Method not allowed']);
}

// ---- parse --------------------------------------------------------------
$raw = file_get_contents('php://input');
if ($raw === false || strlen($raw) > 800 * 1024) {   // generous cap; attachments are base64
    done(413, ['ok' => false, 'error' => 'Request too large']);
}
$data = json_decode($raw, true);
if (!is_array($data)) {
    done(400, ['ok' => false, 'error' => 'Malformed request']);
}

// ---- rate limit ---------------------------------------------------------
// Throttle FIRST, so nothing below (which now emails rather than drops) can be
// used to flood the inbox: at most one report per IP per THROTTLE_S seconds.
$ip = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
$throttle = sys_get_temp_dir() . '/pdoom_bug_' . hash('sha256', $ip);
$now = time();
if (is_file($throttle) && ($now - (int)@file_get_contents($throttle)) < THROTTLE_S) {
    done(429, ['ok' => false, 'error' => 'Please wait a moment before sending another report.']);
}
@file_put_contents($throttle, (string)$now);

// ---- spam signals -> FLAG, never silently drop --------------------------
// A silently-dropped report is indistinguishable from success to the sender, so
// a legit fast typer, a prefilled paste, or a browser that autofills the honeypot
// used to vanish with no trace -- and we couldn't even tell which guard fired.
// Now a tripped signal only TAGS the report; it still reaches the inbox, and the
// tag names the reason (with the raw elapsed_ms) so the cause is visible next time.
$flags = [];
if (!empty($data['hp'])) {
    $flags[] = 'honeypot hidden field was filled (a bot, or an over-eager autofill)';
}
$elapsed = isset($data['elapsed_ms']) ? (int)$data['elapsed_ms'] : -1;
if ($elapsed >= 0 && $elapsed < MIN_FILL_MS) {
    $flags[] = "submitted in {$elapsed}ms (under " . MIN_FILL_MS . "ms -- a bot, or a very fast/prefilled human)";
}

// ---- validate + normalise ----------------------------------------------
$clean = static function ($v, int $max): string {
    $v = is_string($v) ? $v : '';
    // strip control chars except tab/newline; trim; cap length
    $v = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', '', $v);
    return mb_substr(trim($v), 0, $max);
};

$title = $clean($data['title'] ?? '', MAX_TITLE);
$desc  = $clean($data['description'] ?? '', MAX_DESC);
$type  = in_array($data['type'] ?? '', TYPES, true) ? $data['type'] : 'bug';
$email = $clean($data['email'] ?? '', MAX_EMAIL);
$email = ($email !== '' && filter_var($email, FILTER_VALIDATE_EMAIL)) ? $email : '';
// Opt-in credit name. Unlike $email this MAY be published, so it is labelled
// explicitly in the mail -- whoever writes the release notes must be able to tell
// at a glance that consent was given, and never mine the Contact line for a name.
$credit = $clean($data['credit_name'] ?? '', MAX_CREDIT);

if ($title === '' || $desc === '') {
    done(422, ['ok' => false, 'error' => 'A title and description are required.']);
}

// ---- attachment (optional) ---------------------------------------------
// The client base64-encodes the picked file into attachment.content. We decode
// it, hard-cap the size, and sanitise the filename to inert characters (no CR/LF
// or quotes -> no header injection, no path traversal), then MIME-attach it. The
// bytes are inert in an email and Gmail scans attachments on receipt; we never
// execute, store, or trust the declared type -- everything is octet-stream.
$att = $data['attachment'] ?? null;
$attBytes = '';
$attName = '';
if (is_array($att) && !empty($att['content']) && is_string($att['content'])) {
    $attName = preg_replace('/[^\w.\- ]+/u', '_', basename($clean($att['filename'] ?? 'attachment', 120)));
    if ($attName === '') { $attName = 'attachment'; }
    $decoded = base64_decode(preg_replace('/\s+/', '', $att['content']), true);
    if ($decoded !== false && $decoded !== '' && strlen($decoded) <= MAX_ATTACH_BYTES) {
        $attBytes = $decoded;
    }
}
$hasAttachment = ($attBytes !== '');
$attNote = $hasAttachment
    ? "\n\nAttachment: \"$attName\" (" . strlen($attBytes) . " bytes) is attached to this email."
    : (isset($att['filename'])
        ? "\n\nAttachment: reporter picked \"" . $clean($att['filename'] ?? '', 120)
          . "\" but it could not be attached (too large or unreadable) -- reply to ask for it."
        : '');

// ---- compose (all user text in the BODY; headers are constants) ---------
$subject = 'p(Doom)1 ' . $type . ($flags ? ' [REVIEW]' : '') . ': ' . mb_substr($title, 0, 80);
$subject = str_replace(["\r", "\n"], ' ', $subject);   // belt-and-braces

$textBody = "New feedback from the pdoom1.com bug form.\n"
      . "----------------------------------------\n"
      . "Type:    $type\n"
      . "Title:   $title\n"
      . "Contact: " . ($email !== '' ? $email : '(none given)') . "\n"
      . "Credit:  " . ($credit !== ''
            ? $credit . '  <-- OK to credit publicly (reporter opted in)'
            : '(anonymous -- do NOT name this reporter publicly)') . "\n"
      . "When:    " . gmdate('Y-m-d H:i:s') . " UTC\n"
      . ($flags ? "Flags:   " . implode("\n         ", $flags)
                  . "\n         ^ auto-flagged; likely still a real report -- read it.\n" : "")
      . "----------------------------------------\n\n"
      . $desc
      . $attNote . "\n";

if ($hasAttachment) {
    // multipart/mixed: the text report + the file, in one email.
    $boundary = '=_pdoom_' . bin2hex(random_bytes(12));
    $headers = 'From: p(Doom)1 site <' . FROM . ">\r\n"
             . "MIME-Version: 1.0\r\n"
             . 'Content-Type: multipart/mixed; boundary="' . $boundary . '"' . "\r\n"
             . 'X-Mailer: pdoom1-bug-form';
    $body = "--$boundary\r\n"
          . "Content-Type: text/plain; charset=utf-8\r\n"
          . "Content-Transfer-Encoding: 8bit\r\n\r\n"
          . $textBody . "\r\n"
          . "--$boundary\r\n"
          . "Content-Type: application/octet-stream; name=\"$attName\"\r\n"
          . "Content-Transfer-Encoding: base64\r\n"
          . "Content-Disposition: attachment; filename=\"$attName\"\r\n\r\n"
          . chunk_split(base64_encode($attBytes)) . "\r\n"
          . "--$boundary--\r\n";
} else {
    $headers = 'From: p(Doom)1 site <' . FROM . ">\r\n"
             . 'Content-Type: text/plain; charset=utf-8' . "\r\n"
             . 'X-Mailer: pdoom1-bug-form';
    $body = $textBody;
}

// Record BEFORE sending. If mail() throws, dies, or the process is killed, the
// submission still survives on disk -- which is the entire point. The outcome
// is appended as a second line keyed by the same id, so the pair is
// append-only and neither write depends on the other succeeding.
$submissionId = bin2hex(random_bytes(8));
submission_log([
    'id'        => $submissionId,
    'at'        => gmdate('c'),
    'event'     => 'accepted',
    'type'      => $type,
    'title'     => $title,
    'body'      => $desc,
    'email'     => $email,
    'credit'    => $credit,
    'flags'     => $flags,
    'attach'    => $attName,
    'ip_hash'   => hash('sha256', $ip),   // hashed: enough to correlate, not to identify
    'ua'        => mb_substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 200),
]);

// The 5th parameter is what makes this mail capable of passing DMARC, and it
// only became useful once the SPF record above existed. Measured on a real
// delivered message 2026-08-17: without it the envelope sender is
// pdoom1_dot_com_shell@iad1-shared-b8-18.dreamhost.com, so Google reports
// `spf=pass ... dmarc=fail (p=NONE dis=NONE) header.from=pdoom1.com` and shows
// the recipient a spoof warning on the site's own feedback mail.
//
// `-f team@pdoom1.com` puts the envelope domain on pdoom1.com, so SPF is
// evaluated against OUR record -- which carries include:netblocks.dreamhost.com,
// covering the relay 208.113.156.243 that Google actually authenticated -- and
// the pass then aligns with the From: header.
//
// Safe on this host: the MTA is Postfix (`Received: ... (Postfix, from userid
// 6835806)`), whose sendmail wrapper honours -f without adding the
// X-Authentication-Warning header a real sendmail adds for an untrusted user.
$sent = @mail(RECIPIENT, $subject, $body, $headers, '-f ' . FROM);

submission_log([
    'id'    => $submissionId,
    'at'    => gmdate('c'),
    'event' => 'handoff',
    // NOT "delivered". mail() only reports that the local MTA accepted it.
    'mail_accepted_by_local_mta' => (bool)$sent,
]);

if ($sent) {
    done(200, ['ok' => true]);
}
done(502, ['ok' => false, 'error' => 'Could not send. Please use the GitHub option below.']);
