/**
 * Privacy-Preserving Analytics Integration
 * 
 * This module provides a lightweight, privacy-first analytics solution
 * for the p(Doom)1 website. It uses Plausible Analytics by default.
 * 
 * Features:
 * - No cookies
 * - No personal data collection
 * - GDPR compliant by default
 * - Respects Do Not Track
 * - Easy opt-out mechanism
 */

(function() {
  'use strict';

  const ANALYTICS_CONFIG = {
    enabled: true,
    dataDomain: 'pdoom1.com',
    scriptUrl: 'https://plausible.io/js/script.js',
    optOutKey: 'pdoom1_analytics_optout'
  };

  /**
   * Check if user has opted out of analytics
   */
  function hasOptedOut() {
    try {
      return localStorage.getItem(ANALYTICS_CONFIG.optOutKey) === 'true';
    } catch (e) {
      return false;
    }
  }

  /**
   * Check if Do Not Track is enabled
   */
  function isDNTEnabled() {
    return navigator.doNotTrack === '1' || 
           navigator.doNotTrack === 'yes' ||
           window.doNotTrack === '1';
  }

  /**
   * Initialize analytics if user hasn't opted out
   */
  function initAnalytics() {
    // Respect user preferences
    if (hasOptedOut()) {
      console.log('[Analytics] User has opted out - analytics disabled');
      return;
    }

    // Respect Do Not Track
    if (isDNTEnabled()) {
      console.log('[Analytics] Do Not Track enabled - analytics disabled');
      return;
    }

    // Load Plausible script
    if (ANALYTICS_CONFIG.enabled) {
      const script = document.createElement('script');
      script.defer = true;
      script.setAttribute('data-domain', ANALYTICS_CONFIG.dataDomain);
      script.src = ANALYTICS_CONFIG.scriptUrl;
      
      script.onerror = function() {
        console.warn('[Analytics] Failed to load analytics script');
      };
      
      document.head.appendChild(script);
      console.log('[Analytics] Privacy-preserving analytics initialized');
    }
  }

  /**
   * Opt out of analytics
   */
  function optOut() {
    try {
      localStorage.setItem(ANALYTICS_CONFIG.optOutKey, 'true');
      console.log('[Analytics] Successfully opted out');
      return true;
    } catch (e) {
      console.error('[Analytics] Failed to opt out:', e);
      return false;
    }
  }

  /**
   * Opt back in to analytics
   */
  function optIn() {
    try {
      localStorage.removeItem(ANALYTICS_CONFIG.optOutKey);
      console.log('[Analytics] Successfully opted in');
      return true;
    } catch (e) {
      console.error('[Analytics] Failed to opt in:', e);
      return false;
    }
  }

  /**
   * Track custom event (if Plausible is loaded)
   */
  function trackEvent(eventName, props) {
    if (hasOptedOut() || isDNTEnabled()) {
      return;
    }

    if (typeof window.plausible !== 'undefined') {
      window.plausible(eventName, { props: props });
    }
  }

  // Expose public API
  window.pdoom1Analytics = {
    optOut: optOut,
    optIn: optIn,
    hasOptedOut: hasOptedOut,
    trackEvent: trackEvent
  };

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAnalytics);
  } else {
    initAnalytics();
  }
})();
