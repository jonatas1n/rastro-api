# Rastro API

API FastAPI com **[Turso](https://turso.tech)** (libSQL / SQLite) via SQLModel + `sqlalchemy-libsql`.

## 1. Criar banco no Turso

```bash
curl -sSfL https://get.tur.so/install.sh | bash   # CLI (macOS/Linux)
turso auth login
turso db create rastro --region gru              # ex.: São Paulo (gru)
turso db show rastro --url                         # → libsql://...
turso db tokens create rastro                      # → token
```

Guarde **URL** e **token**.

## 2. Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `TURSO_DATABASE_URL` | Produção | Saída de `turso db show … --url` |
| `TURSO_AUTH_TOKEN` | Produção | Token da base |
| `SECRET_KEY` | Sim | JWT |
| `ANTHROPIC_API_KEY` | Não | LLM |
| `TURSO_LOCAL_DATABASE_PATH` | Local | Default `sqlite+libsql:///rastro.db` se URL/token vazios |

```bash
cp .env.example .env
# Cole TURSO_DATABASE_URL e TURSO_AUTH_TOKEN
```

## 3. Desenvolvimento local

Com **Make** (usa o Python do `venv/` — evita `ModuleNotFoundError: sqlmodel`):

```bash
cd rastro-api
make setup    # venv + pip install + .env
make dev      # reload na porta 8000
make health   # testa /health
```

Porta customizada: `make dev PORT=7600`

**Manual** (equivalente ao `make dev`):

Tabelas criadas no startup (`create_db`). Health: `GET /health`.

Docker:

```bash
docker compose up --build
```

## 4. Deploy na Vercel

1. **Root Directory** = `rastro-api`
2. Env: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `SECRET_KEY`
3. Deploy → `https://<projeto>.vercel.app/health`

`VERCEL=1` usa `NullPool` no SQLAlchemy (adequado a serverless).

```bash
vercel dev
```

## 5. App Flutter

```bash
flutter run --dart-define=API_URL=https://<projeto>.vercel.app
```

## Notas

- Dialect: `sqlite+libsql://` ([sqlalchemy-libsql](https://github.com/tursodatabase/libsql-sqlalchemy))
- Pacote libSQL: **Linux e macOS** no build da Vercel; ambiente de deploy Turso é compatível
- Sync idempotente por `(user_id, local_id)` — igual ao contrato anterior do app
