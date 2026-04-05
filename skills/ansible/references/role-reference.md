# Role Template Reference

This document defines the role scaffolding patterns used by the team. The key principle
is **lean structure** — only create what you need, and grow from there.

## Role Tiers

Roles naturally fall into complexity tiers. Start at the tier that matches the role's
actual needs. Don't scaffold Tier 3 for a Tier 1 job.

### Tier 1 — Task-Only Role

For roles that just execute tasks with no configuration surface. Validation roles,
preflight checks, one-shot operations.

```
roles/preflight/
└── tasks/
    └── main.yml
```

```yaml
# roles/preflight/tasks/main.yml
---
- name: Verify SSH connectivity
  ansible.builtin.ping:

- name: Check minimum OS version
  ansible.builtin.assert:
    that:
      - ansible_distribution_major_version | int >= min_os_major_version | default(8) | int
    fail_msg: "Target OS {{ ansible_distribution }} {{ ansible_distribution_version }} does not meet minimum version requirement"
```

### Tier 2 — Configurable Role

For roles that install packages, template configuration, and manage services. This is
the most common pattern.

```
roles/my_service/
├── defaults/
│   └── main.yml        # Tuneable defaults (overridable by inventory)
├── handlers/
│   └── main.yml        # Service restart/reload handlers
├── tasks/
│   ├── main.yml        # Delegates to concern files
│   ├── install.yml     # Package installation
│   └── configure.yml   # Configuration templating
└── templates/
    └── my_service.conf.j2
```

**defaults/main.yml** — Every variable the role uses that a consumer might want to change.
Include a comment block at the top explaining the role's purpose:

```yaml
# roles/my_service/defaults/main.yml
---
# my_service role defaults
# Manages installation and configuration of my_service

my_service_packages:
  - my-service
  - my-service-utils

my_service_enabled: true
my_service_port: 8080
```

**handlers/main.yml** — Follow the restart-then-verify pattern:

```yaml
# roles/my_service/handlers/main.yml
---
- name: Restart my_service
  ansible.builtin.systemd:
    name: my_service
    state: restarted
  notify: Verify my_service

- name: Verify my_service
  ansible.builtin.wait_for:
    port: "{{ my_service_port }}"
    timeout: 30
  changed_when: false
```

**tasks/main.yml** — Delegates to focused task files:

```yaml
# roles/my_service/tasks/main.yml
---
- name: Install my_service packages
  ansible.builtin.import_tasks: install.yml

- name: Configure my_service
  ansible.builtin.import_tasks: configure.yml
```

### Tier 3 — Full Role

For complex roles that also need static files, custom variables (non-overridable),
or metadata for dependencies. Rarely needed.

```
roles/complex_role/
├── defaults/
│   └── main.yml
├── files/
│   └── custom_script.sh
├── handlers/
│   └── main.yml
├── meta/
│   └── main.yml        # Only if role has Galaxy dependencies
├── tasks/
│   ├── main.yml
│   ├── install.yml
│   ├── configure.yml
│   └── validate.yml
├── templates/
│   └── config.j2
└── vars/
    └── main.yml        # Only for truly internal/non-overridable vars
```

**When to use `vars/` vs `defaults/`**:
- `defaults/` — values the consumer should tune (ports, package lists, feature flags)
- `vars/` — internal constants the consumer should not change (OS-specific paths, computed values)

**When to use `meta/`**:
- Only when the role depends on other roles via Galaxy-style dependencies
- If the role is self-contained, skip `meta/` entirely

## Task File Conventions

### main.yml Structure

Always starts with `---`. Delegates to concern files rather than containing logic directly
(unless the role is Tier 1 with only a few tasks).

### Concern Files

Name task files after what they do, not after the module they use:

```
# Good
tasks/certificates.yml
tasks/chrony.yml
tasks/packages.yml

# Bad
tasks/copy_files.yml
tasks/run_commands.yml
tasks/templates.yml
```

### Variable Naming

Prefix all role variables with the role name to avoid collisions:

```yaml
# Good — namespaced to the role
vm_configure_proxy_url: "http://proxy.example.com:3128"
vm_configure_ntp_servers:
  - ntp1.example.com
  - ntp2.example.com

# Bad — could collide with other roles or group_vars
proxy_url: "http://proxy.example.com:3128"
ntp_servers:
  - ntp1.example.com
```

### Conditional Tasks

When a task file should only run under certain conditions, apply the condition
at the import level in `main.yml`, not inside the task file:

```yaml
# roles/vm_configure/tasks/main.yml
- name: Configure proxy settings
  ansible.builtin.import_tasks: proxy.yml
  when: vm_configure_proxy_url is defined
```

## Scaffolding a New Role

When asked to create a new role, follow this process:

1. **Determine the tier** based on what the role needs to do
2. **Create only the directories that will have files**
3. **Write `defaults/main.yml` first** (if Tier 2+) — this defines the role's API
4. **Write `tasks/main.yml`** with delegation to concern files
5. **Write the concern task files**
6. **Write handlers** (if services are involved)
7. **Write templates** (if configuration files are managed)
8. **Update `requirements.yml`** if new collections are needed