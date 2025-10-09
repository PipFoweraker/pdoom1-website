# File Upload Implementation for Bug Reports

## Overview

This document describes the implementation of file upload functionality for the bug reporting system, allowing users to attach log files, screenshots, and other diagnostic files to bug reports.

## Architecture

The implementation follows this flow:

1. **Client-side (HTML/JavaScript)**: User selects a file through a file input field
2. **Client-side validation**: File size is validated (max 500 KB)
3. **File encoding**: File is read and encoded as base64
4. **API submission**: File data is sent along with bug report to Netlify function
5. **Gist creation**: Netlify function creates a private GitHub Gist with the file
6. **GitHub issue**: Workflow creates an issue with a link to the Gist

## Components Modified

### 1. HTML Form (`public/index.html`)

Added file input field with:
- File type restrictions: `.txt, .log, .json, .zip, .png, .jpg, .jpeg`
- Help text indicating 500 KB size limit
- Error message display area

### 2. Client-side JavaScript (`public/index.html`)

Enhanced form submission handler to:
- Validate file size before upload
- Read file content as base64
- Include file metadata in API request
- Display appropriate error messages

### 3. Netlify Function (`netlify/functions/report-bug.js`)

Added:
- `createGist()` function to create private GitHub Gists
- Attachment handling in `sanitize()` function
- File size validation (500 KB limit)
- Graceful error handling if Gist creation fails

### 4. GitHub Workflow (`.github/workflows/bug-report.yml`)

Enhanced to:
- Accept Gist URL, attachment name, and size from payload
- Include attachment information in issue body
- Display Gist link with file name and size
- Handle duplicate reports with attachments

### 5. Documentation (`docs/03-integrations/bug-reporting.md`)

Updated API documentation to include:
- Attachment field specification
- File size limits
- Supported file types
- Gist integration details

## Configuration

### Environment Variables

The `GITHUB_DISPATCH_TOKEN` must have permissions to:
- Trigger repository dispatch events (existing requirement)
- Create Gists (new requirement)

### File Size Limits

Maximum file size is configurable in `netlify/functions/report-bug.js`:

```javascript
const maxFileSize = 500 * 1024; // 500 KB in bytes
```

### Supported File Types

File types are restricted in the HTML form's `accept` attribute:
```html
accept=".txt,.log,.json,.zip,.png,.jpg,.jpeg"
```

## API Schema

### Request Body Addition

```json
{
  "attachment": {
    "filename": "string (max 255 chars)",
    "content": "string (base64 encoded)",
    "size": "number (bytes, max 500KB)",
    "type": "string (MIME type)"
  }
}
```

### Response

No changes to response format. Attachment processing happens asynchronously.

## GitHub Integration

### Gist Properties

- **Privacy**: Private (not public)
- **Description**: "Bug report attachment: [issue title]"
- **Files**: Single file with original filename
- **Content**: Decoded from base64

### Issue Format

When an attachment is present, the issue includes:

```markdown
## Attachment
📎 **filename.log** (25 KB)

[View attachment on Gist](https://gist.github.com/...)
```

If Gist creation fails:

```markdown
## Attachment
⚠️ Failed to upload attachment
```

## Error Handling

### Client-side
- File size validation before submission
- Clear error messages displayed to user
- Form not submitted if validation fails

### Server-side
- Gist creation wrapped in try-catch
- Bug report still created even if Gist creation fails
- Error logged and indicated in issue

## Testing

### Manual Testing

1. Start local server: `npm start`
2. Navigate to bug report form
3. Fill in required fields
4. Select a test file (< 500 KB)
5. Submit form
6. Verify "local mock" success message

### API Testing

Test script with file attachment:
```bash
node api/test-report-bug-with-file.js
```

Requires Netlify dev server:
```bash
netlify dev --port 8888
```

### Production Testing

Set `DRY_RUN=true` to test without creating actual issues/gists.

## Security Considerations

1. **File Size Limits**: Enforced both client and server-side to prevent abuse
2. **Private Gists**: All attachments uploaded as private Gists
3. **Content Validation**: File content is base64 encoded and decoded server-side
4. **Token Permissions**: Limited to Gist creation and repository dispatch

## Future Enhancements

Potential improvements for future iterations:

1. **Configurable size limit**: Environment variable for max file size
2. **Multiple file uploads**: Support attaching multiple files
3. **Direct issue attachments**: Use GitHub's native attachment API (when available)
4. **File type validation**: Server-side MIME type verification
5. **Virus scanning**: Integration with file scanning service
6. **Expiry management**: Automatic Gist cleanup for old reports
7. **Progress indicator**: Upload progress bar for large files

## Troubleshooting

### Gist Creation Fails

**Symptoms**: Issue created but no attachment link

**Possible causes**:
- Token lacks Gist creation permission
- GitHub API rate limit exceeded
- Network connectivity issues

**Solution**: Check Netlify function logs for detailed error message

### File Too Large

**Symptoms**: Error message "File too large: X KB. Maximum size is 500 KB."

**Solution**: Compress file or split into smaller chunks

### Unsupported File Type

**Symptoms**: File input doesn't accept certain files

**Solution**: Use a supported file type or add type to `accept` attribute
