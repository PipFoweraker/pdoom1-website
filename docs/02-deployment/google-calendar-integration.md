# Google Calendar Integration for Deployment Schedule

## Overview

This document outlines how to integrate the weekly deployment schedule with Google Calendar to provide automated reminders and team coordination.

## Integration Options

### Option 1: Manual Calendar Setup (Simplest)

Create recurring calendar events manually:

1. **Weekly Deployment - Friday 16:00 AEST**
   - Event: "p(Doom)1 Production Deployment"
   - Time: Friday 16:00-17:00 AEST
   - Recurrence: Weekly
   - Reminders: 2 hours before, 30 minutes before
   - Attendees: Dev team
   - Description: Link to deployment checklist

2. **Pre-Deployment Prep - Friday 14:00 AEST**
   - Event: "Deployment Pre-Flight Checks"
   - Time: Friday 14:00-15:30 AEST
   - Recurrence: Weekly
   - Reminder: 15 minutes before

3. **Code Freeze - Thursday 17:00 AEST**
   - Event: "Code Freeze for Friday Deployment"
   - Time: Thursday 17:00 AEST
   - Recurrence: Weekly
   - Reminder: 1 hour before

4. **Weekly League Reset - Monday 00:00 AEST**
   - Event: "Weekly League Automatic Reset"
   - Time: Monday 00:00 AEST (set Sunday 11:55 PM as event)
   - Recurrence: Weekly
   - Note: Automated - no action needed

5. **Twitch Stream - Friday 16:30 AEST**
   - Event: "Deployment Stream on Twitch"
   - Time: Friday 16:30-17:30 AEST
   - Recurrence: Weekly
   - Reminder: 15 minutes before

### Option 2: GitHub Actions with Webhook (Advanced)

GitHub Actions can trigger webhooks to create calendar events automatically.

#### Requirements
- Google Calendar API access
- Service account or OAuth2 credentials
- Webhook endpoint (can use Netlify Functions or similar)

#### Implementation Approach

1. **Create a Netlify Function** (or similar serverless function):
   ```javascript
   // netlify/functions/calendar-webhook.js
   
   const { google } = require('googleapis');
   
   exports.handler = async (event) => {
     // Verify webhook signature
     // Parse deployment event
     // Create calendar event using Google Calendar API
     
     const calendar = google.calendar('v3');
     // Implementation details...
   };
   ```

2. **Add Webhook to GitHub Actions**:
   ```yaml
   - name: Notify Calendar
     if: success()
     run: |
       curl -X POST ${{ secrets.CALENDAR_WEBHOOK_URL }} \
         -H "Content-Type: application/json" \
         -d '{
           "event": "deployment",
           "time": "${{ github.event.head_commit.timestamp }}",
           "version": "${{ needs.version_check.outputs.current_version }}"
         }'
   ```

### Option 3: Airtable Integration (Recommended)

If you're already using Airtable, you can leverage it as a middleware.

#### Setup

1. **Airtable Base Structure**:
   ```
   Deployments Table:
   - Date (DateTime)
   - Version (Single Line Text)
   - Status (Single Select: Scheduled, In Progress, Complete, Failed)
   - Type (Single Select: Weekly, Hotfix)
   - Notes (Long Text)
   ```

2. **Airtable Automation**:
   - Trigger: When record is created with Status = "Scheduled"
   - Action: Create Google Calendar event
   - Use Airtable's native Google Calendar integration

3. **GitHub Actions Integration**:
   ```yaml
   - name: Create Airtable Record
     run: |
       curl -X POST https://api.airtable.com/v0/${{ secrets.AIRTABLE_BASE_ID }}/Deployments \
         -H "Authorization: Bearer ${{ secrets.AIRTABLE_API_KEY }}" \
         -H "Content-Type: application/json" \
         -d '{
           "fields": {
             "Date": "${{ steps.get_date.outputs.date }}",
             "Version": "${{ needs.version_check.outputs.current_version }}",
             "Status": "Scheduled",
             "Type": "Weekly"
           }
         }'
   ```

4. **Airtable to Google Calendar**:
   - In Airtable, go to Automations
   - Create: When record created with Status="Scheduled"
   - Add action: Create Google Calendar event
   - Map fields: Date -> Start time, Notes -> Description

### Option 4: Zapier/Make Integration (No-Code)

Use a no-code automation platform:

1. **Zapier Setup**:
   - Trigger: Webhook from GitHub Actions
   - Action 1: Create Google Calendar event
   - Action 2: Send Slack/Discord notification (optional)

2. **GitHub Actions**:
   ```yaml
   - name: Trigger Zapier
     run: |
       curl -X POST ${{ secrets.ZAPIER_WEBHOOK_URL }} \
         -d "version=${{ needs.version_check.outputs.current_version }}" \
         -d "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   ```

## Recommended Approach

**For Your Use Case: Option 3 (Airtable Integration)**

