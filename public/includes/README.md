# Navigation System

This directory contains the standardized navigation component for the p(Doom)1 website.

## How It Works

The navigation is implemented using JavaScript to ensure consistency across all pages while remaining static-site friendly.

### For New Pages

To add standard navigation to a new page:

1. **Add a header element** in your HTML:
   ```html
   <header>
       <!-- Navigation loaded by navigation.js -->
   </header>
   ```

2. **Include the navigation script** before closing `</body>`:
   ```html
   <script src="/assets/js/navigation.js"></script>
   ```

3. **Ensure site.css is loaded** for proper styling:
   ```html
   <link rel="stylesheet" href="/css/site.css">
   ```

That's it! The navigation will automatically populate with the full menu structure.

## Navigation Structure

The standard navigation includes:

**Main Links:**
- Game (homepage)
- Leaderboard
- Stats
- Risk Dashboard
- Forum (external link)

**Community Dropdown:**
- Issues & Feedback
- Dev Blog
- Updates
- Cat Custodians
- GitHub

**Info Dropdown:**
- About
- AI Safety Resources
- Roadmap
- Documentation
- Press Kit

## Updating Navigation

To update the navigation across all pages:

1. Edit `/assets/js/navigation.js`
2. Update the `navigationHTML` constant
3. All pages using the script will automatically get the updated navigation

## Features

- **Automatic Current Page Highlighting** - Active page is highlighted in nav
- **Dropdown Menus** - Click to expand Community and Info menus
- **Responsive Design** - Works on mobile and desktop
- **Accessibility** - Full ARIA labels and keyboard navigation
- **Version Badge** - Shows current game version

## Files

- `navigation.html` - Static HTML template (reference only)
- `/assets/js/navigation.js` - Dynamic navigation loader (active)
- `/css/site.css` - Navigation styles (shared across site)
