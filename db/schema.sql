-- Profile facts (structured counterpart to the RAG profile_facts collection)
CREATE TABLE IF NOT EXISTS profile (
  id SERIAL PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Projects: work, personal, travel — distinguished by "type"
CREATE TABLE IF NOT EXISTS projects (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('work', 'personal', 'travel')),
  description TEXT,
  deadline TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'done', 'paused')),
  priority SMALLINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sub-tasks / reminders
CREATE TABLE IF NOT EXISTS tasks (
  id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  content TEXT NOT NULL,
  due_date TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done')),
  remind_count INTEGER NOT NULL DEFAULT 0,
  last_reminded_at TIMESTAMPTZ
);

-- Conversation log: RAG source + audit trail
CREATE TABLE IF NOT EXISTS conversation_log (
  id SERIAL PRIMARY KEY,
  message TEXT NOT NULL,
  response TEXT,
  task_type TEXT,
  tokens_used INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
