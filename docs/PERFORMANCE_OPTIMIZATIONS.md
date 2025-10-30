# Performance Optimization Plan for p(Doom)1 Website

**Priority:** High
**Impact:** Page load speed, user experience, SEO
**Effort:** 1-2 days implementation

---

## 🎯 Current Issues

1. ⚠️ **White background flash** on loading elements - FIXED ✅
2. ⚠️ **No lazy loading** for images/iframes
3. ⚠️ **Critical CSS not inlined**
4. ⚠️ **JavaScript blocks rendering**
5. ⚠️ **No resource hints** (preconnect, prefetch)
6. ⚠️ **Large inline styles** repeated across pages

---

## ✅ Quick Wins (Implemented)

### 1. Fixed White Background Flash
**Problem:** Loading placeholders had white backgrounds before JavaScript loaded
**Solution:** Added explicit `background: transparent !important` to:
- `.loading-number`
- `.loading-placeholder`
- `.stat-number`

**Impact:** Eliminated jarring white flash on page load

---

## 🚀 Performance Optimizations to Implement

### 1. Lazy Loading Images

**Current:** All images load immediately
**Target:** Load images only when visible

```html
<!-- Before -->
<img src="assets/screenshot-placeholder-main.svg" alt="Game interface">

<!-- After -->
<img src="assets/screenshot-placeholder-main.svg"
     alt="Game interface"
     loading="lazy"
     decoding="async">
```

**Files to Update:**
- `public/index.html` - All `<img>` tags
- `public/issues/index.html`
- `public/resources/index.html`
- `public/frontier-labs/index.html`

**Estimated Savings:** 30-50% faster initial page load

---

### 2. Preconnect to External Domains

**Current:** No resource hints
**Target:** DNS prefetch and preconnect for external resources

```html
<head>
  <!-- Preconnect to external APIs -->
  <link rel="preconnect" href="https://api.github.com">
  <link rel="dns-prefetch" href="https://api.github.com">

  <!-- Preconnect to external resources -->
  <link rel="preconnect" href="https://stampy.ai">
  <link rel="dns-prefetch" href="https://stampy.ai">
</head>
```

**Estimated Savings:** 100-300ms on external API calls

---

### 3. Defer Non-Critical JavaScript

**Current:** Large JavaScript blocks in `<script>` tags
**Target:** Defer execution until after page load

```html
<!-- Move all <script> tags to bottom of body -->
<!-- OR add defer attribute -->
<script defer>
  // Non-critical JS here
</script>
```

**Files to Update:**
- All JavaScript for tabs, dropdowns, version loading
- Move to separate file: `/assets/js/main.js`
- Add `defer` attribute

**Estimated Savings:** 200-500ms faster First Contentful Paint

---

### 4. Critical CSS Inline

**Current:** All CSS in one large `<style>` block
**Target:** Inline only above-the-fold CSS

**Approach:**
1. Extract critical CSS (hero, header, nav) → inline
2. Move rest to `/css/site.css` → load async
3. Use `media="print" onload="this.media='all'"` trick

```html
<head>
  <!-- Critical CSS inline -->
  <style>
    /* Only hero, header, nav styles */
  </style>

  <!-- Non-critical CSS async -->
  <link rel="stylesheet" href="/css/site.css" media="print" onload="this.media='all'">
  <noscript><link rel="stylesheet" href="/css/site.css"></noscript>
</head>
```

**Estimated Savings:** 100-200ms faster First Contentful Paint

---

### 5. Compress and Minify

**Current:** Uncompressed HTML/CSS/JS
**Target:** Gzip/Brotli compression + minification

**Implementation (Netlify):**
```toml
# netlify.toml
[build.processing.css]
  bundle = true
  minify = true

[build.processing.js]
  bundle = true
  minify = true

[build.processing.html]
  pretty_urls = true
  minify = true
```

**Estimated Savings:** 50-70% file size reduction

---

### 6. Add Service Worker for Caching

**Current:** No offline support
**Target:** Cache static assets for repeat visits

```javascript
// /sw.js
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('pdoom1-v1').then((cache) => {
      return cache.addAll([
        '/',
        '/css/site.css',
        '/assets/js/main.js',
        '/favicon.svg'
      ]);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
```

