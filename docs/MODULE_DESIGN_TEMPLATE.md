# Module Design: [Module Name]

> **Path:** `modules/<module-name>/`
> **Version:** x.y.z
> **Maturity:** _/10
> **Language:** _
> **Runtime:** _
> **Last Updated:** YYYY-MM-DD

---

## 1. Purpose

_3-5 sentences describing what this module does, who uses it, and why it exists._

### Pipeline Position

```
[upstream source] ──→ [ THIS MODULE ] ──→ [downstream target]
                          │
                     reads from:
                     shows/<slug>/config.json
```

---

## 2. Architecture

```
┌─────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Input(s)   │ ──→ │   Processing     │ ──→ │   Output(s)   │
│              │      │                  │      │              │
│ - source A   │      │ - step 1         │      │ - artifact A │
│ - source B   │      │ - step 2         │      │ - artifact B │
└─────────────┘      └──────────────────┘      └──────────────┘
```

### Components

| Component | File Path | Responsibility |
|-----------|-----------|----------------|
| _name_ | `src/...` | _what it does_ |

---

## 3. Data Flow

_Numbered step list referencing components from above._

1. **[Component A]** does X with input Y
2. **[Component B]** transforms result into Z
3. **[Component C]** writes output to destination

---

## 4. CLI Interface

```bash
# Primary command
python -m module_name --show <slug> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--show <slug>` | _(required)_ | Show identifier (reads `shows/<slug>/config.json`) |
| `--dry-run` | `false` | Preview actions without making changes |
| `--env <path>` | `.env` | Path to environment file |
| `--verbose` | `false` | Enable detailed logging |
| _module-specific flags_ | | |

---

## 5. Configuration

### From `shows/<slug>/config.json`

| Field | Used For |
|-------|----------|
| _field path_ | _purpose_ |

### From `shows/<slug>/brand.json`

| Field | Used For |
|-------|----------|
| _field path_ | _purpose_ |

### From `.env`

| Variable | Required | Description |
|----------|----------|-------------|
| _VAR_NAME_ | Yes/No | _purpose_ |

---

## 6. Dependencies

### System Requirements

- _runtime / tool_ (version)

### Packages

_Reference `package.json` or `requirements.txt` — do not duplicate the full list here. Note only non-obvious or critical dependencies._

### External Services

| Service | Purpose | Auth Method |
|---------|---------|-------------|
| _name_ | _what for_ | _API key / OAuth / etc._ |

---

## 7. Error Handling

| Error | Detection | Recovery |
|-------|-----------|----------|
| _what goes wrong_ | _how you know_ | _what to do_ |

### Gotchas

- _Non-obvious constraint or behavior worth documenting_

---

## 8. Claude Code Skills

### Agents

| Agent | Description | Trigger |
|-------|-------------|---------|
| _name_ | _what it does_ | _when to invoke_ |

### Commands

| Command | Description |
|---------|-------------|
| _/command_ | _what it does_ |

### Skill Design Notes

_How should Claude Code interact with this module? What context does it need?_

---

## 9. Current State vs Target State

| Area | Current | Target | Priority |
|------|---------|--------|----------|
| _aspect_ | _what exists now_ | _where it should be_ | High/Med/Low |

### Priority Actions

1. _Most important next step_
2. _Second priority_
3. _Third priority_

---

## 10. Verification Checklist

_Post-run confirmation steps._

- [ ] _Check that output A exists / is correct_
- [ ] _Verify service B received the data_
- [ ] _Confirm no error logs in output_

---

## 11. References

- Module README: `modules/<module-name>/README.md`
- Module CLAUDE.md: `modules/<module-name>/CLAUDE.md`
- Show configs: `shows/<slug>/config.json`, `shows/<slug>/brand.json`
