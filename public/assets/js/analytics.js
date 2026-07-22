/**
 * Analytics consent shim for the p(Doom)1 website.
 *
 * IMPORTANT -- this file does NOT load an analytics script, and must not.
 * The tracker is the self-hosted Plausible tag hardcoded into every page's
 * <head>:
 *     https://analytics.pdoom1.com/js/script.<extensions>.js
 *
 * History (the bug this file used to be): this module injected a SECOND
 * tracker from plausible.io (the CLOUD service, where pdoom1.com is not a
 * registered site). Plausible's tracker overwrites window.plausible on load,
 * so whichever script landed last won. Roughly half the time the cloud one
 * won and every custom event -- crucially the Download events on the
 * homepage -- was posted to plausible.io and silently discarded. Pageviews
 * were unaffected because each tracker fires its own before being clobbered.
 * Do not reintroduce script injection here.
 *
 * What this file DOES do is own the opt-out, by driving the one flag the real
 * tracker reads on every call: localStorage.plausible_ignore === 'true'.
 * The previous code wrote a different key (pdoom1_analytics_optout), so the
 * privacy page's opt-out button set a flag nothing consumed.
 */

(function () {
  'use strict';

  // The key the Plausible tracker itself checks. Non-negotiable -- it is
  // defined by the tracker, not by us.
  var PLAUSIBLE_IGNORE_KEY = 'plausible_ignore';

  // Our own record of an EXPLICIT user choice. Kept separate from the key
  // above so that a Do-Not-Track-derived opt-out can be undone when the
  // browser stops sending DNT, while an explicit opt-out persists.
  var EXPLICIT_OPTOUT_KEY = 'pdoom1_analytics_optout';

  function read(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      return null; // Private mode / storage disabled.
    }
  }

  function write(key, value) {
    try {
      if (value === null) {
        localStorage.removeItem(key);
      } else {
        localStorage.setItem(key, value);
      }
      return true;
    } catch (e) {
      return false;
    }
  }

  function isDNTEnabled() {
    return navigator.doNotTrack === '1' ||
           navigator.doNotTrack === 'yes' ||
           window.doNotTrack === '1';
  }

  function hasExplicitlyOptedOut() {
    return read(EXPLICIT_OPTOUT_KEY) === 'true';
  }

  function isOptedOut() {
    return hasExplicitlyOptedOut() || isDNTEnabled();
  }

  /**
   * Reconcile the tracker's flag with the current intent. Runs on every page
   * load, BEFORE the deferred <head> tracker executes -- this script is a
   * plain (non-deferred) tag, so it runs during parse while deferred scripts
   * wait for parsing to finish. That ordering is what makes honouring DNT
   * real rather than decorative: the flag is set before the pageview fires.
   */
  function sync() {
    if (isOptedOut()) {
      write(PLAUSIBLE_IGNORE_KEY, 'true');
    } else if (read(PLAUSIBLE_IGNORE_KEY) === 'true') {
      // Only clear a flag we would have set ourselves; if the visitor opted
      // out explicitly, hasExplicitlyOptedOut() above already kept it set.
      write(PLAUSIBLE_IGNORE_KEY, null);
    }
  }

  function optOut() {
    var ok = write(EXPLICIT_OPTOUT_KEY, 'true');
    sync();
    return ok;
  }

  function optIn() {
    var ok = write(EXPLICIT_OPTOUT_KEY, null);
    sync();
    return ok;
  }

  /**
   * Fire a custom event through the real (self-hosted) tracker.
   * No-ops safely if the visitor opted out or the tracker was blocked.
   */
  function trackEvent(eventName, props) {
    if (isOptedOut()) {
      return false;
    }
    if (typeof window.plausible === 'function') {
      window.plausible(eventName, { props: props || {} });
      return true;
    }
    return false;
  }

  window.pdoom1Analytics = {
    optOut: optOut,
    optIn: optIn,
    hasOptedOut: isOptedOut,
    isDNTEnabled: isDNTEnabled,
    trackEvent: trackEvent
  };

  sync();
})();
