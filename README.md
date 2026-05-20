**Inspect designs, export assets, and collaborate on Figma files through AI.**

A Model Context Protocol (MCP) server that exposes Figma's API for reading file structures, exporting images, managing comments, and browsing team components.


## Overview

The Figma MCP Server provides deep access to your Figma workspace through AI:

- Read file document trees, nodes, styles, and component libraries
- Export nodes as rendered images in multiple formats and scales
- Post and retrieve comments, and browse team projects and files

Perfect for:

- Letting AI inspect and describe Figma designs without opening the app
- Automating asset export pipelines triggered by natural language
- Surfacing design system components and styles for AI-assisted development


## Tools

<details>
<summary><code>health_check</code> — Check server readiness</summary>

Returns a status object confirming the server is running and reachable.

**Inputs:** _(none)_

**Output:**

```json
{
  "status": "ok",
  "server": "CL Figma MCP Server"
}
```

</details>


<details>
<summary><code>get_me</code> — Get authenticated user profile</summary>

Returns the profile of the Figma user associated with the connected credential.

**Inputs:** _(none)_

**Output:**

```json
{
  "id": "123456789",
  "email": "user@example.com",
  "handle": "username",
  "img_url": "https://..."
}
```

</details>


<details>
<summary><code>get_file</code> — Retrieve a Figma file document tree</summary>

Fetches the full document tree of a Figma file. Use `depth` to limit how deep the node tree is returned and reduce response size.

**Inputs:**
```
- `file_key` (string, required)  — Unique key identifying the Figma file (found in the file URL)
- `depth`    (integer, optional) — Depth of the node tree to return (default: full tree)
```

**Output:**

```json
{
  "name": "My Design File",
  "lastModified": "2024-01-01T00:00:00Z",
  "document": { "id": "0:0", "name": "Document", "type": "DOCUMENT", "children": [...] }
}
```

</details>


<details>
<summary><code>get_file_nodes</code> — Retrieve specific nodes from a file</summary>

Fetches one or more specific nodes from a Figma file by their node IDs, rather than the full document tree.

**Inputs:**
```
- `file_key`  (string, required)  — Unique key identifying the Figma file
- `node_ids`  (string, required)  — Comma-separated list of node IDs to retrieve (e.g. '1:2,3:4')
- `depth`     (integer, optional) — Depth of the node subtree to return
```

**Output:**

```json
{
  "nodes": {
    "1:2": { "document": { "id": "1:2", "name": "Frame", "type": "FRAME" } }
  }
}
```

</details>


<details>
<summary><code>get_file_components</code> — List local components in a file</summary>

Returns all locally-defined components in a Figma file, including their keys and descriptions.

**Inputs:**
```
- `file_key` (string, required) — Unique key identifying the Figma file
```

**Output:**

```json
{
  "meta": {
    "components": [
      { "key": "abc123", "name": "Button/Primary", "description": "" }
    ]
  }
}
```

</details>


<details>
<summary><code>get_file_styles</code> — List styles defined in a file</summary>

Returns all local styles (colors, text, effects, grids) defined in a Figma file.

**Inputs:**
```
- `file_key` (string, required) — Unique key identifying the Figma file
```

**Output:**

```json
{
  "meta": {
    "styles": [
      { "key": "def456", "name": "Primary/Blue", "style_type": "FILL" }
    ]
  }
}
```

</details>


<details>
<summary><code>get_file_versions</code> — Retrieve version history of a file</summary>

Returns the full version history of a Figma file, including version labels and timestamps.

**Inputs:**
```
- `file_key` (string, required) — Unique key identifying the Figma file
```

**Output:**

```json
{
  "versions": [
    { "id": "v1", "label": "Final Review", "created_at": "2024-01-01T00:00:00Z" }
  ]
}
```

</details>


<details>
<summary><code>get_images</code> — Export nodes as rendered image URLs</summary>

Renders one or more nodes as images and returns signed download URLs. Supports PNG, JPG, SVG, and PDF formats.

**Inputs:**
```
- `file_key`  (string, required)  — Unique key identifying the Figma file
- `node_ids`  (string, required)  — Comma-separated list of node IDs to export (e.g. '1:2,3:4')
- `scale`     (float, optional)   — Export scale factor between 0.01 and 4 (default: 1)
- `format`    (string, optional)  — Image format: 'jpg', 'png', 'svg', or 'pdf' (default: 'png')
```

**Output:**

```json
{
  "images": {
    "1:2": "https://figma-alpha-api.s3.us-west-2.amazonaws.com/..."
  }
}
```

</details>


<details>
<summary><code>get_image_fills</code> — Retrieve image fill download URLs</summary>

Returns download URLs for all images embedded in a Figma file as image fills on nodes.

**Inputs:**
```
- `file_key` (string, required) — Unique key identifying the Figma file
```

**Output:**

```json
{
  "meta": {
    "images": { "imageRef123": "https://..." }
  }
}
```

</details>


<details>
<summary><code>get_comments</code> — List comments on a file</summary>

Returns all comments on a Figma file, including resolved and unresolved threads.

**Inputs:**
```
- `file_key` (string, required) — Unique key identifying the Figma file
```

**Output:**

```json
{
  "comments": [
    { "id": "c1", "message": "Looks good!", "resolved_at": null }
  ]
}
```

</details>


<details>
<summary><code>post_comment</code> — Post a comment on a file</summary>

Adds a new comment to a Figma file on behalf of the authenticated user.

