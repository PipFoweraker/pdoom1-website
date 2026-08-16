<?php
/**
 * Runs public/ingest.php under the CLI SAPI and reports what a web SAPI would
 * have returned, as one JSON envelope on stdout.
 *
 * This exists so the destructive suite needs NO web server, NO open port and NO
 * network. The alternative -- `php -S 127.0.0.1:PORT` -- is more faithful but
 * adds a listening socket, a race on startup, and a port that can already be in
 * use, i.e. three new ways for a test to be flaky about something other than the
 * thing under test.
 *
 * KNOWN LIMITATION, stated rather than hidden: under CLI, header() is a no-op and
 * headers_list() returns nothing, so response headers are NOT observable here.
 * The suite therefore asserts Content-Type nowhere and asserts body-parses-as-JSON
 * everywhere instead. http_response_code() DOES work as a getter/setter in CLI.
 * If a row ever needs real headers, run the suite against `php -S` and set
 * PDOOM_INGEST_ENDPOINT accordingly -- do not weaken the assertion.
 *
 * Usage (from scripts/fixtures/ingest_harness.py):
 *   php php_cli_shim.php <path-to-endpoint>   < request-body   > envelope
 */

if ($argc < 2) {
    fwrite(STDERR, "usage: php_cli_shim.php <endpoint.php>\n");
    exit(2);
}
$endpoint = $argv[1];
if (!is_file($endpoint)) {
    fwrite(STDERR, "no such endpoint: $endpoint\n");
    exit(2);
}

$_SERVER['REQUEST_METHOD']  = 'POST';
$_SERVER['CONTENT_TYPE']    = 'application/json';
$_SERVER['DOCUMENT_ROOT']   = getenv('PDOOM_DOCROOT') ?: dirname(dirname(__DIR__)) . '/public';
$_SERVER['REMOTE_ADDR']     = getenv('PDOOM_REMOTE_ADDR') ?: '127.0.0.1';
$_SERVER['HTTP_USER_AGENT'] = getenv('PDOOM_HTTP_USER_AGENT') ?: '';
$_SERVER['SCRIPT_FILENAME'] = $endpoint;
$_SERVER['REQUEST_URI']     = '/ingest.php';

// Emitted from a shutdown function so that an endpoint which calls exit() -- the
// normal way a PHP endpoint returns early -- is still reported rather than
// swallowed. Shutdown functions run before output buffers are flushed.
register_shutdown_function(function () {
    $body = ob_get_clean();
    if ($body === false) { $body = ''; }
    $fatal = error_get_last();
    if ($fatal !== null && in_array($fatal['type'], array(E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR), true)) {
        // A fatal is not a response. Report it as one so the suite sees a crash
        // rather than a plausible-looking empty 200.
        fwrite(STDERR, $fatal['message'] . ' in ' . $fatal['file'] . ':' . $fatal['line'] . "\n");
        fwrite(STDOUT, '');
        return;
    }
    $envelope = array(
        'status'  => http_response_code() ?: 200,
        'headers' => array(),   // see KNOWN LIMITATION above
        'body'    => $body,
    );
    fwrite(STDOUT, json_encode($envelope, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
});

ob_start();
require $endpoint;
