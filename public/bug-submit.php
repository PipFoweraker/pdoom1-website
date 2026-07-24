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
const FROM        = 'team@pdoom1.com';      // same domain -> passes SPF on DreamHost
const MIN_FILL_MS = 3000;                    // faster than this = a bot
const THROTTLE_S  = 30;                      // seconds between reports per IP
const MAX_TITLE   = 200;
const MAX_DESC    = 5000;
const MAX_EMAIL   = 200;
const MAX_CREDIT  = 80;                      // name the reporter wants crediting as
const TYPES       = ['bug', 'feature', 'documentation', 'performance'];

header('Content-Type: application/json; charset=utf-8');

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

// ---- spam guards --------------------------------------------------------
// Honeypot: a hidden field real users never fill. If it's set, pretend success
// so the bot moves on and doesn't probe for the real behaviour.
if (!empty($data['hp'])) {
    done(200, ['ok' => true]);
}
// Time-trap: a human takes seconds to write a report; a bot posts instantly.
if (isset($data['elapsed_ms']) && (int)$data['elapsed_ms'] < MIN_FILL_MS) {
    done(200, ['ok' => true]);
}
// Per-IP throttle. Recipient is fixed, so this only limits inbox spam volume.
$ip = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
$throttle = sys_get_temp_dir() . '/pdoom_bug_' . hash('sha256', $ip);
$now = time();
if (is_file($throttle) && ($now - (int)@file_get_contents($throttle)) < THROTTLE_S) {
    done(429, ['ok' => false, 'error' => 'Please wait a moment before sending another report.']);
}
@file_put_contents($throttle, (string)$now);

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

$hasAttachment = isset($data['attachment']['filename']);
$attNote = $hasAttachment
    ? "\n\nAttachment: reporter attached \"" . $clean($data['attachment']['filename'], 120)
      . "\" (" . (int)($data['attachment']['size'] ?? 0) . " bytes) -- not forwarded by email; "
      . "reply to ask for it, or they can re-file on GitHub with the file attached."
    : '';

// ---- compose (all user text in the BODY; headers are constants) ---------
$subject = 'p(Doom)1 ' . $type . ': ' . mb_substr($title, 0, 80);
$subject = str_replace(["\r", "\n"], ' ', $subject);   // belt-and-braces

$body = "New feedback from the pdoom1.com bug form.\n"
      . "----------------------------------------\n"
      . "Type:    $type\n"
      . "Title:   $title\n"
      . "Contact: " . ($email !== '' ? $email : '(none given)') . "\n"
      . "Credit:  " . ($credit !== ''
            ? $credit . '  <-- OK to credit publicly (reporter opted in)'
            : '(anonymous -- do NOT name this reporter publicly)') . "\n"
      . "When:    " . gmdate('Y-m-d H:i:s') . " UTC\n"
      . "----------------------------------------\n\n"
      . $desc
      . $attNote . "\n";

$headers = 'From: p(Doom)1 site <' . FROM . ">\r\n"
         . 'Content-Type: text/plain; charset=utf-8' . "\r\n"
         . 'X-Mailer: pdoom1-bug-form';

$sent = @mail(RECIPIENT, $subject, $body, $headers);

if ($sent) {
    done(200, ['ok' => true]);
}
done(502, ['ok' => false, 'error' => 'Could not send. Please use the GitHub option below.']);