**Inputs:**
```
- `file_key` (string, required) — Unique key identifying the Figma file
- `message`  (string, required) — The comment text to post
```

**Output:**

```json
{
  "id": "c2",
  "message": "Please update the button radius.",
  "created_at": "2024-01-01T00:00:00Z"
}
```

</details>


<details>
<summary><code>get_team_projects</code> — List projects in a team</summary>

Returns all projects belonging to a Figma team.

**Inputs:**
```
- `team_id` (string, required) — The Figma team ID
```

**Output:**

```json
{
  "projects": [
    { "id": "12345", "name": "Design System" }
  ]
}
```

</details>


<details>
<summary><code>get_project_files</code> — List files in a project</summary>

Returns all files within a specific Figma project.

**Inputs:**
```
- `project_id` (string, required) — The Figma project ID
```

**Output:**

```json
{
  "files": [
    { "key": "abc123", "name": "Components v2", "last_modified": "2024-01-01T00:00:00Z" }
  ]
}
```

</details>


<details>
<summary><code>get_team_components</code> — List published components in a team library</summary>

Returns all published components available in a Figma team's shared component library.

**Inputs:**
```
- `team_id` (string, required) — The Figma team ID
```

**Output:**

```json
{
  "meta": {
    "components": [
      { "key": "ghi789", "name": "Icon/Close", "file_key": "abc123" }
    ]
  }
}
```

</details>


<details>
<summary><code>get_component</code> — Get a specific published component</summary>

Retrieves metadata for a single published component by its unique component key.

**Inputs:**
```
- `component_key` (string, required) — The unique key of the published component
```

**Output:**

```json
{
  "meta": {
    "key": "ghi789",
    "name": "Icon/Close",
    "description": "Close icon, 24px",
    "file_key": "abc123"
  }
}
```

</details>


## API Parameters Reference

<details>
<summary><strong>Common Parameters</strong></summary>

- `file_key` — The unique identifier of a Figma file, extracted from its URL: `figma.com/file/{file_key}/...`
- `node_ids` — Comma-separated node IDs in `{pageId}:{nodeId}` format, e.g. `1:2,3:4`
- `depth` — Integer controlling how many levels of the node tree to return; omit for the full tree

</details>

<details>
<summary><strong>Resource ID Formats</strong></summary>

**File Key:**

```
{alphanumeric string from URL}
Example: aBcDeFgHiJkLmNoP
```

**Node ID:**

```
{page}:{node}
Example: 1:2  (page 1, node 2)
```

**Team ID:**

```
{numeric string}
Example: 123456789
```

**Project ID:**

```
{numeric string}
Example: 987654321
```

</details>

<details>
<summary><strong>Image Export Formats</strong></summary>

- `png` — Raster, default format (default scale: 1×)
- `jpg` — Raster, smaller file size, no transparency
- `svg` — Vector, ideal for icons and simple shapes
- `pdf` — Vector, suitable for print

Scale range: `0.01` – `4` (e.g. `2` for @2x retina export)

</details>


## Troubleshooting

<details>
<summary><strong>Missing or Invalid Headers</strong></summary>

- **Cause:** Figma credential not provided in request headers or incorrect format
- **Solution:**
  1. Verify `Authorization: Bearer YOUR_API_KEY` and `X-Mewcp-Credential-Id: CREDENTIAL-ID` headers are present
  2. Check the credential is active in your MewCP account

</details>

<details>
<summary><strong>Insufficient Credits</strong></summary>

- **Cause:** API calls have exceeded your request limits
- **Solution:**
  1. Check credit usage in your Curious Layer dashboard
  2. Upgrade to a paid plan or add credits for higher limits
  3. Contact support for credit adjustments

</details>

<details>
<summary><strong>Credential Not Connected</strong></summary>

- **Cause:** No Figma credential linked to your account
- **Solution:**
  1. Go to **Credentials** in your MewCP dashboard
  2. Connect your Figma account (OAuth)
  3. Retry the request with the correct `X-Mewcp-Credential-Id` header

</details>

<details>
<summary><strong>Malformed Request Payload</strong></summary>

- **Cause:** JSON payload is invalid or missing required fields
- **Solution:**
  1. Validate JSON syntax before sending
  2. Ensure all required tool parameters are included
  3. Check that `node_ids` is a comma-separated string, not an array

</details>

<details>
<summary><strong>Server Not Found</strong></summary>

- **Cause:** Incorrect server name in the API endpoint
- **Solution:**
  1. Verify endpoint format: `{server-name}/mcp/{tool-name}`
  2. Use correct server name from documentation
  3. Check available servers in your Curious Layer account

</details>

<details>
<summary><strong>Figma API Error</strong></summary>

- **Cause:** Upstream Figma API returned an error
- **Solution:**
  1. Check Figma service status at [Figma Status Page](https://status.figma.com/)
  2. Verify your credential has access to the file or team being queried
  3. Review the error message for specific details (e.g. file not found, insufficient permissions)

</details>

---

<details>
<summary><strong>Resources</strong></summary>

- **[Figma REST API Documentation](https://www.figma.com/developers/api)** — Official API reference
- **[Figma Developer Console](https://www.figma.com/developers)** — Manage apps and access tokens
- **[FastMCP Docs](https://gofastmcp.com/v2/getting-started/welcome)** — FastMCP specification
- **[FastMCP Credentials](https://pypi.org/project/fastmcp-credentials/)** — FastMCP Credentials package for credential handling

</details>