**Register in HTML:**
```html
<script>
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}
</script>
```

**Estimated Savings:** Instant page loads on repeat visits

---

### 7. Optimize Font Loading

**Current:** System font only (Courier New)
**Target:** Already optimal! But add font-display if custom fonts added

```css
/* If adding custom fonts later */
@font-face {
  font-family: 'CustomFont';
  src: url('/fonts/custom.woff2');
  font-display: swap; /* Prevents invisible text */
}
```

**Status:** No action needed (using system fonts)

---

### 8. Reduce JavaScript Payload

**Current:** Inline JS in every page
**Target:** Extract to external file + remove duplicates

**Extract these to `/assets/js/main.js`:**
- Dropdown menu functionality
- Tab switching
- Version info loader
- Quick actions menu
- Newsletter form handler

**Estimated Savings:** 10-15KB reduction per page

---

### 9. Image Optimization

**Current:** SVG placeholders (already optimal)
**Target:** When adding real screenshots:
- Use WebP format with JPEG fallback
- Responsive images with `<picture>` element
- Appropriate sizing (no 4K images for 400px display)

```html
<picture>
  <source srcset="screenshot.webp" type="image/webp">
  <source srcset="screenshot.jpg" type="image/jpeg">
  <img src="screenshot.jpg" alt="Game screenshot" loading="lazy">
</picture>
```

**Status:** Future consideration when adding real screenshots

---

### 10. Prefetch Next Pages

**Current:** No prefetching
**Target:** Prefetch likely next pages

```html
<!-- On homepage -->
<link rel="prefetch" href="/issues/">
<link rel="prefetch" href="/game-stats/">
<link rel="prefetch" href="/resources/">
```

**Estimated Savings:** Instant navigation to prefetched pages

---

## 📊 Expected Performance Improvements

### Current (Estimated)
- **First Contentful Paint:** 1.5-2.0s
- **Time to Interactive:** 2.5-3.0s
- **Total Page Size:** 150-200KB
- **Lighthouse Score:** ~75-85

### Target (After Optimizations)
- **First Contentful Paint:** 0.8-1.2s (40% improvement)
- **Time to Interactive:** 1.2-1.8s (50% improvement)
- **Total Page Size:** 80-120KB (40% reduction)
- **Lighthouse Score:** ~90-95 (A rating)

---

## 🛠️ Implementation Priority

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Fix white background flash
2. Add `loading="lazy"` to all images
3. Add preconnect hints
4. Add defer to JavaScript

### Phase 2: Medium Effort (4-6 hours)
1. Extract JavaScript to external file
2. Implement critical CSS inline
3. Set up Netlify compression

### Phase 3: Advanced (8-12 hours)
1. Service Worker for caching
2. Prefetch strategies
3. Performance monitoring setup
4. A/B testing framework

---

## 📋 Implementation Checklist

### Quick Wins
- [x] White background flash fixed
- [ ] All images have `loading="lazy"`
- [ ] Preconnect hints added
- [ ] JavaScript deferred
- [ ] Netlify compression enabled

### Medium Effort
- [ ] JavaScript extracted to `/assets/js/main.js`
- [ ] Critical CSS inlined
- [ ] Non-critical CSS async loaded
- [ ] Minification enabled

### Advanced
- [ ] Service Worker implemented
- [ ] Prefetch hints added
- [ ] Lighthouse score >90
- [ ] Real User Monitoring setup

---

## 🔧 Code Examples

### Lazy Loading All Images
```bash
# Find all img tags
grep -r '<img' public/*.html

# Add loading="lazy" decoding="async" to each
```

**Script to automate:**
```python
import re
import glob

def add_lazy_loading(html_content):
    # Add loading="lazy" to img tags that don't have it
    pattern = r'<img(?![^>]*loading=)([^>]*)(>)'
    replacement = r'<img\1 loading="lazy" decoding="async"\2'
    return re.sub(pattern, replacement, html_content)

for file in glob.glob('public/**/*.html', recursive=True):
    with open(file, 'r') as f:
        content = f.read()

    updated = add_lazy_loading(content)

    with open(file, 'w') as f:
        f.write(updated)
```

