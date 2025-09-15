# Hotfix 2025-09-15: Mac TypeError Bug

## Issue Summary
Critical bug affecting Mac users where `accumulated_debt` is stored as string instead of integer, causing TypeError in research system.

## Bug Details
- **Reported by:** hlyonskeenan (Mac user)
- **Error Location:** `src/core/research_quality.py` line 223
- **Error Type:** `TypeError: '<' not supported between instances of 'int' and 'str'`
- **GitHub Issue:** [#299](https://github.com/PipFoweraker/pdoom1/issues/299)

## Reproduction Steps
1. Install p(Doom)1 on macOS
2. Run game normally
3. Select any research option
4. Game crashes when attempting to reduce technical debt

## Root Cause Analysis
The `self.accumulated_debt` field is being stored as a string (likely from save/load serialization) but the `min()` function expects both parameters to be the same numeric type.

## Temporary Workaround
Until fixed in main repo, Mac users can:
1. Check if there's a manual type conversion needed
2. Or wait for the official fix

## Status
- [x] Bug reported to main repo (Issue #299)
- [ ] Fix implemented in main repo
- [ ] Website updated with known issues section
- [ ] Fix verified on Mac

## Next Steps
1. Fix will be implemented in main p(Doom)1 repository
2. Website will be updated to note Mac compatibility once resolved
3. Consider adding a "Known Issues" section to website if more platform-specific bugs emerge

## Priority
**HIGH** - Blocks core gameplay functionality on Mac platform.