Reasons:
1. You already have Airtable sync workflows in place
2. Airtable has native Google Calendar integration
3. No custom code needed - just Airtable automations
4. Can track deployment history in Airtable
5. Easy to modify and maintain

## Implementation Steps (Airtable + Google Calendar)

### Step 1: Create Airtable Base

1. Go to Airtable and create a new base: "p(Doom)1 Deployments"
2. Create table "Deployment Schedule" with fields:
   - Deployment Date (DateTime)
   - Version (Single Line Text)
   - Type (Single Select: Weekly, Hotfix, Emergency)
   - Status (Single Select: Scheduled, In Progress, Complete, Failed, Rolled Back)
   - Pre-Deployment Checklist (Checkbox)
   - Deployment Notes (Long Text)
   - Deployed By (Single Line Text)
   - Stream Link (URL)

### Step 2: Set Up Airtable Automation

1. In Airtable, click Automations > Create automation
2. Name: "Create Calendar Event for Scheduled Deployment"
3. Trigger: When record matches conditions
   - When: Record created or updated
   - Condition: Status is "Scheduled"
4. Action: Google Calendar - Create event
   - Connect your Google Calendar
   - Calendar: Select your team calendar
   - Event title: "p(Doom)1 Deployment v{Version}"
   - Start time: {Deployment Date}
   - Duration: 2 hours
   - Description: Link to deployment checklist + notes
   - Attendees: Your team email addresses

### Step 3: Add GitHub Actions Integration

Add to `weekly-deployment.yml`:

```yaml
- name: Log deployment to Airtable
  if: success()
  run: |
    DEPLOYMENT_DATE=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
    
    curl -X POST https://api.airtable.com/v0/${{ secrets.AIRTABLE_BASE_ID }}/Deployment%20Schedule \
      -H "Authorization: Bearer ${{ secrets.AIRTABLE_API_KEY }}" \
      -H "Content-Type: application/json" \
      -d "{
        \"fields\": {
          \"Deployment Date\": \"$DEPLOYMENT_DATE\",
          \"Version\": \"${{ needs.pre_deployment_preparation.outputs.current_version }}\",
          \"Type\": \"Weekly\",
          \"Status\": \"Complete\",
          \"Deployed By\": \"${{ github.actor }}\",
          \"Deployment Notes\": \"Automated weekly deployment\"
        }
      }"
```

### Step 4: Required Secrets

Add to GitHub repository secrets:
- `AIRTABLE_BASE_ID`: Your Airtable base ID
- `AIRTABLE_API_KEY`: Your Airtable API key (from Account settings)

### Step 5: Pre-Schedule Future Deployments

Create Airtable records for upcoming Fridays with Status="Scheduled":
- This will automatically create Google Calendar events
- Team gets notified via Google Calendar
- Can see deployment history in Airtable

## Alternative: Native GitHub Calendar Export

GitHub does not natively support exporting Actions schedules to calendar, but you can:

1. Create an `.ics` (iCalendar) file in the repository
2. Import to Google Calendar
3. Update when schedule changes

Example `deployment-schedule.ics`:
```ics
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//p(Doom)1//Deployment Schedule//EN
BEGIN:VEVENT
UID:pdoom1-weekly-deployment@pdoom1.com
DTSTAMP:20251009T000000Z
DTSTART:20251011T060000Z
RRULE:FREQ=WEEKLY;BYDAY=FR
SUMMARY:p(Doom)1 Weekly Deployment
DESCRIPTION:Automated weekly deployment\nChecklist: https://github.com/PipFoweraker/pdoom1-website/blob/main/docs/02-deployment/weekly-deployment-checklist.md
LOCATION:GitHub Actions
END:VEVENT
BEGIN:VEVENT
UID:pdoom1-league-reset@pdoom1.com
DTSTAMP:20251009T000000Z
DTSTART:20251014T140000Z
RRULE:FREQ=WEEKLY;BYDAY=SU
SUMMARY:Weekly League Reset (Automated)
DESCRIPTION:Automated league reset for new week\nNo action required
END:VEVENT
END:VCALENDAR
```

Import URL: `https://raw.githubusercontent.com/PipFoweraker/pdoom1-website/main/deployment-schedule.ics`

## Summary

**Simplest**: Manual Google Calendar recurring events (5 minutes setup)
**Best for your stack**: Airtable integration with native Google Calendar connector
**Most flexible**: Custom Netlify function with Google Calendar API
**No code**: Zapier/Make webhook to calendar

I recommend starting with **Airtable integration** since you already have Airtable in your workflow. It's low-code, maintainable, and provides deployment tracking as a bonus.

## Next Steps

1. Choose integration approach (recommend Airtable)
2. Set up Airtable base if using that option
3. Configure Google Calendar connection
4. Add webhook/API call to GitHub Actions
5. Test with next deployment

No changes to existing GitHub Actions workflows are required - just add the optional notification step.