---

### Extract Inline JS to External File

**Create `/public/assets/js/main.js`:**
```javascript
// Dropdown menu functionality
function initDropdowns() {
  document.querySelectorAll('.dropdown-toggle').forEach(toggle => {
    toggle.addEventListener('click', function(e) {
      e.preventDefault();
      const dropdown = this.closest('.dropdown');
      const isExpanded = this.getAttribute('aria-expanded') === 'true';

      // Close all other dropdowns
      document.querySelectorAll('.dropdown-toggle').forEach(other => {
        other.setAttribute('aria-expanded', 'false');
      });

      // Toggle current dropdown
      this.setAttribute('aria-expanded', !isExpanded);
    });
  });
}

// Tab switching
function initTabs() {
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const tabName = button.getAttribute('data-tab');

      // Remove active class
      tabButtons.forEach(btn => {
        btn.classList.remove('active');
        btn.style.background = 'var(--bg-tertiary)';
        btn.style.color = 'var(--text-primary)';
        btn.style.border = '1px solid var(--border-color)';
      });
      tabContents.forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
      });

      // Add active class
      button.classList.add('active');
      button.style.background = 'var(--accent-primary)';
      button.style.color = 'var(--bg-primary)';
      button.style.border = 'none';

      const activeContent = document.getElementById(`${tabName}-tab`);
      if (activeContent) {
        activeContent.classList.add('active');
        activeContent.style.display = 'block';
      }
    });
  });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  initDropdowns();
  initTabs();
  // ... other initializations
});
```

**In HTML:**
```html
<script src="/assets/js/main.js" defer></script>
```

---

## 📈 Monitoring & Metrics

### Tools to Use
1. **Lighthouse** - Run in Chrome DevTools
2. **WebPageTest** - https://www.webpagetest.org
3. **GTmetrix** - https://gtmetrix.com
4. **Netlify Analytics** - Built-in (if using Netlify)

### Key Metrics to Track
- **LCP (Largest Contentful Paint):** <2.5s
- **FID (First Input Delay):** <100ms
- **CLS (Cumulative Layout Shift):** <0.1
- **TTFB (Time to First Byte):** <600ms

---

## 💡 Future Optimizations

### When Adding Real Screenshots
1. Use Cloudinary or similar CDN
2. Automatic WebP conversion
3. Responsive image sizes
4. Lazy loading with blur-up placeholders

### When Adding Videos
1. Use poster images
2. Lazy load video embeds
3. Consider YouTube-nocookie.com

### When Traffic Grows
1. CDN for static assets
2. HTTP/3 support
3. Edge computing for dynamic content
4. Database query optimization

---

## 🎯 Success Criteria

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Lighthouse Performance | 75-85 | 90+ | 🟡 In Progress |
| First Contentful Paint | 1.5-2.0s | <1.2s | 🟡 In Progress |
| Time to Interactive | 2.5-3.0s | <1.8s | 🟡 In Progress |
| Total Page Size | 150-200KB | <120KB | 🟡 In Progress |
| Lighthouse Accessibility | 95+ | 95+ | ✅ Already Good |
| Lighthouse SEO | 90+ | 95+ | ✅ Already Good |

---

## 📝 Notes

### Already Optimized
- ✅ System fonts (no custom font loading)
- ✅ SVG icons (no icon fonts)
- ✅ Semantic HTML
- ✅ Accessible markup
- ✅ Mobile-responsive
- ✅ No heavy frameworks (vanilla JS)

### Low Priority (For Now)
- HTTP/2 Server Push (Netlify handles this)
- Brotli compression (Netlify handles this)
- Image sprites (only have SVGs)
- CSS-in-JS (not using React/Vue)

---

**Next Steps:**
1. Implement Phase 1 quick wins (2 hours)
2. Test with Lighthouse
3. Implement Phase 2 if needed
4. Monitor real-world performance

---

*Document Version: 1.0*
*Created: 2025-10-30*
*Author: Claude Code*
*Status: ✅ Ready for Implementation*
