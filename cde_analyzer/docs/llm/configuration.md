# LLM Configuration

API key setup and provider configuration for LLM classification.

## API Key Priority

API keys are resolved in the following order (first found wins):

1. **Configuration file** (recommended)
2. **Environment variables**
3. **CLI arguments** (least preferred)

!!! warning "Security Note"
    Avoid passing API keys via CLI arguments (`--api-keys`) as they may be visible in shell history and process listings. Use configuration files or environment variables instead.

## Configuration File

The recommended approach is to create a configuration file at:

```
~/.cde_analyzer/llm_config.json
```

### File Format

```json
{
  "claude": {
    "api_key": "sk-ant-api03-...",
    "model": "claude-sonnet-4-20250514"
  },
  "openai": {
    "api_key": "sk-proj-...",
    "model": "gpt-4o"
  },
  "google": {
    "api_key": "AIza...",
    "model": "gemini-1.5-pro"
  }
}
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `api_key` | Yes | Provider API key |
| `model` | No | Model identifier (uses default if not specified) |

### Creating the Configuration

```bash
# Create directory
mkdir -p ~/.cde_analyzer

# Create configuration file
cat > ~/.cde_analyzer/llm_config.json << 'EOF'
{
  "claude": {
    "api_key": "YOUR_ANTHROPIC_KEY",
    "model": "claude-sonnet-4-20250514"
  },
  "openai": {
    "api_key": "YOUR_OPENAI_KEY",
    "model": "gpt-4o"
  }
}
EOF

# Secure the file (Unix/Linux/macOS)
chmod 600 ~/.cde_analyzer/llm_config.json
```

### Custom Configuration Path

Use `--config-file` to specify an alternative location:

```bash
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --module instrument \
  --config-file /path/to/custom_config.json
```

## Environment Variables

Set environment variables for each provider:

| Provider | Environment Variable |
|----------|---------------------|
| Claude | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google | `GOOGLE_API_KEY` |

### Setting Variables

=== "Linux/macOS (bash)"

    ```bash
    # Add to ~/.bashrc or ~/.zshrc
    export ANTHROPIC_API_KEY="sk-ant-api03-..."
    export OPENAI_API_KEY="sk-proj-..."
    export GOOGLE_API_KEY="AIza..."

    # Reload shell
    source ~/.bashrc
    ```

=== "Windows (PowerShell)"

    ```powershell
    # Set for current session
    $env:ANTHROPIC_API_KEY = "sk-ant-api03-..."
    $env:OPENAI_API_KEY = "sk-proj-..."

    # Or set permanently (User scope)
    [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
    ```

=== "Windows (CMD)"

    ```cmd
    # Set for current session
    set ANTHROPIC_API_KEY=sk-ant-api03-...
    set OPENAI_API_KEY=sk-proj-...

    # Or set permanently
    setx ANTHROPIC_API_KEY "sk-ant-..."
    ```

## CLI Arguments

!!! warning "Not Recommended"
    CLI arguments are visible in shell history and process listings. Use only for testing.

```bash
# Single provider
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --module instrument \
  --api-keys "claude:sk-ant-api03-..."

# Multiple providers
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --module instrument \
  --providers claude openai \
  --api-keys "claude:sk-ant-..." "openai:sk-proj-..."
```

## Provider Details

### Claude (Anthropic)

**API Key Format**: `sk-ant-api03-...`

**Obtaining Key**:

1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Navigate to API Keys section
3. Create new key with appropriate permissions

**Default Model**: `claude-sonnet-4-20250514`

**Available Models**:

| Model | Context | Best For |
|-------|---------|----------|
| `claude-sonnet-4-20250514` | 200K | Balanced speed/quality (default) |
| `claude-opus-4-20250514` | 200K | Highest quality |
| `claude-haiku-3-20240307` | 200K | Fastest, most economical |

### OpenAI (ChatGPT)

**API Key Format**: `sk-proj-...` or `sk-...`

**Obtaining Key**:

1. Sign up at [platform.openai.com](https://platform.openai.com)
2. Navigate to API Keys
3. Create new secret key

**Default Model**: `gpt-4o`

**Available Models**:

| Model | Context | Best For |
|-------|---------|----------|
| `gpt-4o` | 128K | Balanced performance (default) |
| `gpt-4o-mini` | 128K | Fast, economical |
| `gpt-4-turbo` | 128K | High quality |

### Google (Gemini)

**API Key Format**: `AIza...`

**Obtaining Key**:

1. Go to [makersuite.google.com](https://makersuite.google.com)
2. Click "Get API Key"
3. Create key for your project

**Default Model**: `gemini-1.5-pro`

**Available Models**:

| Model | Context | Best For |
|-------|---------|----------|
| `gemini-1.5-pro` | 1M | High quality (default) |
| `gemini-1.5-flash` | 1M | Fast, economical |

## Validating Configuration

### Dry Run

Verify configuration without making API calls:

```bash
cde-analyzer llm_classify \
  --input-dir phrase_output \
  --module instrument \
  --providers claude openai \
  --dry-run
```

**Output**:
```
Checking API key configuration...
  claude: key=sk-ant-a... (source: config_file)
  openai: key=sk-proj-... (source: environment)

Loading query module: instrument
  Categories: ['instrument_name', 'possible_instrument', 'not_instrument']
  Description: Detect instrument and measurement device names in phrases

Counting phrases in phrase_output...
  Total phrases: 1234
  After min_frequency=1 filter: 1234

Dry run complete. Configuration is valid.
```

### Troubleshooting

| Issue | Symptom | Solution |
|-------|---------|----------|
| Missing key | "No API key found for provider X" | Add key to config file or environment |
| Invalid key | "Authentication failed" | Verify key is correct and active |
| Expired key | "API key expired" | Generate new key from provider console |
| Wrong format | "Invalid API key format" | Check key format matches provider |

## Rate Limits

Each provider has default rate limits configured:

| Provider | Requests/min | Tokens/min | Concurrent |
|----------|-------------|------------|------------|
| Claude | 50 | 100,000 | 5 |
| OpenAI | 60 | 150,000 | 10 |
| Google | 60 | 100,000 | 5 |

The classifier automatically handles rate limiting with:

- Token bucket algorithm for smooth request distribution
- Exponential backoff on rate limit errors
- Retry with `retry_after` hints when provided

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use file permissions** to protect config files (`chmod 600`)
3. **Rotate keys periodically** for long-running projects
4. **Use project-specific keys** rather than personal keys
5. **Set spending limits** in provider dashboards
6. **Monitor usage** through provider consoles

### .gitignore Entry

Add to your `.gitignore`:

```gitignore
# LLM configuration with API keys
.cde_analyzer/
llm_config.json
*_api_key*
```

## Example Configuration

### Development Setup (Single Provider)

```json
{
  "claude": {
    "api_key": "sk-ant-api03-development-key",
    "model": "claude-haiku-3-20240307"
  }
}
```

### Production Setup (Multi-Provider)

```json
{
  "claude": {
    "api_key": "sk-ant-api03-production-key",
    "model": "claude-sonnet-4-20250514"
  },
  "openai": {
    "api_key": "sk-proj-production-key",
    "model": "gpt-4o"
  },
  "google": {
    "api_key": "AIza-production-key",
    "model": "gemini-1.5-pro"
  }
}
```

## See Also

- [llm_classify Command](llm_classify.md) - Full command reference
- [Query Modules](query_modules.md) - Classification module details
- [LLM Overview](index.md) - Module introduction
