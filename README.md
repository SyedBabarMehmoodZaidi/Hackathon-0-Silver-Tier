# Personal AI Employee - Bronze Tier

This is a local-first autonomous digital employee that monitors communications and tasks, reasons using Claude Code, and executes actions via MCP servers with human-in-the-loop safeguards.

## Architecture

The system follows a **Perception → Reasoning → Action → Logging** model:

1. **Watchers (Perception Layer)** - Python scripts monitor inputs such as file drops
2. **Obsidian Vault (Memory & Interface)** - Local Markdown-based state management
3. **Claude Code (Reasoning Engine)** - Generates structured execution plans
4. **MCP Servers (Action Layer)** - Execute approved actions
5. **Logging System** - All activities logged in JSON format

## Security Principles

- No credentials stored in vault
- `.env` for secrets
- Dry-run mode enabled by default
- All actions logged in JSON format
- Human approval required for sensitive operations

## How to Run (Bronze Tier)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in `.env`:
   ```
   CLAUDE_API_KEY=your_api_key_here
   EMAIL_PASSWORD=your_email_password
   ```

3. Initialize the system:
   ```bash
   python main.py --setup
   ```

4. Run the full system:
   ```bash
   python main.py --mode full
   ```

5. Alternatively, run components separately:
   - Just watchers: `python main.py --mode watcher`
   - Just orchestrator: `python main.py --mode orchestrator`

6. Drop a `.md` file into the `Incoming_Files` folder to observe automated plan generation

## File Structure

- `Needs_Action/` - Files requiring processing
- `Approved/` - Plans approved for execution
- `Done/` - Completed tasks
- `Logs/` - Activity logs in JSONL format
- `Vault/` - Obsidian-style knowledge base
- `Incoming_Files/` - Monitored folder for new tasks
- `watchers/` - Watcher implementations
- `mcp_interface.py` - MCP server interface
- `orchestrator.py` - Main orchestration logic

## Configuration

Edit `config.json` to customize:
- Watcher settings
- MCP server configurations
- Paths and intervals
- Dry-run/approval settings