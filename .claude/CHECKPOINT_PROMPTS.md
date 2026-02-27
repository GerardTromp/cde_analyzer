# Claude Code Checkpoint System Prompts
## Comprehensive Prompt Collection for Context Capture

This document contains all prompts needed to generate and maintain the checkpoint system.

---

## Table of Contents
1. [Initial Setup Prompts](#initial-setup-prompts)
2. [Full Checkpoint Prompts](#full-checkpoint-prompts)
3. [Incremental Checkpoint Prompts](#incremental-checkpoint-prompts)
4. [Context File Update Prompts](#context-file-update-prompts)
5. [Recovery Prompts](#recovery-prompts)
6. [Maintenance Prompts](#maintenance-prompts)

---

## Initial Setup Prompts

### Setup 1: Create Directory Structure
```
Create the checkpoint system directory structure:

1. Create directories:
   - .claude/checkpoints/
   - .claude/context/
   - .claude/sessions/
   - .claude/memory-bank/

2. Create a .gitignore entry for:
   - .claude/sessions/*.md (session notes are personal)
   - .claude/checkpoints/*.md (checkpoints can be large)
   
3. Commit the directory structure:
   - .claude/context/ should be version controlled (shared knowledge)
   - .claude/memory-bank/ should be version controlled (team learning)

Confirm when complete and show the created structure.
```

### Setup 2: Initialize Context Files
```
Initialize the checkpoint system context files by analyzing the current codebase:

For each file, analyze the codebase and create initial content:

1. .claude/context/01-architecture.md
   - Identify the architectural style (monolithic/microservices/layered/etc.)
   - Map out the major components and their purposes
   - Document the technology stack (languages, frameworks, databases)
   - Describe how components communicate
   - Identify the data flow patterns

2. .claude/context/02-codebase-map.md
   - Generate a directory tree with annotations for each major directory
   - Identify entry points (main files, servers, scripts)
   - Map module dependencies
   - List hot files (frequently changed) based on git log
   - List stable files (core infrastructure, rarely changed)

3. .claude/context/03-data-models.md
   - Document database schemas if applicable
   - Document key data structures used in code
   - Identify data validation patterns
   - Document serialization/deserialization approaches

4. .claude/context/04-patterns.md
   - Identify design patterns in use (Factory, Repository, Observer, etc.)
   - Document coding conventions (naming, file organization, error handling)
   - Document testing patterns
   - Identify framework-specific patterns

5. .claude/context/05-decisions.md
   - Review git log for commit messages explaining "why"
   - Review README, docs/ for documented decisions
   - Create initial ADRs for major architectural choices visible in code
   - Note: This will be populated incrementally as decisions are discovered

6. .claude/context/06-dependencies.md
   - List external dependencies from package manifests (package.json, requirements.txt, etc.)
   - Document their purposes
   - Identify internal module dependencies
   - Document third-party integrations (APIs, services)

7. .claude/context/07-gotchas.md
   - Review TODO comments for warnings
   - Check for workarounds in code
   - Note: This will be populated incrementally as issues are discovered

8. .claude/context/08-progress.md
   - Review git log for recent work
   - Check for open branches
   - Document current state based on git history
   - Identify any incomplete work

After creating each file, show me a brief summary of what was captured.

Use the git log extensively - run:
- git log --oneline --since="30 days ago"
- git log --stat --since="30 days ago"
- git shortlog -sn --since="90 days ago" (to identify active files)

Read any existing documentation:
- README.md
- docs/ directory
- CONTRIBUTING.md
- Any existing CLAUDE.md files
```

### Setup 3: Create Initial Full Checkpoint
```
Now create the initial full checkpoint by synthesizing all the context files:

1. Read all files in .claude/context/
2. Run git log analysis:
   - Last 10 commits: git log --oneline -10
   - Branch structure: git branch -a
   - Uncommitted changes: git status
   - Recent activity: git log --stat --since="7 days ago"

3. If SESSION_NOTES*.md files exist, read and summarize them

4. Create .claude/checkpoints/checkpoint-[YYYYMMDD-HHMM].md using the full template

The checkpoint should synthesize all information into a comprehensive snapshot
that would allow complete context recovery after interruption.

Focus on:
- Executive summary that captures essence of project
- Current implementation state (what's in progress)
- Known issues and gotchas
- Clear recovery instructions

After creating, show me the Executive Summary and Current State Assessment
sections so I can verify accuracy.
```

---

## Full Checkpoint Prompts

### Full Checkpoint: Comprehensive State Capture
```
Create a comprehensive full checkpoint capturing complete project state:

**CONTEXT GATHERING**

1. Read all context files:
   - .claude/context/*.md

2. Analyze git history:
   - Last 30 commits: git log --oneline -30
   - Last 7 days stats: git log --stat --since="7 days ago"
   - Branch information: git branch -va
   - Uncommitted changes: git status --short
   - File change frequency: git log --name-only --since="30 days ago" | sort | uniq -c | sort -rn | head -20
   - Recent contributors: git shortlog -sn --since="30 days ago"

3. Read all session notes:
   - Find all SESSION_NOTES*.md files
   - Find all files in .claude/sessions/
   - Parse and extract:
     * What was worked on
     * Decisions made
     * Problems encountered
     * Solutions found

4. Read all incremental checkpoints since last full checkpoint:
   - .claude/checkpoints/incremental-*.md
   - Synthesize changes and learnings

5. Analyze codebase statistics:
   - Total lines of code (use cloc or similar)
   - File count by type
   - Test coverage if available

**CHECKPOINT CREATION**

Using the checkpoint template, create:
.claude/checkpoints/checkpoint-[YYYYMMDD-HHMM].md

Ensure you include:

1. Executive Summary (2-3 sentences capturing project essence)

2. Current State Assessment:
   - Implementation phase and completion percentage
   - Active work areas with specific file references
   - Recent completions from git log

3. Architectural Overview:
   - Synthesize from 01-architecture.md
   - Add insights from recent code changes

4. Codebase Map:
   - Synthesize from 02-codebase-map.md
   - Update with hot files from git analysis
   - Include critical path analysis

5. Design Patterns & Conventions:
   - From 04-patterns.md
   - Include examples found in codebase

6. Architecture Decision Records:
   - From 05-decisions.md
   - Add any new decisions from session notes or git messages

7. Current Implementation Details:
   - From 08-progress.md
   - Enhanced with git status and recent commits
   - Include work-in-progress with file-level detail

8. Known Issues & Gotchas:
   - From 07-gotchas.md
   - Add any issues mentioned in session notes
   - Include TODO/FIXME comments found in code

9. Dependencies & Integrations:
   - From 06-dependencies.md
   - Verify current versions from package files

10. Git State Analysis:
    - Recent commit history with meaningful patterns
    - Branch structure and relationships
    - Uncommitted work
    - File churn analysis

11. Session History Integration:
    - Synthesize all session notes
    - Identify patterns in work focus
    - Track velocity and completion trends

12. Lessons Learned:
    - Accumulate from all sources
    - Categorize: what's working, what's not, recommendations

13. Context Recovery Instructions:
    - Step-by-step for immediate resumption
    - Step-by-step for long-term recovery

14. Next Steps:
    - Based on 08-progress.md and recent session notes
    - Prioritized and actionable

**AFTER CREATION**

1. Update .claude/context/08-progress.md with current state
2. Archive synthesized incremental checkpoints
3. Update .claude/memory-bank/lessons-learned.md with new insights

Show me:
- The Executive Summary
- Current State Assessment
- Next Steps sections
- File path where checkpoint was saved
```

### Full Checkpoint: With Deep Git Analysis
```
Create a full checkpoint with deep git repository analysis:

**EXTENDED GIT ANALYSIS**

1. Commit pattern analysis:
   git log --since="90 days ago" --pretty=format:"%h|%an|%ad|%s" --date=short > /tmp/commits.txt
   
   Analyze for:
   - Commit frequency trends
   - Common commit message patterns
   - Work rhythm (time of day, days of week)
   - Focus areas (what's being worked on most)

2. Code churn analysis (files changed most frequently):
   git log --name-only --pretty=format: --since="60 days ago" | sort | uniq -c | sort -rn | head -30
   
   Identify:
   - Hot spots (high change frequency = complexity or instability)
   - Abandoned files (in git but no recent changes)
   - New files (recently added)

3. Contributor analysis:
   git shortlog -sn --since="90 days ago"
   git log --pretty=format:"%an" --since="30 days ago" | sort | uniq -c | sort -rn
   
   Document:
   - Active contributors
   - Areas of focus by contributor
   - Collaboration patterns

4. Branch lifecycle analysis:
   git for-each-ref --sort=-committerdate refs/heads/ --format='%(refname:short)|%(committerdate:relative)|%(subject)'
   
   Identify:
   - Stale branches (no activity >30 days)
   - Active feature branches
   - Branch naming patterns

5. File evolution analysis for critical files:
   For top 5 most important files, run:
   git log --follow --pretty=format:"%h|%ad|%s" --date=short -- [file]
   
   Document their evolution and change drivers

6. Semantic commit analysis:
   Parse commit messages for:
   - Feature additions (feat:, feature:)
   - Bug fixes (fix:, bugfix:)
   - Refactoring (refactor:)
   - Documentation (docs:)
   - Test changes (test:)
   
   Calculate proportions and trends

**CHECKPOINT CREATION**

Create the full checkpoint with enhanced "Git State Analysis" section including:
- All standard git info
- Commit pattern insights
- Code churn heatmap
- Contributor activity
- Branch lifecycle status
- File evolution stories for critical files
- Development velocity trends
- Focus area migration over time

This analysis provides historical context that helps understand:
- Why things are the way they are
- What areas are stable vs. evolving
- Where to be careful (high churn = complexity)
- Team dynamics and collaboration patterns
```

---

## Incremental Checkpoint Prompts

### Incremental Checkpoint: End of Session
```
Create an incremental checkpoint for this session:

**CAPTURE SESSION CHANGES**

1. Git changes in this session:
   git diff --stat HEAD~[n]..HEAD  (where n = commits this session)
   git log --oneline HEAD~[n]..HEAD
   git diff --name-status HEAD~[n]..HEAD
   
   If uncommitted work:
   git status --short
   git diff --stat

2. Session metadata:
   - Duration: [Calculate from session start time]
   - Focus area: [What was the main focus]
   - Achievement: [What was accomplished]

**CAPTURE SESSION CONTEXT**

3. Decisions made this session:
   - Review our conversation for decisions
   - Document: what was decided, why, alternatives considered
   - Format as mini-ADRs

4. Problems and solutions:
   - Review our conversation for problems encountered
   - Document: problem, attempted solutions, final solution, why it worked
   - Extract lessons learned

5. New gotchas discovered:
   - Any surprising behavior discovered
   - Any workarounds needed
   - Any configuration issues

6. Context for next session:
   - What should be continued
   - What needs attention
   - What to remember

**CREATE INCREMENTAL CHECKPOINT**

Create: .claude/checkpoints/incremental-[YYYYMMDD-HHMM].md

Include:
- Session summary (2-3 sentences)
- All files modified with brief description of changes
- Decisions made with rationale
- Problems and solutions
- Lessons learned
- Context for next session
- Git integration (diffs and logs)

**UPDATE RELATED FILES**

After creating incremental checkpoint:

1. Update .claude/context/08-progress.md:
   - Move completed items to "Recently Completed"
   - Update "In Progress" with current state
   - Add new items to "Upcoming" if identified

2. If new gotchas discovered, update .claude/context/07-gotchas.md

3. If architectural decisions made, add to .claude/context/05-decisions.md

4. Update .claude/memory-bank/lessons-learned.md with session insights

Show me:
- Session summary
- Key decisions
- Lessons learned
- Updated progress items
```

### Incremental Checkpoint: Quick Capture
```
Quick incremental checkpoint (for shorter sessions):

**MINIMAL CAPTURE**

1. What changed:
   git diff --stat
   git status --short

2. Brief summary:
   - Main accomplishment (1 sentence)
   - Key decision if any (1 sentence)
   - Next step (1 sentence)

Create: .claude/checkpoints/incremental-[YYYYMMDD-HHMM].md

Include only:
- Session summary
- Files changed
- One decision or lesson learned
- Next action

Update:
- .claude/context/08-progress.md (if progress made)

This is for quick session closure when time is limited.
```

---

## Context File Update Prompts

### Update: 01-architecture.md
```
Update the architecture documentation:

1. Read current .claude/context/01-architecture.md

2. Review recent changes:
   git log --stat --since="7 days ago" -- "*.py" "*.js" "*.ts" "*.go" (adjust for your languages)

3. Identify architectural changes:
   - New components added?
   - Components removed or deprecated?
   - Communication patterns changed?
   - New technologies introduced?

4. Update the file to reflect current state:
   - Keep what's still accurate
   - Update what's changed
   - Add new information
   - Remove obsolete information

5. Add "Last Updated" timestamp

Show me what changed in a git diff format.
```

### Update: 02-codebase-map.md
```
Update the codebase map:

1. Read current .claude/context/02-codebase-map.md

2. Analyze current structure:
   - Generate current directory tree
   - Identify new directories
   - Identify removed directories

3. Update hot files analysis:
   git log --name-only --pretty=format: --since="30 days ago" | sort | uniq -c | sort -rn | head -20
   
   Update the "Hot Files" section with current data

4. Identify new entry points or critical paths

5. Update module dependencies if changed

6. Update the file with current state

7. Add "Last Updated" timestamp

Show me:
- New directories added
- New entry points
- Updated hot files list
```

### Update: 05-decisions.md (Add New ADR)
```
Add a new Architecture Decision Record:

Context: [Briefly describe the decision that was made]

Create a new ADR in .claude/context/05-decisions.md:

ADR-[next-number]: [Decision Title]

Include:
- Date: [today's date]
- Status: Accepted
- Context: [Detailed context about why this decision was needed]
- Decision: [What was decided]
- Consequences:
  * Positive: [Benefits]
  * Negative: [Costs/trade-offs]
  * Risks: [Identified risks]
- Alternatives Considered: [Other options and why they were rejected]
- References: [Links to related discussions, PRs, issues]

Show me the completed ADR.
```

### Update: 07-gotchas.md (Add New Issue)
```
Add a new gotcha/issue to the documentation:

Context: [Describe the issue encountered]

Add to .claude/context/07-gotchas.md:

Under appropriate section (Critical/Environment-Specific/Dependency-Related/etc.):

### [Gotcha Title]
- **Symptom**: [How the issue manifests]
- **Cause**: [Root cause if known]
- **Workaround**: [How to avoid or fix it]
- **When it matters**: [In what scenarios this is important]
- **Tracking**: [Issue link if applicable]
- **Discovered**: [Date]

Show me what was added.
```

### Update: 08-progress.md (Daily Update)
```
Update current progress:

1. Read .claude/context/08-progress.md

2. Review what's changed:
   - What did we complete today?
   - What's still in progress?
   - What's blocked?
   - What's new?

3. Update the file:
   - Move completed items to "Recently Completed" with date
   - Update "In Progress" items with current status and files
   - Add new items to "Upcoming" if identified
   - Update "Blocked Items" section

4. Clean up:
   - Archive "Recently Completed" items older than 7 days
   - Re-prioritize backlog if needed

5. Add timestamp to "Last Updated"

Show me:
- What was marked complete
- Current in-progress items
- Any new blockers
```

### Update: Memory Bank (Lessons Learned)
```
Update lessons learned from recent work:

1. Read .claude/memory-bank/lessons-learned.md

2. Review recent session:
   - What worked well?
   - What didn't work?
   - What would we do differently?
   - What insights were gained?

3. Categorize lessons:
   - **Technical Lessons**: Code/architecture insights
   - **Process Lessons**: Workflow/methodology insights
   - **Tool Lessons**: Tool/technology insights
   - **Team Lessons**: Collaboration insights (if applicable)

4. Update the file:
   Add new lessons under appropriate categories
   Include:
   - Date discovered
   - Context (what was being done)
   - Lesson learned
   - Application (when to apply this lesson)

5. Cross-reference:
   - If lesson relates to a gotcha, link to 07-gotchas.md
   - If lesson relates to a decision, link to ADR in 05-decisions.md

Show me the new lessons added.
```

---

## Recovery Prompts

### Recovery: Full Context Restoration
```
Restore complete project context after interruption:

**CONTEXT LOADING**

1. Find and read most recent full checkpoint:
   ls -lt .claude/checkpoints/checkpoint-*.md | head -1

2. Read all incremental checkpoints since that full checkpoint:
   ls -lt .claude/checkpoints/incremental-*.md
   (Read all created after the full checkpoint timestamp)

3. Read current state files:
   - .claude/context/08-progress.md
   - .claude/context/07-gotchas.md

4. Check current git state:
   git status
   git log --oneline -5
   git branch -va

5. If SESSION_NOTES exist, read most recent:
   ls -lt SESSION_NOTES*.md | head -1

**CONTEXT SYNTHESIS**

Synthesize and present:

1. **Project Identity**:
   - What is this project?
   - What's its current state/maturity?
   - What's the tech stack?

2. **Recent History**:
   - What were we working on? (from checkpoints and progress.md)
   - What was completed recently?
   - What was left in-progress?

3. **Current State**:
   - What's uncommitted?
   - What's the active branch?
   - What was the last commit?

4. **Context for Resumption**:
   - What should I pick up?
   - What needs attention?
   - What gotchas should I remember?

5. **Next Actions**:
   - Immediate priorities from progress.md
   - Blocked items that need unblocking
   - Recommended next step

Present this as a structured briefing document.

Then ask: "What would you like to work on?"
```

### Recovery: Quick Briefing
```
Provide quick context briefing:

1. Read most recent full checkpoint Executive Summary
2. Read most recent incremental checkpoint
3. Check .claude/context/08-progress.md for current work
4. Run: git status

Present in 5 bullets:
- Project: [one sentence]
- Recent focus: [one sentence]
- Last session: [one sentence]
- Current status: [one sentence]
- Suggested next: [one sentence]

Then show:
- Files with uncommitted changes (if any)
- Current in-progress items
```

### Recovery: After Long Break
```
Restore context after extended absence (weeks/months):

**HISTORICAL CONTEXT**

1. Read most recent full checkpoint completely
2. Read all context files in .claude/context/
3. Analyze git history since checkpoint:
   git log --oneline --since="[checkpoint-date]"
   git log --stat --since="[checkpoint-date]"

4. Check for architectural changes:
   git diff [checkpoint-commit] HEAD -- "package.json" "requirements.txt" "go.mod" (adjust)
   (Shows dependency changes)

5. Review lessons learned:
   .claude/memory-bank/lessons-learned.md

**CONTEXT REBUILD**

Present comprehensive briefing:

1. **Project Overview** (from checkpoint)
2. **Architecture** (from 01-architecture.md, note any changes)
3. **What's Changed Since Checkpoint**:
   - Major commits
   - New features
   - Dependencies added/removed
4. **Current State**:
   - Branch structure
   - Uncommitted work
   - Open tasks
5. **Known Issues** (from 07-gotchas.md)
6. **Accumulated Wisdom** (from lessons-learned.md)
7. **Recommended Reorientation Steps**:
   - Quick wins to rebuild muscle memory
   - Critical paths to review
   - Tests to run to verify understanding

Then suggest: "Let's start with [specific small task] to rebuild context"
```

---

## Maintenance Prompts

### Maintenance: Checkpoint Rotation
```
Perform checkpoint maintenance:

1. List all checkpoints:
   ls -lh .claude/checkpoints/

2. Identify for deletion:
   - Incremental checkpoints > 30 days old
   - Full checkpoints > 90 days old (except monthly archives)

3. For monthly archives, keep:
   - One full checkpoint from each month
   - Choose the last one of the month

4. Create archive structure if needed:
   .claude/checkpoints/archive/YYYY/MM/

5. Archive old checkpoints (don't delete):
   mv old-checkpoints .claude/checkpoints/archive/YYYY/MM/

6. Show summary:
   - Checkpoints archived
   - Disk space freed
   - Remaining active checkpoints

Never delete the most recent full checkpoint.
```

### Maintenance: Context File Audit
```
Audit and clean context files:

For each context file:

1. Read current content
2. Verify against actual codebase:
   - Is architectural description still accurate?
   - Are listed files still present?
   - Are dependencies up to date?
   - Are gotchas still relevant?

3. For each discrepancy found:
   - Mark for update
   - Note what changed

4. Update each file:
   - Remove obsolete information
   - Add missing information
   - Correct inaccurate information
   - Update timestamps

5. Show audit report:
   - Files audited
   - Discrepancies found
   - Updates made
   - Accuracy improvement

Run this monthly or after major refactorings.
```

### Maintenance: Session Notes Integration
```
Integrate accumulated session notes into permanent context:

1. Find all SESSION_NOTES*.md files not yet processed:
   ls -lt SESSION_NOTES*.md

2. For each session note:
   - Extract decisions → Add to 05-decisions.md
   - Extract gotchas → Add to 07-gotchas.md
   - Extract lessons → Add to memory-bank/lessons-learned.md
   - Extract progress → Update 08-progress.md
   - Extract patterns → Add to 04-patterns.md

3. After integration, mark session notes as processed:
   - Move to .claude/sessions/processed/
   - Or add "PROCESSED [date]" marker at top

4. Show integration summary:
   - Session notes processed
   - Decisions extracted
   - Gotchas extracted
   - Lessons extracted
   - Files updated

Run this weekly to prevent session notes from piling up.
```

### Maintenance: Lessons Learned Consolidation
```
Consolidate and refine lessons learned:

1. Read .claude/memory-bank/lessons-learned.md

2. Analyze lessons:
   - Identify duplicates or similar lessons
   - Identify contradictions
   - Identify lessons proven/disproven by later experience
   - Group related lessons

3. Consolidate:
   - Merge duplicate lessons
   - Resolve contradictions with notes
   - Promote validated patterns to 04-patterns.md
   - Archive obsolete lessons to memory-bank/archive/

4. Categorize clearly:
   - Technical Lessons
   - Process Lessons
   - Tool Lessons
   - Anti-patterns (what not to do)
   - Validated Patterns (what works)

5. Add cross-references:
   - Link to relevant ADRs
   - Link to relevant gotchas
   - Link to example code

6. Show consolidation report:
   - Lessons merged
   - Contradictions resolved
   - Patterns promoted
   - Lessons archived

Run this monthly to maintain quality.
```

---

## Advanced Prompts

### Advanced: Cross-Project Pattern Mining
```
Mine patterns across multiple projects for reusable insights:

(If you have multiple projects using this checkpoint system)

1. Read lessons-learned.md from multiple projects
2. Identify common patterns:
   - Repeated lessons across projects
   - Similar gotchas
   - Universal anti-patterns
   - Cross-cutting concerns

3. Create:
   ~/.claude/universal-patterns.md
   
   Containing:
   - Universal lessons (applicable everywhere)
   - Technology-specific patterns
   - Team patterns
   - Process patterns

4. Reference from individual projects:
   Add to CLAUDE.md: "See ~/.claude/universal-patterns.md for cross-project wisdom"

Show me the universal patterns identified.
```

### Advanced: Checkpoint-Driven Onboarding
```
Generate onboarding documentation from checkpoints:

1. Read most recent full checkpoint
2. Read all context files
3. Read lessons-learned.md

4. Create: docs/ONBOARDING.md

Structure:
- **Project Overview**: From checkpoint Executive Summary
- **Getting Started**: Setup instructions
- **Architecture Tour**: From 01-architecture.md and 02-codebase-map.md
- **Key Concepts**: From 03-data-models.md and 04-patterns.md
- **Common Pitfalls**: From 07-gotchas.md
- **Lessons from the Trenches**: From lessons-learned.md
- **Where to Find Things**: Directory guide from codebase-map
- **Current Priorities**: From 08-progress.md
- **How We Work**: Process from patterns.md and decisions.md

This creates onboarding docs that stay current with the checkpoint system.
```

### Advanced: Automated Checkpoint on Git Hooks
```
Create git commit hook for automatic incremental checkpoints:

1. Create: .git/hooks/post-commit

Content:
```bash
#!/bin/bash
# Automatically create incremental checkpoint after significant commits

# Count lines changed
CHANGES=$(git diff HEAD~1 HEAD --shortstat | grep -oE '[0-9]+ insertions|[0-9]+ deletions' | grep -oE '[0-9]+' | awk '{sum+=$1} END {print sum}')

# If > 50 lines changed, create checkpoint
if [ "$CHANGES" -gt 50 ]; then
    echo "Significant changes detected. Consider creating incremental checkpoint."
    # Could automatically invoke Claude Code here
fi
```

2. Make executable: chmod +x .git/hooks/post-commit

3. Create wrapper script: .claude/create-checkpoint.sh
   (Script that invokes Claude Code with checkpoint prompt)

This automates checkpoint creation after significant commits.
```

---

## Prompt Templates for Custom Needs

### Template: Custom Context File
```
Create custom context file: .claude/context/[XX-custom-name].md

Purpose: [Describe what this file tracks]

Structure:
[Define sections needed]

Content should include:
[Specific information to capture]

Update frequency: [When this file should be updated]

Relationship to other files:
[How this relates to other context files]

Create this file and populate it by analyzing [data sources].
```

### Template: Specialized Checkpoint
```
Create specialized checkpoint for: [specific purpose]

Focus areas:
- [Area 1]
- [Area 2]

Include only:
- [Specific sections needed]

Exclude:
- [What to omit]

Purpose: [Why this specialized checkpoint]

Save as: .claude/checkpoints/special-[name]-[date].md

Show me the completed specialized checkpoint.
```

---

## Usage Tips

### For Different Checkpoint Frequencies

**After every coding session (>30 min)**:
Use: "Incremental Checkpoint: End of Session"

**End of day**:
Use: "Incremental Checkpoint: Quick Capture" + "Update: 08-progress.md"

**End of week**:
Use: "Full Checkpoint: Comprehensive State Capture"

**After major milestone**:
Use: "Full Checkpoint: With Deep Git Analysis"

**After long break**:
Use: "Recovery: After Long Break"

**Monthly**:
Use: "Maintenance: Context File Audit" + "Maintenance: Lessons Learned Consolidation"

---

## Customization

These prompts are templates. Customize them for your:
- Programming languages (adjust git file patterns)
- Project size (adjust commit analysis ranges)
- Team size (add team-specific sections)
- Domain (add domain-specific context files)
- Tools (integrate with your specific tools)

---

*These prompts transform conversational AI sessions into structured, persistent knowledge.*
