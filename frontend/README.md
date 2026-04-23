# Local development

Default local mode:

```bash
npm run dev
```

Remote backend mode for frontend developers:

```bash
npm run dev:remote
```

This runs Vite locally and proxies `/api` to:

```text
https://bims.su/x9p4k2q7
```

If you prefer env files, copy `frontend/.env.remote.example` to `frontend/.env.local`
and run `npm run dev`.
