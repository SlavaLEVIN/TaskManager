BEGIN;
CREATE TABLE users (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login text NOT NULL CHECK (btrim(login) <> '' AND login = btrim(login)),
    password_hash text NOT NULL CHECK (password_hash ~ '^\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}$'),
    role text NOT NULL CHECK (role IN ('USER','ADMIN'))
);
CREATE UNIQUE INDEX users_login_unique ON users (lower(login));
CREATE TABLE categories (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE CHECK (btrim(name) <> '')
);
CREATE TABLE tasks (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL CHECK (btrim(title) <> ''),
    description text NOT NULL DEFAULT '',
    assignee_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    category_id integer NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    due_date date NOT NULL,
    priority text NOT NULL CHECK (priority IN ('LOW','MEDIUM','HIGH')),
    status text NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW','IN_PROGRESS','COMPLETED'))
);
CREATE INDEX tasks_assignee_idx ON tasks(assignee_id);
CREATE INDEX tasks_due_date_idx ON tasks(due_date);
CREATE INDEX tasks_category_idx ON tasks(category_id);
COMMENT ON TABLE tasks IS 'Текущие задачи. Просрочка вычисляется по CURRENT_DATE.';
COMMIT;
