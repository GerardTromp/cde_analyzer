# VSCode Setup for CDE Analyzer

This project enforces **LF line endings** for all text files. Windows users need to configure VSCode properly.

## Quick Setup

### 1. Install EditorConfig Extension
Install the **EditorConfig for VS Code** extension:
```
ext install EditorConfig.EditorConfig
```

This will automatically read `.editorconfig` and enforce LF line endings.

### 2. Configure VSCode Settings

The `.vscode/` directory is gitignored, so you need to create your local settings.

**Option A: Workspace Settings (Recommended)**

Create `.vscode/settings.json` with:

```json
{
  "files.eol": "\n",
  "files.insertFinalNewline": true,
  "files.trimTrailingWhitespace": true,
  "[python]": {
    "editor.rulers": [88],
    "editor.tabSize": 4,
    "editor.insertSpaces": true,
    "files.eol": "\n"
  },
  "[json]": {
    "editor.tabSize": 2,
    "files.eol": "\n"
  },
  "[yaml]": {
    "editor.tabSize": 2,
    "files.eol": "\n"
  },
  "[markdown]": {
    "files.trimTrailingWhitespace": false,
    "files.eol": "\n"
  }
}
```

**Option B: User Settings (Global)**

Open VSCode Settings (Ctrl+,) and set:
- **Files: Eol** → `\n`
- **Files: Insert Final Newline** → ✓ Checked
- **Files: Trim Trailing Whitespace** → ✓ Checked

### 3. Configure Git (If Not Already Done)

The repository is already configured, but verify:

```bash
cd cde_analyzer
git config core.autocrlf false
git config core.eol lf
```

### 4. Verify Configuration

Open any Python file and check the bottom-right corner of VSCode:
- Should show: **LF** (not CRLF)
- If it shows CRLF, click it and select **LF**

## How It Works

### 1. `.gitattributes` (Repository Level)
Forces git to use LF for all text files when checking in/out.

### 2. `.editorconfig` (Editor Level)
Tells VSCode and other editors to use LF for new files.

### 3. `.vscode/settings.json` (Local Level)
Your personal VSCode workspace settings (not checked into git).

## Converting Existing Files

If you have files with CRLF, convert them:

**Single File:**
```bash
dos2unix filename.py
```

**All Python Files:**
```bash
find . -name "*.py" -type f -exec dos2unix {} \;
```

**Using Git (Safer):**
```bash
# Let git normalize line endings based on .gitattributes
git add --renormalize .
git status  # Check what changed
```

## Troubleshooting

### Issue: Files Keep Getting CRLF

**Check:**
1. VSCode settings show `"files.eol": "\n"`
2. Bottom-right corner shows **LF** not **CRLF**
3. Git config: `git config --get core.autocrlf` should be `false`
4. Git config: `git config --get core.eol` should be `lf`

**Fix:**
```bash
# Repository config
git config core.autocrlf false
git config core.eol lf

# Re-checkout files
git rm --cached -r .
git reset --hard
```

### Issue: Git Shows All Files Modified

This happens if you just added `.gitattributes`. It's normal.

**Solution:**
```bash
# Normalize all files (one-time operation)
git add --renormalize .
git commit -m "Normalize line endings to LF"
```

### Issue: EditorConfig Not Working

**Check:**
1. EditorConfig extension installed: `code --list-extensions | grep EditorConfig`
2. File `.editorconfig` exists in project root
3. VSCode setting: `"editor.formatOnSave": false` (EditorConfig handles formatting)

## Windows-Specific Notes

### Why CRLF is Problematic

1. **Git Diffs:** CRLF causes unnecessary diffs (^M characters)
2. **Shell Scripts:** Bash scripts fail with CRLF line endings
3. **Cross-Platform:** Linux/Mac use LF natively
4. **Python:** Some tools don't handle CRLF well

### Exceptions

The project allows CRLF ONLY for:
- `*.bat` (Windows batch files)
- `*.cmd` (Windows command files)
- `*.ps1` (PowerShell scripts)

These are explicitly configured in `.gitattributes`.

## Verifying Setup

Run this to check your configuration:

```bash
# Check git config
git config --get core.autocrlf  # Should be: false
git config --get core.eol       # Should be: lf

# Check VSCode settings
code --list-extensions | grep EditorConfig  # Should show: editorconfig.editorconfig

# Check a file's line endings
file -b cde_analyzer/utils/logger.py  # Should mention: LF (not CRLF)
```

## Additional Resources

- [EditorConfig](https://editorconfig.org/)
- [Git Line Endings](https://docs.github.com/en/get-started/getting-started-with-git/configuring-git-to-handle-line-endings)
- [VSCode Line Endings](https://code.visualstudio.com/docs/editor/codebasics#_end-of-line-character)

## Quick Reference

| File | Purpose |
|------|---------|
| `.gitattributes` | Git-level line ending enforcement |
| `.editorconfig` | Editor-level formatting rules |
| `.vscode/settings.json` | VSCode workspace settings (create locally) |

---

**TL;DR:** Install EditorConfig extension, create `.vscode/settings.json`, set git configs. All new files will use LF automatically.
